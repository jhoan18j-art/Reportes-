# Yin: asistente personal con Claude

Asistente por voz (o texto) que controla tu computadora, tu Android y tus apps Streamlit de Club Park.

## Instalación

```bash
python -m venv venv
# Windows: venv\Scripts\activate    |  Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # y pon tu ANTHROPIC_API_KEY
```

Si `PyAudio` falla en Windows: `pip install pipwin && pipwin install pyaudio`.
Mac: `brew install portaudio` antes del pip. Linux: `sudo apt install portaudio19-dev python3-pyaudio espeak`.

## Uso

```bash
python main.py --text      # primero pruébalo en texto
python main.py             # voz: di "Yin, abre las apps de Club Park"
python main.py --no-wake   # voz sin palabra de activación
```

Ejemplos: "Yin, enciende app.py", "abre Spotify en la compu", "abre WhatsApp en mi teléfono y dime los chats sin leer",
"sube el scroll del teléfono", "¿qué dice el log de streamlit_app?".

## Android (adb)

1. En el teléfono: Ajustes → Acerca del teléfono → toca 7 veces "Número de compilación" → Opciones de desarrollador → activa **Depuración USB**.
2. En la compu instala *Android platform-tools* (adb) y conecta por USB; acepta la huella RSA en el teléfono.
3. Prueba: `adb devices`. Por Wi-Fi: Depuración inalámbrica y dile a Yin "conéctate a 192.168.x.x:puerto".

Límites: Yin "ve" el teléfono leyendo la interfaz (`uiautomator`) o con capturas. Apps bancarias y algunas otras bloquean ambas.
`input text` solo escribe ASCII (sin acentos ni ñ).

## Seguridad (importante)

- `run_shell`, `write_file` y todo el control de mouse/teclado de la PC **piden tu confirmación** (voz o teclado). Hay una lista de comandos bloqueados.
- Yin solo escribe archivos dentro de `YIN_WORKDIR`.
- Para acciones con efecto externo en el teléfono (enviar mensajes, llamar, pagar) el modelo debe llamar a `confirmar_con_usuario`; no dependas solo de eso en apps de dinero.
- Texto leído de pantallas o archivos se trata como dato, no como órdenes (defensa contra instrucciones ocultas), pero no es infalible: no lo uses sin supervisión en cuentas sensibles.
- Usa `YIN_AUTO_APPROVE` solo cuando confíes en una herramienta (ej. `pc_click`).
- Las apps Streamlit que Yin enciende siguen corriendo al cerrarlo; pídele que las apague.

## Estructura

```
main.py                 punto de entrada
yin/app.py              bucle de voz/texto
yin/brain.py            Claude + uso de herramientas
yin/voice.py            micrófono y voz
yin/safety.py           confirmaciones
yin/tools/computer.py   apps, web, archivos, terminal
yin/tools/desktop.py    ver pantalla/clic/teclado de la PC
yin/tools/android.py    teléfono por adb
yin/tools/streamlit_ctl.py   apps Club Park
```

Para añadir una herramienta nueva, escribe una función con `@tool(...)` en cualquier archivo de `yin/tools/` e impórtalo en `yin/tools/__init__.py`.
