import streamlit as st
import streamlit.components.v1 as components
from duckduckgo_search import DDGS  # Usamos un buscador web rápido y gratuito en Python

st.set_page_config(
    page_title="J.A.R.V.I.S. Web - Club Park",
    page_icon="🌐",
    layout="centered"
)

# Estilo visual futurista tipo HUD (Iron Man)
st.markdown("""
    <style>
    .stApp {
        background-color: #050b14;
        color: #38bdf8;
    }
    h1 {
        color: #38bdf8;
        text-align: center;
        font-family: monospace;
        letter-spacing: 2px;
        text-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
    .resultado-box {
        background-color: #0f172a;
        border: 1px solid #0284c7;
        border-radius: 10px;
        padding: 15px;
        margin-top: 15px;
        color: #f8fafc;
        font-family: monospace;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>J.A.R.V.I.S. // BÚSQUEDA WEB</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b;'>Asistente con Acceso a Internet - Club Park</p>", unsafe_allow_html=True)
st.markdown("---")

# Función para realizar búsquedas en la web
def buscar_en_web(query):
    try:
        with DDGS() as ddgs:
            resultados = [r for r in ddgs.text(query, max_results=2)]
            if resultados:
                return resultados[0]['body']
            else:
                return "No encontré resultados precisos en la red, señor."
    except Exception as e:
        return "Error al conectar con los servidores de búsqueda web."

# Interfaz de chat en Streamlit
if "messages_web" not in st.session_state:
    st.session_state.messages_web = [
        {"role": "assistant", "content": "Sistemas de red en línea. ¿Qué información o datos buscamos en la red hoy, señor?"}
    ]

for message in st.session_state.messages_web:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada de texto para la orden o búsqueda
if prompt := st.chat_input("Escribe lo que quieres buscar en la web..."):
    st.session_state.messages_web.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Si el usuario pide buscar algo, ejecutamos la búsqueda web
    with st.spinner("Buscando en la red..."):
        informacion = buscar_en_web(prompt)
        respuesta = f"🔍 **Resultado de la red:** {informacion}"

    with st.chat_message("assistant"):
        st.markdown(respuesta)
        
        # Script opcional para que también te lea el resultado en voz alta
        voz_js = f"""
        <script>
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance("He encontrado lo siguiente: {informacion[:150]}");
                utterance.lang = 'es-MX';
                window.speechSynthesis.speak(utterance);
            }}
        </script>
        """
        components.html(voz_js, height=0)

    st.session_state.messages_web.append({"role": "assistant", "content": respuesta})
