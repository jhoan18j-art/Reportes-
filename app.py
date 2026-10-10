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

DB_FILE = Path("reportes_clubpark.json")

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
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

# Catálogo inicial. Confirma estos precios antes de usar el sistema en producción.
PRECIOS_SUCURSALES = {
    "PAMPAS INSURGENTES": 50,
    "RAMMA": 70,
    "SUSHITTO": 40,
    "BARRANCA": 0,
    "CARAJILLO": 100,
    "PENNYGANS": 40,
    "SALÓN ROMANCE": 65,
    "JUNGLA TLALPAN": 100,
    "JUNGLA DIVISIÓN": 100,
    "JUNGLA PICACHO": 100,
    "JUNGLA EMPRESAS": 100,
    "CIPIRILÍ": 80,
    "MAROMETA SATÉLITE": 70,
    "MAROMETA MARINA": 70,
    "VETERINARIA": 0,
    "CLÍNICA": 100,
    "ZUMO SANTA MÓNICA": 50,
    "ZUMO CHEGARAY": 50,
    "RYOSHI POLANCO": 80,
    "ENCANTO POLANCO": 90,
    "S. AZURA": 0,
    "E-BNI": 0,
    "CHURRASQUERÍA": 70,
}

# Jesús supervisa estos sitios; Víctor Manuel supervisa los suyos.
SITIOS_POR_SUPERVISOR = {
    "José de Jesús": {
        "PAMPAS INSURGENTES", "RAMMA", "SUSHITTO", "BARRANCA",
        "CARAJILLO", "PENNYGANS", "CLÍNICA",
    },
    "Víctor Manuel": {
        "ZUMO SANTA MÓNICA", "ZUMO CHEGARAY", "RYOSHI POLANCO",
        "ENCANTO POLANCO", "CHURRASQUERÍA",
    },
}
SITIOS_COMPARTIDOS = {
    "SALÓN ROMANCE", "JUNGLA TLALPAN", "JUNGLA DIVISIÓN",
    "JUNGLA PICACHO", "JUNGLA EMPRESAS", "CIPIRILÍ",
    "MAROMETA SATÉLITE", "MAROMETA MARINA", "VETERINARIA",
}
SITIOS_COMPARTIDOS |= {"S. AZURA", "E-BNI"}

# Credenciales heredadas del prototipo. Cámbialas por secretos antes de producción.
USUARIOS = {
    "Víctor Manuel": {"password": "visor123", "rol": "Supervisor"},
    "Víctor Manuel Díaz": {"password": "visor123", "rol": "Supervisor"},
    "José de Jesús": {"password": "visor123", "rol": "Supervisor"},
    "Víctor (Contador)": {"password": "contador123", "rol": "Contador Auditor"},
}


def cargar_registros_guardados():
    if not DB_FILE.exists():
        return []
    try:
        with DB_FILE.open("r", encoding="utf-8") as archivo:
            registros = json.load(archivo)
        if not isinstance(registros, list):
            return []
        for registro in registros:
            foto_b64 = registro.pop("foto_b64", None)
            if foto_b64:
                try:
                    registro["foto_bytes"] = base64.b64decode(foto_b64)
                except (ValueError, TypeError):
                    registro["foto_bytes"] = None
        return registros
    except (OSError, json.JSONDecodeError):
        return []


def guardar_registros_permanentes(registros):
    datos = []
    for registro in registros:
        copia = dict(registro)
        foto = copia.pop("foto_bytes", None)
        copia.pop("foto_b64", None)
        if foto:
            copia["foto_b64"] = base64.b64encode(foto).decode("ascii")
        datos.append(copia)

    temporal = DB_FILE.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    temporal.replace(DB_FILE)


def actualizar_costo_sucursal():
    sitio = st.session_state.get("select_sitio")
    if sitio in PRECIOS_SUCURSALES:
        st.session_state["costo_boleto_val"] = PRECIOS_SUCURSALES[sitio]


def sitios_permitidos(usuario):
    if usuario in SITIOS_POR_SUPERVISOR:
        return sorted(SITIOS_POR_SUPERVISOR[usuario] | SITIOS_COMPARTIDOS)
    # Víctor Manuel Díaz es un usuario separado y no es el auditor.
    if usuario == "Víctor Manuel Díaz":
        return sorted(SITIOS_COMPARTIDOS)
    return sorted(PRECIOS_SUCURSALES)


def calcular_folios(inicial, final):
    """Cuenta ambos extremos del rango usando el número completo del folio."""
    inicial, final = int(inicial), int(final)
    if inicial <= 0 or final < inicial:
        return 0
    return final - inicial + 1


def convertir_foto_jpeg(upload):
    if upload is None:
        return None
    imagen = Image.open(upload).convert("RGB")
    imagen.thumbnail((1400, 1400))
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=82, optimize=True)
    return salida.getvalue()


if "registros" not in st.session_state:
    st.session_state.registros = cargar_registros_guardados()
if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None
if "rol" not in st.session_state:
    st.session_state.rol = None
if "costo_boleto_val" not in st.session_state:
    st.session_state.costo_boleto_val = 40
for clave, valor in {
    "f_ini": 0, "f_fin": 0, "f_sin": 0, "f_can": 0, "f_per": 0,
    "g_esp": 0.0, "g_gen": 0.0, "elaboro_val": "", "recibe_dinero_val": "",
    "recibe_reporte_val": "",
}.items():
    st.session_state.setdefault(clave, valor)

# ---------------- Inicio de sesión ----------------
if st.session_state.usuario_autenticado is None:
    izquierda, centro, derecha = st.columns([1, 2, 1])
    with centro:
        if Path("logo.png").exists():
            st.image("logo.png", width=350)
        else:
            st.markdown("<h1 style='text-align:center'>🚗 CLUB PARK</h1>", unsafe_allow_html=True)
        st.subheader("Control de acceso")
        usuario = st.selectbox("Selecciona tu usuario", ["-- Selecciona --", *USUARIOS.keys()])
        password = st.text_input("Contraseña", type="password")
        if st.button("🔑 Entrar", use_container_width=True):
            datos_usuario = USUARIOS.get(usuario)
            if datos_usuario and password == datos_usuario["password"]:
                st.session_state.usuario_autenticado = usuario
                st.session_state.rol = datos_usuario["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

usuario_actual = st.session_state.usuario_autenticado
rol_actual = st.session_state.rol

logo_col, titulo_col = st.columns([1, 4])
with logo_col:
    if Path("logo.png").exists():
        st.image("logo.png", width=180)
    else:
        st.markdown("## CP")
with titulo_col:
    st.title("CLUB PARK VALET Y ESTACIONAMIENTOS S.A. DE C.V.")
    st.subheader(f"Usuario: {usuario_actual} · Rol: {rol_actual}")

if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state.usuario_autenticado = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.info(
    f"**Usuario:** {usuario_actual}\n\n**Rol:** {rol_actual}\n\n"
    f"**Reportes registrados:** {len(st.session_state.registros)}\n\n**Moneda:** MXN"
)

# ---------------- Panel del contador auditor ----------------
if rol_actual == "Contador Auditor":
    st.header("🔍 Panel de auditoría y balance financiero")
    registros = st.session_state.registros
    if not registros:
        st.info("Todavía no hay reportes registrados.")
        st.stop()

    limpios = [
        {k: v for k, v in r.items() if k not in ("foto_bytes", "foto_b64")}
        for r in registros
    ]
    df = pd.DataFrame(limpios)
    if "Estado" in df.columns:
        df_aceptados = df[df["Estado"] == "ACEPTADO"].copy()
    else:
        df_aceptados = df.iloc[0:0].copy()

    st.caption("Los balances operativos usan únicamente reportes con estado ACEPTADO.")
    st.metric("Reportes almacenados", len(df))
    st.metric("Reportes aceptados", len(df_aceptados))
    st.metric("Reportes rechazados", int((df.get("Estado", pd.Series(dtype=str)) == "RECHAZADO").sum()))

    if not df_aceptados.empty:
        columnas_suma = [
            "Ingreso Bruto (MXN)", "Total Gastos y Nóminas (MXN)",
            "Ingreso Neto / Utilidad (MXN)",
        ]
        for col in columnas_suma:
            if col not in df_aceptados.columns:
                df_aceptados[col] = 0.0
        agrupado = df_aceptados.groupby("Sitio / Unidad", dropna=False)[columnas_suma].sum().reset_index()
        st.subheader("Balance por sitio (reportes aceptados)")
        st.dataframe(agrupado, use_container_width=True)

        ingreso = float(df_aceptados["Ingreso Bruto (MXN)"].sum())
        gastos = float(df_aceptados["Total Gastos y Nóminas (MXN)"].sum())
        utilidad = float(df_aceptados["Ingreso Neto / Utilidad (MXN)"].sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos", f"${ingreso:,.2f} MXN")
        m2.metric("Gastos", f"${gastos:,.2f} MXN")
        m3.metric("Utilidad", f"${utilidad:,.2f} MXN")

        csv = df_aceptados.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Descargar consolidado de reportes aceptados (CSV compatible con Excel)",
            data=csv,
            file_name=f"ClubPark_aceptados_{date.today():%Y%m%d}.csv",
            mime="text/csv",
        )

    st.subheader("Todos los registros y motivos de rechazo")
    st.dataframe(df, use_container_width=True)
    with st.expander("📸 Evidencias fotográficas"):
        for indice, registro in enumerate(registros, start=1):
            if registro.get("foto_bytes"):
                st.image(
                    Image.open(io.BytesIO(registro["foto_bytes"])),
                    caption=f"#{indice} · {registro.get('Fecha')} · {registro.get('Sitio / Unidad')} · {registro.get('Estado')}",
                    width=320,
                )

    st.warning("La eliminación es irreversible. Descarga primero los datos si necesitas conservarlos.")
    confirmar_borrado = st.checkbox("Confirmo que deseo borrar permanentemente todos los registros")
    if st.button("🗑️ Borrar todos los registros", disabled=not confirmar_borrado):
        st.session_state.registros = []
        guardar_registros_permanentes([])
        st.success("Registros eliminados.")
        st.rerun()
    st.stop()

# ---------------- Captura de reportes ----------------
st.header("📸 1. Fotografía del reporte")
foto_upload = st.file_uploader(
    "Toma o selecciona la fotografía del reporte",
    type=["jpg", "jpeg", "png"],
    key="foto_reporte",
)
imagen = None
if foto_upload is not None:
    try:
        imagen = Image.open(foto_upload).convert("RGB")
        st.image(imagen, caption="Vista previa del reporte", width=420)
    except Exception:
        st.error("No se pudo abrir la imagen. Prueba con un archivo JPG o PNG.")
        imagen = None

api_key = os.environ.get("GEMINI_API_KEY", "")
try:
    if not api_key:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    api_key = api_key or ""

if imagen is not None:
    if not GENAI_AVAILABLE:
        st.caption("La lectura con IA requiere instalar google-generativeai en requirements.txt.")
    elif not api_key:
        st.caption("Para activar la lectura automática, configura GEMINI_API_KEY en Secrets.")
    else:
        if st.button("🤖 Leer campos de la fotografía con IA"):
            try:
                genai.configure(api_key=api_key)
                modelo = genai.GenerativeModel("gemini-1.5-flash")
                prompt = """
Lee la fotografía de un reporte de valet parking. Devuelve solo JSON válido.
No inventes datos: si un campo no se distingue, usa null.
Esquema:
{
 "fecha": "YYYY-MM-DD o null",
 "sitio": "nombre o null",
 "costo_boleto": número o null,
 "folio_inicial": entero o null,
 "folio_final": entero o null,
 "folio_sin_desprender": entero o null,
 "cancelados": entero o null,
 "perdidos": entero o null,
 "gastos_especiales": número o null,
 "gastos_generales": número o null,
 "elaboro": "nombre o null",
 "recibe_dinero": "nombre o null",
 "recibe_reporte": "nombre o null"
}
"""
                respuesta = modelo.generate_content([prompt, imagen])
                texto = respuesta.text.strip().replace("```json", "").replace("```", "").strip()
                datos = json.loads(texto)
                st.session_state["lectura_ia"] = datos
                st.success("Lectura completada. Revisa los campos detectados; la IA no decide por sí sola si el reporte es válido.")
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudo leer la imagen: {exc}")

datos_ia = st.session_state.get("lectura_ia", {})
st.header("📝 2. Datos del reporte")
sitios = sitios_permitidos(usuario_actual)
opciones = ["-- Selecciona sitio --", *sitios]
sitio_ia = datos_ia.get("sitio")
indice_sitio = opciones.index(sitio_ia) if sitio_ia in opciones else 0

sitio = st.selectbox(
    "Sitio / unidad",
    opciones,
    index=indice_sitio,
    key="select_sitio",
    on_change=actualizar_costo_sucursal,
)
c1, c2, c3 = st.columns(3)
with c1:
    fecha_default = date.today()
    fecha_ia = datos_ia.get("fecha")
    if fecha_ia:
        try:
            fecha_default = date.fromisoformat(str(fecha_ia))
        except ValueError:
            pass
    fecha_reporte = st.date_input("Fecha del reporte", value=fecha_default)
with c2:
    costo_default = PRECIOS_SUCURSALES.get(sitio, 40)
    costo_boleto = st.number_input(
        "Costo por boleto (MXN)", min_value=0.0, step=1.0,
        value=float(datos_ia.get("costo_boleto") or costo_default),
    )
with c3:
    folio_inicial = int(st.number_input(
        "Folio inicial utilizado", min_value=0, step=1,
        value=int(datos_ia.get("folio_inicial") or 0),
    ))

c4, c5, c6 = st.columns(3)
with c4:
    folio_final = int(st.number_input(
        "Folio final utilizado", min_value=0, step=1,
        value=int(datos_ia.get("folio_final") or 0),
    ))
with c5:
    folio_sin_desprender = int(st.number_input(
        "Folio de inicio sin desprender", min_value=0, step=1,
        value=int(datos_ia.get("folio_sin_desprender") or 0),
    ))
with c6:
    cancelados = int(st.number_input(
        "Boletos cancelados", min_value=0, step=1,
        value=int(datos_ia.get("cancelados") or 0),
    ))

c7, c8 = st.columns(2)
with c7:
    perdidos = int(st.number_input(
        "Boletos perdidos", min_value=0, step=1,
        value=int(datos_ia.get("perdidos") or 0),
    ))
with c8:
    st.caption("Los folios se cuentan incluyendo el inicial y el final.")

if sitio == "BARRANCA":
    ingreso_bruto = st.number_input("Ingreso total directo de Barranca (MXN)", min_value=0.0, step=50.0)
    gastos_especiales = st.number_input("Gastos de operación de Barranca (MXN)", min_value=0.0, step=10.0)
    gastos_generales = 0.0
    total_boletos = 0
    boletos_pagados = 0
else:
    total_boletos = calcular_folios(folio_inicial, folio_final)
    boletos_pagados = total_boletos - cancelados - perdidos
    ingreso_bruto = max(0, boletos_pagados) * costo_boleto
    g1, g2 = st.columns(2)
    with g1:
        gastos_especiales = st.number_input(
            "Gastos especiales (MXN)", min_value=0.0, step=10.0,
            value=float(datos_ia.get("gastos_especiales") or 0.0),
        )
    with g2:
        gastos_generales = st.number_input(
            "Gastos generales (MXN)", min_value=0.0, step=10.0,
            value=float(datos_ia.get("gastos_generales") or 0.0),
        )

total_gastos = gastos_especiales + gastos_generales
utilidad = ingreso_bruto - total_gastos
rentabilidad = utilidad / ingreso_bruto * 100 if ingreso_bruto > 0 else 0.0

st.subheader("📊 Resumen calculado (MXN)")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Boletos entregados", total_boletos if sitio != "BARRANCA" else "No aplica")
m2.metric("Boletos pagados", boletos_pagados if sitio != "BARRANCA" else "No aplica")
m3.metric("Ingreso bruto", f"${ingreso_bruto:,.2f}")
m4.metric("Utilidad calculada", f"${utilidad:,.2f}")

st.header("👥 3. Responsables y validación")
r1, r2 = st.columns(2)
with r1:
    elaboro = st.text_input(
        "Quién elaboró el reporte",
        value=str(datos_ia.get("elaboro") or st.session_state.elaboro_val),
    )
    recibe_dinero = st.text_input(
        "Quién recibe el dinero",
        value=str(datos_ia.get("recibe_dinero") or st.session_state.recibe_dinero_val),
    )
with r2:
    recibe_reporte = st.text_input(
        "Quién recibe físicamente el reporte",
        value=str(datos_ia.get("recibe_reporte") or st.session_state.recibe_reporte_val),
    )
    st.caption("Los nombres de los receptores deben cotejarse con el catálogo autorizado antes de producción.")

st.caption("El prototipo registra el motivo de rechazo y evita incluir reportes rechazados en el balance operativo.")
if st.button("🔎 Validar y registrar reporte", type="primary"):
    errores = []
    if sitio == "-- Selecciona sitio --":
        errores.append("Selecciona un sitio válido.")
    if sitio != "BARRANCA":
        if folio_inicial <= 0 or folio_final <= 0:
            errores.append("Los folios inicial y final son obligatorios.")
        elif folio_final < folio_inicial:
            errores.append("El folio final no puede ser menor que el inicial.")
        if cancelados + perdidos > total_boletos:
            errores.append("Cancelados más perdidos superan el total de folios.")
        if boletos_pagados < 0:
            errores.append("El total de boletos pagados no puede ser negativo.")
        precio_catalogo = PRECIOS_SUCURSALES.get(sitio)
        if precio_catalogo is not None and float(costo_boleto) != float(precio_catalogo):
            errores.append(
                f"El costo del catálogo para {sitio} es ${precio_catalogo:.2f}; "
                f"se capturó ${costo_boleto:.2f}."
            )
    elif ingreso_bruto <= 0:
        errores.append("El ingreso directo de Barranca debe ser mayor que cero.")

    if fecha_reporte != date.today() and rol_actual != "Contador Auditor":
        errores.append("La fecha debe ser la de hoy. Solo el contador auditor puede revisar fechas anteriores.")
    if not elaboro.strip():
        errores.append("Indica quién elaboró el reporte.")
    if not recibe_dinero.strip():
        errores.append("Indica quién recibe el dinero.")
    if not recibe_reporte.strip():
        errores.append("Indica quién recibe físicamente el reporte.")
    if foto_upload is None or imagen is None:
        errores.append("Adjunta la fotografía del reporte.")

    estado = "RECHAZADO" if errores else "PENDIENTE DE AUTORIZACIÓN"
    # Sin un catálogo de receptores autorizado, no se marca como ACEPTADO automáticamente.
    motivo = " ".join(errores) if errores else (
        "Validaciones numéricas básicas correctas; requiere cotejo del auditor "
        "con la fotografía y los catálogos autorizados."
    )

    try:
        foto_bytes = convertir_foto_jpeg(foto_upload) if foto_upload is not None else None
    except Exception:
        foto_bytes = None
        estado = "RECHAZADO"
        motivo = (motivo + " No fue posible procesar la fotografía.").strip()

    registro = {
        "ID": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "Fecha": fecha_reporte.strftime("%d/%m/%Y"),
        "Fecha ISO": fecha_reporte.isoformat(),
        "Fecha de registro": datetime.now().isoformat(timespec="seconds"),
        "Supervisor": usuario_actual,
        "Rol": rol_actual,
        "Sitio / Unidad": sitio,
        "Costo Boleto (MXN)": float(costo_boleto),
        "Folio Inicial": folio_inicial,
        "Folio Final": folio_final,
        "Folio sin desprender": folio_sin_desprender,
        "Total Boletos Entregados": total_boletos,
        "Boletos Pagados": boletos_pagados,
        "Cancelados": cancelados,
        "Perdidos": perdidos,
        "Gastos Especiales (MXN)": float(gastos_especiales),
        "Gastos Generales (MXN)": float(gastos_generales),
        "Total Gastos y Nóminas (MXN)": float(total_gastos),
        "Ingreso Bruto (MXN)": float(ingreso_bruto),
        "Ingreso Neto / Utilidad (MXN)": float(utilidad),
        "Rentabilidad (
