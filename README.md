Validador de Reportes — versión móvil
Esta versión está preparada para usarse desde un teléfono Android mediante un navegador.
Flujo
Iniciar sesión.
Tomar fotografía del reporte.
Leer automáticamente con IA/OCR.
Revisar los datos detectados.
Validar:
fecha
sitio
autorización del usuario
costo
folios
boletos pagados/cancelados/perdidos
boletos entregados
gastos
resultado
quién recibe el dinero
quién recibe físicamente el reporte
Aceptar o rechazar.
Registrar el resultado en SQLite.
Generar Excel semanal con reportes aceptados.
Ejecutar en una computadora
pip install -r requirements.txt
streamlit run app.py
Luego abre la dirección que muestra Streamlit.
Lectura automática
Para activar la lectura con Anthropic configura:
ANTHROPIC_API_KEY
opcionalmente CLAUDE_MODEL
Sin la API, la aplicación sigue funcionando para pruebas, pero no realizará la lectura automática.
Contraseñas
Para pruebas locales, si no se configuran variables de entorno, la clave temporal es:
1234
Antes de producción deben configurarse contraseñas reales.
Importante antes de producción
La lista de receptores autorizados de dinero/reportes es provisional y debe reemplazarse por el catálogo real de la empresa.
También conviene agregar después:
catálogo de costos por sitio
catálogo de operadores
catálogo de supervisores
marcado visual de errores directamente sobre la fotografía
auditoría de quién aceptó/rechazó
respaldo de base de datos
despliegue seguro con HTTPS
autenticación de producción
PWA/instalación en pantalla de Android