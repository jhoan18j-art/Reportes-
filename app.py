import base64
import io
import json
import os
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

# =========================================================
# CONFIGURACIÓN
# =========================================================
DB_FILE = Path("reportes_clubpark.json")
LOGO_FILE = Path("logo.png")

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

st.set_page_config(
    page_title="Club Park - Control Operativo MXN",
    page_icon="🚗",
    layout="wide",
)

st.markdown(
    """
    <style>
    input[type=number]::-webkit-inner-spin-button,
    input[type=number]::-webkit-outer-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type=number] { -moz-appearance: textfield; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# CATÁLOGO DE SUCURSALES Y COSTOS
# Ajusta los nombres y precios si el catálogo oficial cambia.
# =========================================================
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
OPCION_SITIO = "-- Selecciona una sucursal --"
SUCURSALES_LISTA = [OPCION_SITIO] + list(PRECIOS_SUCURSALES.keys())


# =========================================================
# ALMACENAMIENTO PERMANENTE JSON
# =========================================================
def cargar_registros_guardados():
    if not DB_FILE.exists():
        return []
    try:
        with DB_FILE.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, list):
            return []
        for registro in datos:
            foto_b64 = registro.pop("foto_b64", None)
            if foto_b64:
                try:
                    registro["foto_bytes"] = base64.b64decode(foto_b64)
                except Exception:
                    registro["foto_bytes"] = None
        return datos
    except (OSError, json.JSONDecodeError):
        return []


def guardar_registros_permanentes(registros):
    datos_guardar = []
    for registro in registros:
        copia = dict(registro)
        foto_bytes = copia.pop("foto_bytes", None)
        copia.pop("foto_b64", None)
        if foto_bytes:
            copia["foto_b64"] = base64.b64encode(foto_bytes).decode("ascii")
        datos_guardar.append(copia)

    archivo_temporal = DB_FILE.with_suffix(".tmp")
    with archivo_temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos_guardar, archivo, ensure_ascii=False, indent=2)
    archivo_temporal.replace(DB_FILE)


def obtener_api_key():
    try:
        return os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def imagen_a_jpeg_bytes(archivo_subido, max_size=(1200, 1200), quality=80):
    imagen = Image.open(archivo_subido).convert("RGB")
    imagen.thumbnail(max_size)
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=quality)
    return salida.getvalue()


def calcular_total_folios(inicial, final):
    """
    Cuenta folios incluyendo ambos extremos y permite que el folio final
    sea menor que el inicial. La regla usa los dos últimos dígitos,
    de modo que al pasar de 99 a 00 el conteo continúa.
    Ejemplos: 5080-5100 = 21; 5098-5102 = 5; 1890-1898 = 9.
    """
    inicial = int(inicial)
    final = int(final)
    if inicial <= 0 or final <= 0:
        return 0
    return ((final % 100) - (inicial % 100)) % 100 + 1


# =========================================================
# SESIÓN
# =========================================================
if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()
if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
if "rol" not in st.session_state:
    st.session_state.rol = None
if "costo_boleto_val" not in st.session_state:
    st.session_state.costo_boleto_val = 40
if "datos_ia_pendientes" not in st.session_state:
    st.session_state.datos_ia_pendientes = {}


def actualizar_costo_sucursal():
    sitio_actual = st.session_state.get("select_sitio")
    if sitio_actual in PRECIOS_SUCURSALES:
        st.session_state.costo_boleto_val = PRECIOS_SUCURSALES[sitio_actual]


# =========================================================
# INICIO DE SESIÓN
# Nota: cambia estas contraseñas antes de usar el sistema en producción.
# =========================================================
if st.session_state.usuario_autenticado is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), width=400)
        else:
            st.markdown(
                "<h1 style='text-align:center'>🚗 CLUB PARK VALET Y ESTACIONAMIENTOS</h1>",
                unsafe_allow_html=True,
            )
        st.markdown(
            "<h3 style='text-align:center;color:gray'>Control de Acceso al Sistema</h3>",
            unsafe_allow_html=True,
        )
        usuario = st.selectbox(
            "Selecciona tu usuario",
            ["-- Selecciona --", "Víctor Manuel Díaz", "José de Jesús", "Víctor (Contador)"],
        )
        password = st.text_input("Contraseña de acceso", type="password")
        if st.button("🔑 Entrar al sistema", use_container_width=True):
            usuarios = {
                "Víctor Manuel Díaz": ("visor123", "Supervisor"),
                "José de Jesús": ("visor123", "Supervisor"),
                "Víctor (Contador)": ("contador123", "Contador Auditor"),
            }
            credencial = usuarios.get(usuario)
            if credencial and password == credencial[0]:
                st.session_state.usuario_autenticado = usuario
                st.session_state.rol = credencial[1]
                st.rerun()
            else:
                st.error("Contraseña incorrecta o usuario no seleccionado.")
    st.stop()


# =========================================================
# ENCABEZADO Y MENÚ
# =========================================================
col_logo, col_titulo = st.columns([1, 4])
with col_logo:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=220)
    else:
        st.markdown("### **CP** - Club Park")
with col_titulo:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.subheader(
        f"Bienvenido, {st.session_state.usuario_autenticado} "
        f"({st.session_state.rol})"
    )

if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(
    f"**Usuario:** {st.session_state.usuario_autenticado}\n\n"
    f"**Rol:** {st.session_state.rol}\n\n"
    f"**Reportes almacenados:** {len(st.session_state.registros)}\n\n"
    "**Moneda:** MXN"
)


# =========================================================
# PANEL DEL CONTADOR AUDITOR
# =========================================================
if st.session_state.rol == "Contador Auditor":
    st.markdown("---")
    st.header("🔍 Panel de Auditoría y Balance Financiero")
    st.info(
        "Aquí puedes revisar los reportes guardados, consultar evidencias "
        "y descargar los datos consolidados."
    )

    if st.session_state.registros:
        df = pd.DataFrame([
            {k: v for k, v in registro.items() if k not in ("foto_bytes", "foto_b64")}
            for registro in st.session_state.registros
        ])

        for columna in [
            "Supervisor", "Sitio / Unidad", "Fecha", "Ingreso Bruto (MXN)",
            "Total Gastos y Nóminas (MXN)", "Ingreso Neto / Utilidad (MXN)",
            "Rentabilidad (%)",
        ]:
            if columna not in df.columns:
                df[columna] = 0 if "MXN" in columna or "%" in columna else ""

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Reportes de Víctor Manuel Díaz",
            int((df["Supervisor"] == "Víctor Manuel Díaz").sum()),
        )
        c2.metric(
            "Reportes de José de Jesús",
            int((df["Supervisor"] == "José de Jesús").sum()),
        )
        c3.metric("Reportes almacenados", len(df))

        st.subheader("🏢 Balance por sitio")
        df["Ingreso Bruto (MXN)"] = pd.to_numeric(
            df["Ingreso Bruto (MXN)"], errors="coerce"
        ).fillna(0)
        df["Total Gastos y Nóminas (MXN)"] = pd.to_numeric(
            df["Total Gastos y Nóminas (MXN)"], errors="coerce"
        ).fillna(0)
        df["Ingreso Neto / Utilidad (MXN)"] = pd.to_numeric(
            df["Ingreso Neto / Utilidad (MXN)"], errors="coerce"
        ).fillna(0)
        df["Rentabilidad (%)"] = pd.to_numeric(
            df["Rentabilidad (%)"], errors="coerce"
        ).fillna(0)

        balance = df.groupby("Sitio / Unidad", dropna=False).agg({
            "Ingreso Bruto (MXN)": "sum",
            "Total Gastos y Nóminas (MXN)": "sum",
            "Ingreso Neto / Utilidad (MXN)": "sum",
            "Rentabilidad (%)": "mean",
        }).reset_index()
        st.dataframe(balance, use_container_width=True)

        st.subheader("📊 Todos los reportes")
        st.dataframe(df, use_container_width=True)

        ingresos = df["Ingreso Bruto (MXN)"].sum()
        gastos = df["Total Gastos y Nóminas (MXN)"].sum()
        utilidad = df["Ingreso Neto / Utilidad (MXN)"].sum()
        rentabilidad = utilidad / ingresos * 100 if ingresos > 0 else 0

        a, b, c, d = st.columns(4)
        a.metric("Ingreso bruto acumulado", f"${ingresos:,.2f} MXN")
        b.metric("Gastos acumulados", f"${gastos:,.2f} MXN")
        c.metric("Utilidad acumulada", f"${utilidad:,.2f} MXN")
        d.metric("Rentabilidad global", f"{rentabilidad:.2f}%")

        st.subheader("📸 Evidencias fotográficas")
        with st.expander("Ver fotos de los reportes"):
            for idx, registro in enumerate(st.session_state.registros, start=1):
                if registro.get("foto_bytes"):
                    try:
                        st.image(
                            registro["foto_bytes"],
                            caption=(
                                f"Reporte #{idx} · {registro.get('Fecha', '')} · "
                                f"{registro.get('Sitio / Unidad', '')} · "
                                f"{registro.get('Supervisor', '')}"
                            ),
                            width=350,
                        )
                    except Exception:
                        st.warning(f"No se pudo abrir la foto del reporte #{idx}.")

        st.subheader("📥 Descargar consolidado")
        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Descargar consolidado CSV (compatible con Excel)",
            data=csv_data,
            file_name=f"Control_ClubPark_{date.today().strftime('%d_%m_%Y')}.csv",
            mime="text/csv",
        )

        st.warning("La eliminación es permanente y no se puede deshacer.")
        confirmar_borrado = st.checkbox("Confirmo que quiero borrar todos los registros")
        if st.button("🗑️ Borrar todos los registros", disabled=not confirmar_borrado):
            st.session_state.registros = []
            guardar_registros_permanentes([])
            st.success("Se borraron los registros.")
            st.rerun()
    else:
        st.warning("Todavía no hay reportes guardados.")
    st.stop()


# =========================================================
# CAPTURA DEL REPORTE PARA SUPERVISORES
# =========================================================
st.markdown("---")
st.header("📸 1. Evidencia fotográfica")
foto_reporte = st.file_uploader(
    "Toma o selecciona la foto de la hoja de reporte",
    type=["jpg", "jpeg", "png"],
    key="foto_reporte",
)

imagen = None
if foto_reporte is not None:
    try:
        imagen = Image.open(foto_reporte).convert("RGB")
        st.image(imagen, caption="Vista previa del reporte físico", width=400)
    except Exception:
        st.error("El archivo seleccionado no es una imagen válida.")
        imagen = None

    api_key = obtener_api_key()
    if not GENAI_AVAILABLE:
        st.caption(
            "La lectura automática con IA requiere instalar google-generativeai "
            "y configurar GEMINI_API_KEY."
        )
    elif not api_key:
        st.caption(
            "Para activar la lectura automática, configura GEMINI_API_KEY "
            "en los Secrets de Streamlit."
        )
    else:
        if st.button("🤖 Leer datos de la foto con IA"):
            with st.spinner("Leyendo el reporte..."):
                try:
                    genai.configure(api_key=api_key)
                    modelo = genai.GenerativeModel("gemini-1.5-flash")
                    prompt = """
Lee la fotografía de un reporte de valet parking. Devuelve SOLO JSON válido,
sin Markdown ni explicaciones, con estas claves:
{
 "folio_inicial": 0,
 "folio_final": 0,
 "folio_sin_desprender": 0,
 "cancelados": 0,
 "perdidos": 0,
 "gastos_especiales": 0.0,
 "gastos_generales": 0.0,
 "elaboro": "",
 "recibe": ""
}
Si un dato no se distingue, utiliza 0 para cantidades o cadena vacía para texto.
No inventes valores. Los folios deben ser números enteros.
"""
                    respuesta = modelo.generate_content([prompt, imagen])
                    texto = respuesta.text.strip()
                    texto = texto.removeprefix("```json").removeprefix("```")
                    texto = texto.removesuffix("```").strip()
                    datos = json.loads(texto)
                    st.session_state.datos_ia_pendientes = datos
                    st.success(
                        "Lectura terminada. Revisa y confirma manualmente los datos "
                        "antes de guardar el reporte."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"No se pudo leer la foto: {error}")

datos_ia = st.session_state.datos_ia_pendientes or {}


def dato_ia(clave, predeterminado=0):
    return datos_ia.get(clave, predeterminado)


st.markdown("---")
st.header("📝 2. Datos del reporte")
st.warning(
    "Verifica los datos extraídos de la foto. La lectura automática puede equivocarse; "
    "el reporte no se guarda hasta que pulses el botón de validación."
)

sitio = st.selectbox(
    "🏢 Sitio / Sucursal *",
    SUCURSALES_LISTA,
    key="select_sitio",
    on_change=actualizar_costo_sucursal,
)
es_barranca = sitio == "BARRANCA"

col_fecha, col_costo = st.columns(2)
with col_fecha:
    fecha_reporte = st.date_input("📅 Fecha del reporte", value=date.today())
with col_costo:
    if es_barranca:
        st.number_input(
            "💵 Costo del boleto ($ MXN)",
            value=0,
            disabled=True,
            help="Barranca usa una captura diaria de utilidad y gastos, sin cálculo por boletos.",
        )
        costo_boleto = 0
    else:
        costo_boleto = st.number_input(
            "💵 Costo del boleto ($ MXN)",
            min_value=0,
            value=int(st.session_state.costo_boleto_val),
            step=1,
            key="costo_boleto_input",
        )

# Inicializa valores para que siempre existan en ambos flujos.
folio_inicial = 0
folio_final = 0
folio_sin_desprender = 0
cancelados = 0
perdidos = 0
gastos_especiales = 0.0
gastos_generales = 0.0
utilidad_barranca = 0.0
gastos_operacion_barranca = 0.0

st.markdown("---")
if es_barranca:
    st.subheader("🏢 Barranca — captura diaria especial")
    st.info(
        "Para Barranca no se capturan folios ni boletos. Ingresa la utilidad "
        "del día y los gastos de operación del día."
    )
    cb1, cb2 = st.columns(2)
    with cb1:
        utilidad_barranca = st.number_input(
            "💰 Utilidad del día ($ MXN)",
            min_value=0.0,
            value=float(dato_ia("utilidad_dia", 0.0)),
            step=100.0,
            key="utilidad_barranca",
        )
    with cb2:
        gastos_operacion_barranca = st.number_input(
            "🛠️ Gastos de operación del día ($ MXN)",
            min_value=0.0,
            value=float(dato_ia("gastos_operacion_dia", dato_ia("gastos_generales", 0.0))),
            step=50.0,
            key="gastos_operacion_barranca",
        )

    total_boletos_entregados = 0
    boletos_pagados = 0
    gastos_especiales = 0.0
    gastos_generales = gastos_operacion_barranca
    total_gastos_live = gastos_operacion_barranca
    ingreso_neto_live = utilidad_barranca
    # En Barranca, utilidad neta + gastos = ingreso antes de gastos.
    ingreso_bruto_live = utilidad_barranca + gastos_operacion_barranca
    rentabilidad_live = (
        utilidad_barranca / ingreso_bruto_live * 100
        if ingreso_bruto_live > 0 else 0.0
    )
else:
    st.subheader("🔢 Folios y boletos")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        folio_inicial = st.number_input(
            "Folio inicial utilizado",
            min_value=0,
            value=int(dato_ia("folio_inicial", 0)),
            step=1,
            key="folio_inicial_input",
        )
        folio_final = st.number_input(
            "Folio final utilizado",
            min_value=0,
            value=int(dato_ia("folio_final", 0)),
            step=1,
            key="folio_final_input",
        )
    with fc2:
        cancelados = st.number_input(
            "Boletos cancelados",
            min_value=0,
            value=int(dato_ia("cancelados", 0)),
            step=1,
            key="cancelados_input",
        )
        perdidos = st.number_input(
            "Boletos perdidos",
            min_value=0,
            value=int(dato_ia("perdidos", 0)),
            step=1,
            key="perdidos_input",
        )
    with fc3:
        folio_sin_desprender = st.number_input(
            "Folio de inicio sin desprender del block",
            min_value=0,
            value=int(dato_ia("folio_sin_desprender", 0)),
            step=1,
            key="folio_sin_input",
        )

    total_boletos_entregados = calcular_total_folios(folio_inicial, folio_final)
    boletos_pagados = max(
        0, int(total_boletos_entregados) - int(cancelados) - int(perdidos)
    )

    st.subheader("🛠️ Gastos de operación")
    cg1, cg2 = st.columns(2)
    with cg1:
        gastos_especiales = st.number_input(
            "Gastos especiales ($ MXN)",
            min_value=0.0,
            value=float(dato_ia("gastos_especiales", 0.0)),
            step=10.0,
            key="gastos_especiales_input",
        )
    with cg2:
        gastos_generales = st.number_input(
            "Gastos generales / operación ($ MXN)",
            min_value=0.0,
            value=float(dato_ia("gastos_generales", 0.0)),
            step=10.0,
            key="gastos_generales_input",
        )

    total_gastos_live = gastos_especiales + gastos_generales
    ingreso_bruto_live = boletos_pagados * costo_boleto
    ingreso_neto_live = ingreso_bruto_live - total_gastos_live
    rentabilidad_live = (
        ingreso_neto_live / ingreso_bruto_live * 100
        if ingreso_bruto_live > 0 else 0.0
    )

st.markdown("---")
st.subheader("📊 Resumen financiero en vivo (MXN)")
if es_barranca:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Utilidad del día", f"${utilidad_barranca:,.2f}")
    m2.metric("Gastos de operación", f"${gastos_operacion_barranca:,.2f}")
    m3.metric("Ingreso antes de gastos*", f"${ingreso_bruto
