import pandas as pd
import streamlit as st
from datetime import datetime, date
from PIL import Image
import os

st.set_page_config(page_title="Club Park - Control Operativo MXN", page_icon="🚗", layout="wide")

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
    st.markdown("## 🔍 Panel de Auditoría, Gastos vs. Ingresos y Rentabilidad (Contador)")
    st.info("Estimado Víctor, desde este panel tienes acceso exclusivo para auditar la rentabilidad por sucursal y descargar el reporte completo en Excel (MXN).")
    
    if st.session_state.registros:
        df_auditoria = pd.DataFrame(st.session_state.registros)
        st.dataframe(df_auditoria, use_container_width=True)
        
        total_ingresos_brutos = df_auditoria["Ingreso Bruto (MXN)"].sum() if "Ingreso Bruto (MXN)" in df_auditoria.columns else 0.0
        total_gastos_gral = df_auditoria["Total Gastos y Nóminas (MXN)"].sum() if "Total Gastos y Nóminas (MXN)" in df_auditoria.columns else 0.0
        total_ingresos_netos = df_auditoria["Ingreso Neto / Utilidad (MXN)"].sum() if "Ingreso Neto / Utilidad (MXN)" in df_auditoria.columns else 0.0
        rentabilidad_global = (total_ingresos_netos / total_ingresos_brutos * 100) if total_ingresos_brutos > 0 else 0.0
        
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("Ingreso Bruto Total", f"${total_ingresos_brutos:,.2f} MXN")
        col_a2.metric("Gastos y Nóminas Totales", f"${total_gastos_gral:,.2f} MXN")
        col_a3.metric("Utilidad / Ingreso Neto", f"${total_ingresos_netos:,.2f} MXN")
        col_a4.metric("Rentabilidad Global (%)", f"{rentabilidad_global:.2f}%")
        
        st.markdown("---")
        st.markdown("### 📥 Descarga Exclusiva de Auditoría con Análisis Financiero (Excel / CSV)")
        csv_export = df_auditoria.to_csv(index=False).encode('utf-8')
        
        fecha_actual_str = datetime.now().strftime("%d_%m_%Y")
        st.download_button(
            label="📥 Descargar Reporte Semanal Completo en Excel (CSV)",
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
# VISTA PARA SUPERVISORES (Víctor Manuel y José de Jesús)
# ==========================================
st.markdown("---")
st.markdown("### 📸 1. Evidencia Fotográfica del Reporte Físico")
foto_reporte = st.file_uploader("Tomar o subir foto de la hoja de reporte", type=["jpg", "jpeg", "png"], key="foto")

if foto_reporte is not None:
    imagen = Image.open(foto_reporte)
    st.image(imagen, caption="Vista previa de la hoja de reporte física", width=350)

st.markdown("---")
st.markdown("### 📝 2. Captura Obligatoria de Datos del Reporte")
st.warning("⚠️ Todos los campos son obligatorios. Las cantidades deben ingresarse en Moneda Nacional Mexicana (MXN).")

sitio = st.selectbox("🏢 Sitio / Sucursal*", SUCURSALES_LISTA, key="select_sitio", on_change=actualizar_costo_sucursal)

with st.form("form_reporte_completo"):
    c1, c2, c3 = st.columns(3)
    
    with c1:
        fecha_reporte = st.date_input("📅 Fecha del Reporte", value=date.today())
        fecha_formateada = fecha_reporte.strftime("%d/%m/%Y")
        
        costo_boleto = st.number_input("💵 Costo del Boleto ($ MXN)", value=int(st.session_state.costo_boleto_val), step=1)
        
        folio_inicial = st.number_input("🔢 Folio Inicial Utilizado", value=0, step=1)
        folio_final = st.number_input("🔢 Folio Final Utilizado", value=0, step=1)
        folio_sin_desprender = st.number_input("🔖 Folio inicio sin desprender del block", value=0, step=1)

    with c2:
        cancelados = st.number_input("❌ Boletos Cancelados", value=0, step=1)
        perdidos = st.number_input("⚠️ Boletos Pérdidos", value=0, step=1)
        
        # --- CÁLCULO AUTOMÁTICO DE BOLETOS EXPEDIDOS (ENTREGADOS) ---
        total_boletos_entregados = (folio_final - folio_inicial + 1) if folio_final >= folio_inicial else 0
        st.info(f"📦 Boletos Entregados (Expedidos): **{total_boletos_entregados}**")

        gastos_operacion = st.number_input("🛠️ Gastos de Operación ($ MXN)", value=0.0, step=10.0)

    with c3:
        lider_sueldo = st.number_input("👔 Líder de Unidad - Sueldo ($ MXN)", value=0.0, step=10.0)
        operador1_sueldo = st.number_input("👷 Operador 1 - Sueldo ($ MXN)", value=280.0, step=10.0)
        operador2_sueldo = st.number_input("👷 Operador 2 - Sueldo ($ MXN)", value=0.0, step=10.0)
        gastos_especiales = st.number_input("📌 Gastos Especiales ($ MXN)", value=0.0, step=10.0)
        gastos_generales = st.number_input("📋 Gastos Generales ($ MXN)", value=0.0, step=10.0)
        
    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        elaboro = st.text_input("✍️ Elaboró Reporte (Nombre)*", placeholder="Ej. Gaby")
    with c5:
        recibe = st.text_input("👤 Quien Recibe Reporte (Nombre)*", placeholder="Ej. Jesús")

    # --- CÁLCULOS FINANCIEROS Y MULTIPLICACIÓN POR COSTO DE BOLETO (MXN) ---
    boletos_pagados = max(0, total_boletos_entregados - cancelados - perdidos)
    
    total_sueldos_nominas = lider_sueldo + operador1_sueldo + operador2_sueldo
    total_gastos = gastos_operacion + gastos_especiales + gastos_generales + total_sueldos_nominas
    
    # Multiplicación exacta de boletos expedidos/vendidos por el costo del boleto
    ingreso_bruto = boletos_pagados * costo_boleto
    ingreso_neto = ingreso_bruto - total_gastos
    cantidad_entregar = ingreso_neto
    
    rentabilidad_porcentaje = (ingreso_neto / ingreso_bruto * 100) if ingreso_bruto > 0 else 0.0

    st.markdown("### 📊 Resumen Financiero y Conteo de Boletos (MXN)")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Boletos Entregados", total_boletos_entregados)
    r2.metric("Boletos Pagados (Vendidos)", boletos_pagados)
    r3.metric("Ingreso Bruto", f"${ingreso_bruto:,.2f} MXN")
    r4.metric("Ingreso Neto (Utilidad)", f"${ingreso_neto:,.2f} MXN", delta=f"${ingreso_neto:,.2f} MXN")

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
                "Boletos Pagados": boletos_pagados,
                "Cancelados": cancelados,
                "Pérdidos": perdidos,
                "Gastos Operación (MXN)": gastos_operacion,
                "Líder Sueldo (MXN)": lider_sueldo,
                "Operador 1 Sueldo (MXN)": operador1_sueldo,
                "Operador 2 Sueldo (MXN)": operador2_sueldo,
                "Gastos Especiales (MXN)": gastos_especiales,
                "Total Gastos y Nóminas (MXN)": total_gastos,
                "Gastos Generales (MXN)": gastos_generales,
                "Ingreso Bruto (MXN)": ingreso_bruto,
                "Ingreso Neto / Utilidad (MXN)": ingreso_neto,
                "Rentabilidad (%)": round(rentabilidad_porcentaje, 2),
                "Cantidad a Entregar (MXN)": cantidad_entregar,
                "Elaboró": elaboro,
                "Recibe": recibe,
                "Evidencia Foto": "Sí"
            }
            st.session_state.registros.append(nuevo_registro)
            st.success(f"¡El reporte del sitio '{sitio}' ha sido validado y guardado exitosamente por {st.session_state.usuario_autenticado}!")

if st.session_state.registros:
    st.markdown("---")
    st.markdown("### 📈 Mis Registros Enviados en la Semana")
    df_reportes = pd.DataFrame(st.session_state.registros)
    cols_super = [c for c in ["Fecha", "Sitio / Unidad", "Total Boletos Entregados", "Boletos Pagados", "Ingreso Bruto (MXN)", "Total Gastos y Nóminas (MXN)", "Ingreso Neto / Utilidad (MXN)", "Rentabilidad (%)", "Elaboró", "Recibe"] if c in df_reportes.columns]
    st.dataframe(df_reportes[cols_super], use_container_width=True)
    st.info("ℹ️ Nota: La descarga del archivo consolidado de Excel con el análisis financiero completo está reservada exclusivamente para el contador Víctor.")
    
