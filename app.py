import pandas as pd
import streamlit as st
from datetime import datetime, date
from PIL import Image
import os
import io
import json
import base64
import urllib.parse

# Archivo permanente de base de datos local
DB_FILE = "reportes_clubpark.json"

# Soporte opcional para análisis automático de imagen con Gemini Vision
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

st.set_page_config(page_title="Club Park - Control Operativo MXN", page_icon="🚗", layout="wide")

# Estilo CSS para ocultar los botones de más (+) y menos (-) en los inputs numéricos
st.markdown("""
    <style>
        /* Ocultar botones de incremento y decremento en st.number_input */
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

# --- FUNCIONES DE ALMACENAMIENTO PERMANENTE ---
def cargar_registros_guardados():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for reg in data:
                    if reg.get("foto_b64"):
                        reg["foto_bytes"] = base64.b64decode(reg["foto_b64"])
                return data
        except Exception:
            return []
    return []

def guardar_registros_permanentes(registros):
    data_to_save = []
    for reg in registros:
        reg_copy = dict(reg)
        if "foto_bytes" in reg_copy and reg_copy["foto_bytes"]:
            reg_copy["foto_b64"] = base64.b64encode(reg_copy["foto_bytes"]).decode("utf-8")
            del reg_copy["foto_bytes"]
        elif "foto_bytes" in reg_copy:
            del reg_copy["foto_bytes"]
        data_to_save.append(reg_copy)
        
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()

PRECIOS_SUCURSALES = {
    "PAMPAS": 50,
    "RAMMA": 70,
    "SUSHITTO": 40,
    "BARRANCA": 0,
    "CARAJILLO": 100,
    "BENINGANS": 40,
    "ROMAS": 65,
    "J.TLALPAN": 100,
    "J.DIVISION": 100,
    "J.PICACHO": 100,
    "J.EMPRESA": 100,
    "sipily": 80,
    "M SATÉLITE": 70,
    "M MARINA": 70,
    "VETERINARIA": 0,
    "CLÍNICA": 100,
    "SUMO STA": 50,
    "CHEGARAY": 50,
    "RYOSHI": 80,
    "ENCANTO": 90,
    "S. AZURA": 0,
    "E-BNI": 0,
    "CHURRASCA": 70
}

SUCURSALES_LISTA = ["-- Selecciona o busca la sucursal --"] + list(PRECIOS_SUCURSALES.keys())

if "costo_boleto_val" not in st.session_state:
    st.session_state.costo_boleto_val = 40

defaults = {
    "f_ini": 0,
    "f_fin": 0,
    "f_sin": 0,
    "f_can": 0,
    "f_per": 0,
    "g_esp": 0.0,
    "g_gen": 0.0,
    "elaboro_val": "",
    "recibe_val": ""
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

def actualizar_costo_sucursal():
    sucursal_seleccionada = st.session_state.get("select_sitio")
    if sucursal_seleccionada in PRECIOS_SUCURSALES:
        st.session_state.costo_boleto_val = PRECIOS_SUCURSALES[sucursal_seleccionada]

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=400)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK VALET Y ESTACIONAMIENTOS</h1>", unsafe_allow_html=True)
            
        st.markdown("<h3 style='text-align: center; color: gray;'>Control de Acceso al Sistema</h3>", unsafe_allow_html=True)
        
        nombre_usuario = st.selectbox("Selecciona tu Usuario:", ["-- Selecciona --", "Víctor Manuel", "José de Jesús", "Víctor (Contador)"])
        password = st.text_input("Contraseña de Acceso:", type="password")
        
        if st.button("🔑 Entrar al Sistema"):
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
st.sidebar.info(f"**Usuario actual:** {st.session_state.usuario_autenticado}\n\n**Rol:** {st.session_state.rol}\n\n**Total Acumulado:** {len(st.session_state.registros)} reportes guardados\n\n**Moneda:** Pesos Mexicanos (MXN)")

# ==========================================
# VISTA EXCLUSIVA PARA EL CONTADOR AUDITOR (VÍCTOR)
# ==========================================
if st.session_state.rol == "Contador Auditor":
    st.markdown("---")
    st.markdown("## 🔍 Panel de Auditoría, Balance Financiero y Control de Reportes (Contador)")
    st.info("Estimado Víctor, desde este panel tienes acceso al control masivo de reportes guardados permanentemente, balance semanal por unidad y descarga de la hoja de Excel consolidada.")
    
    if st.session_state.registros:
        registros_limpios = []
        for reg in st.session_state.registros:
            reg_sin_bytes = {k: v for k, v in reg.items() if k not in ["foto_bytes", "foto_b64"]}
            registros_limpios.append(reg_sin_bytes)
        df_auditoria = pd.DataFrame(registros_limpios)
        
        st.markdown(f"### 👥 Control de Hojas de Reporte Subidas (Total Almacenado: {len(st.session_state.registros)})")
        v_manuel_count = df_auditoria[df_auditoria["Supervisor"] == "Víctor Manuel"].shape[0]
        j_jesus_count = df_auditoria[df_auditoria["Supervisor"] == "José de Jesús"].shape[0]
        v_contador_count = df_auditoria[df_auditoria["Supervisor"].str.contains("Contador", case=False, na=False)].shape[0]
        
        c_u1, c_u2, c_u3 = st.columns(3)
        c_u1.metric("Víctor Manuel", f"{v_manuel_count} reportes")
        c_u2.metric("José de Jesús", f"{j_jesus_count} reportes")
        c_u3.metric("Víctor (Contador)", f"{v_contador_count} reportes")

        st.markdown("---")
        st.markdown("### 🏢 Balance Semanal por Unidad / Servicio")
        df_sucursal = df_auditoria.groupby("Sitio / Unidad").agg({
            "Ingreso Bruto (MXN)": "sum",
            "Total Gastos y Nóminas (MXN)": "sum",
            "Ingreso Neto / Utilidad (MXN)": "sum",
            "Rentabilidad (%)": "mean"
        }).reset_index()
        
        st.dataframe(df_sucursal, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📊 Tabla Global de Todos los Reportes Acumulados")
        st.dataframe(df_auditoria, use_container_width=True)
        
        st.markdown("### 📸 Visor de Evidencias Fotográficas")
        with st.expander("📂 Desplegar galería de fotos de reportes acumulados"):
            for idx, reg in enumerate(st.session_state.registros):
                if reg.get("foto_bytes"):
                    st.image(Image.open(io.BytesIO(reg["foto_bytes"])), caption=f"Reporte #{idx+1} - {reg['Fecha']} - {reg['Sitio / Unidad']} (Sup: {reg['Supervisor']})", width=300)

        total_ingresos_brutos = df_auditoria["Ingreso Bruto (MXN)"].sum() if "Ingreso Bruto (MXN)" in df_auditoria.columns else 0.0
        total_gastos_gral = df_auditoria["Total Gastos y Nóminas (MXN)"].sum() if "Total Gastos y Nóminas (MXN)" in df_auditoria.columns else 0.0
        total_ingresos_netos = df_auditoria["Ingreso Neto / Utilidad (MXN)"].sum() if "Ingreso Neto / Utilidad (MXN)" in df_auditoria.columns else 0.0
        rentabilidad_global = (total_ingresos_netos / total_ingresos_brutos * 100) if total_ingresos_brutos > 0 else 0.0
        
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("Ingreso Bruto Global", f"${total_ingresos_brutos:,.2f} MXN")
        col_a2.metric("Gasto Total Global", f"${total_gastos_gral:,.2f} MXN")
        col_a3.metric("Utilidad Total Global", f"${total_ingresos_netos:,.2f} MXN")
        col_a4.metric("Rentabilidad Global (%)", f"{rentabilidad_global:.2f}%")
        
        st.markdown("---")
        st.markdown("### 📥 Descarga de la Hoja de Excel Semanal")
        csv_export = df_auditoria.to_csv(index=False).encode('utf-8')
        
        fecha_actual_str = datetime.now().strftime("%d_%m_%Y")
        st.download_button(
            label="📥 Descargar Reporte Semanal Completo en Excel (CSV)",
            data=csv_export,
            file_name=f"Control_Semanal_ClubPark_{fecha_actual_str}.csv",
            mime="text/csv",
        )
        
        if st.button("🗑️ Limpiar / Borrar Todos los Registros"):
            st.session_state.registros = []
            guardar_registros_permanentes([])
            st.success("Se han borrado todos los registros guardados en la base de datos.")
            st.rerun()
    else:
        st.warning("⚠️ No hay registros cargados en el sistema todavía por parte de los supervisores.")
        
    st.stop()

# ==========================================
# VISTA PARA SUPERVISORES
# ==========================================
st.markdown("---")
st.markdown("### 📸 1. Evidencia Fotográfica del Reporte Físico")
foto_reporte = st.file_uploader("Tomar o subir foto de la hoja de reporte", type=["jpg", "jpeg", "png"], key="foto")

if foto_reporte is not None:
    imagen = Image.open(foto_reporte)
    st.image(imagen, caption="Vista previa de la hoja de reporte física", width=350)
    
    api_key_env = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", "")
    if GENAI_AVAILABLE and api_key_env:
        if st.button("🤖 Analizar Foto y Llenar Datos Automáticamente con IA"):
            with st.spinner("Analizando reporte físico y leyendo folios/gastos..."):
                try:
                    genai.configure(api_key=api_key_env)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    
                    prompt = """
                    Analiza esta imagen de reporte de valet parking y devuelve ÚNICAMENTE un objeto JSON válido con este formato exacto:
                    {
                        "folio_inicial": 0,
                        "folio_final": 0,
                        "folio_sin_desprender": 0,
                        "cancelados": 0,
                        "perdidos": 0,
                        "gastos_especiales": 0.0,
                        "gastos_generales": 0.0,
                        "elaboro": "",
                        "recibe": ""
                    }
                    Devuelve números enteros para folios/boletos y flotantes para gastos.
                    """
                    
                    response = model.generate_content([prompt, imagen])
                    texto_res = response.text.strip().replace("```json", "").replace("```", "")
                    datos_ia = json.loads(texto_res)
                    
                    st.session_state.f_ini = int(datos_ia.get("folio_inicial", 0))
                    st.session_state.f_fin = int(datos_ia.get("folio_final", 0))
                    st.session_state.f_sin = int(datos_ia.get("folio_sin_desprender", 0))
                    st.session_state.f_can = int(datos_ia.get("cancelados", 0))
                    st.session









