import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="J.A.R.V.I.S. Voz - Club Park",
    page_icon="🎙️",
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
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>J.A.R.V.I.S. // ASISTENTE DE VOZ</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b;'>Control Operativo por Voz - Club Park</p>", unsafe_allow_html=True)
st.markdown("---")

# Interfaz HTML y JavaScript con reconocimiento y síntesis de voz nativa del celular
voice_assistant_html = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            background-color: #050b14;
            color: #38bdf8;
            font-family: monospace;
            text-align: center;
            padding: 10px;
        }
        .mic-btn {
            background: linear-gradient(135deg, #0284c7, #0369a1);
            color: white;
            border: 2px solid #38bdf8;
            border-radius: 50%;
            width: 110px;
            height: 110px;
            font-size: 36px;
            cursor: pointer;
            box-shadow: 0 0 25px rgba(56, 189, 248, 0.5);
            transition: all 0.3s ease;
            margin: 15px auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .mic-btn.listening {
            background: linear-gradient(135deg, #dc2626, #991b1b);
            border-color: #fca5a5;
            box-shadow: 0 0 35px rgba(220, 38, 38, 0.9);
            transform: scale(1.08);
        }
        .status {
            font-size: 15px;
            margin-top: 10px;
            color: #94a3b8;
            min-height: 40px;
        }
        .log-box {
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 10px;
            padding: 12px;
            margin-top: 15px;
            min-height: 120px;
            max-height: 220px;
            overflow-y: auto;
            text-align: left;
        }
        .log-item {
            margin: 8px 0;
            font-size: 14px;
        }
        .user-text { color: #f8fafc; }
        .jarvis-text { color: #38bdf8; }
    </style>
</head>
<body>

    <div>
        <button id="micBtn" class="mic-btn" onclick="toggleListening()">🎙️</button>
        <div id="statusText" class="status">Toca el botón para hablar con J.A.R.V.I.S.</div>
    </div>

    <div class="log-box" id="logBox">
        <div class="log-item jarvis-text"><strong>J.A.R.V.I.S.:</strong> Sistemas de voz activos. ¿Qué operamos hoy, señor?</div>
    </div>

    <script>
        const micBtn = document.getElementById('micBtn');
        const statusText = document.getElementById('statusText');
        const logBox = document.getElementById('logBox');

        let recognition;
        let isListening = false;

        // Configuración del motor de reconocimiento de voz del celular
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'es-MX';
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onstart = function() {
                isListening = true;
                micBtn.classList.add('listening');
                statusText.innerText = "Escuchando orden operativa...";
            };

            recognition.onresult = function(event) {
                const speechResult = event.results[0][0].transcript;
                appendLog("Tú", speechResult, "user-text");
                procesarComando(speechResult);
            };

            recognition.onerror = function(event) {
                statusText.innerText = "Aviso de audio: " + event.error;
                stopListening();
            };

            recognition.onend = function() {
                stopListening();
            };
        } else {
            statusText.innerText = "Tu navegador no soporta voz directa. Usa Google Chrome en Android.";
            micBtn.style.display = 'none';
        }

        function toggleListening() {
            if (!recognition) return;
            if (isListening) {
                recognition.stop();
            } else {
                try {
                    window.speechSynthesis.cancel(); // Detener voz anterior si habla
                    recognition.start();
                } catch(e) {
                    console.error(e);
                }
            }
        }

        function stopListening() {
            isListening = false;
            micBtn.classList.remove('listening');
            statusText.innerText = "Toca el botón para dar otra orden.";
        }

        function hablar(texto) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(texto);
                utterance.lang = 'es-MX';
                utterance.rate = 1.05;
                utterance.pitch = 0.95;
                window.speechSynthesis.speak(utterance);
            }
        }

        function procesarComando(texto) {
            let lower = texto.toLowerCase();
            let respuesta = "";

            if (lower.includes("folio") || lower.includes("buscar")) {
                respuesta = "Localizando el registro de vehículo en los servidores de la sucursal, señor.";
            } else if (lower.includes("reporte") || lower.includes("corte")) {
                respuesta = "Compilando datos operativos para el informe de Héctor y contabilidad.";
            } else if (lower.includes("hola") || lower.includes("jarvis")) {
                respuesta = "Saludos, señor. Todos los sistemas de Club Park operando al cien por ciento.";
            } else {
                respuesta = "Comando de voz registrado correctamente: " + texto;
            }

            appendLog("J.A.R.V.I.S.", respuesta, "jarvis-text");
            hablar(respuesta);
        }

        function appendLog(sender, text, className) {
            const div = document.createElement('div');
            div.className = `log-item ${className}`;
            div.innerHTML = `<strong>${sender}:</strong> ${text}`;
            logBox.appendChild(div);
            logBox.scrollTop = logBox.scrollHeight;
        }

        // Saludo inicial por voz al cargar la página
        window.onload = function() {
            setTimeout(() => {
                hablar("Sistemas de voz en línea y sincronizados. ¿Qué operación revisamos hoy, señor?");
            }, 1000);
        };
    </script>
</body>
</html>
"""

components.html(voice_assistant_html, height=480)
