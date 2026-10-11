import io
import json
import os
import shutil
import uuid
import hashlib
import hmac
import base64
from datetime import date, datetime, time, timedelta
import urllib.parse
import pandas as pd
import streamlit as st
from PIL import Image

# Import opcional para exportación con estilo en Excel
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# =========================================================================
# CONFIGURACIÓN GENERAL Y PERSISTENCIA ATÓMICA EN NUBE
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_FILE = os.path.join(BASE_DIR, "reportes_clubpark.json")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos_reportes")
os.makedirs(FOTOS_DIR, exist_ok=True)

st.set_page_config(
    page_title="Club Park - Control Operativo MXN",
    page_icon="🚗",
    layout="wide"
)

# Estilo CSS para optimizar inputs numéricos y visualización
st.markdown("""
    <style>
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        input[type=number] {
            -moz-appearance: textfield;
        }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# MÓDULO CRIPTOGRÁFICO: CIFRADO Y DESCIFRADO DE RESPALDOS SENSIBLES
# =========================================================================
def cifrar_respaldo_seguro(datos_obj, clave_secreta):
    """Cifra los datos con PBKDF2 HMAC SHA-256 (100,000 iteraciones) y firma digital."""
    try:
        datos_bytes = json.dumps(datos_obj, ensure_ascii=False).encode('utf-8')
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac('sha256', clave_secreta.encode('utf-8'), salt, 100000, dklen=32)
        
        keystream = b''
        counter = 0
        while len(keystream) < len(datos_bytes):
            keystream += hashlib.sha256(key + counter.to_bytes(4, 'big')).digest()
            counter += 1
            
        cifrado = bytes(a ^ b for a, b in zip(datos_bytes, keystream[:len(datos_bytes)]))
        tag = hmac.new(key, salt + cifrado, hashlib.sha256).digest()
        
        paquete = {
            "seguridad": "PBKDF2-HMAC-SHA256",
            "fecha_cifrado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salt": base64.b64encode(salt).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8'),
            "data": base64.b64encode(cifrado).decode('utf-8')
        }
        return json.dumps(paquete, indent=2)
    except Exception as e:
        st.error(f"Error durante el cifrado del respaldo: {e}")
        return None

def descifrar_respaldo_seguro(paquete_cifrado_str, clave_secreta):
    """Verifica autenticidad y descifra el respaldo seguro."""
    try:
        paquete = json.loads(paquete_cifrado_str)
        if "salt" not in paquete or "tag" not in paquete or "data" not in paquete:
            return None, "El archivo no tiene el formato de respaldo cifrado válido."
            
        salt = base64.b64decode(paquete["salt"])
        tag_esperado = base64.b64decode(paquete["tag"])
        cifrado = base64.b64decode(paquete["data"])
        
        key = hashlib.pbkdf2_hmac('sha256', clave_secreta.encode('utf-8'), salt, 100000, dklen=32)
        tag_calculado = hmac.new(key, salt + cifrado, hashlib.sha256).digest()
        
        if not hmac.compare_digest(tag_esperado, tag_calculado):
            return None, "❌ Clave de descifrado incorrecta o archivo alterado."
        
        keystream = b''
        counter = 0
        while len(keystream) < len(cifrado):
            keystream += hashlib.sha256(key + counter.to_bytes(4, 'big')).digest()
            counter += 1
            
        datos_bytes = bytes(a ^ b for a, b in zip(cifrado, keystream[:len(cifrado)]))
        datos_json = json.loads(datos_bytes.decode('utf-8'))
        return datos_json, "OK"
    except Exception as e:
        return None, f"Error al procesar archivo cifrado: {e}"
        if duplicado and not es_contador:
    st.error(f"🚫 **REPORTE YA EXISTE:** La sucursal **{sucursal}** ya cuenta con un reporte para la fecha **{fecha_op_str}**.")
    st.warning("⚠️ Como supervisor, no puedes duplicar reportes para la misma sucursal en el mismo día. Si necesitas corregirlo, solicita apoyo al Contador Auditor.")
    puede_guardar = False
elif duplicado and es_contador:
    st.warning(f"⚠️ **Atención:** Ya existe un reporte de **{sucursal}** para la fecha **{fecha_op_str}**. Como Contador Auditor, puedes registrar este turno o reporte adicional.")

# BOTÓN DE GUARDADO PRINCIPAL
if st.button("💾 Guardar y Confirmar Reporte Diario", type="primary", use_container_width=True, disabled=not puede_guardar):
    if sucursal == "-- Selecciona o busca la sucursal --":
        st.error("❌ Debes seleccionar una sucursal válida antes de guardar.")
    else:
        id_nuevo = f"REP_{uuid.uuid4().hex[:8]}"
        ruta_foto_guardada = None
        
        if foto_subida is not None:
            ruta_foto_guardada = guardar_imagen_optimizada(foto_subida, id_nuevo, sucursal, fecha_op_str)

        nuevo_reporte = {
            "ID": id_nuevo,
            "Fecha": fecha_op_str,
            "Sitio / Unidad": sucursal,
            "Horario": f"{hora_ini.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}",
            "Costo Boleto": 0.0 if es_ingreso_directo else float(costo_boleto),
            "Folio Inicial": 0 if es_ingreso_directo else int(f_ini),
            "Folio Final": 0 if es_ingreso_directo else int(f_fin),
            "Total Boletos": total_boletos_calc,
            "Sin Cobro": 0 if es_ingreso_directo else int(f_sin),
            "Cancelados": 0 if es_ingreso_directo else int(f_can),
            "Perdidos": 0 if es_ingreso_directo else int(f_per),
            "Boletos Cobrados": boletos_cobrados_calc,
            "Ingreso Bruto": ingreso_bruto_calc,
            "Gastos Especiales": float(g_esp),
            "Gastos Generales / Nómina": float(g_gen),
            "Total Gastos": total_gastos_calc,
            "Ingreso Neto": ingreso_neto_calc,
            "Margen (%)": round(margen_calc, 2),
            "Rentabilidad": rentabilidad_calc,
            "Elaboró": elaboro if elaboro else st.session_state.usuario_autenticado,
            "Recibe": recibe,
            "Tipo": "Operación Regular",
            "foto_path": ruta_foto_guardada,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        st.session_state.registros.append(nuevo_reporte)
        guardado_exitoso = guardar_registros_permanentes(st.session_state.registros)

        if guardado_exitoso:
            st.success(f"✅ Reporte guardado exitosamente con ID: `{id_nuevo}`")
            st.balloons()
            st.rerun()
        else:
            st.error("❌ Ocurrió un error al guardar el reporte en el disco permanente.")
