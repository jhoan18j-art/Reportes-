import streamlit as st

# Configuración de página optimizada para móviles (oculta barra lateral y centra el diseño)
st.set_page_config(
    page_title="Club Park - Control Operativo",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilos CSS personalizados para dar apariencia de aplicación nativa móvil
st.markdown("""
    <style>
    .main {
        background-color: #f4f6f9;
    }
    .stButton>button {
        width: 100%;
        background-color: #0F172A;
        color: white;
        border-radius: 10px;
        height: 50px;
        font-size: 16px;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1E293B;
        color: white;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 8px;
        border: 1px solid #CBD5E1;
    }
    h1 {
        color: #0F172A;
        text-align: center;
        font-size: 1.6rem !important;
        margin-bottom: 0px;
    }
    .card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Encabezado principal
st.markdown("<h1>Club Park Valet</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748B;'>Control y Registro Operativo</p>", unsafe_allow_html=True)

# Formulario adaptado para captura rápida en campo
with st.form("form_operativo", clear_on_submit=True):
    st.subheader("📝 Nuevo Registro")
    
    sucursal = st.selectbox(
        "Sucursal / Ubicación", 
        ["Seleccionar...", "San Ángel", "Polanco", "Santa Fe", "Reforma"]
    )
    
    folio = st.text_input("Número de Folio / Ticket")
    placas = st.text_input("Placas del Vehículo")
    observaciones = st.text_area("Observaciones o Daños Previos")
    
    submitted = st.form_submit_button("Guardar y Registrar")
    
    if submitted:
        if sucursal == "Seleccionar...":
            st.error("Por favor selecciona una sucursal válida.")
        elif not folio or not placas:
            st.warning("El folio y las placas son obligatorios.")
        else:
            st.success(f"¡Registro guardado correctamente para el folio {folio}!")
            # Aquí puedes agregar la lógica para guardar en base de datos o exportar a Excel

# Sección de consulta rápida inferior
with st.expander("🔍 Consultar Estado de Folios"):
    filtro_folio = st.text_input("Buscar por Folio")
    if st.button("Buscar"):
        if filtro_folio:
            st.info(f"Buscando información del folio: {filtro_folio}...")
        else:
            st.warning("Ingresa un folio para buscar.")
