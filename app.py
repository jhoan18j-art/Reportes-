import base64
import io
import json
import os
from datetime import date, datetime, time
import urllib.parse
import pandas as pd
import streamlit as st
from PIL import Image

# Soporte opcional para análisis de imágenes con Gemini
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

def evaluar_rentabilidad(margen):
    if margen >= 40.0:
        return "🟢 Alta"
    elif margen >= 15.0:
        return "🟡 Moderada"
    elif margen > 0.0:
        return "🟠 Baja"
    else:
        return "🔴 No Rentable (Pérdida)"

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

# Valores iniciales de los campos del formulario
CAMPOS_INICIALES = {
    "f_ini_val": 0, "f_fin_val": 0, "f_sin_val": 0,
    "f_can_val": 0, "f_per_val": 0,
    "g_esp_val": 0.0, "g_gen_val": 0.0,
    "elaboro_val": "", "recibe_val": "",
    "costo_boleto_val": 40,
}
for k, v in CAMPOS_INICIALES.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
            ev_h1, ev_h2 = st.columns(2)
            with ev_h1:
                ev_hora_ini = st.time_input("Horario: inicio del evento", value=time(18, 0))
            with ev_h2:
                ev_hora_fin = st.time_input("Horario: fin del evento", value=time(23, 0))
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
                    margen_evt = (neto_evt / bruto_evt * 100) if bruto_evt > 0 else 0.0
                    rentabilidad_evt = evaluar_rentabilidad(margen_evt)
                    horario_evt = f"{ev_hora_ini.strftime('%H:%M')} a {ev_hora_fin.strftime('%H:%M')}"

                    nuevo_evento = {
                        "Fecha": ev_fecha.strftime("%d/%m/%Y"),
                        "Sitio / Unidad": ev_sucursal,
                        "Horario": horario_evt,
                        "Costo Boleto": float(ev_costo),
                        "Folio Inicial": int(ev_ini),
                        "Folio Final": int(ev_fin),
                        "Total Boletos": boletos_evt,
                        "Sin Cobro": 0,
                        "Cancelados": 0,
                        "Perdidos": 0,
                        "Boletos Cobrados": boletos_evt,
                        "Ingreso Bruto": bruto_evt,
                        "Gastos Especiales": float(ev_gastos),
                        "Gastos Generales / Nómina": 0.0,
                        "Total Gastos": float(ev_gastos),
                        "Ingreso Neto": neto_evt,
                        "Margen (%)": round(margen_evt, 2),
                        "Rentabilidad": rentabilidad_evt,
                        "Elaboró": ev_elaboro,
                        "Recibe": ev_recibe,
                        "Tipo": "Evento Extraordinario",
                        "foto_bytes": None
                    }
                    st.session_state.registros.append(nuevo_evento)
                    guardar_registros_permanentes(st.session_state.registros)
                    st.success("✅ Reporte de evento registrado con éxito.")
                    st.rerun()
                else:
                    st.error("❌ Por favor, selecciona una sucursal válida.")

    st.markdown("### 📊 Base de Datos General de Reportes")
    if st.session_state.registros:
        df_registros = pd.DataFrame(st.session_state.registros)
        st.dataframe(df_registros.drop(columns=["foto_bytes", "foto_b64"], errors="ignore"), use_container_width=True)
    else:
        st.info("No hay reportes registrados hasta el momento.")

# ==========================================
# PANEL SUPERVISORES
# ==========================================
else:
    st.markdown("---")
    st.markdown(f"## 📋 Registro Diario de Operaciones ({st.session_state.usuario_autenticado})")

    sucursal = st.selectbox(
        "Sucursal / Unidad:",
        SUCURSALES_LISTA,
        key="select_sitio",
        on_change=actualizar_costo_sucursal
    )

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_op = st.date_input("Fecha:", value=date.today())
    with col_f2:
        costo_boleto = st.number_input("Costo por Boleto ($ MXN):", value=st.session_state.costo_boleto_val, step=5)

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        hora_ini = st.time_input("Hora de Apertura:", value=time(13, 0))
    with col_h2:
        hora_fin = st.time_input("Hora de Cierre:", value=time(23, 0))

    with st.expander("📷 Captura o Escaneo de Reporte Físico", expanded=False):
        foto = st.file_uploader("Subir foto del reporte físico:", type=["png", "jpg", "jpeg"])
        if foto:
            st.image(foto, caption="Reporte Cargado", width=300)

    with st.form("form_reporte_diario"):
        st.markdown("#### 🎫 Control de Boletos")
        c_b1, c_b2, c_b3 = st.columns(3)
        with c_b1:
            f_ini = st.number_input("Folio Inicial:", value=st.session_state.f_ini_val, step=1)
            f_fin = st.number_input("Folio Final:", value=st.session_state.f_fin_val, step=1)
        with c_b2:
            f_sin = st.number_input("Boletos Sin Cobro:", value=st.session_state.f_sin_val, step=1)
            f_can = st.number_input("Boletos Cancelados:", value=st.session_state.f_can_val, step=1)
        with c_b3:
            f_per = st.number_input("Boletos Perdidos:", value=st.session_state.f_per_val, step=1)

        st.markdown("#### 💵 Egresos y Gastos Operativos")
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            g_esp = st.number_input("Gastos Especiales ($ MXN):", value=st.session_state.g_esp_val, step=10.0)
        with c_g2:
            g_gen = st.number_input("Gastos Generales o Nómina ($ MXN):", value=st.session_state.g_gen_val, step=10.0)

        st.markdown("#### ✍️ Firmas")
        c_fir1, c_fir2 = st.columns(2)
        with c_fir1:
            elaboro = st.text_input("Elaboró:", value=st.session_state.usuario_autenticado)
        with c_fir2:
            recibe = st.text_input("Recibe:", value=st.session_state.recibe_val)

        # Previsualización del balance en el formulario
        boletos_total_prev = max(0, (int(f_fin) - int(f_ini)) + 1) if int(f_fin) >= int(f_ini) and int(f_ini) > 0 else 0
        boletos_cobrados_prev = max(0, boletos_total_prev - int(f_sin) - int(f_can))
        ingreso_bruto_prev = boletos_cobrados_prev * float(costo_boleto)
        total_gastos_prev = float(g_esp) + float(g_gen)
        ingreso_neto_prev = ingreso_bruto_prev - total_gastos_prev
        margen_prev = (ingreso_neto_prev / ingreso_bruto_prev * 100) if ingreso_bruto_prev > 0 else 0.0

        st.markdown("---")
        st.markdown("#### 📈 Balance Preliminar del Reporte")
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_c1.metric("Ingreso Bruto", f"${ingreso_bruto_prev:,.2f} MXN")
        m_c2.metric("Gastos Totales", f"${total_gastos_prev:,.2f} MXN")
        m_c3.metric("Ingreso Neto", f"${ingreso_neto_prev:,.2f} MXN")
        m_c4.metric("Rentabilidad", evaluar_rentabilidad(margen_prev), f"{margen_prev:.1f}%")

        if st.form_submit_button("💾 Guardar Reporte Diario"):
            if sucursal != "-- Selecciona o busca la sucursal --":
                total_boletos = max(0, (int(f_fin) - int(f_ini)) + 1)
                boletos_cobrados = max(0, total_boletos - int(f_sin) - int(f_can))
                bruto = boletos_cobrados * float(costo_boleto)
                total_gastos = float(g_esp) + float(g_gen)
                neto = bruto - total_gastos
                margen = (neto / bruto * 100) if bruto > 0 else 0.0
                rentabilidad = evaluar_rentabilidad(margen)

                nuevo_registro = {
                    "Fecha": fecha_op.strftime("%d/%m/%Y"),
                    "Sitio / Unidad": sucursal,
                    "Horario": f"{hora_ini.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}",
                    "Costo Boleto": float(costo_boleto),
                    "Folio Inicial": int(f_ini),
                    "Folio Final": int(f_fin),
                    "Total Boletos": total_boletos,
                    "Sin Cobro": int(f_sin),
                    "Cancelados": int(f_can),
                    "Perdidos": int(f_per),
                    "Boletos Cobrados": boletos_cobrados,
                    "Ingreso Bruto": bruto,
                    "Gastos Especiales": float(g_esp),
                    "Gastos Generales / Nómina": float(g_gen),
                    "Total Gastos": total_gastos,
                    "Ingreso Neto": neto,
                    "Margen (%)": round(margen, 2),
                    "Rentabilidad": rentabilidad,
                    "Elaboró": elaboro,
                    "Recibe": recibe,
                    "Tipo": "Operación Regular",
                    "foto_bytes": foto.getvalue() if foto else None
                }
                st.session_state.registros.append(nuevo_registro)
                guardar_registros_permanentes(st.session_state.registros)
                st.success("✅ Reporte guardado correctamente.")
                st.rerun()
            else:
                st.error("❌ Por favor, selecciona una sucursal.")
        
