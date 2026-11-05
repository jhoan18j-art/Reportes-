
# -*- coding: utf-8 -*-
"""
CLUB PARK VALET Y ESTACIONAMIENTOS - Plataforma unificada.
Un solo acceso y un solo menú para:
  - Valet: tickets, salida y cobro, cortes de caja   (modulos/valet.py)
  - Flujo: reporte diario por foto, auditoría, Excel  (modulos/flujo.py)
"""
import hmac

import streamlit as st

# Debe ser el primer comando de Streamlit; los módulos ya no lo llaman.
st.set_page_config(page_title="Club Park - Control Operativo", page_icon="🚗",
                   layout="wide", initial_sidebar_state="expanded")

from auth import ACCESOS, ACCESOS_FUENTE, lector_qr_camara_trasera, leer_codigo_qr, secreto  # noqa: E402
from PIL import Image  # noqa: E402

for _k in ("usuario_autenticado", "sucursal_asignada", "rol"):
    st.session_state.setdefault(_k, None)

# Acceso con usuario y contraseña (antes en la app de flujo). Contraseñas en variables de entorno / secrets.
USUARIOS_PASSWORD = {
    "José de Jesús": ("PASS_SUPERVISOR", "Supervisor Global"),
    "Víctor Manuel": ("PASS_SUPERVISOR", "Supervisor Global"),
    "Víctor (Contador)": ("PASS_AUDITOR", "Contador Auditor"),
}


def _entrar(nombre, sucursal, rol):
    st.session_state.usuario_autenticado = nombre
    st.session_state.sucursal_asignada = sucursal
    st.session_state.rol = rol
    if "qrscan" in st.query_params:
        del st.query_params["qrscan"]
    st.rerun()


def _validar_token(token):
    info = ACCESOS.get(token)
    if info:
        _entrar(info.get("nombre", "Usuario"), info.get("sucursal", ""), info.get("rol", "Supervisor de Sucursal"))
    else:
        st.error("Token o código QR no reconocido. Verifica con el Contador Auditor.")


def pantalla_login():
    _, centro, _ = st.columns([1, 2.2, 1])
    with centro:
        st.markdown("<h2 style='text-align:center;color:#0B3B24'>🚗 CLUB PARK VALET</h2>"
                    "<p style='text-align:center'>Y ESTACIONAMIENTOS S.A. DE C.V.</p>", unsafe_allow_html=True)
        if ACCESOS_FUENTE == "por_defecto":
            st.warning("Se están usando los tokens de ejemplo del código. Define CLUBPARK_TOKENS_JSON antes de operar.")
        metodo = st.radio("Cómo quieres entrar:", [
            "📷 Foto de QR con la cámara", "🖼️ Subir imagen QR", "🔑 Token manual", "👤 Usuario y contraseña"], key="metodo_login")
        token = str(st.query_params.get("qrscan", "") or "").strip() or None

        if metodo.startswith("📷"):
            if not token:
                token = lector_qr_camara_trasera("lector_login_trasero", height=390)
        elif metodo.startswith("🖼️"):
            archivo = st.file_uploader("Credencial QR", type=["png", "jpg", "jpeg"])
            if archivo:
                token = leer_codigo_qr(Image.open(archivo))
        elif metodo.startswith("🔑"):
            t = st.text_input("Token de acceso", type="password")
            if st.button("Validar acceso", type="primary", use_container_width=True):
                token = t.strip()
        else:
            usuario = st.selectbox("Usuario", ["-- Selecciona --"] + list(USUARIOS_PASSWORD))
            clave = st.text_input("Contraseña", type="password")
            if st.button("🔑 Iniciar sesión", type="primary", use_container_width=True):
                if usuario in USUARIOS_PASSWORD:
                    var, rol = USUARIOS_PASSWORD[usuario]
                    esperada = secreto(var)
                    if not esperada:
                        st.error(f"Falta configurar {var} en el servidor.")
                    elif hmac.compare_digest(clave, esperada):
                        _entrar(usuario, "TODAS", rol)
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    st.error("Selecciona tu usuario.")
        if token:
            _validar_token(token)


if st.session_state.usuario_autenticado is None:
    pantalla_login()
    st.stop()

rol = str(st.session_state.rol or "")
es_global = ("Contador" in rol) or rol == "Supervisor Global"

paginas = [st.Page("modulos/valet.py", title="Valet: tickets y cobro", icon="🚗", url_path="valet", default=True)]
if es_global:  # el reporte de flujo y auditoría es solo para supervisores globales y contador
    paginas.append(st.Page("modulos/flujo.py", title="Flujo diario y auditoría", icon="📊", url_path="flujo"))

st.navigation(paginas).run()
