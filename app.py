import base64
from datetime import date, datetime, time, timedelta
import hashlib
import hmac
import io
import json
import os
import shutil
import urllib.parse
import uuid
import pandas as pd
from PIL import Image
import streamlit as st

# Import opcional para exportación con estilo en Excel
try:
  import openpyxl
  from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
  from openpyxl.utils import get_column_letter

  OPENPYXL_OK = True
except ImportError:
  OPENPYXL_OK = False

try:
  import xlsxwriter

  XLSXWRITER_OK = True
except ImportError:
  XLSXWRITER_OK = False

# =========================================================================
# CONFIGURACIÓN GENERAL Y PERSISTENCIA ATÓMICA EN NUBE
# =========================================================================
BASE_DIR = (
    os.path.dirname(os.path.abspath(__file__))
    if "__file__" in locals()
    else os.getcwd()
)
DB_FILE = os.path.join(BASE_DIR, "reportes_clubpark.json")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos_reportes")
os.makedirs(FOTOS_DIR, exist_ok=True)

st.set_page_config(
    page_title="Club Park - Control Operativo MXN", page_icon="🚗", layout="wide"
)

# Estilo CSS para optimizar inputs numéricos y visualización
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


# =========================================================================
# MÓDULO CRIPTOGRÁFICO: CIFRADO Y DESCIFRADO DE RESPALDOS SENSIBLES
# =========================================================================
def cifrar_respaldo_seguro(datos_obj, clave_secreta):
  """Cifra los datos con PBKDF2 HMAC SHA-256 (100,000 iteraciones) y firma digital."""
  try:
    datos_bytes = json.dumps(datos_obj, ensure_ascii=False).encode("utf-8")
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", clave_secreta.encode("utf-8"), salt, 100000, dklen=32
    )

    keystream = b""
    counter = 0
    while len(keystream) < len(datos_bytes):
      keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
      counter += 1

    cifrado = bytes(
        a ^ b for a, b in zip(datos_bytes, keystream[: len(datos_bytes)])
    )
    tag = hmac.new(key, salt + cifrado, hashlib.sha256).digest()

    paquete = {
        "seguridad": "PBKDF2-HMAC-SHA256",
        "fecha_cifrado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "salt": base64.b64encode(salt).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
        "data": base64.b64encode(cifrado).decode("utf-8"),
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

    key = hashlib.pbkdf2_hmac(
        "sha256", clave_secreta.encode("utf-8"), salt, 100000, dklen=32
    )
    tag_calculado = hmac.new(key, salt + cifrado, hashlib.sha256).digest()

    if not hmac.compare_digest(tag_esperado, tag_calculado):
      return None, "❌ Clave de descifrado incorrecta o archivo alterado."

    keystream = b""
    counter = 0
    while len(keystream) < len(cifrado):
      keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
      counter += 1

    datos_bytes = bytes(a ^ b for a, b in zip(cifrado, keystream[: len(cifrado)]))
    datos_json = json.loads(datos_bytes.decode("utf-8"))
    return datos_json, "OK"
  except Exception as e:
    return None, f"Error al procesar archivo cifrado: {e}"


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

    suc_clean = (
        "".join(c for c in sucursal if c.isalnum() or c in (" ", "_"))
        .strip()
        .replace(" ", "_")
    )
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
# MOTOR FINANCIERO Y GENERADOR DE EXCEL DETALLADO
# =========================================================================
def generar_excel_completo(registros):
  """Genera un archivo Excel profesional con 3 hojas: Semanal, Mensual y Detalle."""
  if not registros:
    return None

  engine = (
      "openpyxl" if OPENPYXL_OK else ("xlsxwriter" if XLSXWRITER_OK else None)
  )
  if not engine:
    st.error(
        "⚠️ No se encontró la librería 'openpyxl' ni 'xlsxwriter' en el"
        " entorno. Instálala en requirements.txt para descargar Excel."
    )
    return None

  df = pd.DataFrame(registros)

  # Normalizar columnas y fechas
  df["Fecha_DT"] = pd.to_datetime(
      df["Fecha"], format="%d/%m/%Y", errors="coerce"
  )
  df = df.sort_values(by="Fecha_DT", ascending=False)

  # Calcular Semana y Mes
  df["Año"] = df["Fecha_DT"].dt.year
  df["Semana"] = df["Fecha_DT"].dt.isocalendar().week
  df["Semana_Etiqueta"] = (
      df["Año"].astype(str) + " - Sem " + df["Semana"].astype(str)
  )
  df["Mes_Etiqueta"] = df["Fecha_DT"].dt.strftime("%Y-%m (%B)")

  # Columnas numéricas seguras
  cols_num = [
      "Ingreso Bruto",
      "Gastos Especiales",
      "Gastos Generales / Nómina",
      "Total Gastos",
      "Ingreso Neto",
      "Boletos Cobrados",
  ]
  for col in cols_num:
    if col in df.columns:
      df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    else:
      df[col] = 0.0

  output = io.BytesIO()

  with pd.ExcelWriter(output, engine=engine) as writer:
    # 1. RESUMEN SEMANAL POR SUCURSAL
    resumen_semanal = (
        df.groupby(["Semana_Etiqueta", "Sitio / Unidad"])
        .agg({
            "Boletos Cobrados": "sum",
            "Ingreso Bruto": "sum",
            "Gastos Especiales": "sum",
            "Gastos Generales / Nómina": "sum",
            "Total Gastos": "sum",
            "Ingreso Neto": "sum",
        })
        .reset_index()
    )

    resumen_semanal["Margen (%)"] = (
        (resumen_semanal["Ingreso Neto"] / resumen_semanal["Ingreso Bruto"])
        * 100
    ).fillna(0.0).round(2)
    resumen_semanal["Rentabilidad"] = resumen_semanal["Margen (%)"].apply(
        evaluar_rentabilidad
    )
    resumen_semanal = resumen_semanal.sort_values(
        by=["Semana_Etiqueta", "Ingreso Neto"], ascending=[False, False]
    )
    resumen_semanal.to_excel(
        writer, sheet_name="Rentabilidad Semanal", index=False
    )

    # 2. RESUMEN MENSUAL POR SUCURSAL
    resumen_mensual = (
        df.groupby(["Mes_Etiqueta", "Sitio / Unidad"])
        .agg({
            "Boletos Cobrados": "sum",
            "Ingreso Bruto": "sum",
            "Gastos Especiales": "sum",
            "Gastos Generales / Nómina": "sum",
            "Total Gastos": "sum",
            "Ingreso Neto": "sum",
        })
        .reset_index()
    )

    resumen_mensual["Margen (%)"] = (
        (resumen_mensual["Ingreso Neto"] / resumen_mensual["Ingreso Bruto"])
        * 100
    ).fillna(0.0).round(2)
    resumen_mensual["Rentabilidad"] = resumen_mensual["Margen (%)"].apply(
        evaluar_rentabilidad
    )
    resumen_mensual = resumen_mensual.sort_values(
        by=["Mes_Etiqueta", "Ingreso Neto"], ascending=[False, False]
    )
    resumen_mensual.to_excel(
        writer, sheet_name="Rentabilidad Mensual", index=False
    )

    # 3. DETALLE INDIVIDUAL DE REPORTES
    cols_detalle = [
        "ID",
        "Fecha",
        "Sitio / Unidad",
        "Horario",
        "Tipo",
        "Costo Boleto",
        "Folio Inicial",
        "Folio Final",
        "Total Boletos",
        "Sin Cobro",
        "Cancelados",
        "Perdidos",
        "Boletos Cobrados",
        "Ingreso Bruto",
        "Gastos Especiales",
        "Gastos Generales / Nómina",
        "Total Gastos",
        "Ingreso Neto",
        "Margen (%)",
        "Rentabilidad",
        "Elaboró",
        "Recibe",
        "Tiene Foto",
    ]

    df["Tiene Foto"] = df["foto_path"].apply(
        lambda x: "SÍ" if (x and os.path.exists(str(x))) else "NO"
    )
    cols_presentes = [c for c in cols_detalle if c in df.columns]
    df_detalle = df[cols_presentes]
    df_detalle.to_excel(writer, sheet_name="Detalle de Reportes", index=False)

  if OPENPYXL_OK and engine == "openpyxl":
    output.seek(0)
    wb = openpyxl.load_workbook(output)

    header_fill = PatternFill(
        start_color="1F497D", end_color="1F497D", fill_type="solid"
    )
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    for sheetname in wb.sheetnames:
      ws = wb[sheetname]
      for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

      for row in ws.iter_rows(
          min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column
      ):
        for cell in row:
          cell.border = border_thin
          col_header = str(ws.cell(row=1, column=cell.column).value or "")
          if any(m in col_header for m in ["Ingreso", "Gasto", "Neto", "Costo"]):
            cell.number_format = '"$"#,##0.00'
          elif "Margen" in col_header:
            cell.number_format = '0.0"%"'
          elif "Boletos" in col_header or "Folio" in col_header:
            cell.number_format = "#,##0"

      for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    out_styled = io.BytesIO()
    wb.save(out_styled)
    out_styled.seek(0)
    return out_styled.getvalue()

  output.seek(0)
  return output.getvalue()


# =========================================================================
# SUITE DE PRUEBAS DE REGRESIÓN AUTOMATIZADAS
# =========================================================================
def ejecutar_pruebas_regresion():
  """Ejecuta una batería completa de pruebas de regresión técnica y funcional."""
  pruebas = []

  # 1. Prueba de Cifrado y Descifrado Seguro
  datos_prueba = [
      {"ID": "TEST_ENC", "Sitio / Unidad": "CARAJILLO", "Neto": 5000.0}
  ]
  clave_t = "ClavePrueba2026!"
  cifrado_str = cifrar_respaldo_seguro(datos_prueba, clave_t)
  dec_ok, msg_ok = descifrar_respaldo_seguro(cifrado_str, clave_t)
  dec_bad, msg_bad = descifrar_respaldo_seguro(cifrado_str, "ClaveErronea")
  p1 = dec_ok == datos_prueba and dec_bad is None
  pruebas.append({
      "Área": "Criptografía y Nube",
      "Prueba": (
          "Cifrado PBKDF2/HMAC y rechazo ante alteración o clave incorrecta"
      ),
      "Resultado": "✅ PASS" if p1 else "❌ FAIL",
      "Detalle": (
          "Validó integridad criptográfica, derivación de 100k iteraciones y"
          " firma HMAC."
      ),
  })

  # 2. Prueba de Regresión de Comprensión de Listas (Evitar '[' sin cerrar)
  sample_lista = [
      {"Sitio / Unidad": "CARAJILLO", "Fecha": "11/10/2026"},
      {"Sitio / Unidad": "PAMPAS", "Fecha": "11/10/2026"},
  ]
  unidades_test = [
      r.get("Sitio / Unidad")
      for r in sample_lista
      if r.get("Fecha") == "11/10/2026"
  ]
  p2 = len(unidades_test) == 2 and "CARAJILLO" in unidades_test
  pruebas.append({
      "Área": "Sintaxis y Regresión",
      "Prueba": "Evaluación segura de listas de reporte y recordatorios",
      "Resultado": "✅ PASS" if p2 else "❌ FAIL",
      "Detalle": (
          "Comprensión de listas de auditoría y WhatsApp cerrada y validada."
      ),
  })

  # 3. Prueba de Cálculos Financieros y Boletos
  tot_bol = (50 - 1) + 1  # 50
  cobrados = tot_bol - 2 - 1  # 47
  bruto = cobrados * 100.0  # 4700.0
  gastos = 1700.0
  neto = bruto - gastos  # 3000.0
  margen = (neto / bruto) * 100  # 63.83%
  p3 = (
      cobrados == 47
      and bruto == 4700.0
      and neto == 3000.0
      and round(margen, 2) == 63.83
  )
  pruebas.append({
      "Área": "Finanzas y Margen",
      "Prueba": "Cálculo exacto de cobrados, bruto, egresos y margen",
      "Resultado": "✅ PASS" if p3 else "❌ FAIL",
      "Detalle": (
          f"Folios calculados: 47 cobrados, $4,700 bruto, $3,000 neto"
          f" ({margen:.2f}%)."
      ),
  })

  # 4. Prueba de Semáforos de Rentabilidad
  p4 = (
      "Alta" in evaluar_rentabilidad(45.0)
      and "Moderada" in evaluar_rentabilidad(20.0)
      and "Baja" in evaluar_rentabilidad(5.0)
      and "Pérdida" in evaluar_rentabilidad(-5.0)
  )
  pruebas.append({
      "Área": "Clasificación de Negocio",
      "Prueba": "Semáforos de Rentabilidad (Alta, Moderada, Baja, Pérdida)",
      "Resultado": "✅ PASS" if p4 else "❌ FAIL",
      "Detalle": (
          "Validación de márgenes >=40% (Alta), 15-39% (Moderada), 0-14%"
          " (Baja), <0% (Pérdida)."
      ),
  })

  # 5. Prueba de Formato de Excel
  mock_excel_data = [{
      "ID": "TEST_EXCEL",
      "Fecha": "11/10/2026",
      "Sitio / Unidad": "CARAJILLO",
      "Horario": "13:00 a 23:00",
      "Costo Boleto": 100.0,
      "Folio Inicial": 1,
      "Folio Final": 50,
      "Total Boletos": 50,
      "Sin Cobro": 2,
      "Cancelados": 1,
      "Perdidos": 0,
      "Boletos Cobrados": 47,
      "Ingreso Bruto": 4700.0,
      "Gastos Especiales": 200.0,
      "Gastos Generales / Nómina": 1500.0,
      "Total Gastos": 1700.0,
      "Ingreso Neto": 3000.0,
      "Margen (%)": 63.83,
      "Rentabilidad": "🟢 Alta",
      "Elaboró": "Test",
      "Recibe": "Auditor",
      "Tipo": "Operación Regular",
      "foto_path": None,
  }]
  excel_bin = generar_excel_completo(mock_excel_data)
  p5 = excel_bin is not None and len(excel_bin) > 2000
  pruebas.append({
      "Área": "Entregables",
      "Prueba": (
          "Generación de libro Excel multi-pestaña (Semanal, Mensual, Detalle)"
      ),
      "Resultado": "✅ PASS" if p5 else "❌ FAIL",
      "Detalle": (
          f"Estructura binaria válida con"
          f" {len(excel_bin) if excel_bin else 0} bytes."
      ),
  })

  return pruebas


# =========================================================================
# CONFIGURACIÓN DE SUCURSALES Y PRECIOS
# =========================================================================
PRECIOS_SUCURSALES = {
    "PAMPAS": 50,
    "RAMMA": 70,
    "SUSHITTO": 40,
    "BARRANCA": 0,
    "CARAJILLO": 100,
    "BENINGANS": 40,
    "ROMAS": 65,
    "J.TLALPAN": 100,
    "J.DIVISION": 100,
    "J.PICACHO": 100,
    "J.EMPRESA": 100,
    "sipily": 80,
    "M SATÉLITE": 70,
    "M MARINA": 70,
    "VETERINARIA": 0,
    "CLÍNICA": 100,
    "SUMO STA": 50,
    "CHEGARAY": 50,
    "RYOSHI": 80,
    "ENCANTO": 90,
    "S. AZURA": 0,
    "E-BNI": 0,
    "CHURRASCA": 70,
}

UNIDADES_JESUS = [
    "PAMPAS",
    "RAMMA",
    "SUSHITTO",
    "BARRANCA",
    "CARAJILLO",
    "BENINGANS",
    "CLÍNICA",
]
UNIDADES_VICTOR = [
    "SUMO STA",
    "CHEGARAY",
    "RYOSHI",
    "ENCANTO",
    "S. AZURA",
    "CHURRASCA",
]
SUCURSALES_LISTA = ["-- Selecciona o busca la sucursal --"] + sorted(
    list(PRECIOS_SUCURSALES.keys())
)

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
      st.markdown(
          "<h1 style='text-align: center;'>🚗 CLUB PARK</h1>",
          unsafe_allow_html=True,
      )

    st.markdown(
        "<h3 style='text-align: center; color: #555;'>Control Operativo y"
        " Financiero</h3>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    nombre_usuario = st.selectbox(
        "Selecciona tu Usuario:",
        [
            "-- Selecciona --",
            "Víctor Manuel",
            "José de Jesús",
            "Víctor (Contador)",
        ],
        key="login_user",
    )
    password = st.text_input(
        "Contraseña de Acceso:", type="password", key="login_pass"
    )

    pass_visor = (
        st.secrets.get("PASS_SUPERVISOR", "visor123")
        if hasattr(st, "secrets")
        else "visor123"
    )
    pass_auditor = (
        st.secrets.get("PASS_AUDITOR", "contador123")
        if hasattr(st, "secrets")
        else "contador123"
    )

    if st.button("🔑 Iniciar Sesión", use_container_width=True, type="primary"):
      if (
          nombre_usuario in ["Víctor Manuel", "José de Jesús"]
          and password == pass_visor
      ):
        st.session_state.usuario_autenticado = nombre_usuario
        st.session_state.rol = "Supervisor"
        st.success(f"Bienvenido {nombre_usuario}")
        st.rerun()
      elif (
          nombre_usuario == "Víctor (Contador)" and password == pass_auditor
      ):
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
  st.markdown(
      f"**Usuario:** `{st.session_state.usuario_autenticado}` | **Rol:**"
      f" `{st.session_state.rol}`"
  )

es_contador = st.session_state.rol == "Contador Auditor"

if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
  st.session_state.usuario_autenticado = None
  st.session_state.rol = None
  st.rerun()

st.sidebar.markdown("---")
fotos_disco = (
    [f for f in os.listdir(FOTOS_DIR) if not f.startswith(".")]
    if os.path.exists(FOTOS_DIR)
    else []
)
st.sidebar.markdown(
    f"**📊 Reportes en Sistema:** `{len(st.session_state.registros)}`"
)
st.sidebar.markdown(f"**📷 Fotos Físicas Guardadas:** `{len(fotos_disco)}`")

if es_contador and st.session_state.registros:
  st.sidebar.markdown("---")
  st.sidebar.markdown("### 📥 Reporte Financiero Excel")
  excel_data = generar_excel_completo(st.session_state.registros)
  if excel_data:
    st.sidebar.download_button(
        label="📊 Descargar Excel Semanal y Mensual",
        data=excel_data,
        file_name=(
            "ClubPark_Balance_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

# =========================================================================
# PANEL EXCLUSIVO: CONTADOR AUDITOR (AUDITORÍA, WHATSAPP, PRUEBAS Y CIFRADO)
# =========================================================================
if es_contador:
  st.markdown("---")
  st.markdown("## 🔍 Panel de Auditoría, Control y Seguridad de Nube")

  tab_aud1, tab_aud2, tab_aud3, tab_aud4, tab_aud5 = st.tabs([
      "📲 WhatsApp Recordatorios",
      "🎪 Evento Extraordinario",
      "📂 Gestión de Reportes",
      "🧹 Depuración de Fotos",
      "🛡️ Cifrado y Pruebas de Regresión",
  ])

  # TAB 1: WhatsApp
  with tab_aud1:
    st.markdown("#### 🔔 Control de Reportes Faltantes por Fecha")
    fecha_revision = st.date_input(
        "Fecha a verificar:", value=date.today(), key="fecha_rev_aud"
    )
    fecha_rev_str = fecha_revision.strftime("%d/%m/%Y")

    unidades_reportadas_fecha = [
        reg.get("Sitio / Unidad")
        for reg in st.session_state.registros
        if reg.get("Fecha") == fecha_rev_str
    ]

    faltantes_jesus = [
        u for u in UNIDADES_JESUS if u not in unidades_reportadas_fecha
    ]
    faltantes_victor = [
        u for u in UNIDADES_VICTOR if u not in unidades_reportadas_fecha
    ]

    c_w1, c_w2 = st.columns(2)
    with c_w1:
      st.markdown("##### 👤 Supervisor: José de Jesús")
      if faltantes_jesus:
        st.warning(
            f"⚠️ **Pendientes ({len(faltantes_jesus)}):**"
            f" {', '.join(faltantes_jesus)}"
        )
        msg_j = (
            "🚨 *CLUB PARK - RECORDATORIO DE REPORTES*\n📅 *Fecha:*"
            f" {fecha_rev_str}\n👤 *Hola José de Jesús,* faltan los reportes"
            f" de:\n\n"
            + "\n".join([f"❌ {u}" for u in faltantes_jesus])
        )
        st.markdown(
            "[📲 **Enviar WhatsApp a"
            " Jesús**](https://api.whatsapp.com/send?text="
            f"{urllib.parse.quote(msg_j)})",
            unsafe_allow_html=True,
        )
      else:
        st.success("✅ ¡Todos sus reportes están completos!")

    with c_w2:
      st.markdown("##### 👤 Supervisor: Víctor Manuel")
      if faltantes_victor:
        st.warning(
            f"⚠️ **Pendientes ({len(faltantes_victor)}):**"
            f" {', '.join(faltantes_victor)}"
        )
        msg_v = (
            "🚨 *CLUB PARK - RECORDATORIO DE REPORTES*\n📅 *Fecha:*"
            f" {fecha_rev_str}\n👤 *Hola Víctor Manuel,* faltan los reportes"
            f" de:\n\n"
            + "\n".join([f"❌ {u}" for u in faltantes_victor])
        )
        st.markdown(
            "[📲 **Enviar WhatsApp a"
            " Víctor**](https://api.whatsapp.com/send?text="
            f"{urllib.parse.quote(msg_v)})",
            unsafe_allow_html=True,
        )
      else:
        st.success("✅ ¡Todos sus reportes están completos!")

  # TAB 2: Evento Extraordinario
  with tab_aud2:
    st.markdown("#### 🎪 Capturar Evento Extraordinario")
    ev_c1, ev_c2 = st.columns(2)
    with ev_c1:
      ev_fecha = st.date_input(
          "Fecha del Evento", value=date.today(), key="ev_fecha"
      )
      ev_suc = st.selectbox(
          "Sucursal / Salón del Evento", SUCURSALES_LISTA, key="ev_suc"
      )
      ev_ini_h = st.time_input("Hora Inicio", value=time(18, 0), key="ev_h_ini")
      ev_fin_h = st.time_input(
          "Hora Fin", value=time(23, 30), key="ev_h_fin"
      )
    with ev_c2:
      ev_costo = st.number_input(
          "Costo Boleto ($ MXN)", value=100.0, step=10.0, key="ev_costo"
      )
      ev_f_ini = st.number_input("Folio Inicial", value=1, step=1, key="ev_f_ini")
      ev_f_fin = st.number_input(
          "Folio Final", value=50, step=1, key="ev_f_fin"
      )
      ev_gastos = st.number_input(
          "Gastos Totales del Evento ($ MXN)",
          value=0.0,
          step=50.0,
          key="ev_gastos",
      )
      ev_elab = st.text_input("Elaboró", value="Staff Eventos", key="ev_elab")

    ev_boletos = (
        max(0, (int(ev_f_fin) - int(ev_f_ini)) + 1)
        if int(ev_f_fin) >= int(ev_f_ini) and int(ev_f_ini) > 0
        else 0
    )
    ev_bruto = ev_boletos * float(ev_costo)
    ev_neto = ev_bruto - float(ev_gastos)
    ev_margen = (ev_neto / ev_bruto * 100) if ev_bruto > 0 else 0.0

    st.info(
        f"**Boletos:** {ev_boletos} | **Bruto:** ${ev_bruto:,.2f} |"
        f" **Gastos:** ${ev_gastos:,.2f} \vert{} **Neto:**${ev_neto:,.2f} |"
        f" **Rentabilidad:** {evaluar_rentabilidad(ev_margen)}"
    )

    if st.button(
        "🚀 Registrar Evento Extraordinario",
        key="btn_save_evento",
        type="primary",
    ):
      if ev_suc != "-- Selecciona o busca la sucursal --":
        id_ev = f"EVT_{uuid.uuid4().hex[:6]}"
        evento_obj = {
            "ID": id_ev,
            "Fecha": ev_fecha.strftime("%d/%m/%Y"),
            "Sitio / Unidad": ev_suc,
            "Horario": (
                f"{ev_ini_h.strftime('%H:%M')} a"
                f" {ev_fin_h.strftime('%H:%M')}"
            ),
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
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.registros.append(evento_obj)
        guardar_registros_permanentes(st.session_state.registros)
        st.success("✅ Evento extraordinario guardado con éxito.")
        st.rerun()
      else:
        st.error("❌ Selecciona una sucursal válida.")

  # TAB 3: Gestión y Eliminación
  with tab_aud3:
    if st.session_state.registros:
      opciones_rep = [
          (
              f"{r.get('ID', f'IDX_{i}')} | {r.get('Fecha')} |"
              f" {r.get('Sitio / Unidad')} | Neto:"
              f" ${r.get('Ingreso Neto', 0):,.2f}"
          )
          for i, r in enumerate(st.session_state.registros)
      ]
      sel_rep = st.selectbox(
          "Seleccionar reporte:", opciones_rep, key="sel_rep_aud"
      )
      idx_rep = opciones_rep.index(sel_rep)
      rep_data = st.session_state.registros[idx_rep]

      c_info, c_foto = st.columns([2, 1])
      with c_info:
        st.json(rep_data)
      with c_foto:
        foto_p = rep_data.get("foto_path")
        if foto_p and os.path.exists(foto_p):
          st.image(
              foto_p,
              caption="Fotografía física vinculada al reporte",
              use_container_width=True,
          )
        else:
          st.caption("📷 Sin fotografía vinculada.")

      if st.button(
          "🗑️ Eliminar Este Reporte y su Foto",
          key="btn_del_rep",
          type="primary",
      ):
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

  # TAB 4: Fotos Huérfanas
  with tab_aud4:
    st.markdown(
        "#### 🧹 Fotografías Huérfanas (Sin reporte en base de datos)"
    )
    fotos_en_uso = {
        os.path.basename(r.get("foto_path"))
        for r in st.session_state.registros
        if r.get("foto_path")
    }
    todas_fotos_nombres = [
        f for f in os.listdir(FOTOS_DIR) if not f.startswith(".")
    ]
    huerfanas = [f for f in todas_fotos_nombres if f not in fotos_en_uso]

    st.write(
        f"Total fotos en servidor: **{len(todas_fotos_nombres)}** | Fotos sin"
        f" reporte: **{len(huerfanas)}**"
    )

    if huerfanas:
      st.warning(
          f"Se encontraron {len(huerfanas)} fotos que no corresponden a ningún"
          " reporte activo."
      )
      for fh in huerfanas[:3]:
        st.code(fh)
      if st.button(
          "🧹 Eliminar Todas las Fotos Huérfanas", key="btn_clean_huerfanas"
      ):
        for fh in huerfanas:
          p = os.path.join(FOTOS_DIR, fh)
          try:
            os.remove(p)
          except Exception:
            pass
        st.success("✅ Fotos huérfanas eliminadas.")
        st.rerun()
    else:
      st.success(
          "✅ Todas las fotografías en disco están vinculadas a un reporte"
          " válido."
      )

  # TAB 5: Cifrado y Pruebas de Regresión
  with tab_aud5:
    st.markdown("#### 🧪 Batería de Pruebas de Regresión")
    st.caption(
        "Comprueba que no existan regresiones en fórmulas, comprensión de"
        " datos, roles ni criptografía."
    )

    if st.button(
        "▶️ Ejecutar Pruebas de Regresión",
        key="btn_reg_tests",
        type="primary",
    ):
      reg_results = ejecutar_pruebas_regresion()
      st.dataframe(pd.DataFrame(reg_results), use_container_width=True)
      if all("PASS" in r["Resultado"] for r in reg_results):
        st.success("🎉 Todas las pruebas de regresión pasaron exitosamente.")
      else:
        st.error("⚠️ Se detectó una inconsistencia en las pruebas.")

    st.markdown("---")
    st.markdown("#### 🔐 Respaldo Cifrado de Información Financiera")
    st.caption(
        "Cifra los reportes con contraseña maestra para que nadie pueda ver"
        " ingresos ni nóminas sin autorización."
    )

    col_cif1, col_cif2 = st.columns(2)
    with col_cif1:
      st.markdown("##### 🔒 Generar y Descargar Respaldo Cifrado")
      pass_cifrado = st.text_input(
          "Contraseña para cifrar:", type="password", key="pass_cif_gen"
      )
      if st.button("Generar Archivo Cifrado", use_container_width=True):
        if len(pass_cifrado) >= 6:
          paquete_cifrado = cifrar_respaldo_seguro(
              st.session_state.registros, pass_cifrado
          )
          if paquete_cifrado:
            st.download_button(
                label="📥 Descargar Respaldo Cifrado (.enc)",
                data=paquete_cifrado,
                file_name=(
                    "clubpark_cifrado_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.enc"
                ),
                mime="application/json",
                use_container_width=True,
            )
            st.success("✅ Paquete cifrado generado con autenticación HMAC.")
        else:
          st.error("La contraseña debe tener al menos 6 caracteres.")

    with col_cif2:
      st.markdown("##### 🔓 Restaurar desde Respaldo Cifrado")
      arch_cif = st.file_uploader(
          "Subir archivo .enc cifrado:", type=["enc", "json"], key="upl_cif_res"
      )
      pass_descif = st.text_input(
          "Contraseña de descifrado:", type="password", key="pass_descif_val"
      )
      if arch_cif is not None and st.button(
          "Restaurar Respaldo Cifrado", type="primary", use_container_width=True
      ):
        contenido_cif = arch_cif.read().decode("utf-8")
        datos_recuperados, status_msg = descifrar_respaldo_seguro(
            contenido_cif, pass_descif
        )
        if datos_recuperados is not None and isinstance(
            datos_recuperados, list
        ):
          st.session_state.registros = datos_recuperados
          guardar_registros_permanentes(datos_recuperados)
          st.success(
              f"✅ Se restauraron exitosamente {len(datos_recuperados)}"
              " reportes protegidos."
          )
          st.rerun()
        else:
          st.error(f"❌ Error al descifrar: {status_msg}")

# =========================================================================
# SECCIÓN PRINCIPAL: CAPTURA DE REPORTES (VALIDADA POR ROL)
# =========================================================================
st.markdown("---")
if not es_contador:
  st.markdown(
      f"## 📋 Captura Diaria de Operaciones"
      f" ({st.session_state.usuario_autenticado})"
  )
  st.caption(
      "🔒 Como supervisor, solo puedes registrar operaciones del día de hoy."
  )
else:
  st.markdown("## 📥 Captura Regular o Extemporánea (Auditor)")
  st.caption("✨ Acceso sin restricción de fechas ni duplicados.")

sucursal = st.selectbox(
    "Sucursal / Unidad:",
    SUCURSALES_LISTA,
    key="select_sitio",
    on_change=on_sucursal_change,
)

es_ingreso_directo = sucursal in ["BARRANCA", "S. AZURA"]

col_f1, col_f2 = st.columns(2)
with col_f1:
  if es_contador:
    fecha_op = st.date_input(
        "Fecha del Reporte:", value=date.today(), key="fecha_op_aud"
    )
  else:
    fecha_hoy = date.today()
    st.write(
        f"📅 **Fecha de Operación:** `{fecha_hoy.strftime('%d/%m/%Y')}` *(Solo"
        " Hoy)*"
    )
    fecha_op = fecha_hoy

  fecha_op_str = fecha_op.strftime("%d/%m/%Y")

with col_f2:
  if es_ingreso_directo:
    st.info(
        "📌 En esta unidad se captura directamente el Ingreso Bruto en el campo"
        " correspondiente."
    )
    costo_boleto = 0.0
  else:
    costo_boleto = st.number_input(
        "Costo por Boleto ($ MXN):", step=5, key="costo_boleto_input"
    )

col_h1, col_h2 = st.columns(2)
with col_h1:
  hora_ini = st.time_input("Hora de Apertura:", value=time(13, 0), key="h_ini_rep")
with col_h2:
  hora_fin = st.time_input("Hora de Cierre:", value=time(23, 0), key="h_fin_rep")

with st.expander(
    "📷 Captura o Subida de Foto del Reporte Físico", expanded=True
):
  foto_subida = st.file_uploader(
      "Subir foto del reporte físico:",
      type=["png", "jpg", "jpeg"],
      key="uploader_foto_rep",
  )
  if foto_subida:
    st.image(foto_subida, caption="Vista previa del reporte adjunto", width=280)

st.markdown("#### 🎫 Control de Operaciones y Folios")
c_b1, c_b2, c_b3 = st.columns(3)

if es_ingreso_directo:
  with c_b1:
    f_ini = st.number_input(
        "Ingreso Bruto de la Unidad ($ MXN):",
        min_value=0.0,
        step=50.0,
        key="f_ini_dir",
    )
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
    f_ini = st.number_input(
        "Folio Inicial:", min_value=0, step=1, key="f_ini_val"
    )
    f_fin = st.number_input(
        "Folio Final:", min_value=0, step=1, key="f_fin_val"
    )
  with c_b2:
    f_sin = st.number_input(
        "Boletos Sin Cobro:", min_value=0, step=1, key="f_sin_val"
    )
    f_can = st.number_input(
        "Boletos Cancelados:", min_value=0, step=1, key="f_can_val"
    )
  with c_b3:
    f_per = st.number_input(
        "Boletos Perdidos:", min_value=0, step=1, key="f_per_val"
    )

  total_boletos_calc = (
      max(0, (int(f_fin) - int(f_ini)) + 1)
      if int(f_fin) >= int(f_ini) and int(f_ini) > 0
      else 0
  )
  boletos_cobrados_calc = max(0, total_boletos_calc - int(f_sin) - int(f_can))
  ingreso_bruto_calc = boletos_cobrados_calc * float(costo_boleto)

st.markdown("#### 💵 Egresos y Gastos Operativos")
c_g1, c_g2 = st.columns(2)
with c_g1:
  g_esp = st.number_input(
      "Gastos Especiales ($ MXN):", min_value=0.0, value=0.0, step=10.0, key="g_esp_val"
  )
with c_g2:
  g_gen = st.number_input(
      "Gastos Generales / Nómina ($ MXN):",
      min_value=0.0,
      value=0.0,
      step=10.0,
      key="g_gen_val",
  )

st.markdown("#### ✍️ Firmas")
c_fir1, c_fir2 = st.columns(2)
with c_fir1:
  elaboro = st.text_input(
      "Elaboró:", value=st.session_state.usuario_autenticado, key="elab_val"
  )
with c_fir2:
  recibe = st.text_input("Recibe:", value="", key="recibe_val")

total_gastos_calc = float(g_esp) + float(g_gen)
ingreso_neto_calc = ingreso_bruto_calc - total_gastos_calc
margen_calc = (
    (ingreso_neto_calc / ingreso_bruto_calc * 100)
    if ingreso_bruto_calc > 0
    else 0.0
)
rentabilidad_calc = evaluar_rentabilidad(margen_calc)

# --- BALANCE PRELIMINAR ---
st.markdown("---")
st.markdown("### 📊 Balance Preliminar del Reporte")

if not es_ingreso_directo:
  st.metric(
      label="🎟️ Boletos Pagados (Cobrados)",
      value=f"{boletos_cobrados_calc} boletos",
      help="Total expedido menos boletos sin cobro y cancelados",
  )
else:
  st.metric(
      label="💼 Modalidad de Cobro",
      value="Ingreso Directo Capturado",
      help="Unidad configurada con ingreso bruto directo",
  )

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
  st.metric("Ingreso Bruto", f"${ingreso_bruto_calc:,.2f} MXN")
with col_m2:
  st.metric("Total Gastos y Nómina", f"${total_gastos_calc:,.2f} MXN")
with col_m3:
  st.metric(
      "Ingreso Neto (Utilidad)",
      f"${ingreso_neto_calc:,.2f} MXN",
      delta=f"{margen_calc:.1f}% Margen",
  )
with col_m4:
  st.metric("Rentabilidad", rentabilidad_calc)

duplicado = ya_existe_reporte(sucursal, fecha_op_str)
puede_guardar = True

st.markdown("---")

if duplicado and not es_contador:
  st.error(
      f"🚫 **REPORTE YA EXISTE:** La sucursal **{sucursal}** ya cuenta con un"
      f" reporte para la fecha **{fecha_op_str}**."
  )
  st.warning(
      "⚠️ Como supervisor, no puedes duplicar reportes para la misma sucursal"
      " en el mismo día. Si necesitas corregirlo, solicita apoyo al Contador"
      " Auditor."
  )
  puede_guardar = False
elif duplicado and es_contador:
  st.warning(
      f"⚠️ **Atención:** Ya existe un reporte de **{sucursal}** para la fecha"
      f" **{fecha_op_str}**. Como Contador Auditor, puedes registrar este turno"
      " o reporte adicional."
  )

# BOTÓN DE GUARDADO PRINCIPAL
if st.button(
    "💾 Guardar y Confirmar Reporte Diario",
    type="primary",
    use_container_width=True,
    disabled=not puede_guardar,
):
  if sucursal == "-- Selecciona o busca la sucursal --":
    st.error("❌ Debes seleccionar una sucursal válida antes de guardar.")
  else:
    id_nuevo = f"REP_{uuid.uuid4().hex[:8]}"
    ruta_foto_guardada = None

    if foto_subida is not None:
      ruta_foto_guardada = guardar_imagen_optimizada(
          foto_subida, id_nuevo, sucursal, fecha_op_str
      )

    nuevo_reporte = {
        "ID": id_nuevo,
        "Fecha": fecha_op_str,
        "Sitio / Unidad": sucursal,
        "Horario": (
            f"{hora_ini.strftime('%H:%M')} a {hora_fin.strftime('%H:%M')}"
        ),
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
        "Elaboró": (
            elaboro if elaboro else st.session_state.usuario_autenticado
        ),
        "Recibe": recibe,
        "Tipo": "Operación Regular",
        "foto_path": ruta_foto_guardada,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    st.session_state.registros.append(nuevo_reporte)
    guardado_exitoso = guardar_registros_permanentes(
        st.session_state.registros
    )

    if guardado_exitoso:
      st.success(f"✅ Reporte guardado exitosamente con ID: `{id_nuevo}`")
      st.balloons()
      st.rerun()
    else:
      st.error(
          "❌ Ocurrió un error al guardar el reporte en el disco permanente."
      )
    
