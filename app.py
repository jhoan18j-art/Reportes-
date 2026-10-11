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

# Rutas locales permanentes
DB_FILE = "reportes_clubpark.json"
FOTOS_DIR = "fotos_reportes"

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

# --- ALMACENAMIENTO PERMANENTE ---
def guardar_imagen_optimizada(archivo_subido, sucursal, fecha_str):
    try:
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
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)

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

def on_sucursal_change():
    seleccion = st.session_state.get("select_sitio")
    if seleccion in PRECIOS_SUCURSALES:
        st.session_state["costo_boleto_input"] = PRECIOS_SUCURSALES[seleccion]

if "costo_boleto_input" not in st.session_state:
    st.session_state["costo_boleto_input"] = 40

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

# --- INICIO DE SESIÓN ---
if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=400)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK VALET Y ESTACIONAMIENTOS</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; color: gray;'>Control de Acceso al Sistema</h3>", unsafe_allow_html=True)

        nombre_usuario = st.selectbox(
            "Selecciona tu Usuario:",
            ["-- Selecciona --", "Víctor Manuel", "José de Jesús", "Víctor (Contador)"]
        )
        password = st.text_input("Contraseña de Acceso:", type="password")

        if st.button("🔑 Entrar al Sistema", use_container_width=True):
            if nombre_usuario == "Víctor Manuel" and password == "visor123":
                st.session_state.usuario_autenticado = "Víctor Manuel"
                st.session_state.rol = "Supervisor"
                st.rerun()
            elif nombre_usuario == "José de Jesús" and password == "visor123":
                st.session_state.usuario_autenticado = "José de Jesús"
                st.session_state.rol = "Supervisor"
                st.rerun()
            elif nombre_usuario == "Víctor (Contador)" and password == "contador123":
                st.session_state.usuario_autenticado = "Víctor (Contador)"
                st.session_state.rol = "Contador Auditor"
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta o usuario no seleccionado.")
    st.stop()

# --- ENCABEZADO ---
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=250)
    else:
        st.markdown("### **CP** - Club Park")

with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.subheader(f"Bienvenido, {st.session_state.usuario_autenticado} ({st.session_state.rol})")

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
fotos_existentes = [f for f in os.listdir(FOTOS_DIR) if not f.startswith('.')] if os.path.exists(FOTOS_DIR) else []
st.sidebar.info(
    f"**Usuario:** {st.session_state.usuario_autenticado}\n\n"
    f"**Rol:** {st.session_state.rol}\n\n"
    f"**Reportes Guardados:** {len(st.session_state.registros)}\n\n"
    f"**Fotos en Servidor:** {len(fotos_existentes)}"
)

es_contador = (st.session_state.rol == "Contador Auditor")

# =========================================================================
# PANEL EXCLUSIVO: CONTADOR AUDITOR (ADMINISTRACIÓN TOTAL Y FOTOS HUÉRFANAS)
# =========================================================================
if es_contador:
    st.markdown("---")
    st.markdown("## 🔍 Herramientas Exclusivas del Contador Auditor")

    # Recordatorio WhatsApp
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

    # Gestión y Eliminación de Reportes / Limpieza de Fotos
    with st.expander("🗑️ Gestión, Auditoría y Eliminación de Reportes y Fotos", expanded=False):
        tab_admin1, tab_admin2, tab_admin3 = st.tabs(["Eliminar Reporte Individual", "Limpiar Fotos Huérfanas", "⚠️ Borrado Masivo Total"])

        with tab_admin1:
            if st.session_state.registros:
                opciones_borrar = [
                    f"ID #{i} | {r.get('Fecha')} | {r.get('Sitio / Unidad')} | Folios: {r.get('Folio Inicial')}-{r.get('Folio Final')} | Neto: ${r.get('Ingreso Neto', 0):,.2f}"
                    for i, r in enumerate(st.session_state.registros)
                ]
                seleccion_eliminar = st.selectbox("Selecciona reporte a inspeccionar o eliminar:", opciones_borrar)
                idx_eliminar = int(seleccion_eliminar.split(" | ")[0].replace("ID #", ""))
                reporte_sel = st.session_state.registros[idx_eliminar]

                col_inf1, col_inf2 = st.columns([2, 1])
                with col_inf1:
                    st.json(reporte_sel)
                with col_inf2:
                    if reporte_sel.get("foto_path") and os.path.exists(reporte_sel["foto_path"]):
                        st.image(reporte_sel["foto_path"], caption="Fotografía física del reporte", width=260)
                    else:
                        st.caption("Sin fotografía adjunta.")

                if st.button("🗑️ Eliminar Este Reporte Individual", key="btn_del_single"):
                    foto_ruta = reporte_sel.get("foto_path")
                    if foto_ruta and os.path.exists(foto_ruta):
                        try:
                            os.remove(foto_ruta)
                        except Exception:
                            pass
                    st.session_state.registros.pop(idx_eliminar)
                    guardar_registros_permanentes(st.session_state.registros)
                    st.success("✅ Reporte eliminado correctamente.")
                    st.rerun()
            else:
                st.info("No hay reportes registrados en la base de datos.")

        with tab_admin2:
            st.markdown("#### 🧹 Eliminar fotos que no están asociadas a ningún reporte")
            fotos_en_uso = {r.get("foto_path") for r in st.session_state.registros if r.get("foto_path")}
            todas_fotos = [os.path.join(FOTOS_DIR, f) for f in os.listdir(FOTOS_DIR) if not f.startswith('.')]
            fotos_huerfanas = [f for f in todas_fotos if f not in fotos_en_uso]

            st.write(f"**Fotos totales en disco:** `{len(todas_fotos)}` | **Fotos huérfanas (sin reporte):** `{len(fotos_huerfanas)}`")

            if fotos_huerfanas:
                st.warning(f"Se encontraron {len(fotos_huerfanas)} fotos que quedaron guardadas sin reporte vinculado.")
                for f_h in fotos_huerfanas[:4]:
                    st.text(f_h)
                if st.button("🧹 Eliminar Todas las Fotos Huérfanas", key="btn_limpiar_huerfanas"):
                    for f in fotos_huerfanas:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    st.success("✅ Fotos huérfanas eliminadas del servidor.")
                    st.rerun()
            else:
                st.success("✅ No hay fotos huérfanas. Todas las fotos en disco corresponden a un reporte activo.")

        with tab_admin3:
            st.error("🚨 ZONA DE ALTO RIESGO: BORRADO COMPLETO DE BASE DE DATOS")
            st.markdown("Esta opción eliminará **TODOS** los reportes y **TODAS** las fotografías del servidor. Esta acción no se puede deshacer.")
            confirmar_borrado_total = st.checkbox("Confirmo que deseo vaciar todos los reportes y fotos", key="chk_borrado_total")
            if st.button("💣 Borrar Absolutamente Todos los Reportes y Fotos", disabled=not confirmar_borrado_total):
                st.session_state.registros = []
                guardar_registros_permanentes([])
                if os.path.exists(FOTOS_DIR):
                    for arch in os.listdir(FOTOS_DIR):
                        r = os.path.join(FOTOS_DIR, arch)
                        try:
                            if os.path.isfile(r):
                                os.remove(r)
                        except Exception:
                            pass
                st.success("💥 Base de datos y galería de fotos vaciadas por completo.")
                st.rerun()

# =========================================================================
# SECCIÓN PRINCIPAL: CAPTURA DE REPORTES (VALIDADA POR ROL)
# =========================================================================
st.markdown("---")
if not es_contador:
    st.markdown(f"## 📋 Registro Diario de Operaciones ({st.session_state.usuario_autenticado})")
    st.caption("🔒 Como supervisor, tus reportes quedan protegidos una vez guardados y solo puedes capturar el día de hoy.")
else:
    st.markdown("## 📥 Captura de Reportes (Modo Auditor: Sin Límite de Fecha ni Frecuencia)")
    st.caption("✨ Puedes registrar reportes extemporáneos, múltiples turnos por sucursal o eventos.")

sucursal = st.selectbox(
    "Sucursal / Unidad:",
    SUCURSALES_LISTA,
    key="select_sitio",
    on_change=on_sucursal_change
)

es_ingreso_directo = sucursal in ["BARRANCA", "S. AZURA"]

col_f1, col_f2 = st.columns(2)
with col_f1:
    if es_contador:
        fecha_op = st.date_input("Fecha del Reporte:", value=date.today())
    else:
        fecha_hoy = date.today()
        st.write(f"📅 **Fecha de Operación:** `{fecha_hoy.strftime('%d/%m/%Y')}` *(Automática por seguridad)*")
        fecha_op = fecha_hoy

    fecha_op_str = fecha_op.strftime("%d/%m/%Y")

with col_f2:
    if es_ingreso_directo:
        st.info("📌 En esta unidad se captura directamente el Ingreso Bruto en el campo correspondiente.")
        costo_boleto = 0.0
    else:
        costo_boleto = st.number_input(
            "Costo por Boleto ($ MXN):",
            step=5,
            key="costo_boleto_input"
        )

col_h1, col_h2 = st.columns(2)
with col_h1:
    hora_ini = st.time_input("Hora de Apertura / Inicio:", value=time(13, 0))
with col_h2:
    hora_fin = st.time_input("Hora de Cierre / Fin:", value=time(23, 0))

with st.expander("📷 Captura o Escaneo de Reporte Físico", expanded=True):
    foto = st.file_uploader("Subir foto del reporte físico:", type=["png", "jpg", "jpeg"])
    if foto:
        st.image(foto, caption="Vista previa del reporte adjunto", width=300)

st.markdown("#### 🎫 Control de Operaciones y Folios")
c_b1, c_b2, c_b3 = st.columns(3)

if es_ingreso_directo:
    with c_b1:
        f_ini = st.number_input("Ingreso Bruto de la Unidad ($ MXN):", min_value=0.0, step=50.0, key="input_f_ini_dir")
        f_fin = 0
    with c_b2:
        f_sin = 0
        f_can = 0
    with c_b3:
        f_per = 0
    
    total_boletos_calc = 0
    boletos_cobrados_calc = 0
    ingreso_bruto_calc = float(f_ini)
else:
    with c_b1:
        f_ini = st.number_input("Folio Inicial:", min_value=0, step=1, key="input_f_ini")
        f_fin = st.number_input("Folio Final:", min_value=0, step=1, key="input_f_fin")
    with c_b2:
        f_sin = st.number_input("Boletos Sin Cobro:", min_value=0, step=1, key="input_f_sin")
        f_can = st.number_input("Boletos Cancelados:", min_value=0, step=1, key="input_f_can")
    with c_b3:
        f_per = st.number_input("Boletos Perdidos:", min_value=0, step=1, key="input_f_per")

    total_boletos_calc = max(0, (int(f_fin) - int(f_ini)) + 1) if int(f_fin) >= int(f_ini) and int(f_ini) > 0 else 0
    boletos_cobrados_calc = max(0, total_boletos_calc - int(f_sin) - int(f_can))
    ingreso_bruto_calc = boletos_cobrados_calc * float(costo_boleto)

st.markdown("#### 💵 Egresos y Gastos Operativos")
c_g1, c_g2 = st.columns(2)
with c_g1:
    g_esp = st.number_input("Gastos Especiales ($ MXN):", min_value=0.0, value=0.0, step=10.0, key="input_g_esp")
with c_g2:
    g_gen = st.number_input("Gastos Generales o Nómina ($ MXN):", min_value=0.0, value=0.0, step=10.0, key="input_g_gen")

st.markdown("#### ✍️ Firmas de Responsabilidad")
c_fir1, c_fir2 = st.columns(2)
with c_fir1:
    elaboro = st.text_input("Elaboró:", value=st.session_state.usuario_autenticado, key="input_elaboro")
with c_fir2:
    recibe = st.text_input("Recibe:", value="" if not es_contador else "Víctor (Contador)", key="input_recibe")

total_gastos_calc = float(g_esp) + float(g_gen)
ingreso_neto_calc = ingreso_bruto_calc - total_gastos_calc
margen_calc = (ingreso_neto_calc / ingreso_bruto_calc * 100) if ingreso_bruto_calc > 0 else 0.0
rentabilidad_calc = evaluar_rentabilidad(margen_calc)

# --- BALANCE PRELIMINAR ---
st.markdown("---")
st.markdown("### 📊 Balance Preliminar del Reporte")

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Boletos Cobrados", f"{boletos_cobrados_calc} boletos" if not es_ingreso_directo else "Directo")
with col_m2:
    st.metric("Ingreso Bruto", f"${ingreso_bruto_calc:,.2f} MXN")
with col_m3:
    st.metric("Total Gastos / Nómina", f"${total_gastos_calc:,.2f} MXN")
with col_m4:
    st.metric("Ingreso Neto", f"${ingreso_neto_calc:,.2f} MXN", delta=f"{margen_calc:.1f}% Margen")

st.info(f"**Rentabilidad Preliminar Estimada:** {rentabilidad_calc}")

# --- VALIDACIONES Y BOTÓN ÚNICO DE GUARDADO ---
ya_existe = existe_reporte_previo(sucursal, fecha_op_str)

st.markdown("---")

puede_guardar = True
mensaje_advertencia = None

if sucursal == "-- Selecciona o busca la sucursal --":
    puede_guardar = False
    mensaje_advertencia = "Por favor selecciona una sucursal para poder guardar el reporte."

elif ya_existe and not es_contador:
    puede_guardar = False
    mensaje_advertencia = (
        f"🔒 **REPORTE YA REGISTRADO:** La sucursal **{sucursal}** ya tiene un reporte guardado el día de hoy ({fecha_op_str}). "
        "Como supervisor, los reportes están protegidos contra sobreescritura. Si requieres hacer un cambio, contacta al Contador Auditor."
    )
elif ya_existe and es_contador:
    st.warning(f"ℹ️ **Modo Auditor:** Ya existe reporte para **{sucursal}** el día **{fecha_op_str}**. Se guardará como un reporte adicional/turno nuevo.")

if mensaje_advertencia:
    st.error(mensaje_advertencia)

if st.button("💾 Guardar y Confirmar Reporte", type="primary", disabled=not puede_guardar, use_container_width=True):
    with st.spinner("Guardando reporte y asegurando en disco..."):
        ruta_guardada = None
        if foto:
            ruta_guardada = guardar_imagen_optimizada(foto, sucursal, fecha_op_str)

        horario_str = f"{hora_ini.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}"

        
nuevo_reporte = {
    "Fecha": fecha_op_str,
    "Sitio / Unidad": sucursal,
    "Horario": horario_str,
    "Costo Boleto": float(costo_boleto),
    "Folio Inicial": (
        float(f_ini) if es_ingreso_directo else int(f_ini)
    ),
    "Folio Final": (
        0 if es_ingreso_directo else int(f_f)
    ),
}

