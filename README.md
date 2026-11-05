# Club Park — plataforma unificada (siempre encendida)

- `main.py`: login único (QR, token o usuario/contraseña) y menú.
- `modulos/valet.py`: app de tickets/cobro/cortes. `modulos/flujo.py`: reporte de flujo + auditoría + Excel (solo Supervisor Global y Contador).
- Datos en `CLUBPARK_DATA_DIR` (`/data` en producción): `valet/` y `flujo/`. Si ya tienes JSON/fotos, cópialos a esas carpetas.

## Variables de entorno
PASS_SUPERVISOR, PASS_AUDITOR, CLUBPARK_TOKENS_JSON (tokens por encargado), CLUBPARK_APP_URL (URL pública, para que el QR abra la app).
Opcionales: SUPABASE_URL, SUPABASE_KEY, LOVABLE_API_KEY, WHATSAPP_API_KEY.

## Despliegue (Render, plan de pago: no se duerme)
1. Sube esta carpeta a un repo de GitHub.
2. Render → New → Blueprint → elige el repo (usa `render.yaml`, crea el disco `/data`).
3. Llena las variables de entorno y abre la URL https.
El `Dockerfile` también sirve en Railway, Fly.io o un VPS (monta un volumen en `/data`).

