import pandas as pd
import streamlit as st
from datetime import datetime, date
from PIL import Image
import os
import google.generativeai as genai
import json

st.set_page_config(page_title="Club Park - Control Operativo MXN", page_icon="🚗", layout="wide")

# Estilo CSS avanzado para ocultar los botones de más (+) y menos (-) en TODOS los inputs numéricos y estilizar la app
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

# Inicializar base de datos de registros en sesión si no existe
if "registros" not in st.session_state:
    st.session_state.registros = []

# Diccionario oficial con los costos predeterminados en Pesos Mexicanos ($ M.N.) por sucursal
PRECIOS_SUCURSALES = {
    "PAMPAS": 50,
    "RAMMA": 70,
    "SUSHITTO": 40,
    "BARRANCA": 0,      # Tiempo libre / Variable
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
    "VETERINARIA": 0,   # No cobra
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

# Inicializar costo en session_state si no existe
if "costo_boleto_val" not in st.session_state:
    st.session_state.costo_boleto_val = 40

# Inicializar estados para auto-relleno por IA si se sube foto nueva
if "ai_filled" not in st.session_state:
    st.session_state.ai_filled = False
if "ai_data" not in st.session_state:
    st.session_state.ai_data = {}

def actualizar_costo_sucursal():
    sucursal_seleccionada = st.session_state.get("select_sitio")
    if sucursal_seleccionada in PRECIOS_SUCURSALES:
        st.session_state.costo_boleto_val = PRECIOS_SUCURSALES[sucursal_seleccionada]

# Sistema de Autenticación de Usuarios
if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

# Pantalla de Login si no ha iniciado sesión
if st.session_state.usuario_autenticado is None:
    st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK VALET Y ESTACIONAMIENTOS</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Control de Acceso al Sistema</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=300)
        
        st.markdown("### Iniciar Sesión")
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

# --- A PARTIR DE AQUÍ EL USUARIO YA ESTÁ LOGUEADO ---

# Cabecera institucional con el Logotipo integrado
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=220)
    else:
        st.markdown("### **CP** - Club Park")

with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.subheader(f"Bienvenido, {st.session_state.usuario_autenticado} ({st.session_state.rol})")

# Botón para cerrar sesión
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(f"**Usuario actual:** {st.session_state.usuario_autenticado}\n\n**Rol:** {st.session_state.rol}\n\n**Moneda:** Pesos Mexicanos (MXN)")

# ==========================================
# VISTA EXCLUSIVA PARA EL CONTADOR AUDITOR (VÍCTOR)
# ==========================================
if st.session_state.rol == "Contador Auditor":
    st.markdown("---")
    st.markdown("## 🔍 Panel de Auditoría, Balance por Unidad y Reportes Semanales (Contador)")
    st.info("Estimado Víctor, desde este panel puedes auditar el rendimiento por sucursal, ver el control de reportes por usuario, análisis de rentabilidad y descargar el consolidado completo en Excel/CSV.")
    
    if st.session_state.registros:
        df_auditoria = pd.DataFrame(st.session_state.registros)
        
        # 1. Control de reportes subidos por usuario
        st.markdown("### 👥 Control de Reportes Subidos por Usuario")
        conteo_usuarios = df_auditoria["Supervisor"].value_counts().reset_index()
        conteo_usuarios.columns = ["Usuario / Supervisor", "Reportes Subidos"]
        col_u1, col_u2 = st.columns([2, 1])
        with col_u1:
            st.dataframe(conteo_usuarios, use_container_width=True)
        with col_u2:
            st.metric("Total Reportes en Semana", len(df_auditoria))
            
        st.markdown("---")
        
        # 2. Tabla Global de Reportes
        st.markdown("### 📋 Tabla Global de Todos los Reportes de la Semana")
        st.dataframe(df_auditoria, use_container_width=True)
        
        total_ingresos_brutos = df_auditoria["Ingreso Bruto (MXN)"].sum() if "Ingreso Bruto (MXN)" in df_auditoria.columns else 0.0
        total_gastos_gral = df_auditoria["Total Gastos y Nóminas (MXN)"].sum() if "Total Gastos y Nóminas (MXN)" in df_auditoria.columns else 0.0
        total_ingresos_netos = df_auditoria["Ingreso Neto / Utilidad (MXN)"].sum() if "Ingreso Neto / Utilidad (MXN)" in df_auditoria.columns else 0.0
        rentabilidad_global = (total_ingresos_netos / total_ingresos_brutos * 100) if total_ingresos_brutos > 0 else 0.0
        
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("Ingreso Bruto Global", f"${total_ingresos_brutos:,.2f} MXN")
        col_a2.metric("Gasto Global", f"${total_gastos_gral:,.2f} MXN")
        col_a3.metric("Utilidad Global", f"${total_ingresos_netos:,.2f} MXN")
        col_a4.metric("Rentabilidad Global (%)", f"{rentabilidad_global:.2f}%")
        
        st.markdown("---")
        
        # 3. Balance por Unidad (Más rentable, menos rentable, más gastos, más ingresos)
        st.markdown("### 📊 Balance Analítico por Unidad o Servicio")
        if "Sitio / Unidad" in df_auditoria.columns:
            df_unidad = df_auditoria.groupby("Sitio / Unidad").agg({
                "Ingreso Bruto (MXN)": "sum",
                "Total Gastos y Nóminas (MXN)": "sum",
                "Ingreso Neto / Utilidad (MXN)": "sum",
                "Rentabilidad (%)": "mean"
            }).reset_index()
            
            st.dataframe(df_unidad, use_container_width=True)
            
            if not df_unidad.empty:
                mas_rentable = df_unidad.loc[df_unidad["Ingreso Neto / Utilidad (MXN)"].idxmax()]
                menos_rentable = df_unidad.loc[df_unidad["Ingreso Neto / Utilidad (MXN)"].idxmin()]
                mas_gastos = df_unidad.loc[df_unidad["Total Gastos y Nóminas (MXN)"].idxmax()]
                mas_ingresos = df_unidad.loc[df_unidad["Ingreso Bruto (MXN)"].idxmax()]
                
                b1, b2, b3, b4 = st.columns(4)
                b1.success(f"🏆 **Más Rentable:**\n\n{mas_rentable['Sitio / Unidad']}\n(${mas_rentable['Ingreso Neto / Utilidad (MXN)']:,.2f} Utilidad)")
                b2.warning(f"⚠️ **Menos Rentable:**\n\n{menos_rentable['Sitio / Unidad']}\n(${menos_rentable['Ingreso Neto / Utilidad (MXN)']:,.2f} Utilidad)")
                b3.error(f"💸 **Mayor Gasto:**\n\n{mas_gastos['Sitio / Unidad']}\n(${mas_gastos['Total Gastos y Nóminas (MXN)']:,.2f} Gasto)")
                b4.info(f"💵 **Más Ingresos:**\n\n{mas_ingresos['Sitio / Unidad']}\n(${mas_ingresos['Ingreso Bruto (MXN)']:,.2f} Ingresos)")

        st.markdown("---")
        st.markdown("### 📥 Descarga de Auditoría con Reportes por Usuario y Balance (Excel / CSV)")
        csv_export = df_auditoria.to_csv(index=False).encode('utf-8')
        
        fecha_actual_str = datetime.now().strftime("%d_%m_%Y")
        st.download_button(
            label="📥 Descargar Reporte Semanal Completo en CSV",
            data=csv_export,
            file_name=f"Control_Rentabilidad_ClubPark_{fecha_actual_str}.csv",
            mime="text/csv",
        )
        
        if st.button("🗑️ Limpiar / Borrar Todos los Registros"):
            st.session_state.registros = []
            st.success("Se han borrado todos los registros del sistema.")
            st.rerun()
    else:
        st.warning("⚠️ No hay registros cargados en el sistema todavía por parte de los supervisores.")
        
    st.stop()

# ==========================================
# VISTA PARA SUPERVISORES (Con IA para auto-relleno y sin botones +/-)
# ==========================================
st.markdown("---")
st.markdown("### 📸 1. Evidencia Fotográfica y Auto-relleno por Inteligencia Artificial")
st.info("💡 Sube la fotografía del reporte físico de la sucursal. La Inteligencia Artificial analizará la imagen y llenará automáticamente los campos del formulario por ti.")

foto_reporte = st.file_uploader("Tomar o subir foto de la hoja de reporte", type=["jpg", "jpeg", "png"], key="foto")

# Función de IA para procesar la imagen con Google Gemini
def analizar_foto_con_ia(imagen_file):
    try:
        # Configurar la API key de Gemini (asegúrate de tenerla en st.secrets o variables de entorno)
        api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
        if not api_key:
            return None
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        img = Image.open(imagen_file)
        
        prompt = """
        Analiza esta imagen de un reporte de valet parking / estacionamiento. Extrae los siguientes datos en formato JSON estricto sin texto adicional:
        {
            "folio_inicial": 0,
            "folio_final": 0,
            "folio_sin_desprender": 0,
            "cancelados": 0,
            "perdidos": 0,
            "gastos_operacion": 0.0,
            "lider_sueldo": 0.0,
            "operador1_sueldo": 0.0,
            "operador2_sueldo": 0.0,
            "gastos_especiales": 0.0,
            "gastos_generales": 0.0,
            "elaboro": "",
            "recibe": ""
        }
        Si algun dato no aparece o no es legible, pon 0 para números o "" para textos.
        """
        response = model.generate_content([prompt, img])
        texto_resp = response.text.strip()
        # Limpiar bloques de código markdown si los hay
        if texto_resp.startswith("```json"):
            texto_resp = texto_resp[7:]
        if texto_resp.endswith("```"):
            texto_resp = texto_resp[:-3]
            
        data_json = json.loads(texto_resp.strip())
        return data_json
    except Exception as e:
        return None

if foto_reporte is not None:
    imagen = Image.open(foto_reporte)
    st.image(imagen, caption="Vista previa de la hoja de reporte física", width=350)
    
    if st.button("✨ Auto-llenar formulario usando Inteligencia Artificial con esta foto"):
        with st.spinner("🤖 Analizando imagen y extrayendo folios, gastos y nombres..."):
            extracted = analizar_foto_con_ia(foto_reporte)
            if extracted:
                st.session_state.ai_data = extracted
                st.session_state.ai_filled = True
                st.success("¡Datos extraídos exitosamente por la Inteligencia Artificial! Revisa el formulario abajo.")
            else:
                st.warning("⚠️ No se pudo conectar con la API de IA o leer la imagen automáticamente. Puedes llenar los datos de forma manual.")

st.markdown("---")
st.markdown("### 📝 2. Captura y Validación de Datos (Sin botones +/-)")
st.warning("⚠️ Todos los campos son obligatorios. Las cantidades se calculan al instante en Moneda Nacional Mexicana (MXN).")

# Valores por defecto o extraídos por IA
ai = st.session_state.ai_data if st.session_state.ai_filled else {}

# Selección de sucursal fuera del form para actualizar costo al instante
sitio = st.selectbox("🏢 Sitio / Sucursal*", SUCURSALES_LISTA, key="select_sitio", on_change=actualizar_costo_sucursal)

# Sección interactiva fuera del formulario para mostrar cálculos en vivo
c_live1, c_live2, c_live3 = st.columns(3)
with c_live1:
    fecha_reporte = st.date_input("📅 Fecha del Reporte", value=date.today())
    fecha_formateada = fecha_reporte.strftime("%d/%m/%Y")
    costo_boleto = st.number_input("💵 Costo del Boleto ($ MXN)", value=int(st.session_state.costo_boleto_val), step=1)
with c_live2:
    folio_inicial = st.number_input("🔢 Folio Inicial Utilizado", value=int(ai.get("folio_inicial", 0)), step=1, key="f_ini")
    folio_final = st.number_input("🔢 Folio Final Utilizado", value=int(ai.get("folio_final", 0)), step=1, key="f_fin")
with c_live3:
    cancelados = st.number_input("❌ Boletos Cancelados", value=int(ai.get("cancelados", 0)), step=1, key="f_can")
    perdidos = st.number_input("⚠️ Boletos Pérdidos", value=int(ai.get("perdidos", 0)), step=1, key="f_per")

# --- CÁLCULO EN TIEMPO REAL (Basado en terminaciones / últimos dos dígitos) ---
i_last = int(folio_inicial) % 100
f_last = int(folio_final) % 100
if f_last >= i_last:
    total_boletos_entregados = (f_last - i_last) + 1
else:
    total_boletos_entregados = (100 - i_last) + f_last + 1

boletos_pagados = max(0, total_boletos_entregados - cancelados - perdidos)
ingreso_bruto_live = boletos_pagados * costo_boleto

# Mostrar métricas en vivo inmediatamente en pantalla
st.info(f"📊 **Cálculo en vivo:** Total Entregados (Folios): **{total_boletos_entregados}** | 🎟️ **Boletos a Entregar (Pagados): {boletos_pagados}** | 💵 **Ingreso Bruto: ${ingreso_bruto_live:,.2f} MXN**")

st.markdown("---")

with st.form("form_reporte_completo"):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        folio_sin_desprender = st.number_input("🔖 Folio inicio sin desprender del block", value=int(ai.get("folio_sin_desprender", 0)), step=1)
        gastos_operacion = st.number_input("🛠️ Gastos de Operación ($ MXN)", value=float(ai.get("gastos_operacion", 0.0)), step=10.0)
        lider_sueldo = st.number_input("👔 Líder de Unidad - Sueldo ($ MXN)", value=float(ai.get("lider_sueldo", 0.0)), step=10.0)
        operador1_sueldo = st.number_input("👷 Operador 1 - Sueldo ($ MXN)", value=float(ai.get("operador1_sueldo", 280.0)), step=10.0)
    with col_f2:
        operador2_sueldo = st.number_input("👷 Operador 2 - Sueldo ($ MXN)", value=float(ai.get("operador2_sueldo", 0.0)), step=10.0)
        gastos_especiales = st.number_input("📌 Gastos Especiales ($ MXN)", value=float(ai.get("gastos_especiales", 0.0)), step=10.0)
        gastos_generales = st.number_input("📋 Gastos Generales ($ MXN)", value=float(ai.get("gastos_generales", 0.0)), step=10.0)

    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        elaboro = st.text_input("✍️ Elaboró Reporte (Nombre)*", value=str(ai.get("elaboro", "")), placeholder="Ej. Gaby")
    with c5:
        recibe = st.text_input("👤 Quien Recibe Reporte (Nombre)*", value=str(ai.get("recibe", "")), placeholder="Ej. Jesús")

    # Cálculos financieros finales dentro del form
    total_sueldos_nominas = lider_sueldo + operador1_sueldo + operador2_sueldo
    total_gastos = gastos_operacion + gastos_especiales + gastos_generales + total_sueldos_nominas
    ingreso_neto = ingreso_bruto_live - total_gastos
    cantidad_entregar = ingreso_neto
    rentabilidad_porcentaje = (ingreso_neto / ingreso_bruto_live * 100) if ingreso_bruto_live > 0 else 0.0

    st.markdown("### 📊 Resumen Financiero Consolidado (MXN)")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Boletos a Entregar", boletos_pagados)
    r2.metric("Total Gastos y Nóminas", f"${total_gastos:,.2f} MXN")
    r3.metric("Ingreso Neto (Utilidad)", f"${ingreso_neto:,.2f} MXN", delta=f"${ingreso_neto:,.2f} MXN")
    r4.metric("Rentabilidad (%)", f"{rentabilidad_porcentaje:.2f}%")

    submitted = st.form_submit_button("💾 Validar y Guardar Registro en el Consolidado")

    if submitted:
        if sitio == "-- Selecciona o busca la sucursal --":
            st.error("❌ Error de validación: Debes seleccionar una sucursal o sitio válido.")
        elif folio_final < folio_inicial:
            st.error("❌ Error de validación: El Folio Final no puede ser menor que el Folio Inicial.")
        elif not elaboro.strip() or not recibe.strip():
            st.error("❌ Error de validación: Los campos 'Elaboró Reporte' y 'Quien Recibe Reporte' son obligatorios.")
        elif foto_reporte is None:
            st.warning("⚠️ Advertencia: Es necesario adjuntar la fotografía de la hoja de reporte físico.")
        else:
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
                "Gastos Operación (MXN)": gastos_operacion,
                "Líder Sueldo (MXN)": lider_sueldo,
                "Operador 1 Sueldo (MXN)": operador1_sueldo,
                "Operador 2 Sueldo (MXN)": operador2_sueldo,
                "Gastos Especiales (MXN)": gastos_especiales,
                "Total Gastos y Nóminas (MXN)": total_gastos,
                "Gastos Generales (MXN)": gastos_generales,
                "Ingreso Bruto (MXN)": ingreso_bruto_live,
                "Ingreso Neto / Utilidad (MXN)": ingreso_neto,
                "Rentabilidad (%)": round(rentabilidad_porcentaje, 2),
                "Cantidad a Entregar (MXN)": cantidad_entregar,
                "Elaboró": elaboro,
                "Recibe": recibe,
                "Evidencia Foto": "Sí"
            }
            st.session_state.registros.append(nuevo_registro)
            # Resetear AI state
            st.session_state.ai_filled = False
            st.session_state.ai_data = {}
            st.success(f"¡El reporte del sitio '{sitio}' ha sido validado y guardado exitosamente por {st.session_state.usuario_autenticado}!")

if st.session_state.registros:
    st.markdown("---")
    st.markdown("### 📈 Mis Registros Enviados en la Semana")
    df_reportes = pd.DataFrame(st.session_state.registros)
    cols_super = [c for c in ["Fecha", "Sitio / Unidad", "Boletos Pagados (A Entregar)", "Ingreso Bruto (MXN)", "Total Gastos y Nóminas (MXN)", "Ingreso Neto / Utilidad (MXN)", "Rentabilidad (%)", "Elaboró", "Recibe"] if c in df_reportes.columns]
   
