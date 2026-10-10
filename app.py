import pandas as pd
import streamlit as st
from datetime import date
from PIL import Image
import os

st.set_page_config(page_title="Club Park - Control Operativo", page_icon="🚗", layout="wide")

# Inicializar base de datos de registros en sesión si no existe
if "registros" not in st.session_state:
    st.session_state.registros = []

# Catálogo oficial de sucursales / sitios
SUCURSALES_CLUB_PARK = [
    "-- Selecciona o busca la sucursal --",
    "PAMPAS",
    "RAMMA",
    "SUSHITTO",
    "BARRANCA",
    "CARAJILLO",
    "BENINGANS",
    "ROMAS",
    "J.TLALPAN",
    "J.DIVISION",
    "J.PICACHO",
    "J.EMPRESA",
    "sipily",
    "M SATÉLITE",
    "M MARINA",
    "VETERINARIA",
    "CLÍNICA",
    "SUMO STA",
    "CHEGARAY",
    "RYOSHI",
    "ENCANTO",
    "S. AZURA",
    "E-BNI",
    "CHURRASCA"
]

# Sistema simple de Autenticación de Usuarios
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
st.sidebar.info(f"**Usuario actual:** {st.session_state.usuario_autenticado}\n\n**Rol:** {st.session_state.rol}")

# ==========================================
# VISTA EXCLUSIVA PARA EL CONTADOR AUDITOR (VÍCTOR)
# ==========================================
if st.session_state.rol == "Contador Auditor":
    st.markdown("---")
    st.markdown("## 🔍 Panel de Auditoría y Control Financiero (Contador)")
    st.info("Estimado Víctor, desde este panel tienes acceso exclusivo para auditar, gestionar, subir registros y descargar la hoja de Excel semanal.")
    
    # Opción para que el contador también pueda subir reportes si lo requiere
    with st.expander("➕ Subir o registrar reporte manualmente (Modo Auditor)"):
        with st.form("form_contador"):
            c_fecha = st.date_input("📅 Fecha", value=date.today())
            c_sitio = st.selectbox("🏢 Sitio / Sucursal", SUCURSALES_CLUB_PARK[1:])
            c_ingreso = st.number_input("💵 Ingreso Neto ($)", value=0.0, step=100.0)
            c_gastos = st.number_input("🛠️ Total Gastos y Nóminas ($)", value=0.0, step=50.0)
            c_elaboro = st.text_input("✍️ Elaboró Reporte", value="Contador Víctor")
            
            btn_add_contador = st.form_submit_button("Guardar Registro de Auditoría")
            if btn_add_contador:
                st.session_state.registros.append({
                    "Fecha": str(c_fecha),
                    "Supervisor": "Contador Víctor",
                    "Sitio / Unidad": c_sitio,
                    "Ingreso Neto": c_ingreso,
                    "Total Gastos y Nóminas": c_gastos,
                    "Elaboró": c_elaboro,
                    "Recibe": "Dirección",
                    "Evidencia Foto": "N/A (Auditor)"
                })
                st.success("¡Registro agregado por el contador con éxito!")
                st.rerun()

    if st.session_state.registros:
        st.markdown("### 📊 Listado Consolidado de Reportes Operativos")
        df_auditoria = pd.DataFrame(st.session_state.registros)
        st.dataframe(df_auditoria, use_container_width=True)
        
        total_ingresos_netos = df_auditoria["Ingreso Neto"].sum() if "Ingreso Neto" in df_auditoria.columns else 0.0
        total_gastos_gral = df_auditoria["Total Gastos y Nóminas"].sum() if "Total Gastos y Nóminas" in df_auditoria.columns else 0.0
        
        col_a1, col_a2 = st.columns(2)
        col_a1.metric("Ingreso Neto Acumulado", f"${total_ingresos_netos:,.2f}")
        col_a2.metric("Total Gastos y Nóminas Acumulado", f"${total_gastos_gral:,.2f}")
        
        st.markdown("---")
        st.markdown("### 📥 Descarga Exclusiva de Auditoría (Excel / CSV)")
        csv_export = df_auditoria.to_csv(index=False).encode('utf-8')
        
        # ÚNICO USUARIO CON PERMISO DE DESCARGA
        st.download_button(
            label="📥 Descargar Reporte Semanal Completo en Excel (CSV)",
            data=csv_export,
            file_name="Consolidado_Semanal_ClubPark_Auditoria.csv",
            mime="text/csv",
        )
        
        if st.button("🗑️ Limpiar / Borrar Todos los Registros"):
            st.session_state.registros = []
            st.success("Se han borrado todos los registros del sistema.")
            st.rerun()
    else:
        st.warning("⚠️ No hay registros cargados en el sistema todavía por parte de los supervisores.")
        
    st.stop() # Detiene la ejecución para que los supervisores no vean este panel

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
st.warning("⚠️ Todos los campos son obligatorios. Como supervisor puedes registrar operaciones, pero la descarga del reporte semanal y la gestión de auditoría están reservadas exclusivamente para el contador Víctor.")

with st.form("form_reporte_completo"):
    c1, c2, c3 = st.columns(3)
    
    with c1:
        fecha = st.date_input("📅 Fecha", value=date.today())
        sitio = st.selectbox("🏢 Sitio / Sucursal*", SUCURSALES_CLUB_PARK)
        costo_boleto = st.number_input("💵 Costo del Boleto ($)", value=40, step=1)
        folio_inicial = st.number_input("🔢 Folio Inicial Utilizado", value=0, step=1)
        folio_final = st.number_input("🔢 Folio Final Utilizado", value=0, step=1)
        folio_sin_desprender = st.number_input("🔖 Folio inicio sin desprender del block", value=0, step=1)

    with c2:
        total_boletos = st.number_input("🎟️ Total de Boletos", value=0, step=1)
        boletos_pagados = st.number_input("✅ Boletos Pagados", value=0, step=1)
        boletos_cancelados = st.number_input("❌ Boletos Cancelados", value=0, step=1)
        boletos_perdidos = st.number_input("⚠️ Boletos Pérdidos", value=0, step=1)
        total_boletos_entregados = st.number_input("📦 Total de Boletos Entregados", value=0, step=1)
        gastos_operacion = st.number_input("🛠️ Gastos de Operación ($)", value=0.0, step=10.0)

    with c3:
        lider_sueldo = st.number_input("👔 Líder de Unidad - Sueldo ($)", value=0.0, step=10.0)
        operador1_sueldo = st.number_input("👷 Operador 1 - Sueldo ($)", value=280.0, step=10.0)
        operador2_sueldo = st.number_input("👷 Operador 2 - Sueldo ($)", value=0.0, step=10.0)
        gastos_especiales = st.number_input("📌 Gastos Especiales ($)", value=0.0, step=10.0)
        gastos_generales = st.number_input("📋 Gastos Generales ($)", value=0.0, step=10.0)
        
    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        elaboro = st.text_input("✍️ Elaboró Reporte (Nombre)*", placeholder="Ej. Gaby")
    with c5:
        recibe = st.text_input("👤 Quien Recibe Reporte (Nombre)*", placeholder="Ej. Jesús")

    # Cálculos automáticos y financieros
    total_sueldos_nominas = lider_sueldo + operador1_sueldo + operador2_sueldo
    total_gastos = gastos_operacion + gastos_especiales + gastos_generales + total_sueldos_nominas
    ingreso_bruto = boletos_pagados * costo_boleto
    ingreso_neto = ingreso_bruto - total_gastos
    cantidad_entregar = ingreso_neto

    st.markdown("### 📊 Resumen Financiero Calculado")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Gastos y Nóminas", f"${total_gastos:,.2f}")
    m2.metric("Ingreso Bruto", f"${ingreso_bruto:,.2f}")
    m3.metric("Ingreso Neto", f"${ingreso_neto:,.2f}", delta=f"${ingreso_neto:,.2f}")
    m4.metric("Cantidad a Entregar", f"${cantidad_entregar:,.2f}")

    submitted = st.form_submit_button("💾 Validar y Guardar Registro en el Consolidado")

    if submitted:
        if sitio == "-- Selecciona o busca la sucursal --":
            st.error("❌ Error de validación: Debes seleccionar una sucursal o sitio válido.")
        elif not elaboro.strip() or not recibe.strip():
            st.error("❌ Error de validación: Los campos 'Elaboró Reporte' y 'Quien Recibe Reporte' son obligatorios.")
        elif foto_reporte is None:
            st.warning("⚠️ Advertencia: Es necesario adjuntar la fotografía de la hoja de reporte físico.")
        else:
            nuevo_registro = {
                "Fecha": str(fecha),
                "Supervisor": st.session_state.usuario_autenticado,
                "Sitio / Unidad": sitio,
                "Costo Boleto": costo_boleto,
                "Folio Inicial": folio_inicial,
                "Folio Final": folio_final,
                "Folio sin desprender": folio_sin_desprender,
                "Total Boletos": total_boletos,
                "Boletos Pagados": boletos_pagados,
                "Cancelados": boletos_cancelados,
                "Pérdidos": boletos_perdidos,
                "Total Entregados": total_boletos_entregados,
                "Gastos Operación": gastos_operacion,
                "Líder Sueldo": lider_sueldo,
                "Operador 1 Sueldo": operador1_sueldo,
                "Operador 2 Sueldo": operador2_sueldo,
                "Gastos Especiales": gastos_especiales,
                "Total Gastos y Nóminas": total_gastos,
                "Gastos Generales": gastos_generales,
                "Ingreso Bruto": ingreso_bruto,
                "Ingreso Neto": ingreso_neto,
                "Cantidad a Entregar": cantidad_entregar,
                "Elaboró": elaboro,
                "Recibe": recibe,
                "Evidencia Foto": "Sí"
            }
            st.session_state.registros.append(nuevo_registro)
            st.success(f"¡El reporte del sitio '{sitio}' ha sido validado y guardado exitosamente por {st.session_state.usuario_autenticado}!")

# Vista resumida para supervisores (sin botón de descarga de Excel)
if st.session_state.registros:
    st.markdown("---")
    st.markdown("### 📈 Mis Registros Enviados en la Semana")
    df_reportes = pd.DataFrame(st.session_state.registros)
    # Mostrar solo columnas esenciales para supervisores
    cols_super = [c for c in ["Fecha", "Sitio / Unidad", "Ingreso Neto", "Total Gastos y Nóminas", "Elaboró", "Recibe"] if c in df_reportes.columns]
    st.dataframe(df_reportes[cols_super], use_container_width=True)
    st.info("ℹ️ Nota: La descarga del archivo consolidado de Excel y la auditoría general de la semana se encuentran restringidas exclusivamente al usuario Contador (Víctor).")
    
