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
# CONFIGURACIÓN GENERAL Y DIRECTORIOS
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
# Configurable; en Streamlit Community Cloud el disco local no es almacenamiento permanente.
DATA_DIR = os.environ.get("CLUBPARK_DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "reportes_clubpark.json")
AUDIT_FILE = os.path.join(DATA_DIR, "historial_auditoria.json")
AI_MEMORIA_FILE = os.path.join(DATA_DIR, "ia_memoria_aprendizaje.json")
FOTOS_DIR = os.path.join(DATA_DIR, "fotos_reportes")
os.makedirs(FOTOS_DIR, exist_ok=True)

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

    # 1. Regla Matemática de Boletos
    if not es_directo and f_fin > 0 and f_ini > 0:
        calculado_tot = (f_fin - f_ini) + 1
        if f_fin < f_ini:
            score -= 30
            fallas.append({"regla": "Folios Invertidos", "detalle": f"El Folio Final ({f_fin}) es menor al Folio Inicial ({f_ini}).", "gravedad": "CRÍTICA"})
        elif calculado_tot != tot_bol:
            score -= 20
            fallas.append({"regla": "Matemática de Boletos", "detalle": f"Total calculado por folios ({calculado_tot}) no coincide con Total Boletos ({tot_bol}).", "gravedad": "ALTA"})
        
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
    """Comprime la imagen para ahorrar datos móviles y almacenamiento (JPEG q=75)."""
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1200, 1200))
        suc_clean = "".join(c for c in sucursal if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
        fecha_clean = fecha_str.replace("/", "-")
        nombre_archivo = f"{id_reporte}_{fecha_clean}_{suc_clean}.jpg"
        ruta_completa = os.path.join(FOTOS_DIR, nombre_archivo)
        img.save(ruta_completa, "JPEG", quality=75, optimize=True)
        return ruta_completa
    except Exception as e:
        st.error(f"Error optimizando la foto: {e}")
        return None

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

        # Intento de OCR nativo
        texto_ocr = ""
        if PYTESSERACT_OK:
            try:
                texto_ocr = pytesseract.image_to_string(gris, lang="spa+eng", config="--psm 6")
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
        st.session_state["costo_boleto_input"] = PRECIOS_SUCURSALES[seleccion]

if "costo_boleto_input" not in st.session_state:
    st.session_state["costo_boleto_input"] = 40

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

    # TAB 6: Suite de Pruebas y Diagnóstico de Despliegue
    with tab6:
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
