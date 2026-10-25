import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="J.A.R.V.I.S. - Club Park",
    page_icon="🤖",
    layout="centered"
)

# Estilo visual futurista tipo HUD (Iron Man)
st.markdown("""
    <style>
    .stApp {
        background-color: #050b14;
        color: #38bdf8;
    }
    .stTextInput>div>div>input {
        background-color: #0f172a;
        color: #38bdf8;
        border: 1px solid #0284c7;
        border-radius: 8px;
    }
    h1 {
        color: #38bdf8;
        text-align: center;
        font-family: monospace;
        letter-spacing: 2px;
        text-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
    .stChatMessage {
        background-color: #0f172a !important;
        border: 1px solid #1e293b;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>J.A.R.V.I.S. // CLUB PARK</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Inteligencia Operativa en Campo</p>", unsafe_allow_html=True)
st.markdown("---")

# Inicializar historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Sistemas en línea y sincronizados. ¿Qué operación o sucursal revisamos hoy, señor?"}
    ]

# Función para que el navegador hable en voz alta la respuesta del asistente
def hablar_texto(texto):
    js_code = f"""
    <script>
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel(); // Detener voz anterior si la hay
            const utterance = new SpeechSynthesisUtterance("{texto}");
            utterance.lang = 'es-MX';
            utterance.rate = 1.05;
            utterance.pitch = 0.95;
            window.speechSynthesis.speak(utterance);
        }}
    </script>
    """
    components.html(js_code, height=0)

# Mostrar el historial del chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada de comandos por texto (o voz mediante el teclado del celular)
if prompt := st.chat_input("Escribe tu orden operativa..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Lógica de respuestas del asistente adaptada al negocio con Héctor
    prompt_lower = prompt.lower()
    
    if "folio" in prompt_lower or "buscar" in prompt_lower:
        respuesta = "Localizando registro de vehículo en los servidores de la sucursal, señor."
    elif "reporte" in prompt_lower or "corte" in prompt_lower:
        respuesta = "Compilando datos operativos para el informe de Héctor y contabilidad."
    elif "hola" in prompt_lower:
        respuesta = "Saludos. Todos los sistemas operativos operando al cien por ciento."
    else:
        respuesta = f"Comando procesado correctamente: {prompt}."

    with st.chat_message("assistant"):
        st.markdown(respuesta)
        # Activa la voz en el celular o computadora automáticamente
        hablar_texto(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
