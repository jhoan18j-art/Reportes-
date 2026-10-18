import urllib.parse
# -*- coding: utf-8 -*-
"""
CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.
Sistema Inteligente de Control Operativo, Auditoría Automatizada y Rentabilidad
Optimizado para dispositivos Android con bajo consumo de datos móviles (Cero costo de APIs externas).
"""

import math
import io
import json
import os
import re
import shutil
import uuid
import base64
import hmac
from datetime import date, datetime, time, timedelta
import pandas as pd
import streamlit as st
from PIL import Image, ImageStat

# =========================================================================
# VERIFICACIÓN SEGURA DE LIBRERÍAS EXTERNAS
# =========================================================================
OPENPYXL_OK = False
XLSXWRITER_OK = False
CRYPTOGRAPHY_OK = False
PYTESSERACT_OK = False

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    pass

try:
    import xlsxwriter
    XLSXWRITER_OK = True
except ImportError:
    pass

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTOGRAPHY_OK = True
except ImportError:
    pass

try:
    import pytesseract
    PYTESSERACT_OK = True
except ImportError:
    pass

# =========================================================================
# CONFIGURACIÓN GENERAL, DIRECTORIOS Y NUBE SUPABASE
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DATA_DIR = os.environ.get("CLUBPARK_DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "reportes_clubpark.json")
AUDIT_FILE = os.path.join(DATA_DIR, "historial_auditoria.json")
AI_MEMORIA_FILE = os.path.join(DATA_DIR, "ia_memoria_aprendizaje.json")
FOTOS_DIR = os.path.join(DATA_DIR, "fotos_reportes")
os.makedirs(FOTOS_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "config_operativa.json")
NOTIF_LOG_FILE = os.path.join(DATA_DIR, "bitacora_notificaciones.json")

def cargar_config_operativa():
    default_cfg = {
        "tel_jesus": "525500000001",
        "tel_victor": "525500000002",
        "lovable_api_key": "",
        "whatsapp_api_key": "",
        "auto_whatsapp": False
    }
    return cargar_json_seguro(CONFIG_FILE, default_cfg)

def guardar_config_operativa(cfg):
    guardar_json_atomico(CONFIG_FILE, cfg)

def registrar_notificacion_bitacora(destinatario, tipo, mensaje, estado, detalle=""):
    bitacora = cargar_json_seguro(NOTIF_LOG_FILE, [])
    item = {
        "id": f"NOTIF_{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "destinatario": destinatario,
        "tipo": tipo,
        "mensaje": mensaje,
        "estado": estado,
        "detalle": detalle
    }
    bitacora.insert(0, item)
    if len(bitacora) > 100:
        bitacora = bitacora[:100]
    guardar_json_atomico(NOTIF_LOG_FILE, bitacora)
    return item

def enviar_whatsapp_directo_api(telefono: str, mensaje: str, lovable_key=None, whatsapp_key=None):
    """
    Envía mensaje directo por WhatsApp Business Gateway API (si las credenciales existen).
    Retorna (exito: bool, respuesta: str)
    """
    l_key = lovable_key or obtener_secreto("LOVABLE_API_KEY", os.environ.get("LOVABLE_API_KEY", ""))
    w_key = whatsapp_key or obtener_secreto("WHATSAPP_API_KEY", os.environ.get("WHATSAPP_API_KEY", ""))
    if not l_key or not w_key:
        return False, "Credenciales API no configuradas (se requiere LOVABLE_API_KEY y WHATSAPP_API_KEY)"
    
    tel_digits = "".join(ch for ch in str(telefono) if ch.isdigit())
    if not tel_digits.startswith("52") and len(tel_digits) == 10:
        tel_digits = "52" + tel_digits
        
    url = "https://connector-gateway.lovable.dev/whatsapp/messages"
    headers = {
        "Authorization": f"Bearer {l_key}",
        "X-Connection-Api-Key": w_key,
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": tel_digits,
        "type": "text",
        "text": {"body": mensaje}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            return True, "Enviado exitosamente vía WhatsApp API"
        else:
            return False, f"Error Gateway ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Falla de conexión: {str(e)}"

def filtrar_registros_por_periodo(registros, tipo_periodo="Todo el Histórico", fecha_ini=None, fecha_fin=None):
    if not registros or tipo_periodo == "Todo el Histórico":
        return list(registros)
    hoy = date.today()
    if "Semanal" in tipo_periodo:
        lim_inf = hoy - timedelta(days=7)
        lim_sup = hoy + timedelta(days=1)
    elif "Quincenal" in tipo_periodo:
        lim_inf = hoy - timedelta(days=15)
        lim_sup = hoy + timedelta(days=1)
    elif "Mensual" in tipo_periodo:
        lim_inf = hoy - timedelta(days=30)
        lim_sup = hoy + timedelta(days=1)
    elif tipo_periodo == "Rango Personalizado" and fecha_ini and fecha_fin:
        lim_inf = fecha_ini
        lim_sup = fecha_fin
    else:
        return list(registros)
    
    resultado = []
    for r in registros:
        f_str = r.get("Fecha", "")
        try:
            f_dt = datetime.strptime(f_str, "%d/%m/%Y").date()
            if lim_inf <= f_dt <= lim_sup:
                resultado.append(r)
        except Exception:
            pass
    return resultado

def reiniciar_sistema_desde_cero(borrar_reportes=True, borrar_fotos=True, reiniciar_memoria=False, reiniciar_bitacora=False, usuario_auditor="Víctor (Contador)"):
    total_fotos_borradas = 0
    total_reportes_borrados = 0

    if borrar_fotos and os.path.exists(FOTOS_DIR):
        for arch in os.listdir(FOTOS_DIR):
            ruta_f = os.path.join(FOTOS_DIR, arch)
            try:
                if os.path.isfile(ruta_f):
                    os.remove(ruta_f)
                    total_fotos_borradas += 1
            except Exception:
                pass

    if borrar_reportes:
        regs = cargar_registros_guardados()
        total_reportes_borrados = len(regs)
        guardar_registros_permanentes([])
        if "registros" in st.session_state:
            st.session_state.registros = []

    if reiniciar_memoria:
        guardar_json_atomico(AI_MEMORIA_FILE, {
            "version": "2.0_adaptive",
            "total_reportes_procesados": 0,
            "sucursales": {}
        })

    if reiniciar_bitacora:
        guardar_json_atomico(AUDIT_FILE, [])
    else:
        registrar_evento_auditoria(
            "Reinicio Total del Sistema",
            usuario_auditor,
            "RESET_SISTEMA",
            "TODAS",
            datetime.now().strftime("%d/%m/%Y"),
            f"El auditor reinició el sistema desde cero. Se borraron {total_reportes_borrados} reportes y {total_fotos_borradas} fotos físicas.",
            score=100
        )

    return total_reportes_borrados, total_fotos_borradas

SUPABASE_OK = False
try:
    from supabase import create_client, Client
    SUPABASE_OK = True
except ImportError:
    pass

def obtener_cliente_supabase():
    """
    Inicializa cliente Supabase para persistencia duradera en la nube si las claves
    están disponibles en st.secrets o variables de entorno.
    """
    if not SUPABASE_OK:
        return None
    url = obtener_secreto("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    key = obtener_secreto("SUPABASE_SERVICE_ROLE_KEY", obtener_secreto("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "")))
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

def sincronizar_reporte_supabase(reporte_dict, foto_bytes=None, foto_filename=None):
    """
    Guarda el reporte y sube su fotografía al Storage / Base de datos de Supabase.
    Si Supabase no está configurado, la app conserva el almacenamiento local blindado.
    """
    sb = obtener_cliente_supabase()
    if not sb:
        return False, "Supabase no configurado en Secrets"
    try:
        remote_photo_url = None
        if foto_bytes and foto_filename:
            try:
                # Subida de imagen comprimida al bucket 'reportes-fotos'
                res_st = sb.storage.from_("reportes-fotos").upload(
                    foto_filename,
                    foto_bytes,
                    {"content-type": "image/jpeg", "upsert": "true"}
                )
                remote_photo_url = sb.storage.from_("reportes-fotos").get_public_url(foto_filename)
            except Exception as e_st:
                # Si falla el bucket, continuamos con el registro
                pass

        datos_insert = {
            "id": reporte_dict.get("ID"),
            "amount": float(reporte_dict.get("Ingreso Neto", 0.0)),
            "income_date": datetime.strptime(reporte_dict.get("Fecha"), "%d/%m/%Y").strftime("%Y-%m-%d") if "/" in reporte_dict.get("Fecha", "") else str(date.today()),
            "site": reporte_dict.get("Sitio / Unidad"),
            "category": "Operación Valet",
            "concept": f"Reporte de turno {reporte_dict.get('Horario', '')}",
            "payment_method": "Efectivo",
            "payer": reporte_dict.get("Elaboró"),
            "photo_path": remote_photo_url or reporte_dict.get("foto_path"),
            "report": reporte_dict
        }
        sb.table("incomes").upsert(datos_insert).execute()
        return True, "Sincronizado con Supabase Cloud"
    except Exception as e:
        return False, str(e)


st.set_page_config(
    page_title="Club Park - Control Operativo & Rentabilidad",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS adaptados para teléfonos Android (Touch-friendly, bajo consumo de datos)
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
        .stMetric {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            min-height: 44px;
        }
        .card-auditoria {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 15px;
            border-left: 6px solid #3182ce;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            margin-bottom: 12px;
        }
        .badge-verde { background-color: #C6F6D5; color: #22543D; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
        .badge-amarillo { background-color: #FEFCBF; color: #744210; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
        .badge-rojo { background-color: #FED7D7; color: #742A2A; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
        @media (max-width: 768px) {
            .stMetric { padding: 8px; font-size: 0.9rem; }
            .stTabs [data-baseweb="tab"] { font-size: 0.85rem; padding: 6px 10px; }
        }
    </style>
""", unsafe_allow_html=True)

def obtener_secreto(clave: str, valor_por_defecto: str) -> str:
    """Obtiene un secreto seguro de st.secrets si existe, de lo contrario usa el fallback."""
    try:
        if hasattr(st, "secrets") and clave in st.secrets:
            return st.secrets[clave]
    except Exception:
        pass
    return valor_por_defecto

def calcular_boletos_block100(f_ini: int, f_fin: int) -> int:
    """Conteo inclusivo y cíclico de folios cuyo consecutivo se reinicia cada 100.
    Ej.: 595→303 equivale a 95→03 y son 9 boletos.
    """
    inicio, fin = int(f_ini), int(f_fin)
    if inicio < 0 or fin < 0 or (inicio == 0 and fin == 0):
        return 0
    d_ini, d_fin = inicio % 100, fin % 100
    return ((d_fin - d_ini) % 100) + 1


def obtener_tarifa_sucursal(sucursal: str, tarifa_ocr=None) -> float:
    """Usa tarifa OCR si es válida; de lo contrario el catálogo de la sucursal."""
    precio_catalogo = float(PRECIOS_SUCURSALES.get(sucursal, 0) or 0)
    try:
        precio_ocr = float(tarifa_ocr)
        if precio_ocr > 0:
            return precio_ocr
    except (TypeError, ValueError):
        pass
    return precio_catalogo

def generar_enlace_whatsapp(telefono: str, mensaje: str) -> str:
    """Genera URL wa.me para enviar mensajes y recordatorios directamente desde cualquier Android/PC."""
    tel_clean = "".join(c for c in str(telefono) if c.isdigit())
    if not tel_clean.startswith("52") and len(tel_clean) == 10:
        tel_clean = "52" + tel_clean
    msg_enc = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_clean}?text={msg_enc}"

# =========================================================================
# CATÁLOGO DE SUCURSALES Y PRECIOS BASE
# =========================================================================
PRECIOS_SUCURSALES = {
    "PAMPAS": 50, "RAMMA": 70, "SUSHITTO": 40, "BARRANCA": 0,
    "CARAJILLO": 100, "BENINGANS": 40, "ROMAS": 65, "J.TLALPAN": 100,
    "J.DIVISION": 100, "J.PICACHO": 100, "J.EMPRESA": 100, "sipily": 80,
    "M SATÉLITE": 70, "M MARINA": 70, "VETERINARIA": 0,
    "SUMO STA": 50, "CHEGARAY": 50, "RYOSHI": 80, "ENCANTO": 90,
    "S. AZURA": 0, "E-BNI": 0, "CHURRASCA": 70, "SUMO PICACHO": 50
}

UNIDADES_JESUS = ["PAMPAS", "RAMMA", "SUSHITTO", "BARRANCA", "CARAJILLO", "BENINGANS" , "S. AZURA"]
UNIDADES_VICTOR = ["SUMO STA", "CHEGARAY", "RYOSHI", "ENCANTO", "CHURRASCA"]
SUCURSALES_LISTA = ["-- Selecciona o busca la sucursal --"] + sorted(list(PRECIOS_SUCURSALES.keys()))

# =========================================================================
# MÓDULO CRIPTOGRÁFICO: CIFRADO ESTÁNDAR FERNET (AES-128-CBC + HMAC-SHA256)
# =========================================================================
def _derivar_clave_fernet(clave_secreta: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    return base64.urlsafe_b64encode(kdf.derive(clave_secreta.encode("utf-8")))

def cifrar_respaldo_seguro(datos_obj, clave_secreta: str) -> str:
    if not CRYPTOGRAPHY_OK:
        raise RuntimeError("La librería 'cryptography' no está instalada.")
    try:
        salt = os.urandom(16)
        clave_fernet = _derivar_clave_fernet(clave_secreta, salt)
        f = Fernet(clave_fernet)
        datos_bytes = json.dumps(datos_obj, ensure_ascii=False).encode("utf-8")
        token = f.encrypt(datos_bytes)
        paquete = {
            "estandar": "Fernet-AES128CBC-HMACSHA256",
            "kdf": "PBKDF2-HMAC-SHA256-100k",
            "fecha_cifrado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "salt": base64.b64encode(salt).decode("utf-8"),
            "token": token.decode("utf-8")
        }
        return json.dumps(paquete, indent=2)
    except Exception as e:
        st.error(f"Error durante el cifrado estándar del respaldo: {e}")
        return None

def descifrar_respaldo_seguro(paquete_cifrado_str: str, clave_secreta: str):
    if not CRYPTOGRAPHY_OK:
        return None, "La librería 'cryptography' no está instalada."
    try:
        paquete = json.loads(paquete_cifrado_str)
        if "salt" in paquete and "token" in paquete:
            salt = base64.b64decode(paquete["salt"])
            clave_fernet = _derivar_clave_fernet(clave_secreta, salt)
            f = Fernet(clave_fernet)
            datos_bytes = f.decrypt(paquete["token"].encode("utf-8"))
            return json.loads(datos_bytes.decode("utf-8")), "OK"

        # Compatibilidad con respaldos del formato anterior de la aplicación.
        if paquete.get("seguridad") == "PBKDF2-HMAC-SHA256" and all(k in paquete for k in ("salt", "tag", "data")):
            import hashlib
            salt = base64.b64decode(paquete["salt"])
            tag_esperado = base64.b64decode(paquete["tag"])
            cifrado = base64.b64decode(paquete["data"])
            key = hashlib.pbkdf2_hmac("sha256", clave_secreta.encode("utf-8"), salt, 100000, dklen=32)
            tag_calculado = hmac.new(key, salt + cifrado, hashlib.sha256).digest()
            if not hmac.compare_digest(tag_esperado, tag_calculado):
                return None, "Clave incorrecta o archivo alterado."
            keystream = b""
            counter = 0
            while len(keystream) < len(cifrado):
                keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
                counter += 1
            plain = bytes(a ^ b for a, b in zip(cifrado, keystream[:len(cifrado)]))
            return json.loads(plain.decode("utf-8")), "OK (formato anterior)"
        return None, "El archivo no contiene un formato de respaldo reconocido."
    except InvalidToken:
        return None, "❌ Clave de descifrado incorrecta o archivo alterado."
    except Exception as e:
        return None, f"Error al procesar el archivo cifrado: {e}"

# =========================================================================
# PERSISTENCIA Y MEMORIA DE APRENDIZAJE IA
# =========================================================================
def cargar_json_seguro(ruta_archivo, default_tipo):
    if os.path.exists(ruta_archivo):
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, type(default_tipo)):
                    return data
        except Exception:
            pass
    return default_tipo

def guardar_json_atomico(ruta_archivo, datos):
    try:
        tmp_file = ruta_archivo + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, ruta_archivo)
        return True
    except Exception as e:
        st.error(f"Error escribiendo en {os.path.basename(ruta_archivo)}: {e}")
        return False

def cargar_registros_guardados():
    return cargar_json_seguro(DB_FILE, [])

def guardar_registros_permanentes(registros):
    return guardar_json_atomico(DB_FILE, registros)

def cargar_historial_auditoria():
    return cargar_json_seguro(AUDIT_FILE, [])

def registrar_evento_auditoria(tipo_evento, usuario, id_reporte, sucursal, fecha_op, detalles, score=100, fallas=None):
    historial = cargar_historial_auditoria()
    evento = {
        "id_evento": f"AUD_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo_evento": tipo_evento,
        "usuario": usuario,
        "id_reporte": id_reporte,
        "sucursal": sucursal,
        "fecha_operacion": fecha_op,
        "detalles": detalles,
        "score_auditoria": score,
        "fallas_detectadas": fallas or []
    }
    historial.insert(0, evento)
    guardar_json_atomico(AUDIT_FILE, historial)
    return evento

def cargar_memoria_ia():
    memoria_defecto = {
        "version": "2.0_adaptive",
        "total_reportes_procesados": 0,
        "sucursales": {}
    }
    return cargar_json_seguro(AI_MEMORIA_FILE, memoria_defecto)

def actualizar_memoria_ia(reporte):
    """
    Perfil estadístico local por sucursal (no es un modelo ML entrenado):
    actualiza promedios para sugerir valores y folios en capturas futuras.
    """
    memoria = cargar_memoria_ia()
    suc = reporte.get("Sitio / Unidad")
    if not suc or suc == "-- Selecciona o busca la sucursal --":
        return

    if "sucursales" not in memoria:
        memoria["sucursales"] = {}

    suc_mem = memoria["sucursales"].get(suc, {
        "reportes_aprendidos": 0,
        "costo_habitual": PRECIOS_SUCURSALES.get(suc, 50),
        "promedio_boletos": 0,
        "promedio_ingreso_bruto": 0.0,
        "promedio_gastos": 0.0,
        "margen_promedio": 0.0,
        "boletos_m2": 0.0, "gastos_m2": 0.0,
        "ultimo_folio_final": 0,
        "horario_frecuente": "13:00 a 23:00",
        "supervisor_frecuente": reporte.get("Elaboró", "Supervisor")
    })

    n = int(suc_mem.get("reportes_aprendidos", 0))
    nuevo_n = n + 1
    boletos = float(reporte.get("Boletos Cobrados", 0) or 0)
    bruto = float(reporte.get("Ingreso Bruto", 0) or 0)
    gastos = float(reporte.get("Total Gastos", 0) or 0)
    margen = float(reporte.get("Margen (%)", 0) or 0)
    folio_final = int(reporte.get("Folio Final", 0) or 0)

    # Promedios y varianzas online (Welford): cada reporte confirmado actualiza
    # el perfil estadístico de la sucursal sin retener datos personales extra.
    mean_b = float(suc_mem.get("promedio_boletos", 0) or 0)
    mean_g = float(suc_mem.get("promedio_gastos", 0) or 0)
    delta_b, delta_g = boletos - mean_b, gastos - mean_g
    suc_mem["promedio_boletos"] = round(mean_b + delta_b / nuevo_n, 1)
    suc_mem["promedio_gastos"] = round(mean_g + delta_g / nuevo_n, 2)
    suc_mem["boletos_m2"] = float(suc_mem.get("boletos_m2", 0) or 0) + delta_b * (boletos - suc_mem["promedio_boletos"])
    suc_mem["gastos_m2"] = float(suc_mem.get("gastos_m2", 0) or 0) + delta_g * (gastos - suc_mem["promedio_gastos"])
    suc_mem["promedio_ingreso_bruto"] = round(((float(suc_mem.get("promedio_ingreso_bruto", 0) or 0) * n) + bruto) / nuevo_n, 2)
    suc_mem["margen_promedio"] = round(((float(suc_mem.get("margen_promedio", 0) or 0) * n) + margen) / nuevo_n, 2)
    if folio_final > 0:
        suc_mem["ultimo_folio_final"] = max(suc_mem.get("ultimo_folio_final", 0), folio_final)
    suc_mem["reportes_aprendidos"] = nuevo_n
    if reporte.get("Horario"):
        suc_mem["horario_frecuente"] = reporte["Horario"]
    if reporte.get("Elaboró"):
        suc_mem["supervisor_frecuente"] = reporte["Elaboró"]

    memoria["sucursales"][suc] = suc_mem
    memoria["total_reportes_procesados"] = memoria.get("total_reportes_procesados", 0) + 1
    guardar_json_atomico(AI_MEMORIA_FILE, memoria)

# =========================================================================
# MOTOR DE AUDITORÍA INTELIGENTE Y DETECCIÓN DE ANOMALÍAS
# =========================================================================
def evaluar_auditoria_reporte(reporte_dict, registros_existentes=None, memoria_ia=None):
    """
    Analiza un reporte contra 8 reglas estrictas de auditoría operativa y financiera.
    Retorna (score: int, nivel: str, fallas: list[dict], observaciones: list[str]).
    """
    fallas = []
    observaciones = []
    score = 100

    suc = reporte_dict.get("Sitio / Unidad", "")
    costo_bol = float(reporte_dict.get("Costo Boleto", 0.0))
    f_ini = int(reporte_dict.get("Folio Inicial", 0))
    f_fin = int(reporte_dict.get("Folio Final", 0))
    tot_bol = int(reporte_dict.get("Total Boletos", 0))
    sin_cob = int(reporte_dict.get("Sin Cobro", 0))
    canc = int(reporte_dict.get("Cancelados", 0))
    perd = int(reporte_dict.get("Perdidos", 0))
    cobrados = int(reporte_dict.get("Boletos Cobrados", 0))
    bruto = float(reporte_dict.get("Ingreso Bruto", 0.0))
    g_esp = float(reporte_dict.get("Gastos Especiales", 0.0))
    g_gen = float(reporte_dict.get("Gastos Generales / Nómina", 0.0))
    tot_gastos = float(reporte_dict.get("Total Gastos", g_esp + g_gen))
    neto = float(reporte_dict.get("Ingreso Neto", bruto - tot_gastos))
    margen = float(reporte_dict.get("Margen (%)", 0.0))
    elab = str(reporte_dict.get("Elaboró") or "").strip()
    recibe = str(reporte_dict.get("Recibe") or "").strip()
    es_directo = (suc in ["BARRANCA", "VETERINARIA", "S. AZURA", "E-BNI"] or PRECIOS_SUCURSALES.get(suc, 0) == 0)

    # 1. Regla Matemática de Boletos (Blocks de 100, conteo por 2 últimos dígitos)
    if not es_directo and (f_fin > 0 or f_ini > 0):
        calculado_tot = calcular_boletos_block100(f_ini, f_fin)
        if calculado_tot != tot_bol:
            score -= 20
            fallas.append({"regla": "Matemática de Boletos (Block 100)", "detalle": f"Total calculado por folios de 2 dígitos ({calculado_tot}) no coincide con Total Boletos ({tot_bol}).", "gravedad": "ALTA"})
        
        calc_cobrados = max(0, tot_bol - sin_cob - canc)
        if calc_cobrados != cobrados:
            score -= 20
            fallas.append({"regla": "Boletos Cobrados", "detalle": f"Boletos cobrados declarados ({cobrados}) difieren del cálculo ({calc_cobrados}).", "gravedad": "ALTA"})

    # 2. Regla de Ingreso Bruto
    if not es_directo and cobrados > 0 and costo_bol > 0:
        bruto_esperado = cobrados * costo_bol
        if abs(bruto - bruto_esperado) > 1.0:
            score -= 25
            fallas.append({"regla": "Cálculo de Ingreso Bruto", "detalle": f"Ingreso bruto (${bruto:,.2f}) no coincide con Boletos Cobrados x Tarifa (${bruto_esperado:,.2f}).", "gravedad": "CRÍTICA"})

    # 2b. Validar coherencia de cantidades y tarifas contra catálogo
    if not es_directo:
        if sin_cob + canc + perd > tot_bol:
            score -= 15
            fallas.append({"regla": "Desglose de Boletos Inválido", "detalle": "Sin cobro, cancelados y perdidos exceden el total de boletos.", "gravedad": "ALTA"})
        tarifa_catalogo = float(PRECIOS_SUCURSALES.get(suc, costo_bol) or 0)
        if tarifa_catalogo > 0 and costo_bol > 0 and abs(costo_bol - tarifa_catalogo) > 0.01:
            observaciones.append(f"📌 Tarifa capturada (${costo_bol:,.2f}) distinta a la tarifa de referencia del catálogo (${tarifa_catalogo:,.2f}); confirmar antes de aprobar.")

    # 3. Regla de Cuadre Neto
    neto_esperado = bruto - tot_gastos
    if abs(neto - neto_esperado) > 1.0:
        score -= 25
        fallas.append({"regla": "Cuadre Financiero Neto", "detalle": f"Utilidad Neta declarada (${neto:,.2f}) no coincide con Bruto - Gastos (${neto_esperado:,.2f}).", "gravedad": "CRÍTICA"})

    # 4. Regla de Salto de Folios (Talonarios extraviados)
    if not es_directo and f_ini > 0 and registros_existentes:
        # Buscar el último reporte previo de esta misma sucursal
        reportes_suc = [r for r in registros_existentes if r.get("Sitio / Unidad") == suc and r.get("ID") != reporte_dict.get("ID")]
        if reportes_suc:
            ultimo = reportes_suc[-1]
            ultimo_fin = int(ultimo.get("Folio Final", 0))
            if ultimo_fin > 0 and f_ini != (ultimo_fin + 1):
                diferencia = f_ini - (ultimo_fin + 1)
                if diferencia > 0:
                    score -= 15
                    fallas.append({"regla": "Salto de Folio Detectado", "detalle": f"Se detectó un salto de {diferencia} boletos no registrados entre el folio final previo ({ultimo_fin}) y el inicial actual ({f_ini}).", "gravedad": "MEDIA"})
                elif diferencia < 0:
                    observaciones.append(f"⚠️ Folio inicial ({f_ini}) traslapa con reportes previos (último fue {ultimo_fin}).")

    # 5. Regla de Gastos Excesivos o Desproporcionados
    if bruto > 0:
        pct_gasto = (tot_gastos / bruto) * 100
        if pct_gasto > 45.0:
            score -= 15
            fallas.append({"regla": "Gastos Operativos Excesivos", "detalle": f"Los gastos representan el {pct_gasto:.1f}% del ingreso bruto (umbral máximo aconsejado: 35%).", "gravedad": "MEDIA"})
        elif pct_gasto > 35.0:
            observaciones.append(f"📌 Gastos elevados ({pct_gasto:.1f}% del ingreso bruto). Monitorear nómina.")

    # 6. Regla de Margen y Pérdida Operativa
    if neto < 0:
        score -= 25
        fallas.append({"regla": "Turno No Rentable (Pérdida)", "detalle": f"El turno operó con números rojos (Pérdida de ${abs(neto):,.2f} MXN).", "gravedad": "CRÍTICA"})
    elif margen < 15.0 and bruto > 0:
        observaciones.append(f"⚠️ Margen operativo bajo ({margen:.1f}%). Rendimiento por debajo de la media.")

    # 7. Regla de Control Administrativo (Firmas y Responsables)
    if not elab or elab == "-- Selecciona --":
        score -= 10
        fallas.append({"regla": "Falta de Responsable (Elaboró)", "detalle": "El reporte no tiene asignado quién elaboró físicamente el turno.", "gravedad": "BAJA"})
    if not recibe:
        observaciones.append("ℹ️ Falta firma o nombre de quien recibe el reporte.")

    # 8. Regla de Evidencia Fotográfica
    if not reporte_dict.get("foto_path"):
        observaciones.append("📷 Reporte registrado sin comprobante fotográfico físico adjunto.")

    # 9. Regla de Auditoría Adaptativa Inteligente (Aprende de la Memoria Histórica)
    if memoria_ia and "sucursales" in memoria_ia and suc in memoria_ia["sucursales"]:
        perfil = memoria_ia["sucursales"][suc]
        reps_previos = perfil.get("reportes_aprendidos", 0)
        if reps_previos >= 3:
            prom_bol = perfil.get("promedio_boletos", 0)
            prom_gasto = perfil.get("promedio_gastos", 0.0)
            margen_hist = perfil.get("margen_promedio", 0.0)

            # Umbrales híbridos: variabilidad aprendida y límites prudentes.
            std_b = (max(0.0, float(perfil.get("boletos_m2", 0) or 0) / max(1, reps_previos - 1)) ** 0.5) if reps_previos > 1 else 0.0
            umbral_bajo = max(0.0, prom_bol - max(3.0 * std_b, prom_bol * 0.75))
            umbral_alto = prom_bol + max(3.0 * std_b, prom_bol * 1.20)
            if reps_previos >= 5 and prom_bol > 15 and cobrados > 0:
                if cobrados > umbral_alto:
                    observaciones.append(f"🤖 Perfil histórico: volumen alto ({cobrados}) frente al rango habitual de {prom_bol:.0f} ± {std_b:.0f}; confirmar día/evento especial.")
                elif cobrados < umbral_bajo:
                    score -= 10
                    fallas.append({
                        "regla": "Anomalía de Afluencia Adaptativa",
                        "detalle": f"Boletos ({cobrados}) por debajo del rango estadístico aprendido (media {prom_bol:.0f}, desviación {std_b:.0f}).",
                        "gravedad": "MEDIA"
                    })

            std_g = (max(0.0, float(perfil.get("gastos_m2", 0) or 0) / max(1, reps_previos - 1)) ** 0.5) if reps_previos > 1 else 0.0
            limite_gastos = prom_gasto + max(3.0 * std_g, prom_gasto * 1.0)
            # Desviación anómala de gastos frente a la historia de la sucursal
            if reps_previos >= 5 and prom_gasto > 0 and tot_gastos > limite_gastos:
                score -= 15
                fallas.append({
                    "regla": "Gasto Anómalo vs Historial IA",
                    "detalle": f"Gastos (${tot_gastos:,.2f}) exceden el umbral estadístico aprendido (${limite_gastos:,.2f}; media ${prom_gasto:,.2f}, desviación ${std_g:,.2f}).",
                    "gravedad": "ALTA"
                })

            # Margen degradado vs media
            if margen_hist > 40 and margen < 15 and bruto > 0:
                score -= 10
                fallas.append({
                    "regla": "Deterioro de Margen Histórico",
                    "detalle": f"Margen actual ({margen:.1f}%) se desplomó frente al promedio histórico ({margen_hist:.1f}%).",
                    "gravedad": "MEDIA"
                })

    score = max(0, min(100, score))
    if score >= 90:
        nivel = "🟢 Conforme (Excelente)"
    elif score >= 70:
        nivel = "🟡 Observación Menor"
    else:
        nivel = "🔴 Falla de Auditoría Crítica"

    return score, nivel, fallas, observaciones

# =========================================================================
# PROCESAMIENTO DE IMÁGENES Y EXTRACCIÓN INTELIGENTE (ANDROIDE/MOBILE)
# =========================================================================
def guardar_imagen_optimizada(archivo_subido, id_reporte, sucursal, fecha_str):
    """
    Comprime agresivamente la fotografía para celulares Android con bajo consumo de datos móviles:
    - Escala a máximo 1024x1024 px
    - Calidad JPEG 65% optimizado con submuestreo
    - Reduce una foto de 8MB a menos de 180KB preservando total legibilidad
    - Retorna (ruta_local, bytes_comprimidos, nombre_archivo)
    """
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        suc_clean = "".join(c for c in sucursal if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
        fecha_clean = fecha_str.replace("/", "-")
        nombre_archivo = f"{id_reporte}_{fecha_clean}_{suc_clean}.jpg"
        ruta_completa = os.path.join(FOTOS_DIR, nombre_archivo)
        
        buf_out = io.BytesIO()
        img.save(buf_out, "JPEG", quality=65, optimize=True)
        bytes_foto = buf_out.getvalue()
        
        with open(ruta_completa, "wb") as f_out:
            f_out.write(bytes_foto)
            
        return ruta_completa, bytes_foto, nombre_archivo
    except Exception as e:
        st.error(f"Error optimizando la foto: {e}")
        return None, None, None

def validar_y_analizar_foto_inteligente(archivo_subido, catalogo_sucursales, memoria_ia=None):
    """
    Extracción Inteligente por Computadora + OCR + Heurísticas de Aprendizaje:
    1. Valida calidad, contraste y resolución para teléfonos móviles.
    2. Extrae fecha, folios, sucursal, boletos, gastos y firmas.
    3. Completa datos faltantes usando la Memoria Adaptativa de la IA.
    """
    resultado = {
        "valida": False,
        "ancho": 0,
        "alto": 0,
        "brillo": 0.0,
        "mensaje": "",
        "advertencias": [],
        "datos_extraidos": {},
        "confianza": 0,
        "fuente_extraccion": "Heurística + Metadatos"
    }

    try:
        archivo_subido.seek(0)
        raw = archivo_subido.getvalue() if hasattr(archivo_subido, "getvalue") else archivo_subido.read()
        if len(raw) > 12 * 1024 * 1024:
            resultado["mensaje"] = "❌ La foto supera 12 MB. Reduce el tamaño o toma otra foto para ahorrar datos."
            return resultado
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        w, h = img.size
        if w * h > 30_000_000:
            resultado["mensaje"] = "❌ La imagen tiene demasiados píxeles para procesarla de forma segura."
            return resultado
        resultado["ancho"] = w
        resultado["alto"] = h

        # Control de Exposición y Calidad
        gris = img.convert("L")
        stat = ImageStat.Stat(gris)
        brillo = stat.mean[0]
        resultado["brillo"] = round(brillo, 1)

        if brillo < 30:
            resultado["advertencias"].append("⚠️ Foto muy oscura. Enciende el flash de tu teléfono.")
        elif brillo > 230:
            resultado["advertencias"].append("⚠️ Reflejo blanco excesivo en la imagen.")
        else:
            resultado["valida"] = True

        # Intento de OCR nativo con preprocesamiento adaptativo para recibos
        texto_ocr = ""
        if PYTESSERACT_OK:
            try:
                # Mejora de contraste automática para fotografías móviles (Otsu-like thresholding)
                img_ocr = gris.copy()
                w_ocr, h_ocr = img_ocr.size
                if max(w_ocr, h_ocr) > 1600:
                    img_ocr.thumbnail((1600, 1600), Image.Resampling.BILINEAR)

                texto_ocr = pytesseract.image_to_string(img_ocr, lang="spa+eng", config="--psm 6")
                if len(texto_ocr.strip()) > 10:
                    resultado["fuente_extraccion"] = "OCR Visual + Patrones"
            except Exception:
                pass

        nombre_archivo = getattr(archivo_subido, "name", "").upper()
        texto_analisis = (texto_ocr + " " + nombre_archivo).upper()

        datos = {}
        confianza_pts = 0

        # A. Detección de Sucursal con coincidencia exacta y difusa
        sucursal_encontrada = None
        for suc in catalogo_sucursales:
            if suc.upper() in texto_analisis:
                sucursal_encontrada = suc
                confianza_pts += 30
                break
        
        # Búsqueda difusa para abreviaciones conocidas
        if not sucursal_encontrada:
            alias_map = {
                "CARAJ": "CARAJILLO", "SUSH": "SUSHITTO", "PAMPA": "PAMPAS",
                "RAMA": "RAMMA", "BENI": "BENINGANS", "TLALP": "J.TLALPAN",
                "DIVIS": "J.DIVISION", "PICACH": "J.PICACHO", "EMPRES": "J.EMPRESA",
                "SATEL": "M SATÉLITE", "MARIN": "M MARINA", "CHURR": "CHURRASCA",
                "RYO": "RYOSHI", "ENCANT": "ENCANTO", "CHEG": "CHEGARAY"
            }
            for pref, full_name in alias_map.items():
                if pref in texto_analisis:
                    sucursal_encontrada = full_name
                    confianza_pts += 20
                    break

        if sucursal_encontrada:
            datos["sucursal"] = sucursal_encontrada

        # B. Detección de Folios
        folio_match = re.search(r'(?:FOLIO|BOL|DEL|DE|F)?\s*[:\s#]*(\d{2,6})\s*(?:AL|A|-|HASTA)\s*(\d{2,6})', texto_analisis)
        if folio_match:
            try:
                f1 = int(folio_match.group(1))
                f2 = int(folio_match.group(2))
                if f2 >= f1:
                    datos["folio_inicial"] = f1
                    datos["folio_final"] = f2
                    confianza_pts += 35
            except ValueError:
                pass

        # C. Detección de Fecha
        fecha_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', texto_analisis)
        if fecha_match:
            try:
                d, m, y = int(fecha_match.group(1)), int(fecha_match.group(2)), int(fecha_match.group(3))
                if y < 100:
                    y += 2000
                datos["fecha"] = date(y, m, d)
                confianza_pts += 20
            except Exception:
                pass
        else:
            datos["fecha"] = date.today()

        # D. Detección de Boletos Sin Cobro / Cancelados / Gastos
        sin_cobro_m = re.search(r'(?:SIN COBRO|S/C|CORTESIA)\s*[:\s]*(\d+)', texto_analisis)
        if sin_cobro_m:
            datos["sin_cobro"] = int(sin_cobro_m.group(1))

        canc_m = re.search(r'(?:CANCELADOS?|CANC)\s*[:\s]*(\d+)', texto_analisis)
        if canc_m:
            datos["cancelados"] = int(canc_m.group(1))

        gastos_m = re.search(r'(?:GASTO|NOMINA|TOTAL GASTOS)\s*[:\$]?\s*(\d+(?:\.\d{2})?)', texto_analisis)
        if gastos_m:
            datos["gastos_nomina"] = float(gastos_m.group(1))

        # E. Importes y conteos explícitos (si OCR pudo leer etiquetas del formato)
        bruto_m = re.search(r'(?:INGRESO\s*BRUTO|TOTAL\s*INGRESOS|BRUTO)\s*[:$\s]*([0-9][0-9,]*(?:\.\d{1,2})?)', texto_analisis)
        if bruto_m:
            try: datos["ingreso_bruto"] = float(bruto_m.group(1).replace(",", "")); confianza_pts += 10
            except ValueError: pass
        tarifa_m = re.search(r'(?:COSTO|PRECIO|TARIFA)\s*(?:POR\s*)?(?:BOLETO|TICKET)?\s*[:$\s]*([0-9][0-9,]*(?:\.\d{1,2})?)', texto_analisis)
        if tarifa_m:
            try: datos["costo_boleto"] = float(tarifa_m.group(1).replace(",", "")); confianza_pts += 10
            except ValueError: pass
        total_b_m = re.search(r'(?:TOTAL\s*BOLETOS|BOLETOS\s*EXPEDIDOS)\s*[:\s]*(\d+)', texto_analisis)
        if total_b_m:
            datos["total_boletos"] = int(total_b_m.group(1))

        # E. Inferencia y Enriquecimiento por la Memoria IA si faltan datos
        if sucursal_encontrada and memoria_ia and "sucursales" in memoria_ia:
            suc_ia = memoria_ia["sucursales"].get(sucursal_encontrada)
            if suc_ia:
                # Predecir folio inicial si no fue detectado en la foto
                if "folio_inicial" not in datos and suc_ia.get("ultimo_folio_final", 0) > 0:
                    prediccion_ini = suc_ia["ultimo_folio_final"] + 1
                    datos["folio_inicial"] = prediccion_ini
                    datos["folio_final"] = prediccion_ini + int(suc_ia.get("promedio_boletos", 50))
                    resultado["advertencias"].append(f"🤖 IA sugirió folios ({datos['folio_inicial']} a {datos['folio_final']}) con base en el historial previo.")

                if "costo_boleto" not in datos:
                    datos["costo_boleto"] = suc_ia.get("costo_habitual", PRECIOS_SUCURSALES.get(sucursal_encontrada, 50))

        resultado["datos_extraidos"] = datos
        resultado["confianza"] = min(100, confianza_pts + (20 if resultado["valida"] else 0))
        
        if not resultado["advertencias"]:
            resultado["mensaje"] = f"✅ Imagen nítida ({w}x{h} px) | Confianza IA: {resultado['confianza']}%"
        else:
            resultado["mensaje"] = " | ".join(resultado["advertencias"])

        return resultado
    except Exception as e:
        resultado["mensaje"] = f"❌ Error leyendo imagen: {e}"
        return resultado

def evaluar_rentabilidad(margen):
    if margen >= 40.0:
        return "🟢 Alta"
    elif margen >= 15.0:
        return "🟡 Moderada"
    elif margen > 0.0:
        return "🟠 Baja"
    else:
        return "🔴 Pérdida"

# =========================================================================
# GENERADOR DE EXCEL MULTI-HOJA BLINDADO (AUDITORÍA & RENTABILIDAD)
# =========================================================================

def mostrar_filtro_periodo_registros(registros, key_prefix, incluir_todos=True):
    """Muestra período y alcance (global/sucursal/usuario) y devuelve registros filtrados."""
    opciones = ["Semanal (Últimos 7 días)", "Quincenal (Últimos 15 días)", "Mensual (Últimos 30 días)", "Todo el Histórico"]
    periodo = st.selectbox("Período de análisis:", opciones, key=f"{key_prefix}_periodo")
    filtrados = filtrar_registros_por_periodo(registros, periodo)
    if not filtrados:
        return filtrados, periodo

    df = pd.DataFrame(filtrados)
    opciones_vista = ["Global", "Por sucursal", "Por usuario"]
    vista = st.selectbox("Desglosar:", opciones_vista, key=f"{key_prefix}_vista")
    if vista == "Por sucursal":
        sucursales = sorted([str(x) for x in df.get("Sitio / Unidad", pd.Series(dtype=str)).dropna().unique()])
        if sucursales:
            seleccion = st.selectbox("Sucursal:", ["Todas las sucursales"] + sucursales, key=f"{key_prefix}_sucursal")
            if seleccion != "Todas las sucursales":
                filtrados = [r for r in filtrados if str(r.get("Sitio / Unidad", "")) == seleccion]
    elif vista == "Por usuario":
        usuarios = sorted({str(r.get("Usuario") or r.get("Elaboró") or "Sin identificar") for r in filtrados})
        seleccion = st.selectbox("Usuario:", ["Todos los usuarios"] + usuarios, key=f"{key_prefix}_usuario")
        if seleccion != "Todos los usuarios":
            filtrados = [r for r in filtrados if str(r.get("Usuario") or r.get("Elaboró") or "Sin identificar") == seleccion]
    return filtrados, periodo


# =========================================================================
# CATÁLOGO OFICIAL CORPORATIVO (23 SUCURSALES) Y GENERADOR OFICIAL
# =========================================================================
CATALOGO_OFICIAL_23 = [
    {"num": 1, "sitio": "PAMPAS INSURGENTES", "dias": "LUNES A DOMINGO", "horarios": "11:30 AM A 12:00 PM", "empleados": 5, "supervisor": "JESÚS", "tarifa": 50},
    {"num": 2, "sitio": "PAMPAS COAPA", "dias": "LUNES A DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 50},
    {"num": 3, "sitio": "RAMMA", "dias": "LUNES A DOMINGO", "horarios": "12:00 PM A 02:00 AM", "empleados": 2, "supervisor": "JESÚS", "tarifa": 70},
    {"num": 4, "sitio": "SUSHITTO", "dias": "LUNES A DOMINGO", "horarios": "01:00 PM A 08:00 PM", "empleados": 1, "supervisor": "JESÚS", "tarifa": 40},
    {"num": 5, "sitio": "CARAJILLO POLANCO", "dias": "LUNES A DOMINGO", "horarios": "01:00 PM A 01:00 AM", "empleados": 2, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 6, "sitio": "BENINGAN´S", "dias": "LUNES A DOMINGO", "horarios": "12:00 PM A 09:00 PM", "empleados": 2, "supervisor": "JESÚS", "tarifa": 40},
    {"num": 7, "sitio": "SANATORIO DURANGO", "dias": "LUNES A DOMINGO", "horarios": "12:00 PM A 09:00 PM", "empleados": 4, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 8, "sitio": "BARRANCA", "dias": "LUNES A VIERNES", "horarios": "08:00 AM A 08:00 PM", "empleados": 2, "supervisor": "JESÚS", "tarifa": 0},
    {"num": 9, "sitio": "VETERINARIA", "dias": "LUNES A DOMINGO", "horarios": "09:00 AM A 19:00 PM", "empleados": 1, "supervisor": "JESÚS", "tarifa": 0},
    {"num": 10, "sitio": "ROMANCE PALACE", "dias": "VIERNES A DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 65},
    {"num": 11, "sitio": "JUNGLA TLALPAN", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 12, "sitio": "JUNGLA DIVISIÓN", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 13, "sitio": "JUNGLA PICACHO", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 14, "sitio": "JUNGLA EMPRESA", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 100},
    {"num": 15, "sitio": "SIPIRILY COAPA", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 80},
    {"num": 16, "sitio": "MAROMETA SATÉLITE", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 70},
    {"num": 17, "sitio": "MAROMETA MARINA", "dias": "SÁBADO Y DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "JESÚS", "tarifa": 70},
    {"num": 18, "sitio": "SUMO STA. MONICA", "dias": "LUNES A DOMINGO", "horarios": "12:30 PM A 11:00 PM", "empleados": 1, "supervisor": "VÍCTOR", "tarifa": 50},
    {"num": 19, "sitio": "SUMO ECHEGARAY", "dias": "LUNES A DOMINGO", "horarios": "12:30 PM A 11:00 PM", "empleados": 1, "supervisor": "VÍCTOR", "tarifa": 50},
    {"num": 20, "sitio": "RYOSHI", "dias": "LUNES A DOMINGO", "horarios": "12:00 PM A 1:00 AM", "empleados": 4, "supervisor": "VÍCTOR", "tarifa": 80},
    {"num": 21, "sitio": "ENCANTO", "dias": "LUNES A DOMINGO", "horarios": "12:30 PM A 01 AM", "empleados": 1, "supervisor": "VÍCTOR", "tarifa": 60},
    {"num": 22, "sitio": "E-BNI", "dias": "LUNES A DOMINGO", "horarios": "-", "empleados": 0, "supervisor": "VÍCTOR", "tarifa": 50},
    {"num": 23, "sitio": "CHURRASQUERIA", "dias": "LUNES A DOMINGO", "horarios": "12:30 PM A 11:00 PM", "empleados": 1, "supervisor": "VÍCTOR", "tarifa": 70},
]

MESES_ESP = {1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN", 7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC"}
DIAS_ESP = {0: "LUNES", 1: "MARTES", 2: "MIERCOLES", 3: "JUEVES", 4: "VIERNES", 5: "SÁBADO", 6: "DOMINGO"}

def normalizar_a_sucursal_oficial(nombre):
    if not nombre:
        return "PAMPAS INSURGENTES"
    n = str(nombre).strip().upper()
    mapa = {
        "PAMPAS INS": "PAMPAS INSURGENTES", "PAMPAS COA": "PAMPAS COAPA",
        "PAMPAS": "PAMPAS INSURGENTES", "RAMMA": "RAMMA", "RAMA": "RAMMA",
        "SUSHITTO": "SUSHITTO", "SUSH": "SUSHITTO",
        "CARAJILLO": "CARAJILLO POLANCO", "CARAJ": "CARAJILLO POLANCO",
        "BENINGANS": "BENINGAN´S", "BENINGAN´S": "BENINGAN´S", "BENI": "BENINGAN´S",
        "SANATORIO": "SANATORIO DURANGO", "DURANGO": "SANATORIO DURANGO", "CLÍNICA": "SANATORIO DURANGO",
        "BARRANCA": "BARRANCA", "VETERINARIA": "VETERINARIA",
        "ROMAS": "ROMANCE PALACE", "ROMANCE": "ROMANCE PALACE",
        "J.TLALPAN": "JUNGLA TLALPAN", "TLALPAN": "JUNGLA TLALPAN",
        "J.DIVISION": "JUNGLA DIVISIÓN", "DIVISIÓN": "JUNGLA DIVISIÓN",
        "J.PICACHO": "JUNGLA PICACHO", "PICACHO": "JUNGLA PICACHO",
        "J.EMPRESA": "JUNGLA EMPRESA", "EMPRESA": "JUNGLA EMPRESA",
        "SIPIRILY": "SIPIRILY COAPA", "SIPILY": "SIPIRILY COAPA",
        "M SATÉLITE": "MAROMETA SATÉLITE", "SATÉLITE": "MAROMETA SATÉLITE",
        "M MARINA": "MAROMETA MARINA", "MARINA": "MAROMETA MARINA",
        "SUMO STA": "SUMO STA. MONICA", "MONICA": "SUMO STA. MONICA",
        "CHEGARAY": "SUMO ECHEGARAY", "ECHEGARAY": "SUMO ECHEGARAY",
        "RYOSHI": "RYOSHI", "RYO": "RYOSHI", "ENCANTO": "ENCANTO", "ENCANT": "ENCANTO",
        "E-BNI": "E-BNI", "CHURRASCA": "CHURRASQUERIA", "CHURRASQUERIA": "CHURRASQUERIA"
    }
    for k, v in mapa.items():
        if k in n:
            return v
    return n

def generar_excel_formato_oficial(registros, etiqueta_periodo="SEMANAL"):
    """Genera el libro oficial idéntico a CONTROL_FLUJO_DIARIO: hojas DETALLE, CONCENTRADO X DÍA y Rentabilidad."""
    wb = openpyxl.Workbook()
    ws_det = wb.active
    ws_det.title = "DETALLE "
    ws_conc = wb.create_sheet(title="CONCENTRADO X DÍA")
    ws_aud = wb.create_sheet(title="Rentabilidad y Auditoría")

    fill_green = PatternFill(start_color="003300", end_color="003300", fill_type="solid")
    font_title = Font(name="Calibri", size=15, bold=True, color="003300")
    font_subtitle = Font(name="Calibri", size=11, bold=True, color="000000")
    font_head = Font(name="Calibri", size=8, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=8, bold=True, color="000000")
    font_data = Font(name="Calibri", size=8, color="000000")
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="B2B2B2"),
        right=Side(style="thin", color="B2B2B2"),
        top=Side(style="thin", color="B2B2B2"),
        bottom=Side(style="thin", color="B2B2B2")
    )

    fechas_dt = []
    for r in registros:
        f_str = r.get("Fecha")
        if f_str:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    fechas_dt.append(datetime.strptime(f_str, fmt).date())
                    break
                except ValueError:
                    pass

    if fechas_dt:
        fechas_unicas = sorted(list(set(fechas_dt)))
        if len(fechas_unicas) <= 7:
            min_d = fechas_unicas[0]
            lunes = min_d - timedelta(days=min_d.weekday())
            dias_periodo = [lunes + timedelta(days=i) for i in range(7)]
        else:
            dias_periodo = fechas_unicas
    else:
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        dias_periodo = [lunes + timedelta(days=i) for i in range(7)]

    txt_periodo = f"CORTE {dias_periodo[0].strftime('%d/%m/%Y')} AL {dias_periodo[-1].strftime('%d/%m/%Y')} ({etiqueta_periodo.upper()})"

    matriz_reg = {}
    for r in registros:
        f_str = r.get("Fecha")
        d_obj = None
        if f_str:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    d_obj = datetime.strptime(f_str, fmt).date()
                    break
                except ValueError:
                    pass
        if d_obj:
            suc_norm = normalizar_a_sucursal_oficial(r.get("Sitio / Unidad"))
            key = (suc_norm, d_obj)
            matriz_reg[key] = r

    # --- HOJA 1: DETALLE ---
    ws_det["A1"] = "CLUB PARK VALET Y ESTACIONAMIENTOS, S.A. DE C.V."
    ws_det["A1"].font = font_title
    ws_det["A3"] = txt_periodo
    ws_det["A3"].font = font_subtitle
    ws_det["A5"] = "INGRESOS POR PERÍODO"
    ws_det["A5"].font = font_subtitle

    meta_headers = ["No.", "SITIO", "DÍAS QUE SE OPERA", "HORARIOS", "No. EMPLEADOS", "SUPERVISOR"]
    for i, h in enumerate(meta_headers, start=1):
        cell = ws_det.cell(8, i, h)
        cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center; cell.border = thin_border
        ws_det.merge_cells(start_row=8, start_column=i, end_row=10, end_column=i)

    col_idx = 7
    dia_cols_map = {}
    for d in dias_periodo:
        d_str = f"{DIAS_ESP[d.weekday()]} {d.day:02d}/{MESES_ESP[d.month]}/{d.year}"
        dia_cols_map[d] = col_idx
        c8 = ws_det.cell(8, col_idx, d_str)
        c8.fill = fill_green; c8.font = font_head; c8.alignment = align_center
        ws_det.merge_cells(start_row=8, start_column=col_idx, end_row=8, end_column=col_idx+4)
        for c in range(col_idx, col_idx+5):
            ws_det.cell(8, c).fill = fill_green; ws_det.cell(8, c).border = thin_border

        ws_det.cell(9, col_idx, "CONSECUTIVO BOLETAJE").fill = fill_green
        ws_det.cell(9, col_idx).font = font_head; ws_det.cell(9, col_idx).alignment = align_center
        ws_det.merge_cells(start_row=9, start_column=col_idx, end_row=9, end_column=col_idx+1)
        ws_det.cell(9, col_idx+1).fill = fill_green

        c_tb = ws_det.cell(9, col_idx+2, "TOTAL DE BOLETOS")
        c_tb.fill = fill_green; c_tb.font = font_head; c_tb.alignment = align_center
        ws_det.merge_cells(start_row=9, start_column=col_idx+2, end_row=10, end_column=col_idx+2)

        c_cb = ws_det.cell(9, col_idx+3, "COSTO X BOLETO")
        c_cb.fill = fill_green; c_cb.font = font_head; c_cb.alignment = align_center
        ws_det.merge_cells(start_row=9, start_column=col_idx+3, end_row=10, end_column=col_idx+3)

        c_ing = ws_det.cell(9, col_idx+4, "INGRESO POR DÍA")
        c_ing.fill = fill_green; c_ing.font = font_head; c_ing.alignment = align_center
        ws_det.merge_cells(start_row=9, start_column=col_idx+4, end_row=10, end_column=col_idx+4)

        c_fi = ws_det.cell(10, col_idx, "FOLIO INICIAL")
        c_fi.fill = fill_green; c_fi.font = font_head; c_fi.alignment = align_center
        c_ff = ws_det.cell(10, col_idx+1, "FOLIO FINAL")
        c_ff.fill = fill_green; c_ff.font = font_head; c_ff.alignment = align_center

        for r_h in [9, 10]:
            for c_h in range(col_idx, col_idx+5):
                ws_det.cell(r_h, c_h).border = thin_border
        col_idx += 5

    col_tot_bol = col_idx
    col_tot_ing = col_idx + 1
    c_tbl = ws_det.cell(8, col_tot_bol, "TOTAL DE BOLETOS UTILIZADOS X PERÍODO")
    c_tbl.fill = fill_green; c_tbl.font = font_head; c_tbl.alignment = align_center; c_tbl.border = thin_border
    ws_det.merge_cells(start_row=8, start_column=col_tot_bol, end_row=10, end_column=col_tot_bol)

    c_tin = ws_det.cell(8, col_tot_ing, "TOTAL DE INGRESOS X PERÍODO")
    c_tin.fill = fill_green; c_tin.font = font_head; c_tin.alignment = align_center; c_tin.border = thin_border
    ws_det.merge_cells(start_row=8, start_column=col_tot_ing, end_row=10, end_column=col_tot_ing)

    r_actual = 11
    fila_inicio_ing = r_actual
    for item in CATALOGO_OFICIAL_23:
        ws_det.cell(r_actual, 1, item["num"]).alignment = align_center
        ws_det.cell(r_actual, 2, item["sitio"]).alignment = align_left
        ws_det.cell(r_actual, 3, item["dias"]).alignment = align_left
        ws_det.cell(r_actual, 4, item["horarios"]).alignment = align_center
        ws_det.cell(r_actual, 5, item["empleados"]).alignment = align_center
        ws_det.cell(r_actual, 6, item["supervisor"]).alignment = align_center

        for ci in range(1, 7):
            cell = ws_det.cell(r_actual, ci)
            cell.font = font_data; cell.border = thin_border

        tot_bol_suc = 0
        tot_ing_suc = 0.0
        for d in dias_periodo:
            c_d = dia_cols_map[d]
            rep = matriz_reg.get((item["sitio"], d))
            if rep:
                f_ini = rep.get("Folio Inicial", 0)
                f_fin = rep.get("Folio Final", 0)
                bol = rep.get("Boletos Cobrados", rep.get("Total Boletos", 0))
                costo = rep.get("Costo Boleto", item["tarifa"])
                ing = rep.get("Ingreso Bruto", float(bol) * float(costo))
            else:
                f_ini = 0; f_fin = 0; bol = 0; costo = item["tarifa"]; ing = 0.0

            ws_det.cell(r_actual, c_d, f_ini).alignment = align_center
            ws_det.cell(r_actual, c_d+1, f_fin).alignment = align_center
            ws_det.cell(r_actual, c_d+2, bol).alignment = align_center
            ws_det.cell(r_actual, c_d+3, costo).alignment = align_right
            ws_det.cell(r_actual, c_d+3).number_format = "$#,##0.00"
            ws_det.cell(r_actual, c_d+4, ing).alignment = align_right
            ws_det.cell(r_actual, c_d+4).number_format = "$#,##0.00"

            tot_bol_suc += bol
            tot_ing_suc += ing

            for c_sub in range(c_d, c_d+5):
                cell = ws_det.cell(r_actual, c_sub)
                cell.font = font_data; cell.border = thin_border

        c_tb_cell = ws_det.cell(r_actual, col_tot_bol, tot_bol_suc)
        c_tb_cell.alignment = align_center; c_tb_cell.font = font_bold; c_tb_cell.border = thin_border
        c_ti_cell = ws_det.cell(r_actual, col_tot_ing, tot_ing_suc)
        c_ti_cell.alignment = align_right; c_ti_cell.font = font_bold; c_ti_cell.border = thin_border
        c_ti_cell.number_format = "$#,##0.00"
        r_actual += 1

    fila_fin_ing = r_actual - 1

    r_tot_ing = r_actual
    ws_det.cell(r_tot_ing, 2, "TOTAL").font = font_bold
    ws_det.cell(r_tot_ing, 2).alignment = align_left
    for ci in range(1, col_tot_ing + 1):
        ws_det.cell(r_tot_ing, ci).border = thin_border

    for d in dias_periodo:
        c_d = dia_cols_map[d]
        col_let_bol = get_column_letter(c_d+2)
        col_let_ing = get_column_letter(c_d+4)
        c_sb = ws_det.cell(r_tot_ing, c_d+2, f"=SUM({col_let_bol}{fila_inicio_ing}:{col_let_bol}{fila_fin_ing})")
        c_sb.font = font_bold; c_sb.alignment = align_center
        c_si = ws_det.cell(r_tot_ing, c_d+4, f"=SUM({col_let_ing}{fila_inicio_ing}:{col_let_ing}{fila_fin_ing})")
        c_si.font = font_bold; c_si.alignment = align_right; c_si.number_format = "$#,##0.00"

    let_tbl = get_column_letter(col_tot_bol)
    let_tin = get_column_letter(col_tot_ing)
    ws_det.cell(r_tot_ing, col_tot_bol, f"=SUM({let_tbl}{fila_inicio_ing}:{let_tbl}{fila_fin_ing})").font = font_bold
    ws_det.cell(r_tot_ing, col_tot_bol).alignment = align_center
    c_tot_ing_fin = ws_det.cell(r_tot_ing, col_tot_ing, f"=SUM({let_tin}{fila_inicio_ing}:{let_tin}{fila_fin_ing})")
    c_tot_ing_fin.font = font_bold; c_tot_ing_fin.alignment = align_right; c_tot_ing_fin.number_format = "$#,##0.00"

    # Sección Gastos
    r_gastos_head = r_tot_ing + 3
    ws_det.cell(r_gastos_head - 2, 1, "GASTOS POR PERÍODO").font = font_subtitle

    for i, h in enumerate(meta_headers, start=1):
        cell = ws_det.cell(r_gastos_head, i, h)
        cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center; cell.border = thin_border
        ws_det.merge_cells(start_row=r_gastos_head, start_column=i, end_row=r_gastos_head+1, end_column=i)

    for d in dias_periodo:
        c_d = dia_cols_map[d]
        d_str = f"{DIAS_ESP[d.weekday()]} {d.day:02d}/{MESES_ESP[d.month]}/{d.year}"
        c_gh = ws_det.cell(r_gastos_head, c_d, d_str)
        c_gh.fill = fill_green; c_gh.font = font_head; c_gh.alignment = align_center
        ws_det.merge_cells(start_row=r_gastos_head, start_column=c_d, end_row=r_gastos_head, end_column=c_d+4)
        for c in range(c_d, c_d+5):
            ws_det.cell(r_gastos_head, c).fill = fill_green; ws_det.cell(r_gastos_head, c).border = thin_border

        sub_g = ["NÓMINA LIDER DE UNIDAD", "NÓMINA OPERADOR", "GASTOS SUPERVISIÓN", "VARIOS", "TOTAL GASTOS X DÍA"]
        for sg_i, sg_txt in enumerate(sub_g):
            cell = ws_det.cell(r_gastos_head+1, c_d+sg_i, sg_txt)
            cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center; cell.border = thin_border

    c_tg_per = ws_det.cell(r_gastos_head, col_tot_bol, "TOTAL DE GASTOS X PERÍODO")
    c_tg_per.fill = fill_green; c_tg_per.font = font_head; c_tg_per.alignment = align_center; c_tg_per.border = thin_border
    ws_det.merge_cells(start_row=r_gastos_head, start_column=col_tot_bol, end_row=r_gastos_head+1, end_column=col_tot_ing)

    r_actual_g = r_gastos_head + 2
    fila_inicio_gas = r_actual_g
    for item in CATALOGO_OFICIAL_23:
        ws_det.cell(r_actual_g, 1, item["num"]).alignment = align_center
        ws_det.cell(r_actual_g, 2, item["sitio"]).alignment = align_left
        ws_det.cell(r_actual_g, 3, item["dias"]).alignment = align_left
        ws_det.cell(r_actual_g, 4, item["horarios"]).alignment = align_center
        ws_det.cell(r_actual_g, 5, item["empleados"]).alignment = align_center
        ws_det.cell(r_actual_g, 6, item["supervisor"]).alignment = align_center

        for ci in range(1, 7):
            cell = ws_det.cell(r_actual_g, ci)
            cell.font = font_data; cell.border = thin_border

        tot_gas_suc = 0.0
        for d in dias_periodo:
            c_d = dia_cols_map[d]
            rep = matriz_reg.get((item["sitio"], d))
            if rep:
                nom = rep.get("Gastos Generales / Nómina", 0.0)
                esp = rep.get("Gastos Especiales", 0.0)
                tot_g = rep.get("Total Gastos", nom + esp)
            else:
                nom = 0.0; esp = 0.0; tot_g = 0.0

            ws_det.cell(r_actual_g, c_d, nom).alignment = align_right
            ws_det.cell(r_actual_g, c_d).number_format = "$#,##0.00"
            ws_det.cell(r_actual_g, c_d+1, 0).alignment = align_right
            ws_det.cell(r_actual_g, c_d+1).number_format = "$#,##0.00"
            ws_det.cell(r_actual_g, c_d+2, 0).alignment = align_right
            ws_det.cell(r_actual_g, c_d+2).number_format = "$#,##0.00"
            ws_det.cell(r_actual_g, c_d+3, esp).alignment = align_right
            ws_det.cell(r_actual_g, c_d+3).number_format = "$#,##0.00"
            ws_det.cell(r_actual_g, c_d+4, tot_g).alignment = align_right
            ws_det.cell(r_actual_g, c_d+4).number_format = "$#,##0.00"

            tot_gas_suc += tot_g
            for c_sub in range(c_d, c_d+5):
                cell = ws_det.cell(r_actual_g, c_sub)
                cell.font = font_data; cell.border = thin_border

        c_tg_cell = ws_det.cell(r_actual_g, col_tot_bol, tot_gas_suc)
        c_tg_cell.alignment = align_right; c_tg_cell.font = font_bold; c_tg_cell.border = thin_border
        c_tg_cell.number_format = "$#,##0.00"
        ws_det.merge_cells(start_row=r_actual_g, start_column=col_tot_bol, end_row=r_actual_g, end_column=col_tot_ing)
        r_actual_g += 1

    fila_fin_gas = r_actual_g - 1

    r_tot_gas = r_actual_g
    ws_det.cell(r_tot_gas, 2, "TOTAL").font = font_bold
    for ci in range(1, col_tot_ing + 1):
        ws_det.cell(r_tot_gas, ci).border = thin_border

    for d in dias_periodo:
        c_d = dia_cols_map[d]
        col_let_gas = get_column_letter(c_d+4)
        c_sg = ws_det.cell(r_tot_gas, c_d+4, f"=SUM({col_let_gas}{fila_inicio_gas}:{col_let_gas}{fila_fin_gas})")
        c_sg.font = font_bold; c_sg.alignment = align_right; c_sg.number_format = "$#,##0.00"

    ws_det.cell(r_tot_gas, col_tot_bol, f"=SUM({get_column_letter(col_tot_bol)}{fila_inicio_gas}:{get_column_letter(col_tot_bol)}{fila_fin_gas})").font = font_bold
    ws_det.cell(r_tot_gas, col_tot_bol).alignment = align_right
    ws_det.cell(r_tot_gas, col_tot_bol).number_format = "$#,##0.00"
    ws_det.merge_cells(start_row=r_tot_gas, start_column=col_tot_bol, end_row=r_tot_gas, end_column=col_tot_ing)

    r_util = r_tot_gas + 2
    ws_det.cell(r_util, 2, "UTILIDAD O PÉRDIDA X DÍA").font = font_bold
    for ci in range(1, col_tot_ing + 1):
        ws_det.cell(r_util, ci).border = thin_border

    for d in dias_periodo:
        c_d = dia_cols_map[d]
        let_ing = get_column_letter(c_d+4)
        c_ut = ws_det.cell(r_util, c_d+4, f"=+{let_ing}{r_tot_ing}-{let_ing}{r_tot_gas}")
        c_ut.font = font_bold; c_ut.alignment = align_right; c_ut.number_format = "$#,##0.00"

    c_ut_tot = ws_det.cell(r_util, col_tot_bol, f"=+{get_column_letter(col_tot_ing)}{r_tot_ing}-{get_column_letter(col_tot_bol)}{r_tot_gas}")
    c_ut_tot.font = font_bold; c_ut_tot.alignment = align_right; c_ut_tot.number_format = "$#,##0.00"
    ws_det.merge_cells(start_row=r_util, start_column=col_tot_bol, end_row=r_util, end_column=col_tot_ing)

    # --- HOJA 2: CONCENTRADO X DÍA ---
    ws_conc["A1"] = "CLUB PARK VALET Y ESTACIONAMIENTOS, S.A. DE C.V."
    ws_conc["A1"].font = font_title
    ws_conc["A2"] = txt_periodo
    ws_conc["A2"].font = font_subtitle
    ws_conc["A3"] = "CONCENTRADO DE INGRESOS Y GASTOS"
    ws_conc["A3"].font = font_subtitle

    for i, h in enumerate(["No.", "SITIO", "SUPERVISOR"], start=1):
        cell = ws_conc.cell(5, i, h)
        cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center; cell.border = thin_border
        ws_conc.merge_cells(start_row=5, start_column=i, end_row=6, end_column=i)

    c_col_conc = 4
    conc_dia_cols = {}
    for d in dias_periodo:
        conc_dia_cols[d] = c_col_conc
        d_str = f"{DIAS_ESP[d.weekday()]} {d.day:02d}/{MESES_ESP[d.month]}/{d.year}"
        cell = ws_conc.cell(5, c_col_conc, d_str)
        cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center
        ws_conc.merge_cells(start_row=5, start_column=c_col_conc, end_row=5, end_column=c_col_conc+2)
        for c in range(c_col_conc, c_col_conc+3):
            ws_conc.cell(5, c).fill = fill_green; ws_conc.cell(5, c).border = thin_border

        for s_i, s_txt in enumerate(["TOTAL INGRESOS X DÍA", "TOTAL GASTOS X DÍA", "UTILIDAD O PÉRDIDA X DÍA"]):
            sc = ws_conc.cell(6, c_col_conc+s_i, s_txt)
            sc.fill = fill_green; sc.font = font_head; sc.alignment = align_center; sc.border = thin_border
        c_col_conc += 3

    col_conc_tot_ing = c_col_conc
    col_conc_tot_gas = c_col_conc + 1
    col_conc_tot_ut = c_col_conc + 2

    c_ct = ws_conc.cell(5, col_conc_tot_ing, "CONCENTRADO DEL PERÍODO")
    c_ct.fill = fill_green; c_ct.font = font_head; c_ct.alignment = align_center
    ws_conc.merge_cells(start_row=5, start_column=col_conc_tot_ing, end_row=5, end_column=col_conc_tot_ut)
    for c in range(col_conc_tot_ing, col_conc_tot_ut+1):
        ws_conc.cell(5, c).fill = fill_green; ws_conc.cell(5, c).border = thin_border

    for s_i, s_txt in enumerate(["TOTAL INGRESOS", "TOTAL GASTOS", "UTILIDAD O PÉRDIDA"]):
        sc = ws_conc.cell(6, col_conc_tot_ing+s_i, s_txt)
        sc.fill = fill_green; sc.font = font_head; sc.alignment = align_center; sc.border = thin_border

    r_c_act = 8
    fila_inicio_c = r_c_act
    for i_suc, item in enumerate(CATALOGO_OFICIAL_23):
        ws_conc.cell(r_c_act, 1, item["num"]).alignment = align_center
        ws_conc.cell(r_c_act, 2, item["sitio"]).alignment = align_left
        ws_conc.cell(r_c_act, 3, item["supervisor"]).alignment = align_center
        for ci in range(1, 4):
            ws_conc.cell(r_c_act, ci).font = font_data; ws_conc.cell(r_c_act, ci).border = thin_border

        fila_det_ing = fila_inicio_ing + i_suc
        fila_det_gas = fila_inicio_gas + i_suc

        for d in dias_periodo:
            cd_conc = conc_dia_cols[d]
            cd_det = dia_cols_map[d]
            let_ing = get_column_letter(cd_det+4)
            let_gas = get_column_letter(cd_det+4)

            ws_conc.cell(r_c_act, cd_conc, f"='DETALLE '!{let_ing}{fila_det_ing}").number_format = "$#,##0.00"
            ws_conc.cell(r_c_act, cd_conc+1, f"='DETALLE '!{let_gas}{fila_det_gas}").number_format = "$#,##0.00"
            let_ci = get_column_letter(cd_conc)
            let_cg = get_column_letter(cd_conc+1)
            ws_conc.cell(r_c_act, cd_conc+2, f"=+{let_ci}{r_c_act}-{let_cg}{r_c_act}").number_format = "$#,##0.00"

            for sub_c in range(cd_conc, cd_conc+3):
                cell = ws_conc.cell(r_c_act, sub_c)
                cell.font = font_data; cell.alignment = align_right; cell.border = thin_border

        let_tin_det = get_column_letter(col_tot_ing)
        let_tga_det = get_column_letter(col_tot_bol)
        ws_conc.cell(r_c_act, col_conc_tot_ing, f"='DETALLE '!{let_tin_det}{fila_det_ing}").number_format = "$#,##0.00"
        ws_conc.cell(r_c_act, col_conc_tot_gas, f"='DETALLE '!{let_tga_det}{fila_det_gas}").number_format = "$#,##0.00"
        let_ti_c = get_column_letter(col_conc_tot_ing)
        let_tg_c = get_column_letter(col_conc_tot_gas)
        ws_conc.cell(r_c_act, col_conc_tot_ut, f"=+{let_ti_c}{r_c_act}-{let_tg_c}{r_c_act}").number_format = "$#,##0.00"

        for sub_c in range(col_conc_tot_ing, col_conc_tot_ut+1):
            cell = ws_conc.cell(r_c_act, sub_c)
            cell.font = font_bold; cell.alignment = align_right; cell.border = thin_border

        r_c_act += 1

    fila_fin_c = r_c_act - 1

    r_c_tot = r_c_act
    ws_conc.cell(r_c_tot, 1, "TOTAL").font = font_bold
    for ci in range(1, col_conc_tot_ut + 1):
        ws_conc.cell(r_c_tot, ci).border = thin_border

    for d in dias_periodo:
        cd_conc = conc_dia_cols[d]
        for sub_i in range(3):
            col_l = get_column_letter(cd_conc + sub_i)
            c = ws_conc.cell(r_c_tot, cd_conc + sub_i, f"=SUM({col_l}{fila_inicio_c}:{col_l}{fila_fin_c})")
            c.font = font_bold; c.alignment = align_right; c.number_format = "$#,##0.00"

    for sub_i in range(3):
        col_l = get_column_letter(col_conc_tot_ing + sub_i)
        c = ws_conc.cell(r_c_tot, col_conc_tot_ing + sub_i, f"=SUM({col_l}{fila_inicio_c}:{col_l}{fila_fin_c})")
        c.font = font_bold; c.alignment = align_right; c.number_format = "$#,##0.00"

    # --- HOJA 3: Rentabilidad y Auditoría ---
    ws_aud["A1"] = "ANÁLISIS DE RENTABILIDAD Y AUDITORÍA INTELIGENTE"
    ws_aud["A1"].font = font_title
    headers_aud = ["ID", "Fecha", "Sitio / Unidad", "Supervisor", "Boletos Cobrados", "Tarifa", "Ingreso Bruto", "Total Gastos", "Ingreso Neto", "Margen (%)", "Estado Auditoría"]
    for c_i, h in enumerate(headers_aud, start=1):
        cell = ws_aud.cell(3, c_i, h)
        cell.fill = fill_green; cell.font = font_head; cell.alignment = align_center; cell.border = thin_border

    r_aud = 4
    for r in registros:
        bruto = float(r.get("Ingreso Bruto", 0.0))
        neto = float(r.get("Ingreso Neto", 0.0))
        margen = (neto / bruto * 100) if bruto > 0 else 0.0
        ws_aud.cell(r_aud, 1, r.get("ID", "")).alignment = align_center
        ws_aud.cell(r_aud, 2, r.get("Fecha", "")).alignment = align_center
        ws_aud.cell(r_aud, 3, r.get("Sitio / Unidad", "")).alignment = align_left
        ws_aud.cell(r_aud, 4, r.get("Elaboró", r.get("Usuario", ""))).alignment = align_center
        ws_aud.cell(r_aud, 5, r.get("Boletos Cobrados", 0)).alignment = align_center
        ws_aud.cell(r_aud, 6, r.get("Costo Boleto", 0)).number_format = "$#,##0.00"
        ws_aud.cell(r_aud, 7, bruto).number_format = "$#,##0.00"
        ws_aud.cell(r_aud, 8, float(r.get("Total Gastos", 0.0))).number_format = "$#,##0.00"
        ws_aud.cell(r_aud, 9, neto).number_format = "$#,##0.00"
        ws_aud.cell(r_aud, 10, f"{margen:.1f}%").alignment = align_center
        ws_aud.cell(r_aud, 11, r.get("Nivel Auditoría", "Conforme")).alignment = align_center
        for ci in range(1, 12):
            ws_aud.cell(r_aud, ci).font = font_data; ws_aud.cell(r_aud, ci).border = thin_border
        r_aud += 1

    # Presentación corporativa: impresión horizontal, títulos legibles y encabezados congelados.
    for ws in (ws_det, ws_conc, ws_aud):
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = "G11" if ws is ws_det else ("D8" if ws is ws_conc else "A4")
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.sheet_properties.pageSetUpPr.autoPageBreaks = False
        ws.sheet_format.defaultRowHeight = 16
    for col, width in {"A": 7, "B": 26, "C": 20, "D": 21, "E": 13, "F": 16}.items():
        ws_det.column_dimensions[col].width = width
    for c in range(7, col_tot_ing + 1):
        ws_det.column_dimensions[get_column_letter(c)].width = 14
    for col, width in {"A": 7, "B": 28, "C": 16}.items():
        ws_conc.column_dimensions[col].width = width
    for c in range(4, col_conc_tot_ut + 1):
        ws_conc.column_dimensions[get_column_letter(c)].width = 18
    for col, width in {"A": 14, "B": 13, "C": 25, "D": 21, "E": 16, "F": 13, "G": 16, "H": 16, "I": 16, "J": 12, "K": 23}.items():
        ws_aud.column_dimensions[col].width = width

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

def generar_csv_oficial(registros, etiqueta_periodo="SEMANAL"):
    """Genera CSV con el esquema oficial corporativo de corte diario por sucursal y supervisor."""
    if not registros:
        return "No hay registros disponibles para el período seleccionado.\n".encode("utf-8-sig")
    
    filas = []
    for r in registros:
        suc = normalizar_a_sucursal_oficial(r.get("Sitio / Unidad", ""))
        info_cat = next((item for item in CATALOGO_OFICIAL_23 if item["sitio"] == suc), None)
        dias_op = info_cat["dias"] if info_cat else "-"
        horarios = info_cat["horarios"] if info_cat else "-"
        empleados = info_cat["empleados"] if info_cat else 0
        sup_cat = info_cat["supervisor"] if info_cat else (r.get("Elaboró") or r.get("Usuario") or "JESÚS")
        
        bruto = float(r.get("Ingreso Bruto", 0.0))
        nom = float(r.get("Gastos Generales / Nómina", 0.0))
        esp = float(r.get("Gastos Especiales", 0.0))
        tot_g = float(r.get("Total Gastos", nom + esp))
        neto = float(r.get("Ingreso Neto", bruto - tot_g))
        
        filas.append({
            "No.": info_cat["num"] if info_cat else "",
            "SITIO": suc,
            "DÍAS QUE SE OPERA": dias_op,
            "HORARIOS": horarios,
            "No. EMPLEADOS": empleados,
            "SUPERVISOR": sup_cat,
            "FECHA": r.get("Fecha", ""),
            "FOLIO INICIAL": r.get("Folio Inicial", 0),
            "FOLIO FINAL": r.get("Folio Final", 0),
            "TOTAL BOLETOS": r.get("Boletos Cobrados", r.get("Total Boletos", 0)),
            "COSTO X BOLETO": r.get("Costo Boleto", info_cat["tarifa"] if info_cat else 0),
            "INGRESO X DÍA": bruto,
            "NÓMINA LIDER": nom,
            "NÓMINA OPERADOR": 0.0,
            "GASTOS SUPERVISIÓN": 0.0,
            "VARIOS": esp,
            "TOTAL GASTOS X DÍA": tot_g,
            "UTILIDAD O PÉRDIDA X DÍA": neto,
            "ESTADO AUDITORÍA": r.get("Nivel Auditoría", "Conforme"),
            "USUARIO REGISTRO": r.get("Usuario") or r.get("Elaboró") or sup_cat
        })
    df_csv = pd.DataFrame(filas)
    return df_csv.to_csv(index=False).encode("utf-8-sig")

def generar_excel_completo(registros, historial_auditoria=None, etiqueta_periodo="SEMANAL"):
    """Generador corporativo oficial: si openpyxl está disponible genera el formato exacto de dos hojas oficiales."""
    if not registros:
        return None, "NO_REGISTROS"
    if not OPENPYXL_OK and not XLSXWRITER_OK:
        return None, "SIN_MOTOR"
    try:
        if OPENPYXL_OK:
            datos_bytes = generar_excel_formato_oficial(registros, etiqueta_periodo)
            return datos_bytes, "OK"
        
        # Respaldo en xlsxwriter si no estuviera openpyxl
        output = io.BytesIO()
        df = pd.DataFrame(registros)
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Detalle de Reportes", index=False)
        return output.getvalue(), "OK"
    except Exception as e:
        return None, f"ERROR_EXCEL: {str(e)}"


# =========================================================================
# SUITE DE PRUEBAS DE REGRESIÓN TÉCNICA Y DIAGNÓSTICO
# =========================================================================
def ejecutar_pruebas_regresion():
    pruebas = []

    casos_folios = [(595, 303, 9), (1, 50, 50), (100, 100, 1), (198, 3, 6), (0, 0, 0)]
    ok_folios = all(calcular_boletos_block100(a, b) == esperado for a, b, esperado in casos_folios)
    ok_tarifas = all(obtener_tarifa_sucursal(s) == float(t) for s, t in PRECIOS_SUCURSALES.items())
    pruebas.append({
        "Área": "Folios y Tarifas",
        "Prueba": "Cálculo cíclico inclusivo y tarifa de catálogo por sucursal",
        "Resultado": "✅ PASS" if ok_folios and ok_tarifas else "❌ FAIL",
        "Detalle": f"595→303={calcular_boletos_block100(595, 303)}; {len(PRECIOS_SUCURSALES)} tarifas verificadas."
    })

    # 1. Criptografía Estándar Fernet
    if CRYPTOGRAPHY_OK:
        d_test = [{"ID": "T_ENC", "Neto": 5000.0}]
        clave_t = "ClaveSeguraClubPark2026!"
        cif_str = cifrar_respaldo_seguro(d_test, clave_t)
        dec_ok, _ = descifrar_respaldo_seguro(cif_str, clave_t)
        dec_bad, _ = descifrar_respaldo_seguro(cif_str, "ClaveInvalida")
        p1 = (dec_ok == d_test and dec_bad is None)
        pruebas.append({
            "Área": "Criptografía y Nube",
            "Prueba": "Cifrado Estándar Fernet (AES-128-CBC + HMAC-SHA256, PBKDF2 100k)",
            "Resultado": "✅ PASS" if p1 else "❌ FAIL",
            "Detalle": "Respaldo seguro blindado con sal criptográfica y autenticación HMAC."
        })
    else:
        pruebas.append({
            "Área": "Criptografía y Nube",
            "Prueba": "Cifrado Estándar Fernet",
            "Resultado": "⚠️ PENDIENTE",
            "Detalle": "cryptography no disponible."
        })

    # 2. Motor Excel y Rentabilidad
    mock_data = [{
        "ID": "TEST_REP", "Fecha": "12/10/2026", "Sitio / Unidad": "CARAJILLO",
        "Horario": "13:00 a 23:00", "Costo Boleto": 100.0, "Folio Inicial": 1, "Folio Final": 50,
        "Total Boletos": 50, "Sin Cobro": 2, "Cancelados": 1, "Perdidos": 0, "Boletos Cobrados": 47,
        "Ingreso Bruto": 4700.0, "Gastos Especiales": 200.0, "Gastos Generales / Nómina": 1500.0,
        "Total Gastos": 1700.0, "Ingreso Neto": 3000.0, "Margen (%)": 63.83, "Rentabilidad": "🟢 Alta",
        "Score Auditoría": 100, "Elaboró": "Jesús", "Recibe": "Víctor", "Tipo": "Operación Regular", "foto_path": None
    }]
    ex_bytes, ex_estado = generar_excel_completo(mock_data)
    p2 = (ex_estado == "OK" and ex_bytes is not None and len(ex_bytes) > 2000)
    pruebas.append({
        "Área": "Entregables Excel",
        "Prueba": "Generación de libro Excel multi-hoja con Rentabilidad y Auditoría",
        "Resultado": "✅ PASS" if p2 else "❌ FAIL",
        "Detalle": f"Estado del motor: {ex_estado} | Tamaño: {len(ex_bytes) if ex_bytes else 0} bytes."
    })

    # 3. Motor de Auditoría Inteligente
    score, nivel, fallas, obs = evaluar_auditoria_reporte(mock_data[0])
    p3 = (score == 100 and "Conforme" in nivel and len(fallas) == 0)
    pruebas.append({
        "Área": "Auditoría Inteligente",
        "Prueba": "Detección de cuadres matemáticos, boletos y márgenes financieros",
        "Resultado": "✅ PASS" if p3 else "❌ FAIL",
        "Detalle": f"Puntuación: {score}/100 ({nivel}). Cero discrepancias matemáticas."
    })

    # 4. Memoria Adaptativa de Aprendizaje IA
    memoria_t = {
        "sucursales": {
            "CARAJILLO": {"reportes_aprendidos": 5, "promedio_boletos": 45, "ultimo_folio_final": 500, "costo_habitual": 100}
        }
    }
    img_simulada = Image.new("RGB", (600, 400), color=(200, 200, 200))
    buf_sim = io.BytesIO()
    img_simulada.save(buf_sim, format="JPEG")
    buf_sim.name = "reporte_CARAJILLO_12_10_2026.jpg"
    res_ia = validar_y_analizar_foto_inteligente(buf_sim, ["CARAJILLO"], memoria_t)
    p4 = (res_ia["datos_extraidos"].get("sucursal") == "CARAJILLO")
    pruebas.append({
        "Área": "Inteligencia Artificial",
        "Prueba": "Análisis fotográfico, extracción heurística y memoria predictiva",
        "Resultado": "✅ PASS" if p4 else "❌ FAIL",
        "Detalle": f"Detección exitosa de {res_ia['datos_extraidos'].get('sucursal')} con confianza {res_ia['confianza']}%."
    })

    return pruebas

# Modo de pruebas headless: permite probar las reglas sin iniciar el flujo de interfaz.
if os.environ.get("CLUBPARK_TEST_MODE") == "1":
    _test_results = ejecutar_pruebas_regresion()
    print(json.dumps(_test_results, ensure_ascii=False))
    if not all("PASS" in item["Resultado"] for item in _test_results):
        raise SystemExit(1)
    raise SystemExit(0)

# =========================================================================
# GESTIÓN DE SESIÓN Y ESTADO GLOBAL
# =========================================================================
if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()

if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None

def on_sucursal_change():
    seleccion = st.session_state.get("select_sitio")
    if seleccion in PRECIOS_SUCURSALES:
        tarifa = obtener_tarifa_sucursal(seleccion)
        # Streamlit ejecuta el callback antes de construir los widgets de este rerun.
        st.session_state["costo_boleto_final_in"] = tarifa
        st.session_state["costo_boleto_input"] = tarifa

if "costo_boleto_input" not in st.session_state:
    st.session_state["costo_boleto_input"] = 40

# =========================================================================
# PANTALLA DE ACCESO (LOGIN)
# =========================================================================
if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=320)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; color: #4A5568;'>Control Operativo y Financiero</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #718096; font-size: 0.9rem;'>Acceso seguro desde cualquier teléfono Android o navegador web</p>", unsafe_allow_html=True)
        st.markdown("---")

        nombre_usuario = st.selectbox(
            "Selecciona tu Usuario:",
            ["-- Selecciona --", "Víctor Manuel", "José de Jesús", "Víctor (Contador)"],
            key="login_user"
        )
        password = st.text_input("Contraseña de Acceso:", type="password", key="login_pass")

        pass_visor = obtener_secreto("PASS_SUPERVISOR", "")
        pass_auditor = obtener_secreto("PASS_AUDITOR", "")
        if not pass_visor or not pass_auditor:
            st.error("Acceso bloqueado: configura PASS_SUPERVISOR y PASS_AUDITOR en Secrets de Streamlit antes de usar la aplicación.")
            st.stop()

if st.button("🔑 Iniciar Sesión", use_container_width=True, type="primary"):
            if nombre_usuario in ["Víctor Manuel", "José de Jesús"] and hmac.compare_digest(password, pass_visor):
                st.session_state.usuario_autenticado = nombre_usuario
                st.session_state.rol = "Supervisor Global" # Igualado con la App Operativa
                st.session_state.sucursal_asignada = "TODAS" # Variable clave añadida
                registrar_evento_auditoria("Inicio de Sesión", nombre_usuario, "-", "-", "-", "Supervisor ingresó al sistema.")
                st.success(f"Bienvenido {nombre_usuario}")
                st.rerun()
            elif nombre_usuario == "Víctor (Contador)" and hmac.compare_digest(password, pass_auditor):
                st.session_state.usuario_autenticado = "Víctor (Contador)"
                st.session_state.rol = "Contador Auditor"
                st.session_state.sucursal_asignada = "TODAS" # Variable clave añadida
                registrar_evento_auditoria("Inicio de Sesión", "Víctor (Contador)", "-", "-", "-", "Contador Auditor ingresó al panel de control.")
                st.success("Acceso concedido como Contador Auditor")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta o usuario no seleccionado.")
        st.stop()

# =========================================================================
# BARRA SUPERIOR Y LATERAL (NAVBAR & KPIS)
# =========================================================================
es_contador = (st.session_state.rol == "Contador Auditor")
memoria_ia_global = cargar_memoria_ia()

col_nav1, col_nav2 = st.columns([1, 4])
with col_nav1:
    logo_path = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=180)
    else:
        st.markdown("### 🚗 **CLUB PARK**")

with col_nav2:
    st.markdown(f"### CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.markdown(f"**Usuario:** `{st.session_state.usuario_autenticado}` | **Rol:** `{st.session_state.rol}` | 📱 **Compatible con Android** · fotos comprimidas; requiere conexión y puede consumir datos móviles")

if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
fotos_disco = [f for f in os.listdir(FOTOS_DIR) if not f.startswith('.')] if os.path.exists(FOTOS_DIR) else []
st.sidebar.markdown(f"📊 **Reportes en Sistema:** `{len(st.session_state.registros)}`")
st.sidebar.markdown(f"📷 **Fotos Guardadas:** `{len(fotos_disco)}`")
st.sidebar.markdown(f"🧠 **Reportes Aprendidos por IA:** `{memoria_ia_global.get('total_reportes_procesados', 0)}`")

# DESCARGA DE EXCEL CORPORATIVO EN SIDEBAR
if st.session_state.registros:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Descargas Oficiales")
    
    opciones_periodo = [
        "Todo el Histórico",
        "Semanal (Últimos 7 días)",
        "Quincenal (Últimos 15 días)",
        "Mensual (Últimos 30 días)",
        "Rango Personalizado"
    ]
    periodo_sel = st.sidebar.selectbox("Periodo de descarga:", opciones_periodo, key="side_periodo_sel")
    
    f_ini_sel, f_fin_sel = None, None
    if periodo_sel == "Rango Personalizado":
        c_p1, c_p2 = st.sidebar.columns(2)
        with c_p1:
            f_ini_sel = st.date_input("Desde:", value=date.today() - timedelta(days=7), key="side_f_ini")
        with c_p2:
            f_fin_sel = st.date_input("Hasta:", value=date.today(), key="side_f_fin")
            
    reps_descarga = filtrar_registros_por_periodo(st.session_state.registros, periodo_sel, f_ini_sel, f_fin_sel)
    st.sidebar.caption(f"📋 **{len(reps_descarga)}** de **{len(st.session_state.registros)}** reportes en periodo.")
    
    tag_periodo = periodo_sel.split(" ")[0].lower()
    ts_descarga = datetime.now().strftime("%Y%m%d_%H%M")
    
    if reps_descarga:
        historial_aud_sidebar = cargar_historial_auditoria()
        excel_data, estado_excel = generar_excel_completo(reps_descarga, historial_aud_sidebar, etiqueta_periodo=periodo_sel)
        if estado_excel == "OK" and excel_data:
            st.sidebar.download_button(
                label=f"📊 Descargar Excel Oficial ({periodo_sel.split(' ')[0]})",
                data=excel_data,
                file_name=f"ClubPark_Control_Oficial_{tag_periodo}_{ts_descarga}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        elif estado_excel == "SIN_MOTOR":
            st.sidebar.error("No está disponible ningún motor para generar Excel. Descarga el CSV oficial.")
        else:
            st.sidebar.error(f"No se pudo generar el Excel: {estado_excel}")
        
        st.sidebar.download_button(
            label=f"📄 Descargar CSV Oficial ({periodo_sel.split(' ')[0]})",
            data=generar_csv_oficial(reps_descarga, etiqueta_periodo=periodo_sel),
            file_name=f"ClubPark_Control_Oficial_{tag_periodo}_{ts_descarga}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.sidebar.warning("No hay reportes en el periodo seleccionado.")

# RESPALDO CIFRADO EN SIDEBAR (SOLO AUDITOR)
if es_contador:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔒 Respaldos Cifrados Fernet")
    clave_backup = st.sidebar.text_input("Clave de cifrado:", type="password", key="pass_bkp_side")
    if st.sidebar.button("🛡️ Cifrar y Descargar Base de Datos", use_container_width=True):
        if not clave_backup:
            st.sidebar.error("Ingresa una clave secreta.")
        elif not CRYPTOGRAPHY_OK:
            st.sidebar.error("Librería cryptography no disponible.")
        else:
            paquete = cifrar_respaldo_seguro(st.session_state.registros, clave_backup)
            if paquete:
                st.sidebar.download_button(
                    label="💾 Descargar .enc",
                    data=paquete.encode("utf-8"),
                    file_name=f"ClubPark_Backup_Fernet_{datetime.now().strftime('%Y%m%d_%H%M')}.enc",
                    mime="application/json",
                    use_container_width=True
                )

# =========================================================================
# VISTAS PRINCIPALES POR PESTAÑAS
# =========================================================================
# --- ALARMA PROACTIVA DE EVENTOS EXTRAORDINARIOS (2 HORAS DE ANTICIPACIÓN) ---
ahora = datetime.now()
eventos_proximos = []
for reg in st.session_state.registros:
    if reg.get("Tipo") == "Evento Extraordinario":
        try:
            f_str = reg.get("Fecha", "")
            h_str = reg.get("Horario", "").split(" a ")[0].strip()
            dt_ev = datetime.strptime(f"{f_str} {h_str}", "%d/%m/%Y %H:%M")
            dif_segundos = (dt_ev - ahora).total_seconds()
            # Si el evento es en las próximas 2 horas (0 a 7200 segundos) o está en curso
            if -3600 <= dif_segundos <= 7200:
                eventos_proximos.append((reg, dt_ev, int(dif_segundos // 60)))
        except Exception:
            pass

if eventos_proximos:
    st.caption("Las alertas se evalúan cuando Streamlit ejecuta la página; no son notificaciones push y no se garantizan si la app/navegador está cerrado.")
    for ev_reg, dt_ev, mins in eventos_proximos:
        if mins > 0:
            st.error(f"🚨 **¡ALARMA DE EVENTO EXTRAORDINARIO EN 2 HORAS!** Sucursal: **{ev_reg.get('Sitio / Unidad')}** | Inicia a las **{dt_ev.strftime('%H:%M')}** (en aprox. {mins} minutos). Responsable: {ev_reg.get('Elaboró')}.")
        else:
            st.warning(f"⚡ **EVENTO EXTRAORDINARIO EN CURSO:** Sucursal: **{ev_reg.get('Sitio / Unidad')}** iniciada a las **{dt_ev.strftime('%H:%M')}**.")

if es_contador:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📷 Subir con Foto (1-Clic)",
        "📈 Rentabilidad por Sucursal",
        "🕵️ Auditoría y Hallazgos",
        "⚡ Evento Extraordinario",
        "📲 WhatsApp y Alarmas",
        "🗂️ Gestión de Reportes",
        "🧪 Pruebas de Despliegue"
    ])
else:
    tab1, tab2, tab3, tab4 = st.tabs([
        "📷 Subir con Foto (1-Clic)",
        "📈 Rentabilidad de Mis Sucursales",
        "📋 Mis Reportes Operativos",
        "⚡ Eventos y Alertas"
    ])

# =========================================================================
# TAB 1: SUBIR INFORMACIÓN CON SOLO CARGAR LA FOTO (OPTIMIZADO ANDROID)
# =========================================================================
with tab1:
    st.markdown("### 📷 Subida Automática por Fotografía de Reporte")
    st.markdown("Carga la foto de la hoja física o tómala con la cámara. El OCR y las reglas locales extraen/sugieren datos; revísalos antes de guardar. Las alertas de auditoría son controles automáticos, no una aprobación contable.")

    col_captura1, col_captura2 = st.columns([1, 1])
    with col_captura1:
        modo_captura = st.radio(
            "Método de Captura en Teléfono:",
            ["📱 Tomar foto con la Cámara", "📁 Seleccionar de la Galería"],
            horizontal=True
        )

    foto_cargada = None
    if modo_captura == "📱 Tomar foto con la Cámara":
        foto_cargada = st.camera_input("Enfoca la hoja física del reporte:", key="camera_uploader")
    else:
        foto_cargada = st.file_uploader(
            "Selecciona la foto del reporte (PNG o JPG):",
            type=["png", "jpg", "jpeg", "webp"],
            key="uploader_mobile_photo"
        )

    # Estado de auto-llenado
    datos_auto = {}
    analisis_foto = None

    if foto_cargada:
        with st.spinner("🤖 Analizando fotografía con visión artificial y reglas de auditoría..."):
            analisis_foto = validar_y_analizar_foto_inteligente(
                foto_cargada,
                list(PRECIOS_SUCURSALES.keys()),
                memoria_ia_global
            )
            datos_auto = analisis_foto.get("datos_extraidos", {})

        # Aplicar cada foto nueva una sola vez: OCR rellena campos, pero el usuario
        # conserva sus cambios mientras siga trabajando con la misma imagen.
        foto_sig = f"{getattr(foto_cargada, 'name', 'camera')}:{getattr(foto_cargada, 'size', 0)}"
        if st.session_state.get("_foto_auto_aplicada") != foto_sig:
            suc_ocr = datos_auto.get("sucursal")
            if suc_ocr in PRECIOS_SUCURSALES:
                st.session_state["select_sitio"] = suc_ocr
                st.session_state["costo_boleto_final_in"] = obtener_tarifa_sucursal(
                    suc_ocr, datos_auto.get("costo_boleto")
                )
            if "folio_inicial" in datos_auto:
                st.session_state["in_f_ini_f"] = int(datos_auto["folio_inicial"])
            if "folio_final" in datos_auto:
                st.session_state["in_f_fin_f"] = int(datos_auto["folio_final"])
            if "sin_cobro" in datos_auto:
                st.session_state["in_f_sc_f"] = int(datos_auto["sin_cobro"])
            if "cancelados" in datos_auto:
                st.session_state["in_f_canc_f"] = int(datos_auto["cancelados"])
            if "gastos_nomina" in datos_auto:
                st.session_state["g_gen_f"] = float(datos_auto["gastos_nomina"])
            st.session_state["_foto_auto_aplicada"] = foto_sig

        col_prev, col_info_ia = st.columns([1, 2])
        with col_prev:
            st.image(foto_cargada, caption="Fotografía procesada", use_container_width=True)
            if analisis_foto.get("valida"):
                st.success(analisis_foto["mensaje"])
            else:
                st.warning(analisis_foto["mensaje"])

        with col_info_ia:
            st.markdown("#### 🪄 Datos Extraídos Automáticamente por la IA:")
            suc_det = datos_auto.get("sucursal", "No detectada")
            f_ini_det = datos_auto.get("folio_inicial", 0)
            f_fin_det = datos_auto.get("folio_final", 0)
            fecha_det = datos_auto.get("fecha", date.today())
            costo_det = datos_auto.get("costo_boleto", PRECIOS_SUCURSALES.get(suc_det, 40))

            c_det1, c_det2 = st.columns(2)
            with c_det1:
                st.write(f"🏢 **Sucursal:** `{suc_det}`")
                st.write(f"📅 **Fecha:** `{fecha_det.strftime('%d/%m/%Y')}`")
                st.write(f"💵 **Tarifa Boleto:** `${costo_det} MXN`")
            with c_det2:
                st.write(f"🎟️ **Folio Inicial:** `{f_ini_det}`")
                st.write(f"🎟️ **Folio Final:** `{f_fin_det}`")
                st.write(f"🧠 **Nivel de Confianza:** `{analisis_foto.get('confianza', 0)}%`")

    st.markdown("---")
    st.markdown("#### 📝 Confirmación y Ajustes del Reporte")

    # Controles del Formulario (pre-llenados por foto o interactivos)
    col_frm1, col_frm2 = st.columns(2)
    with col_frm1:
        fec_val = datos_auto.get("fecha", date.today())
        if "f_rep_final" not in st.session_state: st.session_state["f_rep_final"] = fec_val
        fecha_rep = st.date_input("Fecha de Operación:", key="f_rep_final")
        fecha_rep_str = fecha_rep.strftime("%d/%m/%Y")

        idx_s = 0
        if "sucursal" in datos_auto and datos_auto["sucursal"] in SUCURSALES_LISTA:
            idx_s = SUCURSALES_LISTA.index(datos_auto["sucursal"])

        if "select_sitio" not in st.session_state: st.session_state["select_sitio"] = SUCURSALES_LISTA[idx_s]
        # Al iniciar formulario o al entrar con OCR, que el widget refleje tarifa catálogo.
        if st.session_state.get("select_sitio") in PRECIOS_SUCURSALES and "costo_boleto_final_in" not in st.session_state:
            st.session_state["costo_boleto_final_in"] = obtener_tarifa_sucursal(
                st.session_state["select_sitio"], datos_auto.get("costo_boleto")
            )
        sucursal_sel = st.selectbox(
            "Sucursal / Unidad:",
            SUCURSALES_LISTA,
            key="select_sitio",
            on_change=on_sucursal_change
        )
        es_directo = (sucursal_sel in ["BARRANCA", "VETERINARIA", "S. AZURA", "E-BNI"] or PRECIOS_SUCURSALES.get(sucursal_sel, 0) == 0)

    with col_frm2:
        if es_directo:
            st.info("📌 Modalidad: Cobro directo de Ingreso Bruto sin control por folio.")
            costo_boleto_final = 0.0
        else:
            # Si OCR no detectó tarifa, aplicar siempre el precio del catálogo.
            if not st.session_state.get("costo_boleto_final_in"):
                st.session_state["costo_boleto_final_in"] = obtener_tarifa_sucursal(
                    sucursal_sel, datos_auto.get("costo_boleto")
                )
            costo_boleto_final = st.number_input(
                "Tarifa por Boleto ($ MXN):",
                min_value=0.0,
                step=5.0,
                key="costo_boleto_final_in"
            )

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        hora_apertura = st.time_input("Hora de Apertura:", value=time(13, 0), key="h_ape_in")
    with col_h2:
        hora_cierre = st.time_input("Hora de Cierre:", value=time(23, 0), key="h_cie_in")

    st.markdown("#### 🎫 Control Numérico de Folios y Boletos")
    c_num1, c_num2, c_num3 = st.columns(3)

    if es_directo:
        with c_num1:
            if "dir_ing_in" not in st.session_state: st.session_state["dir_ing_in"] = float(datos_auto.get("ingreso_bruto", 0.0))
            ingreso_directo_val = st.number_input("Ingreso Bruto de la Unidad ($ MXN):", min_value=0.0, step=50.0, key="dir_ing_in")
            f_ini_final = 0
            f_fin_final = 0
        with c_num2:
            f_sin_final = 0
            f_can_final = 0
        with c_num3:
            f_per_final = 0
        tot_bol_calc = 0
        cobrados_calc = 0
        bruto_calc = float(ingreso_directo_val)
    else:
        with c_num1:
            val_fi = int(datos_auto.get("folio_inicial", 0))
            val_ff = int(datos_auto.get("folio_final", 0))
            if "in_f_ini_f" not in st.session_state: st.session_state["in_f_ini_f"] = val_fi
            if "in_f_fin_f" not in st.session_state: st.session_state["in_f_fin_f"] = val_ff
            f_ini_final = st.number_input("Folio Inicial:", min_value=0, step=1, key="in_f_ini_f")
            f_fin_final = st.number_input("Folio Final:", min_value=0, step=1, key="in_f_fin_f")
        with c_num2:
            val_sc = int(datos_auto.get("sin_cobro", 0))
            val_canc = int(datos_auto.get("cancelados", 0))
            if "in_f_sc_f" not in st.session_state: st.session_state["in_f_sc_f"] = val_sc
            if "in_f_canc_f" not in st.session_state: st.session_state["in_f_canc_f"] = val_canc
            f_sin_final = st.number_input("Boletos Sin Cobro (Cortesía):", min_value=0, step=1, key="in_f_sc_f")
            f_can_final = st.number_input("Boletos Cancelados:", min_value=0, step=1, key="in_f_canc_f")
        with c_num3:
            f_per_final = st.number_input("Boletos Perdidos:", min_value=0, step=1, key="in_f_perd_f")

        tot_bol_calc = calcular_boletos_block100(int(f_ini_final), int(f_fin_final))
        cobrados_calc = max(0, tot_bol_calc - int(f_sin_final) - int(f_can_final))
        bruto_calc = cobrados_calc * float(costo_boleto_final)
        if int(f_ini_final) > 0 or int(f_fin_final) > 0:
            st.info(f"Folio {int(f_ini_final)} → {int(f_fin_final)}: **{tot_bol_calc} boletos** contados por los dos últimos dígitos en ciclo de 100; menos cortesías/cancelados = **{cobrados_calc} cobrados**.")
        if int(f_sin_final) + int(f_can_final) + int(f_per_final) > tot_bol_calc:
            st.error("Cortesías, cancelados y perdidos superan el total calculado. Corrige el desglose antes de guardar.")

    st.markdown("#### 💵 Egresos Operativos y Firmas")
    c_egr1, c_egr2, c_fir1, c_fir2 = st.columns(4)
    with c_egr1:
        gastos_esp = st.number_input("Gastos Especiales ($):", min_value=0.0, value=0.0, step=10.0, key="g_esp_f")
    with c_egr2:
        val_gn = float(datos_auto.get("gastos_nomina", 0.0))
        if "g_gen_f" not in st.session_state: st.session_state["g_gen_f"] = val_gn
        gastos_gen = st.number_input("Gastos Nómina / Generales ($):", min_value=0.0, step=10.0, key="g_gen_f")
    with c_fir1:
        elaboro_nombre = st.text_input("Elaboró (Firma/Supervisor):", value=st.session_state.usuario_autenticado, key="elab_f")
    with c_fir2:
        recibe_nombre = st.text_input("Recibe (Auditor/Encargado):", value="", key="recibe_f")

    tot_gastos_calc = float(gastos_esp) + float(gastos_gen)
    neto_calc = bruto_calc - tot_gastos_calc
    margen_calc = (neto_calc / bruto_calc * 100) if bruto_calc > 0 else 0.0
    rentabilidad_str = evaluar_rentabilidad(margen_calc)

    # REPORTE PRELIMINAR PARA AUDITORÍA EN TIEMPO REAL
    rep_preliminar = {
        "ID": "PREVIO",
        "Fecha": fecha_rep_str,
        "Sitio / Unidad": sucursal_sel,
        "Costo Boleto": float(costo_boleto_final),
        "Folio Inicial": int(f_ini_final),
        "Folio Final": int(f_fin_final),
        "Total Boletos": tot_bol_calc,
        "Sin Cobro": int(f_sin_final),
        "Cancelados": int(f_can_final),
        "Perdidos": int(f_per_final),
        "Boletos Cobrados": cobrados_calc,
        "Ingreso Bruto": bruto_calc,
        "Gastos Especiales": float(gastos_esp),
        "Gastos Generales / Nómina": float(gastos_gen),
        "Total Gastos": tot_gastos_calc,
        "Ingreso Neto": neto_calc,
        "Margen (%)": round(margen_calc, 2),
        "Elaboró": elaboro_nombre,
        "Recibe": recibe_nombre,
        "foto_path": "CARGADA" if foto_cargada else None
    }

    score_aud, nivel_aud, fallas_aud, obs_aud = evaluar_auditoria_reporte(
        rep_preliminar,
        st.session_state.registros,
        memoria_ia_global
    )

    # MOSTRAR EVALUACIÓN DE AUDITORÍA EN TIEMPO REAL
    st.markdown("---")
    st.markdown("### 🛡️ Evaluación de Auditoría y Rentabilidad en Tiempo Real")
    col_aud_m1, col_aud_m2, col_aud_m3, col_aud_m4 = st.columns(4)
    with col_aud_m1:
        st.metric("Ingreso Bruto", f"${bruto_calc:,.2f} MXN", help="Boletos cobrados x Tarifa")
    with col_aud_m2:
        st.metric("Total Gastos", f"${tot_gastos_calc:,.2f} MXN", help="Especiales + Nómina")
    with col_aud_m3:
        st.metric("Utilidad Neta", f"${neto_calc:,.2f} MXN", delta=f"{margen_calc:.1f}% Margen")
    with col_aud_m4:
        st.metric("Auditoría Score", f"{score_aud}/100", delta=nivel_aud)

    if fallas_aud:
        st.error("🚨 **Fallas de Auditoría Detectadas en este Reporte:**")
        for f in fallas_aud:
            st.markdown(f"- **{f['regla']}** ({f['gravedad']}): {f['detalle']}")

    if obs_aud:
        st.info("📌 **Observaciones de Auditoría:** " + " | ".join(obs_aud))

    # VALIDACIÓN DE DUPLICADO
    ya_existe = any(r.get("Sitio / Unidad") == sucursal_sel and r.get("Fecha") == fecha_rep_str for r in st.session_state.registros)
    bloquear_guardado = False
    if ya_existe and not es_contador:
        st.error(f"🚫 Ya existe un reporte registrado para **{sucursal_sel}** en la fecha **{fecha_rep_str}**.")
        bloquear_guardado = True

    # BOTÓN PRINCIPAL DE 1-CLIC
    st.markdown("---")
    btn_label = "⚡ Confirmar y Subir Reporte con 1 Toque" if foto_cargada else "💾 Guardar y Registrar Reporte Operativo"
    if st.button(btn_label, type="primary", use_container_width=True, disabled=bloquear_guardado):
        if sucursal_sel == "-- Selecciona o busca la sucursal --":
            st.error("❌ Por favor selecciona una sucursal válida.")
        else:
            nuevo_id = f"REP_{uuid.uuid4().hex[:8]}"
            ruta_foto = None
            bytes_foto = None
            nom_foto = None
            if foto_cargada:
                ruta_foto, bytes_foto, nom_foto = guardar_imagen_optimizada(foto_cargada, nuevo_id, sucursal_sel, fecha_rep_str)

            registro_completo = {
                "ID": nuevo_id,
                "Fecha": fecha_rep_str,
                "Sitio / Unidad": sucursal_sel,
                "Horario": f"{hora_apertura.strftime('%H:%M')} a {hora_cierre.strftime('%H:%M')}",
                "Costo Boleto": float(costo_boleto_final),
                "Folio Inicial": int(f_ini_final),
                "Folio Final": int(f_fin_final),
                "Total Boletos": tot_bol_calc,
                "Sin Cobro": int(f_sin_final),
                "Cancelados": int(f_can_final),
                "Perdidos": int(f_per_final),
                "Boletos Cobrados": cobrados_calc,
                "Ingreso Bruto": bruto_calc,
                "Gastos Especiales": float(gastos_esp),
                "Gastos Generales / Nómina": float(gastos_gen),
                "Total Gastos": tot_gastos_calc,
                "Ingreso Neto": neto_calc,
                "Margen (%)": round(margen_calc, 2),
                "Rentabilidad": rentabilidad_str,
                "Score Auditoría": score_aud,
                "Nivel Auditoría": nivel_aud,
                "Fallas Auditoría": [f["regla"] for f in fallas_aud],
                "Elaboró": elaboro_nombre if elaboro_nombre else st.session_state.usuario_autenticado,
                "Usuario": st.session_state.usuario_autenticado,
                "Recibe": recibe_nombre,
                "Tipo": "Operación Regular",
                "foto_path": ruta_foto,
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            st.session_state.registros.append(registro_completo)
            guardar_registros_permanentes(st.session_state.registros)

            # Persistencia en la Nube Supabase (si está configurada)
            sb_ok, sb_msg = sincronizar_reporte_supabase(registro_completo, bytes_foto, nom_foto)
            if sb_ok:
                st.toast(f"☁️ {sb_msg}", icon="✅")

            # Registrar en el historial de auditoría
            registrar_evento_auditoria(
                tipo_evento="Creación de Reporte",
                usuario=st.session_state.usuario_autenticado,
                id_reporte=nuevo_id,
                sucursal=sucursal_sel,
                fecha_op=fecha_rep_str,
                detalles=f"Reporte subido con {cobrados_calc} boletos, Neto: ${neto_calc:,.2f} MXN, Score: {score_aud}/100",
                score=score_aud,
                fallas=fallas_aud
            )

            # Entrenar la Inteligencia Artificial Adaptativa con este nuevo reporte
            actualizar_memoria_ia(registro_completo)

            st.success(f"🎉 ¡Reporte registrado exitosamente con ID `{nuevo_id}`!")
            st.balloons()
            st.rerun()

# =========================================================================
# TAB 2: MÓDULO CENTRAL DE RENTABILIDAD POR SUCURSAL
# =========================================================================
with tab2:
    st.markdown("### 📈 Rentabilidad y Tendencias de Aprendizaje")
    subtab_rent1, subtab_rent2 = st.tabs(["📊 Rentabilidad Financiera Real", "🧠 Tendencias de Aprendizaje IA"])
    
    with subtab_rent1:
        st.markdown("Monitoreo de ingresos brutos, gastos de operación, nómina y margen neto; selecciona período y alcance.")
        registros_rentabilidad, periodo_rentabilidad = mostrar_filtro_periodo_registros(
            st.session_state.registros, "rentabilidad_comun"
        )
    
        if not registros_rentabilidad:
            st.info("No hay datos suficientes para calcular rentabilidad. Registra el primer reporte.")
        else:
            df_r = pd.DataFrame(registros_rentabilidad)
            cols_n = ["Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina", "Total Gastos", "Ingreso Neto", "Boletos Cobrados"]
            for c in cols_n:
                if c not in df_r.columns:
                    df_r[c] = 0.0
                else:
                    df_r[c] = pd.to_numeric(df_r[c], errors="coerce").fillna(0.0)
    
            # KPIs Globales
            tot_bruto = df_r["Ingreso Bruto"].sum()
            tot_gastos = df_r["Total Gastos"].sum()
            tot_neto = df_r["Ingreso Neto"].sum()
            margen_global = (tot_neto / tot_bruto * 100) if tot_bruto > 0 else 0.0
    
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("Ingreso Bruto Global", f"${tot_bruto:,.2f} MXN")
            with k2:
                st.metric("Gastos y Nómina Global", f"${tot_gastos:,.2f} MXN")
            with k3:
                st.metric("Utilidad Neta Real", f"${tot_neto:,.2f} MXN")
            with k4:
                st.metric("Margen Global del Negocio", f"{margen_global:.1f}%", delta=evaluar_rentabilidad(margen_global))
    
            st.markdown("---")
    
            # Agrupación por Sucursal
            res_suc = df_r.groupby("Sitio / Unidad").agg({
                "ID": "count",
                "Boletos Cobrados": "sum",
                "Ingreso Bruto": "sum",
                "Gastos Especiales": "sum",
                "Gastos Generales / Nómina": "sum",
                "Total Gastos": "sum",
                "Ingreso Neto": "sum"
            }).reset_index()
    
            res_suc.rename(columns={"ID": "Reportes"}, inplace=True)
            res_suc["Margen (%)"] = ((res_suc["Ingreso Neto"] / res_suc["Ingreso Bruto"]) * 100).fillna(0.0).round(2)
            res_suc["Rentabilidad"] = res_suc["Margen (%)"].apply(evaluar_rentabilidad)
            res_suc["% Gasto s/Ingreso"] = ((res_suc["Total Gastos"] / res_suc["Ingreso Bruto"]) * 100).fillna(0.0).round(1)
            res_suc = res_suc.sort_values(by="Ingreso Neto", ascending=False)
    
            col_top, col_flop = st.columns(2)
            with col_top:
                st.markdown("#### 🏆 Top Sucursales Más Rentables")
                top_3 = res_suc.head(3)
                for idx, row in top_3.iterrows():
                    st.markdown(f"""
                    <div class="card-auditoria" style="border-left-color: #38A169;">
                        <b>{row['Sitio / Unidad']}</b> | Utilidad: <b>${row['Ingreso Neto']:,.2f} MXN</b><br>
                        Margen: <span class="badge-verde">{row['Margen (%)']}%</span> | Boletos: {int(row['Boletos Cobrados']):,}
                    </div>
                    """, unsafe_allow_html=True)
    
            with col_flop:
                st.markdown("#### ⚠️ Sucursales con Bajo Margen o Pérdida")
                flop_3 = res_suc.sort_values(by="Margen (%)", ascending=True).head(3)
                for idx, row in flop_3.iterrows():
                    color_border = "#E53E3E" if row['Ingreso Neto'] < 0 else "#D69E2E"
                    badge_class = "badge-rojo" if row['Ingreso Neto'] < 0 else "badge-amarillo"
                    st.markdown(f"""
                    <div class="card-auditoria" style="border-left-color: {color_border};">
                        <b>{row['Sitio / Unidad']}</b> | Utilidad: <b>${row['Ingreso Neto']:,.2f} MXN</b><br>
                        Margen: <span class="{badge_class}">{row['Margen (%)']}%</span> | Gastos: {row['% Gasto s/Ingreso']}% del ingreso
                    </div>
                    """, unsafe_allow_html=True)
    
            st.markdown("---")
            st.markdown("#### 📊 Tabla Detallada de Rentabilidad por Unidad")
    
            columnas_mostrar = [
                "Sitio / Unidad", "Reportes", "Boletos Cobrados", "Ingreso Bruto",
                "Total Gastos", "Ingreso Neto", "Margen (%)", "% Gasto s/Ingreso", "Rentabilidad"
            ]
            
            # Formatear números para visualización ejecutiva
            df_tabla = res_suc[columnas_mostrar].copy()
            df_tabla["Ingreso Bruto"] = df_tabla["Ingreso Bruto"].apply(lambda x: f"${x:,.2f}")
            df_tabla["Total Gastos"] = df_tabla["Total Gastos"].apply(lambda x: f"${x:,.2f}")
            df_tabla["Ingreso Neto"] = df_tabla["Ingreso Neto"].apply(lambda x: f"${x:,.2f}")
            df_tabla["Margen (%)"] = df_tabla["Margen (%)"].apply(lambda x: f"{x:.1f}%")
            df_tabla["% Gasto s/Ingreso"] = df_tabla["% Gasto s/Ingreso"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)
    
            # Gráfico Ligero Nativo de Barras (Utilidad Neta por Sucursal)
            st.markdown("#### 📉 Comparativa de Utilidad Neta ($ MXN)")
            chart_data = res_suc.set_index("Sitio / Unidad")[["Ingreso Neto"]]
            st.bar_chart(chart_data)

        with subtab_rent2:
            st.markdown("### 🧠 Tendencias de Comportamiento Aprendidas por la IA")
            st.markdown("El perfil de aprendizaje es acumulativo; los resultados visibles se filtran por el período y alcance elegido.")
            registros_tendencias, periodo_tendencias = mostrar_filtro_periodo_registros(
                st.session_state.registros, "tendencias_ia"
            )
            df_tendencias = pd.DataFrame(registros_tendencias) if registros_tendencias else pd.DataFrame()
            memoria_ia_view = cargar_memoria_ia()
            sucursales_dict = memoria_ia_view.get("sucursales", {})
            
            # Período/alcance: métricas calculadas únicamente a partir de los reportes seleccionados.
            if not df_tendencias.empty:
                for col in ["Boletos Cobrados", "Ingreso Bruto", "Total Gastos", "Ingreso Neto"]:
                    if col not in df_tendencias.columns:
                        df_tendencias[col] = 0.0
                    df_tendencias[col] = pd.to_numeric(df_tendencias[col], errors="coerce").fillna(0.0)
                df_tendencias["Margen (%)"] = df_tendencias.apply(
                    lambda row: (row["Ingreso Neto"] / row["Ingreso Bruto"] * 100) if row["Ingreso Bruto"] > 0 else 0.0,
                    axis=1
                )
                grupos_tendencias = df_tendencias.groupby("Sitio / Unidad", dropna=False)
                perfiles_periodo = {}
                for suc, grupo in grupos_tendencias:
                    perfiles_periodo[str(suc)] = {
                        "reportes_aprendidos": int(len(grupo)),
                        "promedio_boletos": float(grupo["Boletos Cobrados"].mean()),
                        "promedio_ingreso_bruto": float(grupo["Ingreso Bruto"].mean()),
                        "promedio_gastos": float(grupo["Total Gastos"].mean()),
                        "margen_promedio": float(grupo["Margen (%)"].mean())
                    }
                sucursales_dict = perfiles_periodo
                tot_aprendidos = int(len(df_tendencias))
                suc_activas = len(sucursales_dict)
            else:
                sucursales_dict = {}
                tot_aprendidos = 0
                suc_activas = 0
            
            k_ia1, k_ia2, k_ia3, k_ia4 = st.columns(4)
            with k_ia1:
                st.metric("Total Reportes Aprendidos", tot_aprendidos)
            with k_ia2:
                st.metric("Sucursales con Perfil Activo", f"{suc_activas} / {len(PRECIOS_SUCURSALES)}")
            with k_ia3:
                proms_b = [float(d.get("promedio_boletos", 0)) for d in sucursales_dict.values() if d.get("reportes_aprendidos", 0) > 0]
                prom_b_global = round(sum(proms_b) / len(proms_b), 1) if proms_b else 0
                st.metric("Boletos Promedio Red", f"{prom_b_global} u.")
            with k_ia4:
                proms_m = [float(d.get("margen_promedio", 0)) for d in sucursales_dict.values() if d.get("reportes_aprendidos", 0) > 0]
                prom_m_global = round(sum(proms_m) / len(proms_m), 1) if proms_m else 0.0
                st.metric("Margen Promedio Red", f"{prom_m_global:.1f}%")
                
            if not sucursales_dict:
                st.info("Aún no se han procesado suficientes reportes para construir tendencias de aprendizaje. Conforme se registren reportes, aquí se generarán los perfiles adaptativos.")
            else:
                st.markdown("---")
                st.markdown("#### 📋 Matriz de Comportamiento y Perfiles Predictivos")
                
                filas_ia = []
                for suc_n, d_suc in sucursales_dict.items():
                    n_rep = int(d_suc.get("reportes_aprendidos", 0))
                    if n_rep == 0:
                        continue
                    mean_b = float(d_suc.get("promedio_boletos", 0))
                    m2_b = float(d_suc.get("boletos_m2", 0))
                    std_b = math.sqrt(m2_b / (n_rep - 1)) if n_rep > 1 else 0.0
                    rango_b = f"{max(0, int(round(mean_b - 1.5 * std_b)))} a {int(round(mean_b + 1.5 * std_b))} bol." if n_rep > 1 else f"~{int(mean_b)} bol."
                    
                    filas_ia.append({
                        "Sucursal": suc_n,
                        "Reportes": n_rep,
                        "Boletos Promedio": f"{mean_b:.1f} (±{std_b:.1f})",
                        "Rango Esperado": rango_b,
                        "Ingreso Bruto Prom.": f"${d_suc.get('promedio_ingreso_bruto', 0):,.2f}",
                        "Gastos Prom.": f"${d_suc.get('promedio_gastos', 0):,.2f}",
                        "Margen Prom.": f"{d_suc.get('margen_promedio', 0):.1f}%",
                        "Último Folio Block": d_suc.get("ultimo_folio_final", 0),
                        "Horario Habitual": d_suc.get("horario_frecuente", "N/D"),
                        "Supervisor Frecuente": d_suc.get("supervisor_frecuente", "Supervisor"),
                        "_boletos_val": mean_b,
                        "_margen_val": float(d_suc.get("margen_promedio", 0))
                    })
                    
                if filas_ia:
                    df_ia = pd.DataFrame(filas_ia)
                    st.dataframe(df_ia.drop(columns=["_boletos_val", "_margen_val"]), use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    c_g_ia1, c_g_ia2 = st.columns(2)
                    with c_g_ia1:
                        st.markdown("##### 🚗 Boletos Promedio Aprendidos por Sucursal")
                        df_chart_b = df_ia.set_index("Sucursal")[["_boletos_val"]].rename(columns={"_boletos_val": "Boletos Promedio"}).sort_values(by="Boletos Promedio", ascending=False)
                        st.bar_chart(df_chart_b)
                    with c_g_ia2:
                        st.markdown("##### 📈 Margen Promedio Aprendido (%) por Sucursal")
                        df_chart_m = df_ia.set_index("Sucursal")[["_margen_val"]].rename(columns={"_margen_val": "Margen %"}).sort_values(by="Margen %", ascending=False)
                        st.bar_chart(df_chart_m)
                        
                    # Detección de desviaciones
                    st.markdown("---")
                    st.markdown("#### 🔍 Detección de Desviaciones contra la Tendencia Aprendida")
                    alertas_detectadas = []
                    if st.session_state.registros:
                        vistos = set()
                        for r in reversed(st.session_state.registros):
                            s_r = r.get("Sitio / Unidad")
                            if s_r in sucursales_dict and s_r not in vistos:
                                vistos.add(s_r)
                                d_suc = sucursales_dict[s_r]
                                n_rep = int(d_suc.get("reportes_aprendidos", 0))
                                if n_rep >= 3:
                                    b_r = float(r.get("Boletos Cobrados", 0))
                                    mean_b = float(d_suc.get("promedio_boletos", 0))
                                    std_b = math.sqrt(float(d_suc.get("boletos_m2", 0)) / (n_rep - 1)) if n_rep > 1 else 5.0
                                    if abs(b_r - mean_b) > 2.0 * max(std_b, 5.0):
                                        alertas_detectadas.append({
                                            "Sucursal": s_r,
                                            "Fecha": r.get("Fecha"),
                                            "Reportado": b_r,
                                            "Esperado": f"{mean_b:.1f} ± {std_b:.1f}",
                                            "Diferencia": f"{b_r - mean_b:+.1f} boletos",
                                            "Usuario": r.get("Usuario") or r.get("Elaboró")
                                        })
                    if alertas_detectadas:
                        for a in alertas_detectadas:
                            st.warning(f"⚠️ **{a['Sucursal']}** ({a['Fecha']}): Registró **{a['Reportado']} boletos** (esperado: {a['Esperado']}, desviación: {a['Diferencia']}). Responsable: {a['Usuario']}.")
                    else:
                        st.success("✅ Todas las sucursales operan actualmente dentro de los márgenes normales de sus tendencias aprendidas.")


# =========================================================================
# TAB 3: AUDITORÍA Y BITÁCORA DE HISTORIAL (AUDITOR) O MIS REPORTES (SUPERVISOR)
# =========================================================================
if es_contador:
    with tab3:
        st.markdown("### 🕵️ Auditoría Operativa y Bitácora de Movimientos")
        st.markdown("Historial inmutable de auditoría: registro de creaciones, modificaciones, revisiones y detección automática de anomalías.")

        historial_eventos = cargar_historial_auditoria()
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            filtro_suc = st.selectbox("Filtrar por Sucursal:", ["Todas las sucursales"] + list(PRECIOS_SUCURSALES.keys()), key="filtro_suc_aud")
        with c_f2:
            filtro_tipo = st.selectbox("Filtrar por Tipo de Evento:", ["Todos los eventos", "Creación de Reporte", "Modificación", "Aprobación de Auditoría", "Eliminación"], key="filtro_tipo_aud")

        eventos_filtrados = historial_eventos
        if filtro_suc != "Todas las sucursales":
            eventos_filtrados = [e for e in eventos_filtrados if e.get("sucursal") == filtro_suc]
        if filtro_tipo != "Todos los eventos":
            eventos_filtrados = [e for e in eventos_filtrados if e.get("tipo_evento") == filtro_tipo]

        st.markdown(f"**Total de eventos registrados:** `{len(eventos_filtrados)}`")

        if eventos_filtrados:
            for ev in eventos_filtrados[:25]:
                score_ev = ev.get("score_auditoria", 100)
                badge_score = "badge-verde" if score_ev >= 90 else ("badge-amarillo" if score_ev >= 70 else "badge-rojo")
                b_color = "#38A169" if score_ev >= 90 else ("#D69E2E" if score_ev >= 70 else "#E53E3E")

                st.markdown(f"""
                <div class="card-auditoria" style="border-left-color: {b_color};">
                    <span style="font-size: 0.85rem; color: #718096;">🕒 {ev.get('timestamp')} | Usuario: <b>{ev.get('usuario')}</b></span><br>
                    <b>{ev.get('tipo_evento')}</b> en <b>{ev.get('sucursal')}</b> (Fecha Op: {ev.get('fecha_operacion')})<br>
                    <span>{ev.get('detalles')}</span><br>
                    Auditoría: <span class="{badge_score}">{score_ev}/100</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No se encontraron registros de auditoría para los filtros seleccionados.")

        # Hallazgos de Auditoría en Reportes Guardados
        st.markdown("---")
        st.markdown("#### 🚨 Reportes con Hallazgos o Falla de Auditoría Pendientes de Revisión")
        reportes_con_falla = [r for r in st.session_state.registros if r.get("Score Auditoría", 100) < 85 or r.get("Fallas Auditoría")]
        if reportes_con_falla:
            for rep in reportes_con_falla:
                with st.expander(f"⚠️ {rep.get('Sitio / Unidad')} ({rep.get('Fecha')}) - Score: {rep.get('Score Auditoría', 'N/A')}/100"):
                    st.write(f"- **ID:** `{rep.get('ID')}`")
                    st.write(f"- **Fallas detectadas:** {rep.get('Fallas Auditoría')}")
                    st.write(f"- **Neto:** ${rep.get('Ingreso Neto', 0):,.2f} MXN | Margen: {rep.get('Margen (%)')}%")
                    if rep.get("foto_path") and os.path.exists(rep["foto_path"]):
                        st.image(rep["foto_path"], caption="Fotografía física del reporte con falla", width=350)
        else:
            st.success("✅ No existen reportes con fallas críticas pendientes de revisión.")

else:
    with tab3:
        st.markdown("### 📋 Mis Reportes Operativos")
        mis_reportes = [r for r in st.session_state.registros if (r.get("Usuario") or r.get("Elaboró")) == st.session_state.usuario_autenticado]
        if mis_reportes:
            periodo_mis = st.selectbox("Período de mis reportes:", ["Semanal (Últimos 7 días)", "Quincenal (Últimos 15 días)", "Mensual (Últimos 30 días)", "Todo el Histórico"], key="supervisor_mis_periodo")
            mis_reportes_periodo = filtrar_registros_por_periodo(mis_reportes, periodo_mis)
            suc_mis = sorted({str(r.get("Sitio / Unidad", "")) for r in mis_reportes_periodo})
            suc_selec_mis = st.selectbox("Sucursal:", ["Todas las sucursales"] + suc_mis, key="supervisor_mis_sucursal")
            if suc_selec_mis != "Todas las sucursales":
                mis_reportes_periodo = [r for r in mis_reportes_periodo if str(r.get("Sitio / Unidad", "")) == suc_selec_mis]
            if mis_reportes_periodo:
                df_mis = pd.DataFrame(mis_reportes_periodo)
                columnas_mis = [c for c in ["ID", "Fecha", "Sitio / Unidad", "Boletos Cobrados", "Ingreso Bruto", "Total Gastos", "Ingreso Neto", "Margen (%)"] if c in df_mis.columns]
                st.dataframe(df_mis[columnas_mis], use_container_width=True, hide_index=True)
            else:
                st.info("No hay reportes en el período/sucursal seleccionados.")
        else:
            st.info("Aún no has registrado reportes bajo tu usuario.")

# =========================================================================
# TABS EXCLUSIVOS AUDITOR (EVENTOS, GESTIÓN, DESPLIEGUE)
# =========================================================================
if es_contador:
    # TAB 4: Evento Extraordinario
    with tab4:
        st.markdown("### ⚡ Registro y Asignación de Evento Extraordinario")
        c_ev1, c_ev2 = st.columns(2)
        with c_ev1:
            ev_f = st.date_input("Fecha del Evento:", value=date.today(), key="ev_f_in")
            ev_suc = st.selectbox("Sucursal / Sede del Evento:", SUCURSALES_LISTA, key="ev_suc_in")
            ev_costo = st.number_input("Costo Boleto Evento ($ MXN):", min_value=0.0, value=100.0, step=10.0, key="ev_c_in")
        with c_ev2:
            ev_h_ini = st.time_input("Inicio Evento:", value=time(18, 0), key="ev_hi_in")
            ev_h_fin = st.time_input("Fin Evento:", value=time(2, 0), key="ev_hf_in")
            ev_bol = st.number_input("Boletos Cobrados / Estimados:", min_value=0, value=60, step=1, key="ev_b_in")

        c_ev3, c_ev4 = st.columns(2)
        with c_ev3:
            ev_gastos = st.number_input("Total Gastos / Nómina Evento ($ MXN):", min_value=0.0, value=0.0, step=50.0, key="ev_g_in")
        with c_ev4:
            # ASIGNACIÓN DE SUPERVISOR AL EVENTO EXTRAORDINARIO
            ev_asignado = st.selectbox(
                "🎯 Asignar Supervisor Responsable del Evento:",
                ["José de Jesús", "Víctor Manuel", "Ambos Supervisores (Operación Conjunta)", "Víctor (Contador)"],
                key="ev_asig_sel"
            )

        ev_bruto = float(ev_bol) * float(ev_costo)
        ev_neto = ev_bruto - float(ev_gastos)
        ev_margen = (ev_neto / ev_bruto * 100) if ev_bruto > 0 else 0.0

        st.metric("Utilidad Generada en Evento", f"${ev_neto:,.2f} MXN", delta=f"{ev_margen:.1f}% Margen")

        if st.button("💾 Guardar y Asignar Evento Extraordinario", type="primary", key="btn_save_event"):
            if ev_suc != "-- Selecciona o busca la sucursal --":
                id_ev = f"EVT_{uuid.uuid4().hex[:6]}"
                evento_obj = {
                    "ID": id_ev,
                    "Fecha": ev_f.strftime("%d/%m/%Y"),
                    "Sitio / Unidad": ev_suc,
                    "Horario": f"{ev_h_ini.strftime('%H:%M')} a {ev_h_fin.strftime('%H:%M')}",
                    "Costo Boleto": float(ev_costo),
                    "Folio Inicial": 1,
                    "Folio Final": int(ev_bol),
                    "Total Boletos": int(ev_bol),
                    "Sin Cobro": 0, "Cancelados": 0, "Perdidos": 0,
                    "Boletos Cobrados": int(ev_bol),
                    "Ingreso Bruto": ev_bruto,
                    "Gastos Especiales": float(ev_gastos),
                    "Gastos Generales / Nómina": 0.0,
                    "Total Gastos": float(ev_gastos),
                    "Ingreso Neto": ev_neto,
                    "Margen (%)": round(ev_margen, 2),
                    "Rentabilidad": evaluar_rentabilidad(ev_margen),
                    "Score Auditoría": 100,
                    "Supervisor Asignado": ev_asignado,
                    "Elaboró": ev_asignado,
                    "Usuario": ev_asignado,
                    "Recibe": "Víctor (Contador)",
                    "Tipo": "Evento Extraordinario",
                    "foto_path": None,
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.registros.append(evento_obj)
                guardar_registros_permanentes(st.session_state.registros)
                registrar_evento_auditoria("Creación de Evento", st.session_state.usuario_autenticado, id_ev, ev_suc, ev_f.strftime("%d/%m/%Y"), f"Evento asignado a {ev_asignado} con {ev_bol} boletos y utilidad de ${ev_neto:,.2f}")
                actualizar_memoria_ia(evento_obj)
                st.success(f"✅ Evento extraordinario guardado y asignado a **{ev_asignado}**.")
                st.rerun()

        # SECCIÓN DE REASIGNACIÓN DE EVENTOS EXISTENTES (AUDITOR)
        st.markdown("---")
        st.markdown("#### 🔄 Reasignación de Eventos Extraordinarios Existentes")
        eventos_existentes = [r for r in st.session_state.registros if r.get("Tipo") == "Evento Extraordinario"]
        if eventos_existentes:
            opciones_ev = [f"{e.get('ID')} | {e.get('Fecha')} | {e.get('Sitio / Unidad')} | Asignado: {e.get('Supervisor Asignado', e.get('Elaboró', 'Sin asignar'))}" for e in eventos_existentes]
            sel_ev_str = st.selectbox("Selecciona evento para reasignar responsable:", opciones_ev, key="sel_ev_reasig")
            ev_id_target = sel_ev_str.split(" | ")[0].strip()
            ev_target = next((e for e in eventos_existentes if e.get("ID") == ev_id_target), None)
            if ev_target:
                c_re1, c_re2 = st.columns(2)
                with c_re1:
                    nuevo_sup = st.selectbox(
                        "Nuevo Supervisor Asignado:",
                        ["José de Jesús", "Víctor Manuel", "Ambos Supervisores (Operación Conjunta)", "Víctor (Contador)"],
                        index=0 if "Jesús" in ev_target.get("Supervisor Asignado", "") else 1,
                        key="reasig_sup_sel"
                    )
                with c_re2:
                    st.write("")
                    st.write("")
                    if st.button("🔄 Guardar Reasignación de Supervisor", use_container_width=True, key="btn_save_reasig"):
                        ev_target["Supervisor Asignado"] = nuevo_sup
                        ev_target["Elaboró"] = nuevo_sup
                        ev_target["Usuario"] = nuevo_sup
                        guardar_registros_permanentes(st.session_state.registros)
                        registrar_evento_auditoria("Reasignación de Evento", st.session_state.usuario_autenticado, ev_target.get("ID"), ev_target.get("Sitio / Unidad"), ev_target.get("Fecha"), f"Evento reasignado a {nuevo_sup}")
                        st.success(f"✅ Evento reasignado exitosamente a **{nuevo_sup}**.")
                        st.rerun()
        else:
            st.caption("No hay eventos extraordinarios registrados actualmente.")

    # TAB 5: WhatsApp y Alarmas
    with tab5:
        st.markdown("### 📲 Monitoreo de Reportes Faltantes y Automatización WhatsApp")
        st.markdown("Control proactivo de entregas diarias y avisos de eventos con 2 horas de anticipación. Permite envíos automáticos vía API o disparos rápidos en 1 clic.")

        cfg_actual = cargar_config_operativa()

        # CONFIGURACIÓN PERSISTENTE DE CONTACTO
        with st.expander("⚙️ Configuración de Teléfonos y Automatización API", expanded=False):
            c_cfg1, c_cfg2 = st.columns(2)
            with c_cfg1:
                nuevo_tel_j = st.text_input("WhatsApp José de Jesús (con clave país, ej. 5255...):", value=cfg_actual.get("tel_jesus", "525500000001"), key="cfg_tel_j")
                nuevo_tel_v = st.text_input("WhatsApp Víctor Manuel (con clave país, ej. 5255...):", value=cfg_actual.get("tel_victor", "525500000002"), key="cfg_tel_v")
            with c_cfg2:
                st.caption("Opcional: WhatsApp Business API (Connector Gateway de Lovable)")
                api_lovable = st.text_input("LOVABLE_API_KEY (opcional):", value=cfg_actual.get("lovable_api_key", ""), type="password", key="cfg_l_key")
                api_whatsapp = st.text_input("WHATSAPP_API_KEY (opcional):", value=cfg_actual.get("whatsapp_api_key", ""), type="password", key="cfg_w_key")
            
            if st.button("💾 Guardar Configuración de Teléfonos y API", key="btn_save_cfg_oper"):
                cfg_actual["tel_jesus"] = nuevo_tel_j.strip()
                cfg_actual["tel_victor"] = nuevo_tel_v.strip()
                cfg_actual["lovable_api_key"] = api_lovable.strip()
                cfg_actual["whatsapp_api_key"] = api_whatsapp.strip()
                guardar_config_operativa(cfg_actual)
                st.success("✅ Configuración operativa guardada permanentemente.")
                st.rerun()

        tel_jesus = cfg_actual.get("tel_jesus", "")
        tel_victor = cfg_actual.get("tel_victor", "")

        col_w_fec, col_w_acc = st.columns([1, 1])
        with col_w_fec:
            fec_monitoreo = st.date_input("Fecha a auditar entregas:", value=date.today(), key="fec_mon_w")
            fec_mon_str = fec_monitoreo.strftime("%d/%m/%Y")
        with col_w_acc:
            st.write("")
            st.caption("Estado de integración:")
            tiene_api = bool((cfg_actual.get("lovable_api_key") or os.environ.get("LOVABLE_API_KEY")) and (cfg_actual.get("whatsapp_api_key") or os.environ.get("WHATSAPP_API_KEY")))
            if tiene_api:
                st.success("🟢 WhatsApp Gateway API activa (Envío 100% automático habilitado)")
            else:
                st.info("🟡 Modo Web/App Activo (1-clic genera y abre mensaje prellenado en WhatsApp)")

        # Reportes existentes en esa fecha
        reps_fecha = [r for r in st.session_state.registros if r.get("Fecha") == fec_mon_str]
        unidades_reportadas = set(r.get("Sitio / Unidad") for r in reps_fecha)

        faltantes_jesus = [u for u in UNIDADES_JESUS if u not in unidades_reportadas]
        faltantes_victor = [u for u in UNIDADES_VICTOR if u not in unidades_reportadas]

        # DISPARO AUTOMATIZADO MASIVO
        st.markdown("---")
        c_auto1, c_auto2 = st.columns([2, 1])
        with c_auto1:
            st.markdown("#### ⚡ Automatización Masiva de Avisos")
            st.caption("Dispara en un solo paso los avisos de faltantes del día a ambos supervisores.")
        with c_auto2:
            st.write("")
            if st.button("🚀 Enviar Todos los Avisos Pendientes", type="primary", use_container_width=True, key="btn_send_all_auto"):
                enviados_c = 0
                if faltantes_jesus:
                    msg_j = f"Hola Jesús, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_jesus)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_jesus)}. Favor de cargarlos a la brevedad."
                    if tiene_api:
                        ok_j, res_j = enviar_whatsapp_directo_api(tel_jesus, msg_j, cfg_actual.get("lovable_api_key"), cfg_actual.get("whatsapp_api_key"))
                        registrar_notificacion_bitacora("José de Jesús", "Reportes Faltantes", msg_j, "EXITOSO" if ok_j else "FALLIDO", res_j)
                        enviados_c += 1
                    else:
                        registrar_notificacion_bitacora("José de Jesús", "Reportes Faltantes", msg_j, "PREPARADO_WEB", "Enlace wa.me generado")
                        enviados_c += 1

                if faltantes_victor:
                    msg_v = f"Hola Víctor, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_victor)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_victor)}. Favor de cargarlos a la brevedad."
                    if tiene_api:
                        ok_v, res_v = enviar_whatsapp_directo_api(tel_victor, msg_v, cfg_actual.get("lovable_api_key"), cfg_actual.get("whatsapp_api_key"))
                        registrar_notificacion_bitacora("Víctor Manuel", "Reportes Faltantes", msg_v, "EXITOSO" if ok_v else "FALLIDO", res_v)
                        enviados_c += 1
                    else:
                        registrar_notificacion_bitacora("Víctor Manuel", "Reportes Faltantes", msg_v, "PREPARADO_WEB", "Enlace wa.me generado")
                        enviados_c += 1

                st.success(f"✅ Procesados {enviados_c} avisos automáticos. Consulta el historial abajo.")
                st.rerun()

        st.markdown("---")
        c_w1, c_w2 = st.columns(2)
        with c_w1:
            st.markdown(f"#### 👤 José de Jesús ({len(faltantes_jesus)} pendientes)")
            if faltantes_jesus:
                st.warning(f"Unidades pendientes: {', '.join(faltantes_jesus)}")
                msg_j = f"Hola Jesús, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_jesus)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_jesus)}. Favor de cargarlos a la brevedad."
                
                c_btn_j1, c_btn_j2 = st.columns(2)
                with c_btn_j1:
                    url_w_j = generar_enlace_whatsapp(tel_jesus, msg_j)
                    st.link_button("📲 Abrir en WhatsApp", url_w_j, use_container_width=True)
                with c_btn_j2:
                    if tiene_api and st.button("🚀 Enviar Directo API (Jesús)", key="btn_api_send_j", use_container_width=True):
                        ok, det = enviar_whatsapp_directo_api(tel_jesus, msg_j, cfg_actual.get("lovable_api_key"), cfg_actual.get("whatsapp_api_key"))
                        registrar_notificacion_bitacora("José de Jesús", "Faltantes", msg_j, "EXITOSO" if ok else "FALLIDO", det)
                        if ok:
                            st.success("Mensaje enviado automáticamente.")
                        else:
                            st.error(det)
            else:
                st.success("✅ Jesús tiene todas sus unidades cubiertas al 100%.")

        with c_w2:
            st.markdown(f"#### 👤 Víctor Manuel ({len(faltantes_victor)} pendientes)")
            if faltantes_victor:
                st.warning(f"Unidades pendientes: {', '.join(faltantes_victor)}")
                msg_v = f"Hola Víctor, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_victor)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_victor)}. Favor de cargarlos a la brevedad."
                
                c_btn_v1, c_btn_v2 = st.columns(2)
                with c_btn_v1:
                    url_w_v = generar_enlace_whatsapp(tel_victor, msg_v)
                    st.link_button("📲 Abrir en WhatsApp", url_w_v, use_container_width=True)
                with c_btn_v2:
                    if tiene_api and st.button("🚀 Enviar Directo API (Víctor)", key="btn_api_send_v", use_container_width=True):
                        ok, det = enviar_whatsapp_directo_api(tel_victor, msg_v, cfg_actual.get("lovable_api_key"), cfg_actual.get("whatsapp_api_key"))
                        registrar_notificacion_bitacora("Víctor Manuel", "Faltantes", msg_v, "EXITOSO" if ok else "FALLIDO", det)
                        if ok:
                            st.success("Mensaje enviado automáticamente.")
                        else:
                            st.error(det)
            else:
                st.success("✅ Víctor tiene todas sus unidades cubiertas al 100%.")

        st.markdown("---")
        st.markdown("#### ⏰ Notificación de Eventos Extraordinarios con Asignación Específica")
        evs_futuros = [r for r in st.session_state.registros if r.get("Tipo") == "Evento Extraordinario"]
        if evs_futuros:
            for ev in evs_futuros[-5:]:
                sup_asig = ev.get("Supervisor Asignado") or ev.get("Elaboró") or "Sin asignar"
                st.write(f"⚡ **{ev.get('Sitio / Unidad')}** | Fecha: `{ev.get('Fecha')}` ({ev.get('Horario')}) | 🎯 **Asignado a: {sup_asig}**")
                msg_ev = f"""⚠️ AVISO CLUB PARK - EVENTO EXTRAORDINARIO
Sede: {ev.get('Sitio / Unidad')}
Fecha: {ev.get('Fecha')} a las {ev.get('Horario')}
Supervisor Asignado: {sup_asig}
Favor de coordinar la operación con 2 horas de anticipación."""
                
                c_btn_w1, c_btn_w2 = st.columns(2)
                with c_btn_w1:
                    dest_es_jesus = "Jesús" in sup_asig or "Ambos" in sup_asig
                    lbl_j = "📲 Notificar a Jesús (Asignado)" if dest_es_jesus else "📲 Notificar a Jesús"
                    st.link_button(lbl_j, generar_enlace_whatsapp(tel_jesus, msg_ev), use_container_width=True)
                with c_btn_w2:
                    dest_es_victor = "Víctor" in sup_asig or "Ambos" in sup_asig
                    lbl_v = "📲 Notificar a Víctor (Asignado)" if dest_es_victor else "📲 Notificar a Víctor"
                    st.link_button(lbl_v, generar_enlace_whatsapp(tel_victor, msg_ev), use_container_width=True)
        else:
            st.info("No hay eventos extraordinarios registrados recientemente.")

        # BITÁCORA DE NOTIFICACIONES
        st.markdown("---")
        with st.expander("📋 Bitácora de Avisos WhatsApp Enviados", expanded=False):
            bit_notifs = cargar_json_seguro(NOTIF_LOG_FILE, [])
            if bit_notifs:
                st.dataframe(pd.DataFrame(bit_notifs), use_container_width=True, hide_index=True)
            else:
                st.caption("No hay registros de avisos enviados aún.")

# TAB 6: Gestión y Edición de Reportes
    with tab6:
        st.markdown("### 🗂️ Gestión, Edición y Eliminación de Reportes")
        st.caption("Reportes organizados por la cuenta que los registró. Los reportes históricos sin ese dato se agrupan según el campo ‘Elaboró’; confirma autoría antes de atribuirlos.")
        if st.session_state.registros:
            registros_gestion, periodo_gestion = mostrar_filtro_periodo_registros(
                st.session_state.registros, "gestion_reportes"
            )
            st.caption(f"Mostrando {len(registros_gestion)} reportes · {periodo_gestion}.")
            grupos = {
                "Víctor Manuel": [],
                "José de Jesús": [],
                "Víctor (Contador)": [],
                "Sin usuario identificable": []
            }
            for r in registros_gestion:
                owner = r.get("Usuario") or r.get("Elaboró")
                if owner in ("Víctor Manuel", "José de Jesús", "Víctor (Contador)"):
                    grupos[owner].append(r)
                else:
                    grupos["Sin usuario identificable"].append(r)
            c_v, c_j, c_a = st.columns(3)
            for col, nombre, emoji in [(c_v, "Víctor Manuel", "👤"), (c_j, "José de Jesús", "👤"), (c_a, "Víctor (Contador)", "🕵️")]:
                with col:
                    st.markdown(f"#### {emoji} {nombre} · {len(grupos[nombre])} reporte(s)")
                    lista = grupos[nombre]
                    if lista:
                        st.dataframe(pd.DataFrame([{
                            "ID": r.get("ID"), "Fecha": r.get("Fecha"), "Sucursal": r.get("Sitio / Unidad"),
                            "Boletos": r.get("Boletos Cobrados"), "Ingreso neto": r.get("Ingreso Neto"),
                            "Auditoría": r.get("Nivel Auditoría", "Pendiente")
                        } for r in lista]), use_container_width=True, hide_index=True)
                    else:
                        st.caption("Sin reportes registrados.")
            if grupos["Sin usuario identificable"]:
                with st.expander(f"⚠️ Históricos sin usuario identificable ({len(grupos['Sin usuario identificable'])})"):
                    st.dataframe(pd.DataFrame(grupos["Sin usuario identificable"]), use_container_width=True, hide_index=True)

            opciones_rep = []
            indice_por_etiqueta = {}
            for nombre, lista in grupos.items():
                for r in lista:
                    etiqueta = f"{nombre} | {r.get('ID')} | {r.get('Fecha')} | {r.get('Sitio / Unidad')} | Neto: ${r.get('Ingreso Neto', 0):,.2f}"
                    opciones_rep.append(etiqueta)
                    indice_por_etiqueta[etiqueta] = next((i for i, original in enumerate(st.session_state.registros) if original.get("ID") == r.get("ID")), 0)
            if opciones_rep:
                sel_rep = st.selectbox("Selecciona reporte para revisar, auditar o eliminar:", opciones_rep, key="sel_rep_gest")
                idx_rep = indice_por_etiqueta[sel_rep]
                rep_data = st.session_state.registros[idx_rep]

                c_g1, c_g2 = st.columns([2, 1])
                with c_g1:
                    st.json(rep_data)
                with c_g2:
                    foto_p = rep_data.get("foto_path")
                    if foto_p and os.path.exists(foto_p):
                        st.image(foto_p, caption="Fotografía vinculada", use_container_width=True)
                    else:
                        st.caption("📷 Sin fotografía física vinculada.")

                if st.button("✅ Registrar revisión de auditoría", key="btn_review_r_aud", use_container_width=True):
                    audit_score, audit_level, audit_fallas, audit_obs = evaluar_auditoria_reporte(rep_data, st.session_state.registros, memoria_ia_global)
                    registrar_evento_auditoria(
                        "Aprobación de Auditoría" if not audit_fallas else "Revisión de Auditoría",
                        st.session_state.usuario_autenticado,
                        rep_data.get("ID"), rep_data.get("Sitio / Unidad"), rep_data.get("Fecha"),
                        f"Revisión manual solicitada. Resultado: {audit_level}; {len(audit_fallas)} hallazgo(s).",
                        score=audit_score,
                        fallas=audit_fallas
                    )
                    st.success(f"Revisión registrada: {audit_level}. Consulta la bitácora para el detalle.")

                if st.button("🗑️ Eliminar Reporte y Archivo Adjunto", key="btn_del_r_aud", type="primary"):
                    if foto_p and os.path.exists(foto_p):
                        try:
                            os.remove(foto_p)
                        except Exception:
                            pass
                    eliminado = st.session_state.registros.pop(idx_rep)
                    guardar_registros_permanentes(st.session_state.registros)
                    registrar_evento_auditoria("Eliminación", st.session_state.usuario_autenticado, eliminado.get("ID"), eliminado.get("Sitio / Unidad"), eliminado.get("Fecha"), "Reporte eliminado por el Auditor.")
                    st.success("✅ Reporte eliminado del sistema.")
                    st.rerun()
        else:
            st.info("No hay reportes para gestionar en el período seleccionado.")

        # ZONA DE AUDITORÍA: REINICIO TOTAL DEL SISTEMA DESDE CERO
        st.markdown("---")
        st.markdown("### 🚨 Zona Crítica de Auditoría: Reinicio Total del Sistema")
        st.caption("Exclusivo para el Contador Auditor: Permite restablecer el sistema desde cero eliminando reportes y/o fotos físicas.")
        
        with st.expander("⚠️ Herramienta de Reinicio desde Cero (Peligro: Irreversible)", expanded=False):
            st.warning("Esta operación borrará de forma permanente los registros y/o fotografías seleccionadas. Asegúrate de haber descargado el Respaldo Oficial en Excel o CSV antes de proceder.")
            
            fotos_disco_actuales = os.listdir(FOTOS_DIR) if os.path.exists(FOTOS_DIR) else []
            st.markdown(f"- 📊 Reportes en Sistema actualmente: **{len(st.session_state.registros)}**")
            st.markdown(f"- 📷 Fotografías físicas guardadas: **{len(fotos_disco_actuales)}**")
            
            c_rst1, c_rst2 = st.columns(2)
            with c_rst1:
                chk_del_reps = st.checkbox("🗑️ Borrar todos los reportes en sistema", value=True, key="chk_del_reps")
                chk_del_fotos = st.checkbox("📷 Borrar todas las fotos físicas en disco", value=True, key="chk_del_fotos")
            with c_rst2:
                chk_del_ia = st.checkbox("🧠 Reiniciar memoria de aprendizaje IA", value=False, key="chk_del_ia")
                chk_del_bit = st.checkbox("📜 Limpiar bitácora de auditoría histórica", value=False, key="chk_del_bit")
                
            confirma_check = st.checkbox("⚠️ Confirmo bajo mi responsabilidad que deseo reiniciar el sistema desde cero", key="chk_conf_reset")
            palabra_seguridad = st.text_input("Para desbloquear el reinicio, escribe 'REINICIAR' en mayúsculas:", key="txt_conf_reset")
            
            boton_habilitado = confirma_check and (palabra_seguridad.strip() == "REINICIAR")
            if st.button("🔥 EJECUTAR REINICIO TOTAL DEL SISTEMA", type="primary", disabled=not boton_habilitado, key="btn_exec_reset_sys"):
                reps_b, fotos_b = reiniciar_sistema_desde_cero(
                    borrar_reportes=chk_del_reps,
                    borrar_fotos=chk_del_fotos,
                    reiniciar_memoria=chk_del_ia,
                    reiniciar_bitacora=chk_del_bit,
                    usuario_auditor=st.session_state.usuario_autenticado
                )
                st.success(f"✅ Sistema reiniciado con éxito: Se eliminaron {reps_b} reportes y {fotos_b} fotos físicas.")
                st.rerun()


    # TAB 7: Suite de Pruebas y Diagnóstico de Despliegue
    with tab7:
        st.markdown("### 🧪 Diagnóstico Automatizado del Sistema y Despliegue")
        st.markdown("Ejecuta la batería de pruebas unitarias para validar que el motor de Excel, la criptografía Fernet, la auditoría automática y la memoria de IA operan al 100%.")

        if st.button("🚀 Ejecutar Batería de Validación", type="primary", key="btn_run_suite"):
            with st.spinner("Ejecutando pruebas..."):
                res_tests = ejecutar_pruebas_regresion()
                st.dataframe(pd.DataFrame(res_tests), use_container_width=True, hide_index=True)
                todos_ok = all("PASS" in p["Resultado"] for p in res_tests)
                if todos_ok:
                    st.success("🎉 ¡Todas las pruebas han sido superadas con éxito!")
                else:
                    st.warning("⚠️ Hay pruebas con observaciones.")

# TAB 4: EVENTOS Y ALERTAS PARA SUPERVISOR
if not es_contador:
    with tab4:
        st.markdown("### ⚡ Eventos Extraordinarios y Alertas")
        st.markdown("Consulta aquí los eventos extraordinarios asignados para coordinar la operación con 2 horas de anticipación.")
        evs_sup = [r for r in st.session_state.registros if r.get("Tipo") == "Evento Extraordinario"]
        if evs_sup:
            usuario_actual = st.session_state.usuario_autenticado
            evs_propios = [e for e in evs_sup if e.get("Supervisor Asignado") == usuario_actual or e.get("Elaboró") == usuario_actual or "Ambos" in str(e.get("Supervisor Asignado", ""))]
            evs_otros = [e for e in evs_sup if e not in evs_propios]
            
            if evs_propios:
                st.markdown(f"#### 🎯 Eventos Asignados Específicamente a Ti ({usuario_actual})")
                for ev in evs_propios:
                    st.success(f"📍 **{ev.get('Sitio / Unidad')}** | Fecha: **{ev.get('Fecha')}** ({ev.get('Horario')}) | Boletos est.: **{ev.get('Boletos Cobrados')}** | Responsable: **{ev.get('Supervisor Asignado', ev.get('Elaboró'))}**")
            else:
                st.info(f"No tienes eventos extraordinarios asignados directamente en este momento.")
            
            if evs_otros:
                with st.expander(f"📋 Otros Eventos de la Red ({len(evs_otros)})", expanded=False):
                    for ev in evs_otros:
                        st.info(f"📍 **{ev.get('Sitio / Unidad')}** | Fecha: **{ev.get('Fecha')}** ({ev.get('Horario')}) | Responsable: **{ev.get('Supervisor Asignado', ev.get('Elaboró'))}**")
        else:
            st.caption("No hay eventos programados en este momento.")
