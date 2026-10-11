import io
import json
import os
import shutil
import uuid
from datetime import date, datetime, time, timedelta
import urllib.parse
import pandas as pd
import streamlit as st
from PIL import Image

# Import opcional para exportación con estilo en Excel
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# =========================================================================
# CONFIGURACIÓN GENERAL Y RUTAS PERMANENTES
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_FILE = os.path.join(BASE_DIR, "reportes_clubpark.json")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos_reportes")
os.makedirs(FOTOS_DIR, exist_ok=True)

st.set_page_config(
    page_title="Club Park - Control Operativo MXN",
    page_icon="🚗",
    layout="wide"
)

# Estilo CSS para optimizar inputs numéricos y visualización
st.markdown("""
    <style>
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        input[type=number] {
            -moz-appearance: textfield;
        }
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            border-left: 5px solid #0d6efd;
        }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# FUNCIONES DE BASE DE DATOS Y PERSISTENCIA
# =========================================================================
def cargar_registros_guardados():
    """Carga los reportes desde el archivo JSON de manera segura."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            st.error(f"Error al leer la base de datos: {e}")
            return []
    return []

def guardar_registros_permanentes(registros):
    """Guarda los reportes en el archivo JSON con respaldo atómico."""
    try:
        tmp_file = DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=4)
        os.replace(tmp_file, DB_FILE)
        return True
    except Exception as e:
        st.error(f"Error al escribir en la base de datos: {e}")
        return False

def guardar_imagen_optimizada(archivo_subido, id_reporte, sucursal, fecha_str):
    """Guarda y comprime la foto física vinculada estrictamente al ID del reporte."""
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        
        suc_clean = "".join(c for c in sucursal if c.isalnum() or c in (' ', '_')).strip().replace(" ", "_")
        fecha_clean = fecha_str.replace('/', '-')
        nombre_archivo = f"{id_reporte}_{fecha_clean}_{suc_clean}.jpg"
        ruta_completa = os.path.join(FOTOS_DIR, nombre_archivo)
        
        img.save(ruta_completa, "JPEG", quality=78, optimize=True)
        return ruta_completa
    except Exception as e:
        st.error(f"Error al procesar la fotografía: {e}")
        return None

def evaluar_rentabilidad(margen):
    """Clasifica el nivel de rentabilidad según el margen porcentual."""
    if margen >= 40.0:
        return "🟢 Alta"
    elif margen >= 15.0:
        return "🟡 Moderada"
    elif margen > 0.0:
        return "🟠 Baja"
    else:
        return "🔴 No Rentable (Pérdida)"

def ya_existe_reporte(sucursal, fecha_str):
    """Verifica si ya existe un reporte para esa sucursal en esa fecha."""
    if sucursal == "-- Selecciona o busca la sucursal --":
        return False
    for reg in st.session_state.registros:
        if reg.get("Sitio / Unidad") == sucursal and reg.get("Fecha") == fecha_str:
            return True
    return False

# =========================================================================
# CONFIGURACIÓN DE SUCURSALES Y PRECIOS
# =========================================================================
PRECIOS_SUCURSALES = {
    "PAMPAS": 50, "RAMMA": 70, "SUSHITTO": 40, "BARRANCA": 0,
    "CARAJILLO": 100, "BENINGANS": 40, "ROMAS": 65, "J.TLALPAN": 100,
    "J.DIVISION": 100, "J.PICACHO": 100, "J.EMPRESA": 100, "sipily": 80,
    "M SATÉLITE": 70, "M MARINA": 70, "VETERINARIA": 0, "CLÍNICA": 100,
    "SUMO STA": 50, "CHEGARAY": 50, "RYOSHI": 80, "ENCANTO": 90,
    "S. AZURA": 0, "E-BNI": 0, "CHURRASCA": 70
}

UNIDADES_JESUS = ["PAMPAS", "RAMMA", "SUSHITTO", "BARRANCA", "CARAJILLO", "BENINGANS", "CLÍNICA"]
UNIDADES_VICTOR = ["SUMO STA", "CHEGARAY", "RYOSHI", "ENCANTO", "S. AZURA", "CHURRASCA"]
SUCURSALES_LISTA = ["-- Selecciona o busca la sucursal --"] + sorted(list(PRECIOS_SUCURSALES.keys()))

# Inicializar sesión de memoria
if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

def on_sucursal_change():
    seleccion = st.session_state.get("select_sitio")
    if seleccion in PRECIOS_SUCURSALES:
        st.session_state["costo_boleto_input"] = PRECIOS_SUCURSALES[seleccion]

if "costo_boleto_input" not in st.session_state:
    st.session_state["costo_boleto_input"] = 40

# =========================================================================
# GENERADOR DE EXCEL DETALLADO (SEMANAL, MENSUAL Y DETALLADO)
# =========================================================================
def generar_excel_completo(registros):
    """Genera un archivo Excel profesional con 3 hojas: Semanal, Mensual y Detalle."""
    if not registros:
        return None
    
    df = pd.DataFrame(registros)
    
    # Normalizar columnas y fechas
    df["Fecha_DT"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
    df = df.sort_values(by="Fecha_DT", ascending=False)
    
    # Calcular Semana y Mes
    df["Año"] = df["Fecha_DT"].dt.year
    df["Semana"] = df["Fecha_DT"].dt.isocalendar().week
    df["Semana_Etiqueta"] = df["Año"].astype(str) + " - Sem " + df["Semana"].astype(str)
    df["Mes_Etiqueta"] = df["Fecha_DT"].dt.strftime("%Y-%m (%B)")
    
    # Columnas numéricas seguras
    cols_num = ["Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina", "Total Gastos", "Ingreso Neto", "Boletos Cobrados"]
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine="openpyxl" if OPENPYXL_OK else "xlsxwriter") as writer:
        # 1. RESUMEN SEMANAL POR SUCURSAL
        resumen_semanal = df.groupby(["Semana_Etiqueta", "Sitio / Unidad"]).agg({
            "Boletos Cobrados": "sum",
            "Ingreso Bruto": "sum",
            "Gastos Especiales": "sum",
            "Gastos Generales / Nómina": "sum",
            "Total Gastos": "sum",
            "Ingreso Neto": "sum"
        }).reset_index()
        
        resumen_semanal["Margen (%)"] = (
            (resumen_semanal["Ingreso Neto"] / resumen_semanal["Ingreso Bruto"]) * 100
        ).fillna(0.0).round(2)
        resumen_semanal["Rentabilidad"] = resumen_semanal["Margen (%)"].apply(evaluar_rentabilidad)
        resumen_semanal = resumen_semanal.sort_values(by=["Semana_Etiqueta", "Ingreso Neto"], ascending=[False, False])
        resumen_semanal.to_excel(writer, sheet_name="Rentabilidad Semanal", index=False)

        # 2. RESUMEN MENSUAL POR SUCURSAL
        resumen_mensual = df.groupby(["Mes_Etiqueta", "Sitio / Unidad"]).agg({
            "Boletos Cobrados": "sum",
            "Ingreso Bruto": "sum",
            "Gastos Especiales": "sum",
            "Gastos Generales / Nómina": "sum",
            "Total Gastos": "sum",
            "Ingreso Neto": "sum"
        }).reset_index()
        
        resumen_mensual["Margen (%)"] = (
            (resumen_mensual["Ingreso Neto"] / resumen_mensual["Ingreso Bruto"]) * 100
        ).fillna(0.0).round(2)
        resumen_mensual["Rentabilidad"] = resumen_mensual["Margen (%)"].apply(evaluar_rentabilidad)
        resumen_mensual = resumen_mensual.sort_values(by=["Mes_Etiqueta", "Ingreso Neto"], ascending=[False, False])
        resumen_mensual.to_excel(writer, sheet_name="Rentabilidad Mensual", index=False)

        # 3. DETALLE INDIVIDUAL DE REPORTES
        cols_detalle = [
            "ID", "Fecha", "Sitio / Unidad", "Horario", "Tipo", "Costo Boleto",
            "Folio Inicial", "Folio Final", "Total Boletos", "Sin Cobro", "Cancelados", "Perdidos",
            "Boletos Cobrados", "Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina",
            "Total Gastos", "Ingreso Neto", "Margen (%)", "Rentabilidad", "Elaboró", "Recibe", "Tiene Foto"
        ]
        
        df["Tiene Foto"] = df["foto_path"].apply(lambda x: "SÍ" if (x and os.path.exists(str(x))) else "NO")
        cols_presentes = [c for c in cols_detalle if c in df.columns]
        df_detalle = df[cols_presentes]
        df_detalle.to_excel(writer, sheet_name="Detalle de Reportes", index=False)

    # Estilizar con openpyxl si está disponible
    if OPENPYXL_OK:
        output.seek(0)
        wb = openpyxl.load_workbook(output)
        
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        border_thin = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )

        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            # Formato encabezados
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Formatos numéricos y bordes para datos
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.border = border_thin
                    col_header = str(ws.cell(row=1, column=cell.column).value or "")
                    if any(m in col_header for m in ["Ingreso", "Gasto", "Neto", "Costo"]):
                        cell.number_format = '"$"#,##0.00'
                    elif "Margen" in col_header:
                        cell.number_format = '0.0"%"'
                    elif "Boletos" in col_header or "Folio" in col_header:
                        cell.number_format = '#,##0'

            # Autoajuste de columnas
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        out_styled = io.BytesIO()
        wb.save(out_styled)
        out_styled.seek(0)
        return out_styled.getvalue()

    output.seek(0)
    return output.getvalue()

# =========================================================================
# PANTALLA DE ACCESO (LOGIN CON ROLES SEGUROS)
# =========================================================================
if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=380)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; color: #555;'>Control Operativo y Financiero</h3>", unsafe_allow_html=True)
        st.markdown("---")

        nombre_usuario = st.selectbox(
            "Selecciona tu Usuario:",
            ["-- Selecciona --", "Víctor Manuel", "José de Jesús", "Víctor (Contador)"],
            key="login_user"
        )
        password = st.text_input("Contraseña de Acceso:", type="password", key="login_pass")

        # Claves desde st.secrets si existen, o valores estándar
        pass_visor = st.secrets.get("PASS_SUPERVISOR", "visor123") if hasattr(st, "secrets") else "visor123"
        pass_auditor = st.secrets.get("PASS_AUDITOR", "contador123") if hasattr(st, "secrets") else "contador123"

        if st.button("🔑 Iniciar Sesión", use_container_width=True, type="primary"):
            if nombre_usuario in ["Víctor Manuel", "José de Jesús"] and password == pass_visor:
                st.session_state.usuario_autenticado = nombre_usuario
                st.session_state.rol = "Supervisor"
                st.success(f"Bienvenido {nombre_usuario}")
                st.rerun()
            elif nombre_usuario == "Víctor (Contador)" and password == pass_auditor:
                st.session_state.usuario_autenticado = "Víctor (Contador)"
                st.session_state.rol = "Contador Auditor"
                st.success("Acceso concedido como Contador Auditor")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta o usuario no seleccionado.")
    st.stop()

# =========================================================================
# ENCABEZADO Y BARRA LATERAL
# =========================================================================
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    logo_path = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=220)
    else:
        st.markdown("### 🚗 **CLUB PARK**")

with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.markdown(f"**Usuario:** `{st.session_state.usuario_autenticado}` | **Rol:** `{st.session_state.rol}`")

es_contador = (st.session_state.rol == "Contador Auditor")

# Barra lateral con estadísticas
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
fotos_disco = [f for f in os.listdir(FOTOS_DIR) if not f.startswith('.')] if os.path.exists(FOTOS_DIR) else []
st.sidebar.markdown(f"**📊 Reportes en Sistema:** `{len(st.session_state.registros)}`")
st.sidebar.markdown(f"**📷 Fotos Físicas Guardadas:** `{len(fotos_disco)}`")

# Descarga de Excel en Sidebar para Auditor
if es_contador and st.session_state.registros:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Reporte Financiero Excel")
    excel_data = generar_excel_completo(st.session_state.registros)
    if excel_data:
        st.sidebar.download_button(
            label="📊 Descargar Excel Semanal y Mensual",
            data=excel_data,
            file_name=f"ClubPark_Balance_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# =========================================================================
# PANEL EXCLUSIVO: CONTADOR AUDITOR (AUDITORÍA, WHATSAPP, FOTOS Y LIMPIEZA)
# =========================================================================
if es_contador:
    st.markdown("---")
    st.markdown("## 🔍 Panel de Auditoría y Control Financiero")

    tab_aud1, tab_aud2, tab_aud3, tab_aud4 = st.tabs([
        "📲 WhatsApp Recordatorios",
        "🎪 Registro de Evento Extraordinario",
        "📂 Gestión y Eliminación de Reportes",
        "🧹 Depuración de Fotos Huérfanas"
    ])

    # TAB 1: WhatsApp
    with tab_aud1:
        st.markdown("#### 🔔 Control de Reportes Faltantes por Fecha")
        fecha_revision = st.date_input("Fecha a verificar:", value=date.today(), key="fecha_rev_aud")
        fecha_rev_str = fecha_revision.strftime("%d/%m/%Y")

        unidades_reportadas_fecha = [
            reg.get("Sitio / Unidad") for reg in st.session_state.registros if reg.get("Fecha") == fecha_rev_str
        ]

        faltantes_jesus = [u for u in UNIDADES_JESUS if u not in unidades_reportadas_fecha]
        faltantes_victor = [u for u in UNIDADES_VICTOR if u not in unidades_reportadas_fecha]

        c_w1, c_w2 = st.columns(2)
        with c_w1:
            st.markdown("##### 👤 Supervisor: José de Jesús")
            if faltantes_jesus:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_jesus)}):** {', '.join(faltantes_jesus)}")
                msg_j = f"🚨 *CLUB PARK - RECORDATORIO DE REPORTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola José de Jesús,* faltan los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_jesus])
                st.markdown(f"[📲 **Enviar WhatsApp a Jesús**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_j)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡Todos sus reportes están completos!")

        with c_w2:
            st.markdown("##### 👤 Supervisor: Víctor Manuel")
            if faltantes_victor:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_victor)}):** {', '.join(faltantes_victor)}")
                msg_v = f"🚨 *CLUB PARK - RECORDATORIO DE REPORTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola Víctor Manuel,* faltan los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_victor])
                st.markdown(f"[📲 **Enviar WhatsApp a Víctor**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_v)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡Todos sus reportes están completos!")

    # TAB 2: Evento Extraordinario
    with tab_aud2:
        st.markdown("#### 🎪 Capturar Evento Extraordinario")
        ev_c1, ev_c2 = st.columns(2)
        with ev_c1:
            ev_fecha = st.date_input("Fecha del Evento", value=date.today(), key="ev_fecha")
            ev_suc = st.selectbox("Sucursal / Salón del Evento", SUCURSALES_LISTA, key="ev_suc")
            ev_ini_h = st.time_input("Hora Inicio", value=time(18, 0), key="ev_h_ini")
            ev_fin_h = st.time_input("Hora Fin", value=time(23, 30), key="ev_h_fin")
        with ev_c2:
            ev_costo = st.number_input("Costo Boleto ($ MXN)", value=100.0, step=10.0, key="ev_costo")
            ev_f_ini = st.number_input("Folio Inicial", value=1, step=1, key="ev_f_ini")
            ev_f_fin = st.number_input("Folio Final", value=50, step=1, key="ev_f_fin")
            ev_gastos = st.number_input("Gastos Totales del Evento ($ MXN)", value=0.0, step=50.0, key="ev_gastos")
            ev_elab = st.text_input("Elaboró", value="Staff Eventos", key="ev_elab")

        ev_boletos = max(0, (int(ev_f_fin) - int(ev_f_ini)) + 1) if int(ev_f_fin) >= int(ev_f_ini) and int(ev_f_ini) > 0 else 0
        ev_bruto = ev_boletos * float(ev_costo)
        ev_neto = ev_bruto - float(ev_gastos)
        ev_margen = (ev_neto / ev_bruto * 100) if ev_bruto > 0 else 0.0

        st.info(f"**Boletos:** {ev_boletos} | **Bruto:** ${ev_bruto:,.2f} | **Gastos:** ${ev_gastos:,.2f} | **Neto:** ${ev_neto:,.2f} | **Rentabilidad:** {evaluar_rentabilidad(ev_margen)}")

        if st.button("🚀 Registrar Evento Extraordinario", key="btn_save_evento", type="primary"):
            if ev_suc != "-- Selecciona o busca la sucursal --":
                id_ev = f"EVT_{uuid.uuid4().hex[:6]}"
                evento_obj = {
                    "ID": id_ev,
                    "Fecha"
