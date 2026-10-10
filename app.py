import base64
import io
import json
import os
from datetime import date, datetime
import urllib.parse
import pandas as pd
import streamlit as st
from PIL import Image

# Soporte para análisis de imágenes con Gemini
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False

# Archivo permanente de base de datos local
DB_FILE = "reportes_clubpark.json"

st.set_page_config(page_title="Club Park - Control Operativo MXN", page_icon="🚗", layout="wide")

# Estilo CSS para ocultar botones +/- en inputs numéricos
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

# Variables en session_state para los campos del formulario
if "f_ini_val" not in st.session_state: st.session_state.f_ini_val = 0
if "f_fin_val" not in st.session_state: st.session_state.f_fin_val = 0
if "f_sin_val" not in st.session_state: st.session_state.f_sin_val = 0
if "f_can_val" not in st.session_state: st.session_state.f_can_val = 0
if "f_per_val" not in st.session_state: st.session_state.f_per_val = 0
if "g_esp_val" not in st.session_state: st.session_state.g_esp_val = 0.0
if "g_gen_val" not in st.session_state: st.session_state.g_gen_val = 0.0
if "elaboro_val" not in st.session_state: st.session_state.elaboro_val = ""
if "recibe_val" not in st.session_state: st.session_state.recibe_val = ""
if "costo_boleto_val" not in st.session_state: st.session_state.costo_boleto_val = 40

def actualizar_costo_sucursal():
    sucursal_seleccionada = st.session_state.get("select_sitio")
    if sucursal_seleccionada in PRECIOS_SUCURSALES:
        st.session_state.costo_boleto_val = PRECIOS_SUCURSALES[sucursal_seleccionada]

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
st.sidebar.info(f"**Usuario actual:** {st.session_state.usuario_autenticado}\n\n**Rol:** {st.session_state.rol}\n\n**Total Acumulado:** {len(st.session_state.registros)} reportes guardados")

# ==========================================
# PANEL CONTADOR AUDITOR
# ==========================================
if st.session_state.rol == "Contador Auditor":
    st.markdown("---")
    st.markdown("## 🔍 Panel de Auditoría, Balance Financiero y Control de Eventos (Contador)")
    st.info("Estimado Víctor, desde este panel tienes acceso al control masivo, balance semanal y facultad especial para registrar reportes de eventos.")
    
    with st.expander("📲 Enviar Recordatorio de Reportes Faltantes por WhatsApp", expanded=True):
        st.markdown("### 🔔 Control de Reportes Faltantes a Supervisores")
        fecha_revision = st.date_input("Selecciona la fecha a revisar:", value=date.today(), key="fecha_rev_contador")
        fecha_rev_str = fecha_revision.strftime("%d/%m/%Y")
        
        unidades_reportadas_fecha = [
            reg["Sitio / Unidad"] for reg in st.session_state.registros if reg.get("Fecha") == fecha_rev_str
        ]
        
        faltantes_jesus = [u for u in UNIDADES_JESUS if u not in unidades_reportadas_fecha]
        faltantes_victor = [u for u in UNIDADES_VICTOR if u not in unidades_reportadas_fecha]
        
        col_notif1, col_notif2 = st.columns(2)
        with col_notif1:
            st.markdown("#### 👤 Supervisor: José de Jesús")
            if faltantes_jesus:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_jesus)}):** " + ", ".join(faltantes_jesus))
                msg_jesus = f"🚨 *RECORDATORIO DE REPORTES FALTANTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola José de Jesús,* te hacen falta los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_jesus])
                st.markdown(f"[📲 **Enviar WhatsApp a Jesús**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_jesus)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡José de Jesús ha completado todos sus reportes!")
                
        with col_notif2:
            st.markdown("#### 👤 Supervisor: Víctor Manuel")
            if faltantes_victor:
                st.warning(f"⚠️ **Pendientes ({len(faltantes_victor)}):** " + ", ".join(faltantes_victor))
                msg_victor = f"🚨 *RECORDATORIO DE REPORTES FALTANTES*\n📅 *Fecha:* {fecha_rev_str}\n👤 *Hola Víctor Manuel,* te hacen falta los reportes de:\n\n" + "\n".join([f"❌ {u}" for u in faltantes_victor])
                st.markdown(f"[📲 **Enviar WhatsApp a Víctor**](https://api.whatsapp.com/send?text={urllib.parse.quote(msg_victor)})", unsafe_allow_html=True)
            else:
                st.success("✅ ¡Víctor Manuel ha completado todos sus reportes!")

    st.markdown("---")

    with st.expander("🎪 Registrar Reporte de Eventos Extraordinarios", expanded=True):
        with st.form("form_evento_contador"):
            ev_fecha = st.date_input("Fecha del Evento", value=date.today())
            ev_sucursal = st.selectbox("Sucursal / Salón de Evento", SUCURSALES_LISTA, key="ev_suc")
            ev_costo = st.number_input("Costo por Boleto ($ MXN)", value=100, step=1)
            ev_ini = st.number_input("Folio Inicial", value=1, step=1)
            ev_fin = st.number_input("Folio Final", value=50, step=1)
            ev_gastos = st.number_input("Gastos del Evento ($ MXN)", value=0.0, step=10.0)
            ev_elaboro = st.text_input("Personal que elaboró", value="Staff Eventos")
            ev_recibe = st.text_input("Recibe", value="Víctor (Contador)")
            
            if st.form_submit_button("🚀 Registrar Evento Extraordinario"):
                if ev_sucursal != "-- Selecciona o busca la sucursal --":
                    boletos_evt = max(0, (int(ev_fin) - int(ev_ini)) + 1)
                    bruto_evt = boletos_evt * float(ev_costo)
                    neto_evt = bruto_evt - float(ev_gastos)
                    
                    reg_evento = {
                        "Fecha": ev_fecha.strftime("%d/%m/%Y"),
                        "Supervisor": "Víctor (Contador - Evento)",
                        "Sitio / Unidad": ev_sucursal,
                        "Costo Boleto (MXN)": ev_costo,
                        "Folio Inicial": ev_ini, "Folio Final": ev_fin, "Folio sin desprender": 0,
                        "Total Boletos Entregados": boletos_evt, "Boletos Pagados (A Entregar)": boletos_evt,
                        "Cancelados": 0, "Pérdidos": 0,
                        "Gastos de Operación": "Evento Especial", "Gastos Especiales (MXN)": ev_gastos,
                        "Gastos Generales (MXN)": 0.0, "Total Gastos y Nóminas (MXN)": ev_gastos,
                        "Ingreso Bruto (MXN)": bruto_evt, "Ingreso Neto / Utilidad (MXN)": neto_evt,
                        "Rentabilidad (%)": 100.0 if bruto_evt > 0 else 0.0,
                        "Cantidad a Entregar (MXN)": neto_evt,
                        "Elaboró": ev_elaboro, "Recibe": ev_recibe,
                        "Evidencia Foto": "N/A", "foto_bytes": None
                    }
                    st.session_state.registros.append(reg_evento)
                    guardar_registros_permanentes(st.session_state.registros)
                    st.success("¡Reporte de evento guardado!")
                    st.rerun()

    if st.session_state.registros:
        registros_limpios = [{k: v for k, v in reg.items() if k not in ["foto_bytes", "foto_b64"]} for reg in st.session_state.registros]
        df_auditoria = pd.DataFrame(registros_limpios)
        
        st.markdown(f"### 👥 Control de Hojas de Reporte Subidas ({len(st.session_state.registros)})")
        st.dataframe(df_auditoria, use_container_width=True)
        
        csv_export = df_auditoria.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte Completo (CSV)", data=csv_export, file_name=f"Control_ClubPark_{datetime.now().strftime('%d_%m_%Y')}.csv", mime="text/csv")
        
        if st.button("🗑️ Limpiar / Borrar Todos los Registros"):
            st.session_state.registros = []
            guardar_registros_permanentes([])
            st.rerun()
    st.stop()

# ==========================================
# PANEL SUPERVISORES Y CAPTURA CON IA
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
            with st.spinner("Analizando reporte físico con IA..."):
                prompt_text = (
                    "Analiza la foto del reporte impreso o manuscrito. "
                    "Devuelve UNICAMENTE un JSON estricto sin comillas de bloque markdown con este formato: "
                    '{"folio_inicial": 0, "folio_final": 0, "folio_sin_desprender": 0, '
                    '"cancelados": 0, "perdidos": 0, "gastos_especiales": 0.0, '
                    '"gastos_generales": 0.0, "elaboro": "", "recibe": ""}'
                )

                texto_res = None
                try:
                    # Intento 1: SDK Nuevo
                    from google import genai
                    client = genai.Client(api_key=api_key_env)
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[prompt_text, imagen]
                    )
                    texto_res = (response.text or "").strip()
                except Exception:
                    try:
                        # Intento 2: SDK Legacy
                        import google.generativeai as genai_legacy
                        genai_legacy.configure(api_key=api_key_env)
                        model_legacy = genai_legacy.GenerativeModel("gemini-2.5-flash")
                        response_legacy = model_legacy.generate_content([prompt_text, imagen])
                        texto_res = (response_legacy.text or "").strip()
                    except Exception as err:
                        st.error(f"❌ Error al conectar con la IA: {err}")

        if texto_res:
            try:
                clean_json = texto_res.replace("```json", "").replace("```", "").strip()
                datos_ia = json.loads(clean_json)

                # Asignación segura a variables de estado
                st.session_state.f_ini_val = int(datos_ia.get("folio_inicial", 0) or 0)
                st.session_state.f_fin_val = int(datos_ia.get("folio_final", 0) or 0)
                st.session_state.f_sin_val = int(datos_ia.get("folio_sin_desprender", 0) or 0)
                st.session_state.f_can_val = int(datos_ia.get("cancelados", 0) or 0)
                st.session_state.f_per_val = int(datos_ia.get("perdidos", 0) or 0)
                st.session_state.g_esp_val = float(datos_ia.get("gastos_especiales", 0.0) or 0.0)
                st.session_state.g_gen_val = float(datos_ia.get("gastos_generales", 0.0) or 0.0)
                st.session_state.elaboro_val = str(datos_ia.get("elaboro", "") or "")
                st.session_state.recibe_val = str(datos_ia.get("recibe", "") or "")

                st.success("✨ ¡Datos leídos de la imagen e insertados en los campos!")
                st.rerun()
            except Exception as parse_err:
                st.warning(f"⚠️ No se pudo procesar la respuesta de la IA: {parse_err}")

st.markdown("---")
st.markdown("### 📝 2. Captura / Verificación de Datos del Reporte")


# FORMULARIO CON VALORES CONECTADOS CORRECTAMENTE AL SESSION_STATE
with st.form("form_reporte_supervisor"):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_rep = st.date_input("Fecha de Operación", value=date.today())
        sucursal_sel = st.selectbox(
            "Sitio / Unidad",
            SUCURSALES_LISTA,
            key="select_sitio",
            on_change=actualizar_costo_sucursal
        )
    with col_f2:
        costo_boleto = st.number_input(
            "Costo por Boleto ($ MXN)",
            value=int(st.session_state.costo_boleto_val),
            step=1
        )
        supervisor_nombre = st.session_state.usuario_autenticado

    st.markdown("#### 🎟️ Control de Folios y Boletos")
    c_fol1, c_fol2, c_fol3 = st.columns(3)
    with c_fol1:
        f_ini = st.number_input("Folio Inicial", value=int(st.session_state.f_ini_val), step=1)
        f_fin = st.number_input("Folio Final", value=int(st.session_state.f_fin_val), step=1)
    with c_fol2:
        f_sin = st.number_input("Folio sin Desprender", value=int(st.session_state.f_sin_val), step=1)
        f_can = st.number_input("Boletos Cancelados", value=int(st.session_state.f_can_val), step=1)
    with c_fol3:
        f_per = st.number_input("Boletos Perdidos", value=int(st.session_state.f_per_val), step=1)

    st.markdown("#### 💸 Gastos de Operación")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        g_esp = st.number_input("Gastos Especiales ($ MXN)", value=float(st.session_state.g_esp_val), step=5.0)
    with col_g2:
        g_gen = st.number_input("Gastos Generales / Nómina ($ MXN)", value=float(st.session_state.g_gen_val), step=5.0)

    st.markdown("#### ✍️ Firmas y Control")
    col_firm1, col_firm2 = st.columns(2)
    with col_firm1:
        elaboro_txt = st.text_input("Elaboró", value=str(st.session_state.elaboro_val))
    with col_firm2:
        recibe_txt = st.text_input("Recibe", value=str(st.session_state.recibe_val))

    btn_guardar_reporte = st.form_submit_button("💾 Guardar y Finalizar Reporte")

    if btn_guardar_reporte:
        if sucursal_sel == "-- Selecciona o busca la sucursal --":
            st.error("❌ Por favor selecciona una sucursal válida.")
        else:
            tot_entregados = max(0, (f_fin - f_ini) + 1 - f_sin)
            tot_pagados = max(0, tot_entregados - f_can - f_per)
            
            ingreso_bruto = tot_pagados * float(costo_boleto)
            total_gastos = float(g_esp) + float(g_gen)
            ingreso_neto = ingreso_bruto - total_gastos
            rentabilidad = (ingreso_neto / ingreso_bruto * 100) if ingreso_bruto > 0 else 0.0

            foto_bytes = foto_reporte.getvalue() if foto_reporte is not None else None

            nuevo_registro = {
                "Fecha": fecha_rep.strftime("%d/%m/%Y"),
                "Supervisor": supervisor_nombre,
                "Sitio / Unidad": sucursal_sel,
                "Costo Boleto (MXN)": costo_boleto,
                "Folio Inicial": f_ini,
                "Folio Final": f_fin,
                "Folio sin desprender": f_sin,
                "Total Boletos Entregados": tot_entregados,
                "Boletos Pagados (A Entregar)": tot_pagados,
                "Cancelados": f_can,
                "Pérdidos": f_per,
                "Gastos de Operación": "Detallado",
                "Gastos Especiales (MXN)": g_esp,
                "Gastos Generales (MXN)": g_gen,
                "Total Gastos y Nóminas (MXN)": total_gastos,
                "Ingreso Bruto (MXN)": ingreso_bruto,
                "Ingreso Neto / Utilidad (MXN)": ingreso_neto,
                "Rentabilidad (%)": rentabilidad,
                "Cantidad a Entregar (MXN)": ingreso_neto,
                "Elaboró": elaboro_txt,
                "Recibe": recibe_txt,
                "Evidencia Foto": "Adjunta" if foto_bytes else "Sin foto",
                "foto_bytes": foto_bytes
            }

            st.session_state.registros.append(nuevo_registro)
            guardar_registros_permanentes(st.session_state.registros)

            # Limpiar campos temporales
            st.session_state.f_ini_val = 0
            st.session_state.f_fin_val = 0
            st.session_state.f_sin_val = 0
            st.session_state.f_can_val = 0
            st.session_state.f_per_val = 0
            st.session_state.g_esp_val = 0.0
            st.session_state.g_gen_val = 0.0
            st.session_state.elaboro_val = ""
            st.session_state.recibe_val = ""

            st.success(f"✅ ¡Reporte guardado exitosamente para la sucursal {sucursal_sel}!")
            st.rerun()
            
