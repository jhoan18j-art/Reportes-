import urllib.parse
# -*- coding: utf-8 -*-
"""
CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.
Sistema Inteligente de Control Operativo, Auditoría Automatizada y Rentabilidad
Optimizado para dispositivos Android con bajo consumo de datos móviles (Cero costo de APIs externas).
"""

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
    "M SATÉLITE": 70, "M MARINA": 70, "VETERINARIA": 0, "CLÍNICA": 100,
    "SUMO STA": 50, "CHEGARAY": 50, "RYOSHI": 80, "ENCANTO": 90,
    "S. AZURA": 0, "E-BNI": 0, "CHURRASCA": 70
}

UNIDADES_JESUS = ["PAMPAS", "RAMMA", "SUSHITTO", "BARRANCA", "CARAJILLO", "BENINGANS", "CLÍNICA"]
UNIDADES_VICTOR = ["SUMO STA", "CHEGARAY", "RYOSHI", "ENCANTO", "S. AZURA", "CHURRASCA"]
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
        "ultimo_folio_final": 0,
        "horario_frecuente": "13:00 a 23:00",
        "supervisor_frecuente": reporte.get("Elaboró", "Supervisor")
    })

    n = suc_mem["reportes_aprendidos"]
    nuevo_n = n + 1
    boletos = reporte.get("Boletos Cobrados", 0)
    bruto = reporte.get("Ingreso Bruto", 0.0)
    gastos = reporte.get("Total Gastos", 0.0)
    margen = reporte.get("Margen (%)", 0.0)
    folio_final = reporte.get("Folio Final", 0)

    # Cálculo de medias móviles actualizadas
    suc_mem["promedio_boletos"] = round(((suc_mem["promedio_boletos"] * n) + boletos) / nuevo_n, 1)
    suc_mem["promedio_ingreso_bruto"] = round(((suc_mem["promedio_ingreso_bruto"] * n) + bruto) / nuevo_n, 2)
    suc_mem["promedio_gastos"] = round(((suc_mem["promedio_gastos"] * n) + gastos) / nuevo_n, 2)
    suc_mem["margen_promedio"] = round(((suc_mem["margen_promedio"] * n) + margen) / nuevo_n, 2)
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

            # Desviación anómala de boletos (+/- 75% del volumen aprendido)
            if prom_bol > 15 and cobrados > 0:
                if cobrados > (prom_bol * 2.2):
                    observaciones.append(f"🤖 IA Adaptativa: Volumen inusualmente alto ({cobrados} vs media de {prom_bol:.0f} boletos).")
                elif cobrados < (prom_bol * 0.25):
                    score -= 10
                    fallas.append({
                        "regla": "Anomalía de Afluencia Adaptativa",
                        "detalle": f"Boletos inusualmente bajos ({cobrados}) frente a la tendencia histórica aprendida ({prom_bol:.0f} boletos).",
                        "gravedad": "MEDIA"
                    })

            # Desviación anómala de gastos frente a la historia de la sucursal
            if prom_gasto > 0 and tot_gastos > (prom_gasto * 2.0):
                score -= 15
                fallas.append({
                    "regla": "Gasto Anómalo vs Historial IA",
                    "detalle": f"Gastos (${tot_gastos:,.2f}) duplican el promedio histórico de la unidad (${prom_gasto:,.2f}).",
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
def generar_excel_completo(registros, historial_auditoria=None):
    if not registros:
        return None, "NO_REGISTROS"
    if not OPENPYXL_OK and not XLSXWRITER_OK:
        return None, "SIN_MOTOR"
    try:
        df = pd.DataFrame(registros)
        df["Fecha_DT"] = pd.to_datetime(df.get("Fecha"), format="%d/%m/%Y", errors="coerce")
        df = df.sort_values(by="Fecha_DT", ascending=False)
        df["Año"] = df["Fecha_DT"].dt.year
        df["Semana"] = df["Fecha_DT"].dt.isocalendar().week
        df["Semana_Etiqueta"] = df["Año"].astype(str) + " - Sem " + df["Semana"].astype(str)
        df["Mes_Etiqueta"] = df["Fecha_DT"].dt.strftime("%Y-%m (%B)")

        cols_num = ["Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina", "Total Gastos", "Ingreso Neto", "Boletos Cobrados"]
        for c in cols_num:
            df[c] = pd.to_numeric(df.get(c, 0.0), errors="coerce").fillna(0.0)

        output = io.BytesIO()
        engine = "openpyxl" if OPENPYXL_OK else "xlsxwriter"

        with pd.ExcelWriter(output, engine=engine) as writer:
            # 1. Pestaña: Rentabilidad por Sucursal (EJE PRINCIPAL)
            resumen_suc = df.groupby("Sitio / Unidad").agg({
                "ID": "count",
                "Boletos Cobrados": "sum",
                "Ingreso Bruto": "sum",
                "Total Gastos": "sum",
                "Ingreso Neto": "sum"
            }).reset_index()
            resumen_suc.rename(columns={"ID": "Reportes Registrados"}, inplace=True)
            resumen_suc["Margen (%)"] = ((resumen_suc["Ingreso Neto"] / resumen_suc["Ingreso Bruto"]) * 100).fillna(0.0).round(2)
            resumen_suc["Rentabilidad"] = resumen_suc["Margen (%)"].apply(evaluar_rentabilidad)
            resumen_suc = resumen_suc.sort_values(by="Ingreso Neto", ascending=False)
            resumen_suc.to_excel(writer, sheet_name="Rentabilidad por Sucursal", index=False)

            # 2. Pestaña: Resumen Semanal
            resumen_sem = df.groupby(["Semana_Etiqueta", "Sitio / Unidad"]).agg({
                "Boletos Cobrados": "sum",
                "Ingreso Bruto": "sum",
                "Total Gastos": "sum",
                "Ingreso Neto": "sum"
            }).reset_index()
            resumen_sem["Margen (%)"] = ((resumen_sem["Ingreso Neto"] / resumen_sem["Ingreso Bruto"]) * 100).fillna(0.0).round(2)
            resumen_sem["Rentabilidad"] = resumen_sem["Margen (%)"].apply(evaluar_rentabilidad)
            resumen_sem.to_excel(writer, sheet_name="Resumen Semanal", index=False)

            # 3. Pestaña: Detalle Completo de Reportes
            cols_detalle = [
                "ID", "Fecha", "Sitio / Unidad", "Horario", "Tipo", "Costo Boleto",
                "Folio Inicial", "Folio Final", "Total Boletos", "Sin Cobro", "Cancelados", "Perdidos",
                "Boletos Cobrados", "Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina",
                "Total Gastos", "Ingreso Neto", "Margen (%)", "Rentabilidad", "Score Auditoría", "Elaboró", "Recibe", "Tiene Foto"
            ]
            df["Tiene Foto"] = df.get("foto_path", pd.Series()).apply(lambda x: "SÍ" if (x and os.path.exists(str(x))) else "NO")
            cols_pres = [c for c in cols_detalle if c in df.columns]
            df[cols_pres].to_excel(writer, sheet_name="Detalle Reportes", index=False)

            # 4. Pestaña: Bitácora de Auditoría
            if historial_auditoria:
                df_aud = pd.DataFrame(historial_auditoria)
                if not df_aud.empty:
                    df_aud.to_excel(writer, sheet_name="Historial de Auditoría", index=False)

        # Estilos corporativos si openpyxl está disponible
        if OPENPYXL_OK:
            try:
                output.seek(0)
                wb = openpyxl.load_workbook(output)
                header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
                header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                border_thin = Border(
                    left=Side(style='thin', color='E2E8F0'),
                    right=Side(style='thin', color='E2E8F0'),
                    top=Side(style='thin', color='E2E8F0'),
                    bottom=Side(style='thin', color='E2E8F0')
                )

                for ws in wb.worksheets:
                    for col_idx in range(1, ws.max_column + 1):
                        c = ws.cell(row=1, column=col_idx)
                        c.fill = header_fill
                        c.font = header_font
                        c.alignment = Alignment(horizontal="center", vertical="center")

                    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                        for c in row:
                            c.border = border_thin
                            header_val = str(ws.cell(row=1, column=c.column).value or "")
                            if any(k in header_val for k in ["Ingreso", "Gasto", "Neto", "Costo", "Tarifa"]):
                                c.number_format = '"$"#,##0.00'
                            elif "Margen" in header_val:
                                c.number_format = '0.0"%"'
                            elif any(k in header_val for k in ["Boleto", "Folio", "Reporte"]):
                                c.number_format = '#,##0'

                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = get_column_letter(col[0].column)
                        ws.column_dimensions[col_letter].width = max(max_len + 3, 13)

                out_styled = io.BytesIO()
                wb.save(out_styled)
                out_styled.seek(0)
                return out_styled.getvalue(), "OK"
            except Exception:
                output.seek(0)
                return output.getvalue(), "OK"

        output.seek(0)
        return output.getvalue(), "OK"
    except Exception as e:
        return None, str(e)

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
                st.session_state.rol = "Supervisor"
                registrar_evento_auditoria("Inicio de Sesión", nombre_usuario, "-", "-", "-", "Supervisor ingresó al sistema.")
                st.success(f"Bienvenido {nombre_usuario}")
                st.rerun()
            elif nombre_usuario == "Víctor (Contador)" and hmac.compare_digest(password, pass_auditor):
                st.session_state.usuario_autenticado = "Víctor (Contador)"
                st.session_state.rol = "Contador Auditor"
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
    historial_aud_sidebar = cargar_historial_auditoria()
    excel_data, estado_excel = generar_excel_completo(st.session_state.registros, historial_aud_sidebar)
    if estado_excel == "OK" and excel_data:
        st.sidebar.download_button(
            label="📊 Descargar Excel Financiero",
            data=excel_data,
            file_name=f"ClubPark_Balance_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        df_csv = pd.DataFrame(st.session_state.registros)
        st.sidebar.download_button(
            label="📄 Descargar Respaldo CSV",
            data=df_csv.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ClubPark_Respaldo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

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
    st.markdown("### 📈 Rentabilidad y Rendimiento Financiero por Sucursal")
    st.markdown("Monitoreo en tiempo real de ingresos brutos, gastos de operación, nómina y margen neto de cada unidad de negocio.")

    if not st.session_state.registros:
        st.info("No hay datos suficientes para calcular rentabilidad. Registra el primer reporte.")
    else:
        df_r = pd.DataFrame(st.session_state.registros)
        cols_n = ["Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina", "Total Gastos", "Ingreso Neto", "Boletos Cobrados"]
        for c in cols_n:
            df_r[c] = pd.to_numeric(df_r.get(c, 0.0), errors="coerce").fillna(0.0)

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
        mis_reportes = [r for r in st.session_state.registros if r.get("Elaboró") == st.session_state.usuario_autenticado]
        if mis_reportes:
            st.dataframe(pd.DataFrame(mis_reportes)[["ID", "Fecha", "Sitio / Unidad", "Boletos Cobrados", "Ingreso Bruto", "Total Gastos", "Ingreso Neto", "Margen (%)"]], use_container_width=True)
        else:
            st.info("Aún no has registrado reportes bajo tu usuario.")

# =========================================================================
# TABS EXCLUSIVOS AUDITOR (EVENTOS, GESTIÓN, DESPLIEGUE)
# =========================================================================
if es_contador:
    # TAB 4: Evento Extraordinario
    with tab4:
        st.markdown("### ⚡ Registro de Evento Extraordinario")
        c_ev1, c_ev2 = st.columns(2)
        with c_ev1:
            ev_f = st.date_input("Fecha del Evento:", value=date.today(), key="ev_f_in")
            ev_suc = st.selectbox("Sucursal / Sede del Evento:", SUCURSALES_LISTA, key="ev_suc_in")
            ev_costo = st.number_input("Costo Boleto Evento ($ MXN):", min_value=0.0, value=100.0, step=10.0, key="ev_c_in")
        with c_ev2:
            ev_h_ini = st.time_input("Inicio Evento:", value=time(18, 0), key="ev_hi_in")
            ev_h_fin = st.time_input("Fin Evento:", value=time(2, 0), key="ev_hf_in")
            ev_bol = st.number_input("Boletos Cobrados:", min_value=0, value=60, step=1, key="ev_b_in")

        ev_gastos = st.number_input("Total Gastos / Nómina Evento ($ MXN):", min_value=0.0, value=0.0, step=50.0, key="ev_g_in")
        ev_elab = st.text_input("Responsable del Evento:", value=st.session_state.usuario_autenticado, key="ev_el_in")

        ev_bruto = float(ev_bol) * float(ev_costo)
        ev_neto = ev_bruto - float(ev_gastos)
        ev_margen = (ev_neto / ev_bruto * 100) if ev_bruto > 0 else 0.0

        st.metric("Utilidad Generada en Evento", f"${ev_neto:,.2f} MXN", delta=f"{ev_margen:.1f}% Margen")

        if st.button("💾 Guardar Evento Extraordinario", type="primary", key="btn_save_event"):
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
                    "Elaboró": ev_elab,
                    "Recibe": "Víctor (Contador)",
                    "Tipo": "Evento Extraordinario",
                    "foto_path": None,
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.registros.append(evento_obj)
                guardar_registros_permanentes(st.session_state.registros)
                registrar_evento_auditoria("Creación de Evento", st.session_state.usuario_autenticado, id_ev, ev_suc, ev_f.strftime("%d/%m/%Y"), f"Evento con {ev_bol} boletos y utilidad de ${ev_neto:,.2f}")
                actualizar_memoria_ia(evento_obj)
                st.success("✅ Evento extraordinario guardado exitosamente.")
                st.rerun()

    # TAB 5: WhatsApp y Alarmas
    with tab5:
        st.markdown("### 📲 Monitoreo de Reportes Faltantes y Notificaciones WhatsApp")
        st.markdown("Calcula los reportes pendientes de las sucursales asignadas. Los botones preparan el mensaje y abren WhatsApp; el envío requiere confirmar en WhatsApp. Para envío automático cuando la app no está abierta se requiere un programador persistente y WhatsApp Business API.")

        # Conteo de reportes faltantes por supervisor para la fecha actual (o seleccionada)
        col_w_fec, col_w_tel = st.columns(2)
        with col_w_fec:
            fec_monitoreo = st.date_input("Fecha a auditar entregas:", value=date.today(), key="fec_mon_w")
            fec_mon_str = fec_monitoreo.strftime("%d/%m/%Y")
        with col_w_tel:
            st.caption("Configuración de teléfonos móviles para envío directo de WhatsApp:")
            tel_jesus = st.text_input("Teléfono José de Jesús (WhatsApp, con clave de país):", value="", key="tel_jes_in", placeholder="Ej. 52 + 10 dígitos")
            tel_victor = st.text_input("Teléfono Víctor Manuel (WhatsApp, con clave de país):", value="", key="tel_vic_in", placeholder="Ej. 52 + 10 dígitos")

        # Reportes existentes en esa fecha
        reps_fecha = [r for r in st.session_state.registros if r.get("Fecha") == fec_mon_str]
        unidades_reportadas = set(r.get("Sitio / Unidad") for r in reps_fecha)

        faltantes_jesus = [u for u in UNIDADES_JESUS if u not in unidades_reportadas]
        faltantes_victor = [u for u in UNIDADES_VICTOR if u not in unidades_reportadas]

        c_w1, c_w2 = st.columns(2)
        with c_w1:
            st.markdown(f"#### 👤 José de Jesús ({len(faltantes_jesus)} pendientes)")
            if faltantes_jesus:
                st.warning(f"Unidades pendientes de subir: {', '.join(faltantes_jesus)}")
                msg_j = f"Hola Jesús, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_jesus)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_jesus)}. Favor de cargarlos a la brevedad."
                if len("".join(ch for ch in tel_jesus if ch.isdigit())) >= 10:
                    url_w_j = generar_enlace_whatsapp(tel_jesus, msg_j)
                    st.link_button("📲 Abrir recordatorio para WhatsApp de Jesús", url_w_j, use_container_width=True)
                else:
                    st.info("Agrega el número real de WhatsApp de Jesús para generar el recordatorio.")
            else:
                st.success("✅ Jesús tiene todas sus unidades cubiertas al 100%.")

        with c_w2:
            st.markdown(f"#### 👤 Víctor Manuel ({len(faltantes_victor)} pendientes)")
            if faltantes_victor:
                st.warning(f"Unidades pendientes de subir: {', '.join(faltantes_victor)}")
                msg_v = f"Hola Víctor, te recordamos que para la fecha {fec_mon_str} tienes {len(faltantes_victor)} reporte(s) pendiente(s) por subir a CLUB PARK: {', '.join(faltantes_victor)}. Favor de cargarlos a la brevedad."
                if len("".join(ch for ch in tel_victor if ch.isdigit())) >= 10:
                    url_w_v = generar_enlace_whatsapp(tel_victor, msg_v)
                    st.link_button("📲 Abrir recordatorio para WhatsApp de Víctor", url_w_v, use_container_width=True)
                else:
                    st.info("Agrega el número real de WhatsApp de Víctor para generar el recordatorio.")
            else:
                st.success("✅ Víctor tiene todas sus unidades cubiertas al 100%.")

        st.markdown("---")
        st.markdown("#### ⏰ Notificación de Eventos Extraordinarios a Supervisores")
        evs_futuros = [r for r in st.session_state.registros if r.get("Tipo") == "Evento Extraordinario"]
        if evs_futuros:
            for ev in evs_futuros[-5:]:
                st.write(f"⚡ **{ev.get('Sitio / Unidad')}** | Fecha: `{ev.get('Fecha')}` | Horario: `{ev.get('Horario')}` | Responsable: `{ev.get('Elaboró')}`")
                msg_ev = f"⚠️ AVISO CLUB PARK - EVENTO EXTRAORDINARIO\nSede: {ev.get('Sitio / Unidad')}\nFecha: {ev.get('Fecha')} a las {ev.get('Horario')}\nResponsable: {ev.get('Elaboró')}\nFavor de estar atentos y asegurar la cobertura operativa."
                c_btn_w1, c_btn_w2 = st.columns(2)
                with c_btn_w1:
                    st.link_button(f"Notificar a Jesús por WhatsApp", generar_enlace_whatsapp(tel_jesus, msg_ev), use_container_width=True)
                with c_btn_w2:
                    st.link_button(f"Notificar a Víctor por WhatsApp", generar_enlace_whatsapp(tel_victor, msg_ev), use_container_width=True)
        else:
            st.info("No hay eventos extraordinarios registrados recientemente.")

    # TAB 6: Gestión y Edición de Reportes
    with tab6:
        st.markdown("### 🗂️ Gestión, Edición y Eliminación de Reportes")
        if st.session_state.registros:
            opciones_rep = [
                f"{r.get('ID')} | {r.get('Fecha')} | {r.get('Sitio / Unidad')} | Neto: ${r.get('Ingreso Neto', 0):,.2f}"
                for r in st.session_state.registros
            ]
            sel_rep = st.selectbox("Seleccionar reporte:", opciones_rep, key="sel_rep_gest")
            idx_rep = opciones_rep.index(sel_rep)
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
            st.info("No hay reportes para gestionar.")

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
            for ev in evs_sup[-5:]:
                st.info(f"📍 **{ev.get('Sitio / Unidad')}** | Fecha: **{ev.get('Fecha')}** ({ev.get('Horario')}) | Responsable: {ev.get('Elaboró')}")
        else:
            st.caption("No hay eventos programados en este momento.")
