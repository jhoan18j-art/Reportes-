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
    st.markdown("## 🔍 Panel de Auditoría, Balance Financiero y Control de Eventos (Contador)")
    st.info("Estimado Víctor, desde este panel tienes acceso al control masivo, balance semanal y facultad especial para registrar reportes de eventos y fines de semana.")
    
    # Sección especial para que el contador suba reportes de eventos extraordinarios
    with st.expander("🎪 Registrar Reporte de Eventos / Fines de Semana (Facultad del Contador)"):
        st.warning("Como Contador Auditor, puedes dar de alta reportes adicionales de eventos (múltiples por salón/día) en cualquier fecha.")
        with st.form("form_evento_contador"):
            ev_fecha = st.date_input("Fecha del Evento", value=date.today())
            ev_sucursal = st.selectbox("Sucursal / Salón de Evento", SUCURSALES_LISTA, key="ev_suc")
            ev_costo = st.number_input("Costo por Boleto ($ MXN)", value=100, step=1)
            ev_ini = st.number_input("Folio Inicial", value=1, step=1)
            ev_fin = st.number_input("Folio Final", value=50, step=1)
            ev_gastos = st.number_input("Gastos del Evento ($ MXN)", value=0.0, step=10.0)
            ev_elaboro = st.text_input("Personal que elaboró", value="Staff Eventos")
            ev_recibe = st.text_input("Recibe", value="Víctor (Contador)")
            
            btn_guardar_evento = st.form_submit_button("🚀 Registrar Evento Extraordinario")
            if btn_guardar_evento:
                if ev_sucursal == "-- Selecciona o busca la sucursal --":
                    st.error("Selecciona una sucursal válida.")
                else:
                    boletos_evt = max(0, (ev_fin - ev_ini) + 1)
                    bruto_evt = boletos_evt * ev_costo
                    neto_evt = bruto_evt - ev_gastos
                    
                    reg_evento = {
                        "Fecha": ev_fecha.strftime("%d/%m/%Y"),
                        "Supervisor": "Víctor (Contador - Evento)",
                        "Sitio / Unidad": ev_sucursal,
                        "Costo Boleto (MXN)": ev_costo,
                        "Folio Inicial": ev_ini,
                        "Folio Final": ev_fin,
                        "Folio sin desprender": 0,
                        "Total Boletos Entregados": boletos_evt,
                        "Boletos Pagados (A Entregar)": boletos_evt,
                        "Cancelados": 0,
                        "Pérdidos": 0,
                        "Gastos de Operación": "Evento Especial",
                        "Gastos Especiales (MXN)": ev_gastos,
                        "Gastos Generales (MXN)": 0.0,
                        "Total Gastos y Nóminas (MXN)": ev_gastos,
                        "Ingreso Bruto (MXN)": bruto_evt,
                        "Ingreso Neto / Utilidad (MXN)": neto_evt,
                        "Rentabilidad (%)": 100.0 if bruto_evt > 0 else 0.0,
                        "Cantidad a Entregar (MXN)": neto_evt,
                        "Elaboró": ev_elaboro,
                        "Recibe": ev_recibe,
                        "Evidencia Foto": "N/A (Autorizado por Contador)",
                        "foto_bytes": None
                    }
                    st.session_state.registros.append(reg_evento)
                    guardar_registros_permanentes(st.session_state.registros)
                    st.success(f"¡Reporte de evento para '{ev_sucursal}' registrado exitosamente!")
                    st.rerun()

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
        c_u3.metric("Víctor (Contador / Eventos)", f"{v_contador_count} reportes")

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
        st.warning("⚠️ No hay registros cargados en el sistema todavía.")
        
    st.stop()

# ==========================================
# VISTA PARA SUPERVISORES
# ==========================================
st.markdown("---")

dia_semana_actual = date.today().weekday()  # 0 al 4 es de Lunes a Viernes
if dia_semana_actual < 5:
    st.info("📋 **Control Operativo (Lunes a Viernes):** Meta establecida para supervisores: **15 reportes diarios** requeridos por operación regular.")
else:
    st.info("📅 **Control de Fines de Semana / Eventos:** Los reportes extraordinarios y de múltiples eventos en salón pueden ser cargados y respaldados directamente por el Contador Víctor.")

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
                    st.session_state.f_per = int(datos_ia.get("perdidos", 0))
                    st.session_state.g_esp = float(datos_ia.get("gastos_especiales", 0.0))
                    st.session_state.g_gen = float(datos_ia.get("gastos_generales", 0.0))
                    st.session_state.elaboro_val = str(datos_ia.get("elaboro", ""))
                    st.session_state.recibe_val = str(datos_ia.get("recibe", ""))
                    
                    st.success("✨ ¡Campos autocompletados desde la fotografía exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo leer automáticamente la imagen: {e}")

st.markdown("---")
st.markdown("### 📝 2. Captura en Tiempo Real y Validación de Datos")
st.warning("⚠️ Todos los campos son obligatorios. Las cantidades se calculan al instante en Moneda Nacional Mexicana (MXN).")

sitio = st.selectbox("🏢 Sitio / Sucursal*", SUCURSALES_LISTA, key="select_sitio", on_change=actualizar_costo_sucursal)

c_live1, c_live2, c_live3 = st.columns(3)
with c_live1:
    fecha_reporte = st.date_input("📅 Fecha del Reporte", value=date.today())
    fecha_formateada = fecha_reporte.strftime("%d/%m/%Y")
    costo_boleto = st.number_input("💵 Costo del Boleto ($ MXN)", value=int(st.session_state.costo_boleto_val), step=1)
with c_live2:
    folio_inicial = st.number_input("🔢 Folio Inicial Utilizado", value=int(st.session_state.f_ini), step=1, key="f_ini")
    folio_final = st.number_input("🔢 Folio Final Utilizado", value=int(st.session_state.f_fin), step=1, key="f_fin")
with c_live3:
    cancelados = st.number_input("❌ Boletos Cancelados", value=int(st.session_state.f_can), step=1, key="f_can")
    perdidos = st.number_input("⚠️ Boletos Pérdidos", value=int(st.session_state.f_per), step=1, key="f_per")

if int(folio_inicial) == 0 and int(folio_final) == 0:
    total_boletos_entregados = 0
else:
    i_last = int(folio_inicial) % 100
    f_last = int(folio_final) % 100
    if f_last >= i_last:
        total_boletos_entregados = (f_last - i_last) + 1
    else:
        total_boletos_entregados = (100 - i_last) + f_last + 1

boletos_pagados = max(0, total_boletos_entregados - cancelados - perdidos)
ingreso_bruto_live = boletos_pagados * costo_boleto

st.markdown("---")
st.markdown("### 🛠️ 3. Captura de Gastos (En Tiempo Real)")

col_g1, col_g2 = st.columns(2)
with col_g1:
    folio_sin_desprender = st.number_input("🔖 Folio inicio sin desprender del block", value=int(st.session_state.f_sin), step=1, key="f_sin")
    st.markdown("#### 🛠️ Gastos de Operación")
with col_g2:
    gastos_especiales = st.number_input("📌 Gastos Especiales ($ MXN)", value=float(st.session_state.g_esp), step=10.0, key="g_esp")
    gastos_generales = st.number_input("📋 Gastos Generales ($ MXN)", value=float(st.session_state.g_gen), step=10.0, key="g_gen")

total_gastos_live = gastos_especiales + gastos_generales
ingreso_neto_live = ingreso_bruto_live - total_gastos_live
rentabilidad_live = (ingreso_neto_live / ingreso_bruto_live * 100) if ingreso_bruto_live > 0 else 0.0

st.markdown("### 📊 Resumen Financiero en Vivo (MXN)")
r1, r2, r3, r4, r5 = st.columns(5)
r1.metric("Boletos Pagados", boletos_pagados)
r2.metric("Ingreso Bruto", f"${ingreso_bruto_live:,.2f} MXN")
r3.metric("Total Gastos", f"${total_gastos_live:,.2f} MXN")
r4.metric("Ingreso Neto (Utilidad)", f"${ingreso_neto_live:,.2f} MXN", delta=f"${ingreso_neto_live:,.2f} MXN")
r5.metric("Rentabilidad (%)", f"{rentabilidad_live:.2f}%")

st.markdown("---")

with st.form("form_reporte_guardar"):
    c4, c5 = st.columns(2)
    with c4:
        elaboro = st.text_input("✍️ Elaboró Reporte (Nombre)*", value=str(st.session_state.elaboro_val), placeholder="Ej. Gaby")
    with c5:
        recibe = st.text_input("👤 Quien Recibe Reporte (Nombre)*", value=str(st.session_state.recibe_val), placeholder="Ej. Jesús")

    submitted = st.form_submit_button("💾 Validar y Guardar Registro en el Consolidado")

    if submitted:
        if sitio == "-- Selecciona o busca la sucursal --":
            st.error("❌ Error de validación: Debes seleccionar una sucursal o sitio válido.")
        elif folio_inicial == 0 and folio_final == 0:
            st.error("❌ Error de validación: Debes capturar el Folio Inicial y Folio Final.")
        elif folio_final < folio_inicial:
            st.error("❌ Error de validación: El Folio Final no puede ser menor que el Folio Inicial.")
        elif not elaboro.strip() or not recibe.strip():
            st.error("❌ Error de validación: Los campos 'Elaboró Reporte' y 'Quien Recibe Reporte' son obligatorios.")
        elif foto_reporte is None:
            st.warning("⚠️ Advertencia: Es necesario adjuntar la fotografía de la hoja de reporte físico.")
        else:
            foto_bytes = None
            if foto_reporte is not None:
                img_to_compress = Image.open(foto_reporte)
                img_to_compress.thumbnail((800, 800))
                img_io = io.BytesIO()
                img_to_compress.save(img_io, format="JPEG", quality=75)
                foto_bytes = img_io.getvalue()
            
            nuevo_registro = {
                "Fecha": fecha_formateada,
                "Supervisor": st.session_state.usuario_autenticado,
                "Sitio / Unidad": sitio,
                "Costo Boleto (MXN)": costo_boleto,
                "Folio Inicial": folio_inicial,
                "Folio Final": folio_final,
                "Folio sin desprender": folio_sin_desprender,
                "Total Boletos Entregados": total_boletos_entregados,
                "Boletos Pagados (A Entregar)": boletos_pagados,
                "Cancelados": cancelados,
                "Pérdidos": perdidos,
                "Gastos de Operación": "Título Informativo",
                "Gastos Especiales (MXN)": gastos_especiales,
                "Gastos Generales (MXN)": gastos_generales,
                "Total Gastos y Nóminas (MXN)": total_gastos_live,
                "Ingreso Bruto (MXN)": ingreso_bruto_live,
                "Ingreso Neto / Utilidad (MXN)": ingreso_neto_live,
                "Rentabilidad (%)": round(rentabilidad_live, 2),
                "Cantidad a Entregar (MXN)": ingreso_neto_live,
                "Elaboró": elaboro,
                "Recibe": recibe,
                "Evidencia Foto": "Sí",
                "foto_bytes": foto_bytes
            }
            st.session_state.registros.append(nuevo_registro)
            guardar_registros_permanentes(st.session_state.registros)
            
            st.success(f"¡El reporte del sitio '{sitio}' ha sido validado y guardado PERMANENTEMENTE por {st.session_state.usuario_autenticado}!")

# --- BOTÓN PARA ENVIAR NOTIFICACIÓN POR WHATSAPP ---
if st.session_state.registros:
    st.markdown("---")
    st.markdown("### 💬 Enviar Notificación del Último Reporte por WhatsApp")
    
    ultimo = st.session_state.registros[-1]
    telefono_destino = st.text_input("📱 Número de WhatsApp del Destinatario (Opcional - ej: 5215512345678):", value="")
    
    f_fecha = ultimo.get("Fecha", "")
    f_sitio = ultimo.get("Sitio / Unidad", "")
    f_sup = ultimo.get("Supervisor", "")
    f_bruto = ultimo.get("Ingreso Bruto (MXN)", 0.0)
    f_gastos = ultimo.get("Total Gastos y Nóminas (MXN)", 0.0)
    f_neto = ultimo.get("Ingreso Neto / Utilidad (MXN)", 0.0)
    f_elab = ultimo.get("Elaboró", "")
    f_rec = ultimo.get("Recibe", "")

    mensaje_wht = (
        f"🚗 *REPORTE CLUB PARK*\n"
        f"📅 Fecha: {f_fecha}\n"
        f"🏢 Sucursal: {f_sitio}\n"
        f"👤 Supervisor: {f_sup}\n"
        f"💵 Ingreso Bruto: ${f_bruto:,.2f} MXN\n"
        f"🛠️ Gastos Totales: ${f_gastos:,.2f} MXN\n"
        f"💰 Ingreso Neto: ${f_neto:,.2f} MXN\n"
        f"✍️ Elaboró: {f_elab} | Recibe: {f_rec}"
    )
    
    encoded_msg = urllib.parse.quote(mensaje_wht)
    
    if telefono_destino.strip():
        whatsapp_url = f"https://wa.me/{telefono_destino.strip()}?text={encoded_msg}"
    else:
        whatsapp_url = f"https://wa.me/?text={encoded_msg}"
        
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 20px;">
            <a href="{whatsapp_url}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #25D366; color: white; padding: 12px 24px; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer;">
                    🚀 Enviar Resumen por WhatsApp
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
