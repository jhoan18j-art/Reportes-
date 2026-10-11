import base64
import io
import json
import os
import shutil
from datetime import date, datetime, time, timedelta
import urllib.parse
import pandas as pd
import streamlit as st
from PIL import Image

# =========================================================================
# RUTAS ABSOLUTAS EN DISCO (Persistencia en Streamlit Cloud)
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "reportes_clubpark.json")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos_reportes")

os.makedirs(FOTOS_DIR, exist_ok=True)

st.set_page_config(
    page_title="Club Park - Control Operativo MXN",
    page_icon="🚗",
    layout="wide"
)

# Estilo CSS para inputs numéricos
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
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# GESTIÓN SEGURA DE CREDENCIALES (st.secrets o respaldo local)
# =========================================================================
def obtener_credenciales():
    try:
        if "usuarios" in st.secrets:
            return {
                "Víctor Manuel": {"pass": st.secrets["usuarios"].get("victor_manuel", "visor123"), "rol": "Supervisor"},
                "José de Jesús": {"pass": st.secrets["usuarios"].get("jose_jesus", "visor123"), "rol": "Supervisor"},
                "Víctor (Contador)": {"pass": st.secrets["usuarios"].get("contador", "contador123"), "rol": "Contador Auditor"}
            }
    except Exception:
        pass

    return {
        "Víctor Manuel": {"pass": "visor123", "rol": "Supervisor"},
        "José de Jesús": {"pass": "visor123", "rol": "Supervisor"},
        "Víctor (Contador)": {"pass": "contador123", "rol": "Contador Auditor"}
    }

# =========================================================================
# FUNCIONES DE ALMACENAMIENTO Y PERSISTENCIA
# =========================================================================
def guardar_imagen_optimizada(archivo_subido, sucursal, fecha_str):
    try:
        # Resetear puntero de lectura para evitar error de archivo vacío
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suc_clean = "".join(c for c in sucursal if c.isalnum() or c in (' ', '_')).strip().replace(" ", "_")
        nombre_archivo = f"{fecha_str.replace('/', '-')}_{suc_clean}_{timestamp}.jpg"
        ruta_completa = os.path.join(FOTOS_DIR, nombre_archivo)
        img.save(ruta_completa, "JPEG", quality=75, optimize=True)
        return ruta_completa
    except Exception as e:
        st.error(f"Error al procesar la imagen: {e}")
        return None

def cargar_registros_guardados():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []
    return []

def guardar_registros_permanentes(registros):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Error al guardar datos en disco: {e}")
        return False

def evaluar_rentabilidad(margen):
    if margen >= 40.0:
        return "🟢 Alta"
    elif margen >= 15.0:
        return "🟡 Moderada"
    elif margen > 0.0:
        return "🟠 Baja"
    else:
        return "🔴 No Rentable (Pérdida)"

def existe_reporte_previo(sucursal, fecha_str):
    if sucursal == "-- Selecciona o busca la sucursal --":
        return False
    for reg in st.session_state.registros:
        if reg.get("Sitio / Unidad") == sucursal and reg.get("Fecha") == fecha_str:
            return True
    return False

# Inicializar sesión
if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()

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
SUCURSALES_LISTA = ["-- Selecciona o busca la sucursal --"] + list(PRECIOS_SUCURSALES.keys())

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

# =========================================================================
# LOGIN / CONTROL DE ACCESO
# =========================================================================
if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=400)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK VALET Y ESTACIONAMIENTOS</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; color: gray;'>Control de Acceso Seguro</h3>", unsafe_allow_html=True)

        credenciales = obtener_credenciales()
        lista_usuarios = ["-- Selecciona --"] + list(credenciales.keys())

        with st.form("form_login"):
            nombre_usuario = st.selectbox("Selecciona tu Usuario:", lista_usuarios)
            password = st.text_input("Contraseña de Acceso:", type="password")
            btn_login = st.form_submit_button("🔑 Entrar al Sistema", use_container_width=True)

            if btn_login:
                if nombre_usuario in credenciales and password == credenciales[nombre_usuario]["pass"]:
                    st.session_state.usuario_autenticado = nombre_usuario
                    st.session_state.rol = credenciales[nombre_usuario]["rol"]
                    st.success("Acceso autorizado.")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta o usuario no seleccionado.")
    st.stop()

# =========================================================================
# BARRA SUPERIOR Y LATERAL
# =========================================================================
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    logo_path = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=250)
    else:
        st.markdown("### **CP** - Club Park")

with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.subheader(f"Usuario: {st.session_state.usuario_autenticado} | Rol: {st.session_state.rol}")

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
archivos_fisicos_disco = [f for f in os.listdir(FOTOS_DIR) if not f.startswith('.')] if os.path.exists(FOTOS_DIR) else []
st.sidebar.info(
    f"**Usuario:** {st.session_state.usuario_autenticado}\n\n"
    f"**Rol:** {st.session_state.rol}\n\n"
    f"**Reportes Guardados:** {len(st.session_state.registros)}\n\n"
    f"**Archivos en Carpeta Fotos:** {len(archivos_fisicos_disco)}"
)

es_contador = (st.session_state.rol == "Contador Auditor")

# =========================================================================
# PANEL EXCLUSIVO: CONTADOR AUDITOR (INVESTIGACIÓN Y LIMPIEZA DE FOTOS)
# =========================================================================
if es_contador:
    st.markdown("---")
    st.markdown("## 🔍 Herramientas Exclusivas del Contador Auditor")

    # WhatsApp
    with st.expander("📲 Enviar Recordatorio de Reportes Faltantes por WhatsApp", expanded=False):
        st.markdown("### 🔔 Control de Reportes Faltantes a Supervisores")
        fecha_revision = st.date_input("Selecciona la fecha a revisar:", value=date.today(), key="fecha_rev_contador")
        fecha_rev_str = fecha_revision.strftime("%d/%m/%Y")

        unidades_reportadas_fecha = [
            reg.get("Sitio / Unidad") for reg in st.session_state.registros if reg.get("Fecha") == fecha_rev_str
        ]

        faltantes_jesus = [u for u in UNIDADES_JESUS if u not in unidades_reportadas_fecha]
        faltantes_victor = [u for u in UNIDADES_VICTOR if u not in unidades_reportadas_fecha]

        col_notif1, col_notif2 = st.columns(2)
        with col_notif1:
            st.markdown("#### 👤 Supervisor: José de Jesús")
            if faltantes_jesus:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_jesus)}):** " + ", ".join(faltantes_jesus))
                msg_jesus = f"🚨 *RECORDATORIO DE REPORTES FALTANTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola José de Jesús,* faltan los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_jesus])
                st.markdown(f"[📲 **Enviar WhatsApp a Jesús**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_jesus)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡José de Jesús ha completado todos sus reportes!")

        with col_notif2:
            st.markdown("#### 👤 Supervisor: Víctor Manuel")
            if faltantes_victor:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_victor)}):** " + ", ".join(faltantes_victor))
                msg_victor = f"🚨 *RECORDATORIO DE REPORTES FALTANTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola Víctor Manuel,* faltan los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_victor])
                st.markdown(f"[📲 **Enviar WhatsApp a Víctor**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_victor)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡Víctor Manuel ha completado todos sus reportes!")

    # Explorador directo de las fotos en disco (Resuelve el misterio de las 3 fotos)
    with st.expander("📂 Explorador Físico de Archivos en Disco (fotos_reportes)", expanded=False):
        st.markdown("### 🗂️ Archivos físicos encontrados en la carpeta del servidor:")
        if archivos_fisicos_disco:
            st.info(f"Se encontraron **{len(archivos_fisicos_disco)} archivo(s)** dentro de `fotos_reportes`.")
            for nombre_arch in archivos_fisicos_disco:
                ruta_arch = os.path.join(FOTOS_DIR, nombre_arch)
                tamano_kb = os.path.getsize(ruta_arch) / 1024 if os.path.exists(ruta_arch) else 0

                c_arch1, c_arch2, c_arch3 = st.columns([2, 1, 1])
                with c_arch1:
                    st.write(f"📄 **{nombre_arch}** ({tamano_kb:.1f} KB)")
                with c_arch2:
                    try:
                        st.image(ruta_arch, width=120)
                    except Exception:
                        st.caption("No es imagen válida o dañada.")
                with c_arch3:
                    if st.button("🗑️ Eliminar de Disco", key=f"del_disco_{nombre_arch}"):
                        try:
                            os.remove(ruta_arch)
                            st.success(f"Archivo {nombre_arch} eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al borrar: {e}")

            st.markdown("---")
            if st.button("🧹 Purgar TODOS los archivos de la carpeta fotos_reportes", key="btn_purgar_todas_fotos"):
                for arch in archivos_fisicos_disco:
                    try:
                        os.remove(os.path.join(FOTOS_DIR, arch))
                    except Exception:
                        pass
                st.success("Carpeta de fotos limpiada completamente.")
                st.rerun()
        else:
            st.success("La carpeta `fotos_reportes` está completamente limpia (0 archivos).")

    # Auditoría y Eliminación de Reportes
    with st.expander("🗑️ Administración y Eliminación de Reportes Guardados", expanded=False):
        if st.session_state.registros:
            opciones_borrar = [
                f"ID #{i} | {r.get('Fecha')} | {r.get('Sitio / Unidad')} | Neto: ${r.get('Ingreso Neto', 0):,.2f}"
                for i, r in enumerate(st.session_state.registros)
            ]
            seleccion_eliminar = st.selectbox("Selecciona reporte a inspeccionar o eliminar:", opciones_borrar, key="sel_eliminar_individual")
            idx_eliminar = int(seleccion_eliminar.split(" | ")[0].replace("ID #", ""))
            reporte_sel = st.session_state.registros[idx_eliminar]

            col_inf1, col_inf2 = st.columns([2, 1])
            with col_inf1:
                st.json(reporte_sel)
            with col_inf2:
                if reporte_sel.get("foto_path") and os.path.exists(reporte_sel["foto_path"]):
                    st.image(reporte_sel["foto_path"], caption="Fotografía física", width=250)
                else:
                    st.caption("Sin fotografía física adjunta.")

            if st.button("🗑️ Eliminar Este Reporte Individual", key="btn_del_single"):
                foto_ruta = reporte_sel.get("foto_path")
                if foto_ruta and os.path.exists(foto_ruta):
                    try:
                        os.remove(foto_ruta)
                    except Exception:
                        pass
                st.session_state.registros.pop(idx_eliminar)
                guardar_registros_permanentes(st.session_state.registros)
                st.success("✅ Reporte eliminado.")
                st.rerun()
        else:
            st.info("No hay reportes en la base de datos.")

# =========================================================================
# SECCIÓN PRINCIPAL: CAPTURA DE REPORTES
# =========================================================================
st.markdown("---")
if not es_contador:
    st.markdown(f"## 📋 Registro Diario de Operaciones ({st.session_state.usuario_autenticado})")
    st.caption("🔒 Como supervisor, solo puedes capturar la fecha de hoy y tus reportes quedan protegidos contra sobreescritura.")
else:
    st.markdown("## 📥 Captura de Reportes (Modo Contador Auditor)")
    st.caption("✨ Puedes capturar fechas extemporáneas y múltiples reportes por unidad.")

sucursal_activa = st.selectbox(
    "Selecciona la Sucursal / Unidad:",
    SUCURSALES_LISTA,
    key="select_sucursal_activa"
)

es_ingreso_directo = sucursal_activa in ["BARRANCA", "S. AZURA"]
costo_sugerido = PRECIOS_SUCURSALES.get(sucursal_activa, 40)

# Formulario principal: el botón de guardado SIEMPRE está presente
with st.form("form_captura_reporte", clear_on_submit=False):
    st.markdown("### 📝 Datos de la Operación")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        if es_contador:
            fecha_op = st.date_input("Fecha del Reporte:", value=date.today())
        else:
            fecha_hoy = date.today()
            st.info(f"📅 **Fecha de Operación:** `{fecha_hoy.strftime('%d/%m/%Y')}` *(Automática por rol Supervisor)*")
            fecha_op = fecha_hoy
        fecha_op_str = fecha_op.strftime("%d/%m/%Y")

    with col_f2:
        if es_ingreso_directo:
            st.info("📌 En esta unidad se captura directamente el Ingreso Bruto en el Folio Inicial.")
            costo_boleto = 0.0
        else:
            costo_boleto = st.number_input(
                "Costo por Boleto ($ MXN):",
                min_value=0.0,
                value=float(costo_sugerido),
                step=5.0
            )

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        hora_ini = st.time_input("Hora de Apertura:", value=time(13, 0))
    with col_h2:
        hora_fin = st.time_input("Hora de Cierre:", value=time(23, 0))

    st.markdown("#### 📷 Fotografía Física del Reporte")
    foto = st.file_uploader("Adjuntar fotografía (JPG / PNG):", type=["png", "jpg", "jpeg"])

    st.markdown("#### 🎫 Control de Boletos y Folios")
    c_b1, c_b2, c_b3 = st.columns(3)

    if es_ingreso_directo:
        with c_b1:
            f_ini = st.number_input("Ingreso Bruto Directo ($ MXN):", min_value=0.0, value=0.0, step=50.0)
            f_fin = 0
        with c_b2:
            f_sin = 0
            f_can = 0
        with c_b3:
            f_per = 0
    else:
        with c_b1:
            f_ini = st.number_input("Folio Inicial:", min_value=0, value=1, step=1)
            f_fin = st.number_input("Folio Final:", min_value=0, value=50, step=1)
        with c_b2:
            f_sin = st.number_input("Boletos Sin Cobro:", min_value=0, value=0, step=1)
            f_can = st.number_input("Boletos Cancelados:", min_value=0, value=0, step=1)
        with c_b3:
            f_per = st.number_input("Boletos Perdidos:", min_value=0, value=0, step=1)

    st.markdown("#### 💵 Egresos y Gastos Operativos")
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        g_esp = st.number_input("Gastos Especiales ($ MXN):", min_value=0.0, value=0.0, step=10.0)
    with c_g2:
        g_gen = st.number_input("Gastos Generales / Nómina ($ MXN):", min_value=0.0, value=0.0, step=10.0)

    st.markdown("#### ✍️ Firmas de Responsabilidad")
    c_fir1, c_fir2 = st.columns(2)
    with c_fir1:
        elaboro = st.text_input("Elaboró:", value=st.session_state.usuario_autenticado)
    with c_fir2:
        recibe = st.text_input("Recibe:", value="" if not es_contador else "Víctor (Contador)")

    st.markdown("---")
    btn_guardar_reporte = st.form_submit_button("💾 Guardar y Confirmar Reporte", use_container_width=True)

# Lógica ejecutada al presionar Guardar
if btn_guardar_reporte:
    if sucursal_activa == "-- Selecciona o busca la sucursal --":
        st.error("❌ Por favor selecciona una sucursal válida antes de guardar.")
    else:
        ya_existe = existe_reporte_previo(sucursal_activa, fecha_op_str)

        if ya_existe and not es_contador:
            st.error(
                f"🚫 **REPORTE BLOQUEADO:** La sucursal **{sucursal_activa}** ya cuenta con un reporte registrado el día de hoy ({fecha_op_str}). "
                "Como supervisor, los reportes están protegidos. Contacta al Contador Auditor si requieres ajustes."
            )
        else:
            with st.spinner("Guardando reporte y asegurando en disco..."):
                if es_ingreso_directo:
                    total_boletos = 0
                    boletos_cobrados = 0
                    ingreso_bruto = float(f_ini)
                else:
                    total_boletos = max(0, (int(f_fin) - int(f_ini)) + 1) if int(f_fin) >= int(f_ini) and int(f_ini) > 0 else 0
                    boletos_cobrados = max(0, total_boletos - int(f_sin) - int(f_can))
                    ingreso_bruto = boletos_cobrados * float(costo_boleto)

                total_gastos = float(g_esp) + float(g_gen)
                ingreso_neto = ingreso_bruto - total_gastos
                margen = (ingreso_neto / ingreso_bruto * 100) if ingreso_bruto > 0 else 0.0
                rentabilidad = evaluar_rentabilidad(margen)

                ruta_guardada = None
                if foto is not None:
                    ruta_guardada = guardar_imagen_optimizada(foto, sucursal_activa, fecha_op_str)

                horario_str = f"{hora_ini.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}"

                nuevo_reporte = {
                    "Fecha": fecha_op_str,
               
