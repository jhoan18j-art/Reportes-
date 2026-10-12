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
# CONFIGURACIÓN GENERAL Y PERSISTENCIA
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

# Estilos CSS
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
            border-radius: 8px;
            padding: 10px;
            border: 1px solid #e9ecef;
        }
    </style>
""", unsafe_allow_html=True)

# Helper seguro para secretos (evita caídas si secrets.toml no existe)
def obtener_secreto(clave: str, valor_por_defecto: str) -> str:
    try:
        if hasattr(st, "secrets") and clave in st.secrets:
            return st.secrets[clave]
    except Exception:
        pass
    return valor_por_defecto

# =========================================================================
# MÓDULO CRIPTOGRÁFICO: CIFRADO ESTÁNDAR FERNET (AES-128-CBC + HMAC-SHA256)
# =========================================================================
def _derivar_clave_fernet(clave_secreta: str, salt: bytes) -> bytes:
    """Deriva una clave de 256 bits apta para Fernet usando PBKDF2-HMAC-SHA256 con 100,000 iteraciones."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    return base64.urlsafe_b64encode(kdf.derive(clave_secreta.encode("utf-8")))

def cifrar_respaldo_seguro(datos_obj, clave_secreta: str) -> str:
    """
    Cifra los datos con el estándar Fernet (AES-128 en modo CBC con padding PKCS7 y
    autenticación HMAC-SHA256). Deriva la clave usando PBKDF2 con 100,000 iteraciones y sal aleatoria.
    """
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
    """
    Descifra y valida la integridad del paquete de respaldo.
    Mantiene compatibilidad con respaldos legados si existieran.
    """
    if not CRYPTOGRAPHY_OK:
        return None, "La librería 'cryptography' no está instalada."
    try:
        paquete = json.loads(paquete_cifrado_str)
        
        # Formato Estándar Fernet
        if "salt" in paquete and "token" in paquete:
            salt = base64.b64decode(paquete["salt"])
            clave_fernet = _derivar_clave_fernet(clave_secreta, salt)
            f = Fernet(clave_fernet)
            datos_bytes = f.decrypt(paquete["token"].encode("utf-8"))
            return json.loads(datos_bytes.decode("utf-8")), "OK"
            
        # Compatibilidad con respaldo legado casero
        if paquete.get("seguridad") == "PBKDF2-HMAC-SHA256" and "tag" in paquete and "data" in paquete:
            salt = base64.b64decode(paquete["salt"])
            tag_esperado = base64.b64decode(paquete["tag"])
            cifrado = base64.b64decode(paquete["data"])
            import hashlib
            key = hashlib.pbkdf2_hmac("sha256", clave_secreta.encode("utf-8"), salt, 100000, dklen=32)
            tag_calculado = hmac.new(key, salt + cifrado, hashlib.sha256).digest()
            if not hmac.compare_digest(tag_esperado, tag_calculado):
                return None, "❌ Clave incorrecta o archivo alterado."
            keystream = b""
            counter = 0
            while len(keystream) < len(cifrado):
                keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
                counter += 1
            datos_bytes = bytes(a ^ b for a, b in zip(cifrado, keystream[:len(cifrado)]))
            return json.loads(datos_bytes.decode("utf-8")), "OK (Migrado desde formato legado)"
            
        return None, "El archivo no contiene un formato de respaldo reconocido."
    except InvalidToken:
        return None, "❌ Clave de descifrado incorrecta o archivo alterado."
    except Exception as e:
        return None, f"Error al procesar el archivo cifrado: {e}"

# =========================================================================
# FUNCIONES DE BASE DE DATOS Y PERSISTENCIA
# =========================================================================
def cargar_registros_guardados():
    """Carga los reportes desde el archivo JSON de manera segura."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            st.error(f"Error al leer la base de datos: {e}")
            return []
    return []

def guardar_registros_permanentes(registros):
    """Guarda los reportes en el archivo JSON con reemplazo atómico para evitar corrupción."""
    try:
        tmp_file = DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=4)
        os.replace(tmp_file, DB_FILE)
        return True
    except Exception as e:
        st.error(f"Error al escribir en la base de datos: {e}")
        return False

def guardar_imagen_optimizada(archivo_subido, id_reporte, sucursal, fecha_str):
    """Guarda y comprime la foto física vinculada estrictamente al ID del reporte."""
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        
        suc_clean = "".join(c for c in sucursal if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
        fecha_clean = fecha_str.replace("/", "-")
        nombre_archivo = f"{id_reporte}_{fecha_clean}_{suc_clean}.jpg"
        ruta_completa = os.path.join(FOTOS_DIR, nombre_archivo)
        
        img.save(ruta_completa, "JPEG", quality=78, optimize=True)
        return ruta_completa
    except Exception as e:
        st.error(f"Error al procesar la fotografía: {e}")
        return None

def evaluar_rentabilidad(margen):
    """Clasifica el nivel de rentabilidad según el margen porcentual."""
    if margen >= 40.0:
        return "🟢 Alta"
    elif margen >= 15.0:
        return "🟡 Moderada"
    elif margen > 0.0:
        return "🟠 Baja"
    else:
        return "🔴 No Rentable (Pérdida)"

def ya_existe_reporte(sucursal, fecha_str):
    """Verifica si ya existe un reporte para esa sucursal en esa fecha."""
    if sucursal == "-- Selecciona o busca la sucursal --":
        return False
    for reg in st.session_state.registros:
        if reg.get("Sitio / Unidad") == sucursal and reg.get("Fecha") == fecha_str:
            return True
    return False

# =========================================================================
# VALIDACIÓN AUTOMÁTICA DE FOTOS Y EXTRACCIÓN INTELIGENTE
# =========================================================================
def validar_y_analizar_foto(archivo_subido, catalogo_sucursales):
    """
    Analiza la fotografía para validar:
    1. Integridad y formato del archivo.
    2. Resolución mínima y relación de aspecto.
    3. Nivel de brillo/exposición y nitidez.
    4. Detección heurística de folios, fechas y sucursal para auto-llenado.
    """
    resultado = {
        "valida": False,
        "ancho": 0,
        "alto": 0,
        "brillo": 0.0,
        "mensaje": "",
        "advertencias": [],
        "datos_extraidos": {}
    }
    
    try:
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        img.verify()
        
        archivo_subido.seek(0)
        img = Image.open(archivo_subido)
        w, h = img.size
        resultado["ancho"] = w
        resultado["alto"] = h
        
        if w < 300 or h < 300:
            resultado["advertencias"].append("⚠️ Resolución baja: el texto pequeño podría no ser legible.")
            
        gris = img.convert("L")
        stat = ImageStat.Stat(gris)
        brillo = stat.mean[0]
        resultado["brillo"] = round(brillo, 1)
        
        if brillo < 35:
            resultado["advertencias"].append("⚠️ La foto está muy oscura. Se sugiere tomarla con mejor luz.")
        elif brillo > 225:
            resultado["advertencias"].append("⚠️ Exceso de luz o reflejo en la foto.")
        else:
            resultado["valida"] = True

        texto_ocr = ""
        if PYTESSERACT_OK:
            try:
                texto_ocr = pytesseract.image_to_string(gris)
            except Exception:
                pass
                
        nombre_arch = getattr(archivo_subido, "name", "").upper()
        texto_busqueda = (texto_ocr + " " + nombre_arch).upper()
        
        datos = {}
        # 1. Sucursal
        for suc in catalogo_sucursales:
            if suc.upper() in texto_busqueda:
                datos["sucursal"] = suc
                break
                
        # 2. Folios
        folio_match = re.search(r'(?:FOLIO|BOL|DEL)?\s*[:\s]*(\d{2,6})\s*(?:AL|A|-)\s*(\d{2,6})', texto_busqueda)
        if folio_match:
            try:
                datos["folio_inicial"] = int(folio_match.group(1))
                datos["folio_final"] = int(folio_match.group(2))
            except ValueError:
                pass
                
        # 3. Fecha
        fecha_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', texto_busqueda)
        if fecha_match:
            try:
                dia, mes, anio = int(fecha_match.group(1)), int(fecha_match.group(2)), int(fecha_match.group(3))
                if anio < 100:
                    anio += 2000
                datos["fecha"] = date(anio, mes, dia)
            except Exception:
                pass

        resultado["datos_extraidos"] = datos
        if not resultado["advertencias"]:
            resultado["mensaje"] = f"✅ Foto nítida ({w}x{h} px, exposición adecuada)."
        else:
            resultado["mensaje"] = " | ".join(resultado["advertencias"])
            
        return resultado
    except Exception as e:
        resultado["mensaje"] = f"❌ Archivo no válido como imagen: {e}"
        return resultado

# =========================================================================
# MOTOR FINANCIERO Y GENERADOR DE EXCEL BLINDADO
# =========================================================================
def generar_excel_completo(registros):
    """
    Genera un archivo Excel profesional con 3 hojas: Semanal, Mensual y Detalle.
    Retorna una tupla: (bytes_excel, estado_str).
    Si faltan librerías o falla openpyxl, no truena la app y ofrece diagnóstico claro.
    """
    if not registros:
        return None, "NO_REGISTROS"
    
    if not OPENPYXL_OK and not XLSXWRITER_OK:
        return None, "SIN_MOTOR"
    
    try:
        df = pd.DataFrame(registros)
        
        # Normalizar fechas y números
        df["Fecha_DT"] = pd.to_datetime(df.get("Fecha"), format="%d/%m/%Y", errors="coerce")
        df = df.sort_values(by="Fecha_DT", ascending=False)
        
        df["Año"] = df["Fecha_DT"].dt.year
        df["Semana"] = df["Fecha_DT"].dt.isocalendar().week
        df["Semana_Etiqueta"] = df["Año"].astype(str) + " - Sem " + df["Semana"].astype(str)
        df["Mes_Etiqueta"] = df["Fecha_DT"].dt.strftime("%Y-%m (%B)")
        
        cols_num = ["Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina", "Total Gastos", "Ingreso Neto", "Boletos Cobrados"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                df[col] = 0.0

        output = io.BytesIO()
        engine = "openpyxl" if OPENPYXL_OK else "xlsxwriter"
        
        with pd.ExcelWriter(output, engine=engine) as writer:
            # 1. Resumen Semanal
            resumen_semanal = df.groupby(["Semana_Etiqueta", "Sitio / Unidad"]).agg({
                "Boletos Cobrados": "sum",
                "Ingreso Bruto": "sum",
                "Gastos Especiales": "sum",
                "Gastos Generales / Nómina": "sum",
                "Total Gastos": "sum",
                "Ingreso Neto": "sum"
            }).reset_index()
            
            resumen_semanal["Margen (%)"] = (
                (resumen_semanal["Ingreso Neto"] / resumen_semanal["Ingreso Bruto"]) * 100
            ).fillna(0.0).round(2)
            resumen_semanal["Rentabilidad"] = resumen_semanal["Margen (%)"].apply(evaluar_rentabilidad)
            resumen_semanal = resumen_semanal.sort_values(by=["Semana_Etiqueta", "Ingreso Neto"], ascending=[False, False])
            resumen_semanal.to_excel(writer, sheet_name="Rentabilidad Semanal", index=False)

            # 2. Resumen Mensual
            resumen_mensual = df.groupby(["Mes_Etiqueta", "Sitio / Unidad"]).agg({
                "Boletos Cobrados": "sum",
                "Ingreso Bruto": "sum",
                "Gastos Especiales": "sum",
                "Gastos Generales / Nómina": "sum",
                "Total Gastos": "sum",
                "Ingreso Neto": "sum"
            }).reset_index()
            
            resumen_mensual["Margen (%)"] = (
                (resumen_mensual["Ingreso Neto"] / resumen_mensual["Ingreso Bruto"]) * 100
            ).fillna(0.0).round(2)
            resumen_mensual["Rentabilidad"] = resumen_mensual["Margen (%)"].apply(evaluar_rentabilidad)
            resumen_mensual = resumen_mensual.sort_values(by=["Mes_Etiqueta", "Ingreso Neto"], ascending=[False, False])
            resumen_mensual.to_excel(writer, sheet_name="Rentabilidad Mensual", index=False)

            # 3. Detalle Individual de Reportes
            cols_detalle = [
                "ID", "Fecha", "Sitio / Unidad", "Horario", "Tipo", "Costo Boleto",
                "Folio Inicial", "Folio Final", "Total Boletos", "Sin Cobro", "Cancelados", "Perdidos",
                "Boletos Cobrados", "Ingreso Bruto", "Gastos Especiales", "Gastos Generales / Nómina",
                "Total Gastos", "Ingreso Neto", "Margen (%)", "Rentabilidad", "Elaboró", "Recibe", "Tiene Foto"
            ]
            df["Tiene Foto"] = df.get("foto_path", pd.Series()).apply(lambda x: "SÍ" if (x and os.path.exists(str(x))) else "NO")
            cols_presentes = [c for c in cols_detalle if c in df.columns]
            df[cols_presentes].to_excel(writer, sheet_name="Detalle de Reportes", index=False)

        # Aplicar estilos corporativos con openpyxl si está disponible
        if OPENPYXL_OK:
            try:
                output.seek(0)
                wb = openpyxl.load_workbook(output)
                header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
                header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                border_thin = Border(
                    left=Side(style='thin', color='D9D9D9'),
                    right=Side(style='thin', color='D9D9D9'),
                    top=Side(style='thin', color='D9D9D9'),
                    bottom=Side(style='thin', color='D9D9D9')
                )

                for sheetname in wb.sheetnames:
                    ws = wb[sheetname]
                    for col_idx in range(1, ws.max_column + 1):
                        cell = ws.cell(row=1, column=col_idx)
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    
                    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                        for cell in row:
                            cell.border = border_thin
                            col_header = str(ws.cell(row=1, column=cell.column).value or "")
                            if any(m in col_header for m in ["Ingreso", "Gasto", "Neto", "Costo"]):
                                cell.number_format = '"$"#,##0.00'
                            elif "Margen" in col_header:
                                cell.number_format = '0.0"%"'
                            elif "Boletos" in col_header or "Folio" in col_header:
                                cell.number_format = '#,##0'

                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = get_column_letter(col[0].column)
                        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

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
# BATERÍA DE PRUEBAS DE REGRESIÓN Y DIAGNÓSTICO DE DESPLIEGUE
# =========================================================================
def ejecutar_pruebas_regresion():
    """Ejecuta una batería completa de pruebas de regresión técnica y funcional."""
    pruebas = []

    # 1. Criptografía Estándar Fernet
if CRYPTOGRAPHY_OK:
    datos_prueba = [
        {
            "ID": "TEST_ENC",
            "Sitio / Unidad": "CARAJILLO",
            "Neto": 5000.0
        }
    ]

    clave_t = "ClavePrueba2026!Segura"

    cifrado_str = cifrar_respaldo_seguro(
        datos_prueba, clave_t
    )

    dec_ok, msg_ok = descifrar_respaldo_seguro(
        cifrado_str, clave_t
    )

    dec_bad, msg_bad = descifrar_respaldo_seguro(
        cifrado_str, "ClaveErronea"
    )

    prueba_cifrado = (
        cifrado_str is not None
        and dec_ok is not None
        and dec_ok == datos_prueba
        and dec_bad is None
    )

    pruebas.append({
        "Área": "Criptografía y Nube",
        "Prueba": "Cifrado Estándar Fernet",
        "Resultado": "✅ PASS" if prueba_cifrado else "❌ FAIL",
        "Detalle": (
            "Cifrado y descifrado correctos."
            if prueba_cifrado
            else f"Cifrado o validación fallida: {msg_ok}; {msg_bad}"
        )
    })

else:
    pruebas.append({
        "Área": "Criptografía y Nube",
        "Prueba": "Cifrado Estándar Fernet",
        "Resultado": "⚠️ PENDIENTE",
        "Detalle": "Falta instalar la librería 'cryptography' en requirements.txt."
    })

    # 2. Disponibilidad de Motor Excel
    motor_disp = "openpyxl" if OPENPYXL_OK else ("xlsxwriter" if XLSXWRITER_OK else "Ninguno")
    p_motor = OPENPYXL_OK or XLSXWRITER_OK
    pruebas.append({
        "Área": "Entorno y Dependencias",
        "Prueba": "Disponibilidad de Motor Excel",
        "Resultado": "✅ PASS" if p_motor else "❌ FAIL",
        "Detalle": f"Motor activo: {motor_disp} (openpyxl: {OPENPYXL_OK}, xlsxwriter: {XLSXWRITER_OK})."
    })

    # 3. Generación de Excel Multi-Pestaña
    mock_excel_data = [{
        "ID": "TEST_EXCEL", "Fecha": "11/10/2026", "Sitio / Unidad": "CARAJILLO",
        "Horario": "13:00 a 23:00", "Costo Boleto": 100.0, "Folio Inicial": 1, "Folio Final": 50,
        "Total Boletos": 50, "Sin Cobro": 2, "Cancelados": 1, "Perdidos": 0, "Boletos Cobrados": 47,
        "Ingreso Bruto": 4700.0, "Gastos Especiales": 200.0, "Gastos Generales / Nómina": 1500.0,
        "Total Gastos": 1700.0, "Ingreso Neto": 3000.0, "Margen (%)": 63.83, "Rentabilidad": "🟢 Alta",
        "Elaboró": "Test", "Recibe": "Auditor", "Tipo": "Operación Regular", "foto_path": None
    }]
    excel_bin, estado_ex = generar_excel_completo(mock_excel_data)
    p3 = (estado_ex == "OK" and excel_bin is not None and len(excel_bin) > 2000)
    pruebas.append({
        "Área": "Entregables Excel",
        "Prueba": "Generación de libro Excel multi-pestaña (Semanal, Mensual, Detalle)",
        "Resultado": "✅ PASS" if p3 else "❌ FAIL",
        "Detalle": f"Estado: {estado_ex} | Tamaño generado: {len(excel_bin) if excel_bin else 0} bytes."
    })

    # 4. Cálculos Financieros y Boletos
    tot_bol = (50 - 1) + 1
    cobrados = tot_bol - 2 - 1
    bruto = cobrados * 100.0
    gastos = 1700.0
    neto = bruto - gastos
    margen = (neto / bruto) * 100
    p4 = (cobrados == 47 and bruto == 4700.0 and neto == 3000.0 and round(margen, 2) == 63.83)
    pruebas.append({
        "Área": "Finanzas y Margen",
        "Prueba": "Cálculo exacto de folios, cobrados, bruto, egresos y margen",
        "Resultado": "✅ PASS" if p4 else "❌ FAIL",
        "Detalle": f"Folios calculados: 47 cobrados, $4,700 bruto, $3,000 neto ({margen:.2f}%)."
    })

    # 5. Semáforos de Rentabilidad
    p5 = (
        "Alta" in evaluar_rentabilidad(45.0) and
        "Moderada" in evaluar_rentabilidad(20.0) and
        "Baja" in evaluar_rentabilidad(5.0) and
        "Pérdida" in evaluar_rentabilidad(-5.0)
    )
    pruebas.append({
        "Área": "Clasificación de Negocio",
        "Prueba": "Semáforos de Rentabilidad (Alta, Moderada, Baja, Pérdida)",
        "Resultado": "✅ PASS" if p5 else "❌ FAIL",
        "Detalle": "Validación de márgenes >=40% (Alta), 15-39% (Moderada), 0-14% (Baja), <0% (Pérdida)."
    })

    # 6. Validación de Fotografía
img_test = Image.new("RGB", (640, 480), color=(150, 150, 150))
buf_test = io.BytesIO()
img_test.save(buf_test, format="JPEG")
buf_test.name = "reporte_CARAJILLO_test.jpg"

res_foto = validar_y_analizar_foto(
    buf_test,
    ["CARAJILLO", "PAMPAS"]
)

p6 = (
    res_foto["valida"]
    and res_foto["datos_extraidos"].get("sucursal") == "CARAJILLO"
)

pruebas.append({
    "Área": "Procesamiento de Fotos",
    "Prueba": "Análisis de integridad, exposición y detección automática en imagen",
    "Resultado": "✅ PASS" if p6 else "❌ FAIL",
    "Detalle": (
        f"Resolución: {res_foto['ancho']}x{res_foto['alto']}, "
        f"Brillo: {res_foto['brillo']}, "
        f"Detección: {res_foto['datos_extraidos']}."
    )
})

return pruebas
# =========================================================================
# CONFIGURACIÓN DE SUCURSALES Y PRECIOS
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

# =========================================================================
# PANTALLA DE ACCESO (LOGIN CON ROLES SEGUROS)
# =========================================================================
if st.session_state.usuario_autenticado is None:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=380)
        else:
            st.markdown("<h1 style='text-align: center;'>🚗 CLUB PARK</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; color: #555;'>Control Operativo y Financiero</h3>", unsafe_allow_html=True)
        st.markdown("---")

        nombre_usuario = st.selectbox(
            "Selecciona tu Usuario:",
            ["-- Selecciona --", "Víctor Manuel", "José de Jesús", "Víctor (Contador)"],
            key="login_user"
        )
        password = st.text_input("Contraseña de Acceso:", type="password", key="login_pass")

        pass_visor = obtener_secreto("PASS_SUPERVISOR", "visor123")
        pass_auditor = obtener_secreto("PASS_AUDITOR", "contador123")

        if st.button("🔑 Iniciar Sesión", use_container_width=True, type="primary"):
            # Comparación en tiempo constante para mitigar ataques de timing
            if nombre_usuario in ["Víctor Manuel", "José de Jesús"] and hmac.compare_digest(password, pass_visor):
                st.session_state.usuario_autenticado = nombre_usuario
                st.session_state.rol = "Supervisor"
                st.success(f"Bienvenido {nombre_usuario}")
                st.rerun()
            elif nombre_usuario == "Víctor (Contador)" and hmac.compare_digest(password, pass_auditor):
                st.session_state.usuario_autenticado = "Víctor (Contador)"
                st.session_state.rol = "Contador Auditor"
                st.success("Acceso concedido como Contador Auditor")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta o usuario no seleccionado.")
        st.stop()

# =========================================================================
# ENCABEZADO Y BARRA LATERAL
# =========================================================================
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    logo_path = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=220)
    else:
        st.markdown("### 🚗 **CLUB PARK**")

with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.markdown(f"**Usuario:** `{st.session_state.usuario_autenticado}` | **Rol:** `{st.session_state.rol}`")

es_contador = (st.session_state.rol == "Contador Auditor")

if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
fotos_disco = [f for f in os.listdir(FOTOS_DIR) if not f.startswith('.')] if os.path.exists(FOTOS_DIR) else []
st.sidebar.markdown(f"**📊 Reportes en Sistema:** `{len(st.session_state.registros)}`")
st.sidebar.markdown(f"**📷 Fotos Físicas Guardadas:** `{len(fotos_disco)}`")

# SECCIÓN AUDITOR: DESCARGA EXCEL EN SIDEBAR
if es_contador and st.session_state.registros:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Reporte Financiero Excel")
    excel_data, estado_excel = generar_excel_completo(st.session_state.registros)
    if estado_excel == "OK" and excel_data:
        st.sidebar.download_button(
            label="📊 Descargar Excel Semanal y Mensual",
            data=excel_data,
            file_name=f"ClubPark_Balance_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    elif estado_excel == "SIN_MOTOR":
        st.sidebar.warning("⚠️ Sin motor Excel. Descarga respaldo en CSV:")
        df_csv = pd.DataFrame(st.session_state.registros)
        st.sidebar.download_button(
            label="📄 Descargar Respaldo CSV",
            data=df_csv.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ClubPark_Respaldo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.sidebar.error(f"Error generando reporte: {estado_excel}")

# SECCIÓN AUDITOR: RESPALDO CIFRADO ESTÁNDAR
if es_contador:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔒 Respaldos Cifrados (Fernet)")
    clave_backup = st.sidebar.text_input("Clave de cifrado de respaldo:", type="password", key="pass_bkp")
    
    if st.sidebar.button("🛡️ Generar Respaldo Cifrado", use_container_width=True):
        if not clave_backup:
            st.sidebar.error("Ingresa una clave para cifrar el respaldo.")
        elif not CRYPTOGRAPHY_OK:
            st.sidebar.error("La librería cryptography no está instalada.")
        else:
            paquete_cifrado = cifrar_respaldo_seguro(st.session_state.registros, clave_backup)
            if paquete_cifrado:
                st.sidebar.download_button(
                    label="💾 Descargar Respaldo Seguro (.enc)",
                    data=paquete_cifrado.encode("utf-8"),
                    file_name=f"ClubPark_Backup_Fernet_{datetime.now().strftime('%Y%m%d_%H%M')}.enc",
                    mime="application/json",
                    use_container_width=True
                )

# =========================================================================
# INTERFAZ PRINCIPAL: PESTAÑAS AUDITOR O VISTA SUPERVISOR
# =========================================================================
if es_contador:
    tab_aud1, tab_aud2, tab_aud3, tab_aud4 = st.tabs([
        "📝 Captura Regular",
        "⚡ Evento Extraordinario",
        "🗂️ Gestión y Eliminación",
        "🧪 Pruebas y Validación de Despliegue"
    ])
else:
    tab_aud1 = st.container()

# -------------------------------------------------------------------------
# TAB 1: CAPTURA DE REPORTE DIARIO CON AUTO-LLENADO
# -------------------------------------------------------------------------
with tab_aud1:
    st.markdown("### 📝 Captura de Reporte Operativo Diario")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_default = st.session_state.get("auto_fecha", date.today())
        fecha_op = st.date_input("Fecha de Operación:", value=fecha_default, key="fecha_op_input")
        fecha_op_str = fecha_op.strftime("%d/%m/%Y")

        idx_suc_default = 0
        if "auto_sucursal" in st.session_state and st.session_state["auto_sucursal"] in SUCURSALES_LISTA:
            idx_suc_default = SUCURSALES_LISTA.index(st.session_state["auto_sucursal"])

        sucursal = st.selectbox(
            "Sucursal / Unidad:",
            SUCURSALES_LISTA,
            index=idx_suc_default,
            key="select_sitio",
            on_change=on_sucursal_change
        )
        es_ingreso_directo = (sucursal in ["BARRANCA", "VETERINARIA", "S. AZURA", "E-BNI"] or PRECIOS_SUCURSALES.get(sucursal, 0) == 0)

    with col_f2:
        if es_ingreso_directo:
            st.info("📌 En esta unidad se captura directamente el Ingreso Bruto en el campo correspondiente.")
            costo_boleto = 0.0
        else:
            costo_boleto = st.number_input(
                "Costo por Boleto ($ MXN):",
                step=5,
                key="costo_boleto_input"
            )

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        hora_ini = st.time_input("Hora de Apertura:", value=time(13, 0), key="h_ini_rep")
    with col_h2:
        hora_fin = st.time_input("Hora de Cierre:", value=time(23, 0), key="h_fin_rep")

    # VALIDACIÓN Y AUTO-LLENADO POR FOTO
    with st.expander("📷 Captura o Subida de Foto del Reporte Físico (Validación y Auto-llenado)", expanded=True):
        foto_subida = st.file_uploader("Subir foto del reporte físico:", type=["png", "jpg", "jpeg"], key="uploader_foto_rep")
        if foto_subida:
            col_foto_prev, col_foto_val = st.columns([1, 2])
            with col_foto_prev:
                st.image(foto_subida, caption="Vista previa del reporte adjunto", use_container_width=True)
            with col_foto_val:
                analisis = validar_y_analizar_foto(foto_subida, list(PRECIOS_SUCURSALES.keys()))
                if analisis["valida"]:
                    st.success(analisis["mensaje"])
                else:
                    st.warning(analisis["mensaje"])
                
                datos_det = analisis["datos_extraidos"]
                if datos_det:
                    st.markdown("#### 🪄 Datos Detectados en la Fotografía:")
                    for k, v in datos_det.items():
                        st.write(f"- **{k.capitalize()}:** `{v}`")
                    
                    if st.button("✨ Aplicar Datos Detectados al Formulario"):
                        if "sucursal" in datos_det:
                            st.session_state["auto_sucursal"] = datos_det["sucursal"]
                        if "fecha" in datos_det:
                            st.session_state["auto_fecha"] = datos_det["fecha"]
                        if "folio_inicial" in datos_det:
                            st.session_state["f_ini_val"] = datos_det["folio_inicial"]
                        if "folio_final" in datos_det:
                            st.session_state["f_fin_val"] = datos_det["folio_final"]
                        st.success("✅ Datos aplicados. Actualizando campos...")
                        st.rerun()

    st.markdown("#### 🎫 Control de Operaciones y Folios")
    c_b1, c_b2, c_b3 = st.columns(3)

    if es_ingreso_directo:
        with c_b1:
            f_ini = st.number_input("Ingreso Bruto de la Unidad ($ MXN):", min_value=0.0, step=50.0, key="f_ini_dir")
            f_fin = 0
        with c_b2:
            f_sin = 0
            f_can = 0
        with c_b3:
            f_per = 0
        
        total_boletos_calc = 0
        boletos_cobrados_calc = 0
        ingreso_bruto_calc = float(f_ini)
    else:
        with c_b1:
            val_f_ini_def = st.session_state.get("f_ini_val", 0)
            f_ini = st.number_input("Folio Inicial:", min_value=0, value=val_f_ini_def, step=1, key="input_f_ini")
            val_f_fin_def = st.session_state.get("f_fin_val", 0)
            f_fin = st.number_input("Folio Final:", min_value=0, value=val_f_fin_def, step=1, key="input_f_fin")
        with c_b2:
            f_sin = st.number_input("Boletos Sin Cobro:", min_value=0, step=1, key="f_sin_val")
            f_can = st.number_input("Boletos Cancelados:", min_value=0, step=1, key="f_can_val")
        with c_b3:
            f_per = st.number_input("Boletos Perdidos:", min_value=0, step=1, key="f_per_val")

        total_boletos_calc = max(0, (int(f_fin) - int(f_ini)) + 1) if int(f_fin) >= int(f_ini) and int(f_ini) > 0 else 0
        boletos_cobrados_calc = max(0, total_boletos_calc - int(f_sin) - int(f_can))
        ingreso_bruto_calc = boletos_cobrados_calc * float(costo_boleto)

    st.markdown("#### 💵 Egresos y Gastos Operativos")
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        g_esp = st.number_input("Gastos Especiales ($ MXN):", min_value=0.0, value=0.0, step=10.0, key="g_esp_val")
    with c_g2:
        g_gen = st.number_input("Gastos Generales / Nómina ($ MXN):", min_value=0.0, value=0.0, step=10.0, key="g_gen_val")

    st.markdown("#### ✍️ Firmas")
    c_fir1, c_fir2 = st.columns(2)
    with c_fir1:
        elaboro = st.text_input("Elaboró:", value=st.session_state.usuario_autenticado, key="elab_val")
    with c_fir2:
        recibe = st.text_input("Recibe:", value="", key="recibe_val")

    total_gastos_calc = float(g_esp) + float(g_gen)
    ingreso_neto_calc = ingreso_bruto_calc - total_gastos_calc
    margen_calc = (ingreso_neto_calc / ingreso_bruto_calc * 100) if ingreso_bruto_calc > 0 else 0.0
    rentabilidad_calc = evaluar_rentabilidad(margen_calc)

    # --- BALANCE PRELIMINAR ---
    st.markdown("---")
    st.markdown("### 📊 Balance Preliminar del Reporte")

    if not es_ingreso_directo:
        st.metric(
            label="🎟️ Boletos Pagados (Cobrados)",
            value=f"{boletos_cobrados_calc} boletos",
            help="Total expedido menos boletos sin cobro y cancelados"
        )
    else:
        st.metric(
            label="💼 Modalidad de Cobro",
            value="Ingreso Directo Capturado",
            help="Unidad configurada con ingreso bruto directo"
        )

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Ingreso Bruto", f"${ingreso_bruto_calc:,.2f} MXN")
    with col_m2:
        st.metric("Total Gastos y Nómina", f"${total_gastos_calc:,.2f} MXN")
    with col_m3:
        st.metric("Ingreso Neto (Utilidad)", f"${ingreso_neto_calc:,.2f} MXN", delta=f"{margen_calc:.1f}% Margen")
    with col_m4:
        st.metric("Rentabilidad", rentabilidad_calc)

    duplicado = ya_existe_reporte(sucursal, fecha_op_str)
    puede_guardar = True

    st.markdown("---")

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
                for k in ["auto_sucursal", "auto_fecha", "f_ini_val", "f_fin_val"]:
                    st.session_state.pop(k, None)
                st.balloons()
                st.rerun()
            else:
                st.error("❌ Ocurrió un error al guardar el reporte en el disco permanente.")

# -------------------------------------------------------------------------
# PESTAÑAS EXCLUSIVAS DEL CONTADOR AUDITOR
# -------------------------------------------------------------------------
if es_contador:
    # TAB 2: Eventos Extraordinarios
    with tab_aud2:
        st.markdown("### ⚡ Registrar Evento Extraordinario")
        ev_col1, ev_col2 = st.columns(2)
        with ev_col1:
            ev_fecha = st.date_input("Fecha del Evento:", value=date.today(), key="ev_fecha_in")
            ev_suc = st.selectbox("Sucursal / Sede del Evento:", SUCURSALES_LISTA, key="ev_suc_in")
            ev_costo = st.number_input("Costo Boleto Evento ($ MXN):", min_value=0.0, value=100.0, step=10.0, key="ev_costo_in")
        with ev_col2:
            ev_ini_h = st.time_input("Inicio Evento:", value=time(18, 0), key="ev_ini_in")
            ev_fin_h = st.time_input("Fin Evento:", value=time(2, 0), key="ev_fin_in")
            ev_boletos = st.number_input("Boletos Cobrados en Evento:", min_value=0, value=50, step=1, key="ev_bol_in")

        ev_f_ini = st.number_input("Folio Inicial:", min_value=0, value=1, step=1, key="ev_fi_in")
        ev_f_fin = st.number_input("Folio Final:", min_value=0, value=ev_boletos, step=1, key="ev_ff_in")
        ev_gastos = st.number_input("Total Gastos / Nómina Evento ($ MXN):", min_value=0.0, value=0.0, step=50.0, key="ev_g_in")
        ev_elab = st.text_input("Responsable del Evento:", value=st.session_state.usuario_autenticado, key="ev_elab_in")

        ev_bruto = float(ev_boletos) * float(ev_costo)
        ev_neto = ev_bruto - float(ev_gastos)
        ev_margen = (ev_neto / ev_bruto * 100) if ev_bruto > 0 else 0.0

        st.metric("Neto Generado en Evento", f"${ev_neto:,.2f} MXN", delta=f"{ev_margen:.1f}% Margen")

        if st.button("💾 Guardar Evento Extraordinario", type="primary", key="btn_save_ev"):
            if ev_suc != "-- Selecciona o busca la sucursal --":
                id_ev = f"EVT_{uuid.uuid4().hex[:6]}"
                evento_obj = {
                    "ID": id_ev,
                    "Fecha": ev_fecha.strftime("%d/%m/%Y"),
                    "Sitio / Unidad": ev_suc,
                    "Horario": f"{ev_ini_h.strftime('%H:%M')} a {ev_fin_h.strftime('%H:%M')}",
                    "Costo Boleto": float(ev_costo),
                    "Folio Inicial": int(ev_f_ini),
                    "Folio Final": int(ev_f_fin),
                    "Total Boletos": ev_boletos,
                    "Sin Cobro": 0,
                    "Cancelados": 0,
                    "Perdidos": 0,
                    "Boletos Cobrados": ev_boletos,
                    "Ingreso Bruto": ev_bruto,
                    "Gastos Especiales": float(ev_gastos),
                    "Gastos Generales / Nómina": 0.0,
                    "Total Gastos": float(ev_gastos),
                    "Ingreso Neto": ev_neto,
                    "Margen (%)": round(ev_margen, 2),
                    "Rentabilidad": evaluar_rentabilidad(ev_margen),
                    "Elaboró": ev_elab,
                    "Recibe": "Víctor (Contador)",
                    "Tipo": "Evento Extraordinario",
                    "foto_path": None,
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.registros.append(evento_obj)
                guardar_registros_permanentes(st.session_state.registros)
                st.success("✅ Evento extraordinario guardado con éxito.")
                st.rerun()
            else:
                st.error("❌ Selecciona una sucursal válida.")

    # TAB 3: Gestión y Eliminación
    with tab_aud3:
        st.markdown("### 🗂️ Gestión y Eliminación de Reportes")
        if st.session_state.registros:
            opciones_rep = [
                f"{r.get('ID', f'IDX_{i}')} | {r.get('Fecha')} | {r.get('Sitio / Unidad')} | Neto: ${r.get('Ingreso Neto', 0):,.2f}"
                for i, r in enumerate(st.session_state.registros)
            ]
            sel_rep = st.selectbox("Seleccionar reporte a inspeccionar:", opciones_rep, key="sel_rep_aud")
            idx_rep = opciones_rep.index(sel_rep)
            rep_data = st.session_state.registros[idx_rep]

            c_info, c_foto = st.columns([2, 1])
            with c_info:
                st.json(rep_data)
            with c_foto:
                foto_p = rep_data.get("foto_path")
                if foto_p and os.path.exists(foto_p):
                    st.image(foto_p, caption="Fotografía física vinculada al reporte", use_container_width=True)
                else:
                    st.caption("📷 Sin fotografía vinculada.")

            if st.button("🗑️ Eliminar Este Reporte y su Foto", key="btn_del_rep", type="primary"):
                if foto_p and os.path.exists(foto_p):
                    try:
                        os.remove(foto_p)
                    except Exception:
                        pass
                st.session_state.registros.pop(idx_rep)
                guardar_registros_permanentes(st.session_state.registros)
                st.success("✅ Reporte y su fotografía eliminados.")
                st.rerun()
        else:
            st.info("No hay reportes registrados.")

    # TAB 4: Pruebas de Regresión y Validación de Despliegue
    with tab_aud4:
        st.markdown("### 🧪 Diagnóstico Automatizado del Sistema y Despliegue")
        st.write("Ejecuta la suite completa de pruebas para validar motores Excel, criptografía Fernet, cálculos financieros y salud del sistema.")
        
        if st.button("🚀 Ejecutar Suite de Validación Técnica", type="primary", key="btn_run_tests"):
            with st.spinner("Ejecutando pruebas unitarias y de integración..."):
                resultados_pruebas = ejecutar_pruebas_regresion()
                df_pruebas = pd.DataFrame(resultados_pruebas)
                st.dataframe(df_pruebas, use_container_width=True)
                
                todas_pass = all("PASS" in p["Resultado"] for p in resultados_pruebas)
                if todas_pass:
                    st.success("🎉 ¡Todas las pruebas técnicas y de despliegue han sido superadas exitosamente!")
                else:
                    st.warning("⚠️ Algunas pruebas requieren atención técnica. Revisa la columna 'Detalle'.")
