
import os
import io
import json
import sqlite3
import base64
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

DB = Path("validador_reportes.db")

# ============================================================
# CONFIGURACIÓN
# ============================================================

USERS = {
    "Víctor Manuel Díaz": {"role": "usuario", "password_env": "VICTOR_DIAZ_PASSWORD"},
    "José de Jesús Salinas": {"role": "usuario", "password_env": "JOSE_SALINAS_PASSWORD"},
    "Víctor Manuel": {"role": "auditor", "password_env": "AUDITOR_PASSWORD"},
}

# Catálogo base de sitios y personas autorizadas para operar/subir reportes.
CATALOG = {
    "Pampas Insurgentes": ["José de Jesús Salinas"],
    "Rama": ["José de Jesús Salinas"],
    "Sushito": ["José de Jesús Salinas"],
    "Barranca": ["José de Jesús Salinas"],
    "Carajillo": ["José de Jesús Salinas"],
    "Pennygans": ["José de Jesús Salinas"],
    "Clínica": ["José de Jesús Salinas"],
    "Zumo Santa Mónica": ["Víctor Manuel"],
    "Zumo Chegaray": ["Víctor Manuel"],
    "Ryoshi Polanco": ["Víctor Manuel"],
    "Encanto Polanco": ["Víctor Manuel"],
    "Churrasquería": ["Víctor Manuel"],
    "Salón Romance": ["José de Jesús Salinas", "Víctor Manuel"],
    "Jungla Tlalpan": ["José de Jesús Salinas", "Víctor Manuel"],
    "Jungla División": ["José de Jesús Salinas", "Víctor Manuel"],
    "Jungla Picacho": ["José de Jesús Salinas", "Víctor Manuel"],
    "Jungla Empresas": ["José de Jesús Salinas", "Víctor Manuel"],
    "Cipirilí": ["José de Jesús Salinas", "Víctor Manuel"],
    "Marometa Satélite": ["José de Jesús Salinas", "Víctor Manuel"],
    "Marometa Marina": ["José de Jesús Salinas", "Víctor Manuel"],
    "Veterinaria": ["José de Jesús Salinas", "Víctor Manuel"],
}

# IMPORTANTE:
# Estos nombres son una base provisional. Antes de producción deben sustituirse
# por el catálogo real de personas autorizadas a recibir dinero/reporte.
AUTHORIZED_MONEY_RECEIVERS = {
    "José de Jesús Salinas",
    "Víctor Manuel",
}

AUTHORIZED_REPORT_RECEIVERS = {
    "José de Jesús Salinas",
    "Víctor Manuel",
    "Víctor Manuel Díaz",
}

FIELDS = [
    ("fecha", "Fecha"),
    ("sitio", "Sitio"),
    ("costo_unitario", "Costo unitario"),
    ("folio_inicial", "Folio inicial utilizado"),
    ("folio_final", "Folio final utilizado"),
    ("folio_inicio_block", "Folio de inicio sin desprender en block"),
    ("total_boletos", "Total de boletos"),
    ("boletos_pagados", "Boletos pagados"),
    ("boletos_cancelados", "Boletos cancelados"),
    ("boletos_perdidos", "Boletos perdidos"),
    ("boletos_entregados", "Total de boletos entregados"),
    ("gastos_operacion", "Gastos de operación"),
    ("lider_unidad", "Líder de unidad"),
    ("sueldo", "Sueldo"),
    ("operador", "Operador"),
    ("gastos_especiales", "Gastos especiales"),
    ("total_nominas_gastos", "Total de nóminas y gastos"),
    ("elabora_flujo", "Quién elabora el reporte de flujo"),
    ("elabora_reporte", "Quién elabora el reporte"),
    ("recibe_dinero", "Quién recibe la cantidad de dinero"),
    ("recibe_reporte", "Quién recibe físicamente el reporte"),
]


# ============================================================
# BASE DE DATOS
# ============================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user TEXT NOT NULL,
            status TEXT NOT NULL,
            data_json TEXT NOT NULL,
            errors_json TEXT NOT NULL,
            photo BLOB
        )
    """)
    conn.commit()
    return conn


def save_report(user, status, data, errors, photo):
    conn = db()
    conn.execute(
        """INSERT INTO reports
           (created_at,user,status,data_json,errors_json,photo)
           VALUES(?,?,?,?,?,?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            user,
            status,
            json.dumps(data, ensure_ascii=False),
            json.dumps(errors, ensure_ascii=False),
            photo,
        ),
    )
    conn.commit()
    conn.close()


def accepted_df():
    conn = db()
    rows = conn.execute(
        "SELECT id,created_at,user,data_json FROM reports "
        "WHERE status='ACEPTADO' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        d = json.loads(row["data_json"])
        d["_id"] = row["id"]
        d["_created_at"] = row["created_at"]
        d["_user"] = row["user"]
        records.append(d)

    return pd.DataFrame(records)


def all_reports_df():
    conn = db()
    rows = conn.execute(
        "SELECT id,created_at,user,status,data_json,errors_json "
        "FROM reports ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        d = json.loads(row["data_json"])
        d["_id"] = row["id"]
        d["_created_at"] = row["created_at"]
        d["_user"] = row["user"]
        d["_status"] = row["status"]
        d["_errors"] = json.loads(row["errors_json"])
        records.append(d)

    return pd.DataFrame(records)


# ============================================================
# CÁLCULOS
# ============================================================

def money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def calcular_folios(inicial, final):
    inicial = as_int(inicial)
    final = as_int(final)
    if inicial is None or final is None:
        return None
    if final < inicial:
        return None
    return final - inicial + 1


def calcular_resultados(r):
    total = as_int(r.get("total_boletos")) or 0
    costo = money(r.get("costo_unitario"))
    sueldo = money(r.get("sueldo"))
    gastos_operacion = money(r.get("gastos_operacion"))
    gastos_especiales = money(r.get("gastos_especiales"))

    bruto = costo * total
    total_gastos = sueldo + gastos_operacion + gastos_especiales
    utilidad = bruto - total_gastos

    r["_bruto"] = bruto
    r["_total_gastos"] = total_gastos
    r["_neto"] = utilidad
    return r


# ============================================================
# VALIDACIÓN
# ============================================================

def validate(r, user):
    errors = []
    today = date.today().isoformat()

    # Fecha
    if not r.get("fecha"):
        errors.append(("fecha", "La fecha es obligatoria."))
    elif str(r["fecha"]) != today and USERS[user]["role"] != "auditor":
        errors.append((
            "fecha",
            f"El reporte debe corresponder al día actual ({today}). "
            "Solo el auditor Víctor Manuel puede autorizar otra fecha."
        ))

    # Sitio
    sitio = str(r.get("sitio") or "").strip()
    if not sitio:
        errors.append(("sitio", "El sitio es obligatorio."))
    elif sitio not in CATALOG:
        errors.append(("sitio", "El sitio no está registrado en el catálogo maestro."))
    elif user not in CATALOG[sitio]:
        errors.append((
            "sitio",
            f"{user} no está autorizado para este sitio. "
            f"Permitidos: {', '.join(CATALOG[sitio])}."
        ))

    # Campos críticos
    critical = [
        "lider_unidad",
        "operador",
        "elabora_flujo",
        "elabora_reporte",
        "recibe_dinero",
        "recibe_reporte",
    ]
    for key in critical:
        if not str(r.get(key) or "").strip():
            errors.append((key, "Campo obligatorio y debe poder identificarse en la fotografía."))

    # Costo
    costo = money(r.get("costo_unitario"))
    if costo <= 0:
        errors.append(("costo_unitario", "El costo unitario debe ser mayor que cero."))

    # Folios
    fi = as_int(r.get("folio_inicial"))
    ff = as_int(r.get("folio_final"))
    total = as_int(r.get("total_boletos"))

    if fi is None or ff is None:
        errors.append(("folio_final", "Folio inicial y folio final son obligatorios."))
    else:
        if ff < fi:
            errors.append(("folio_final", "El folio final no puede ser menor que el inicial."))

    if total is None:
        errors.append(("total_boletos", "El total de boletos es obligatorio."))
    elif fi is not None and ff is not None:
        esperado = calcular_folios(fi, ff)
        if esperado != total:
            errors.append((
                "total_boletos",
                f"Los folios {fi} a {ff} representan {esperado} boletos, "
                f"pero el reporte indica {total}."
            ))

    # Distribución de boletos
    pagados = as_int(r.get("boletos_pagados"))
    cancelados = as_int(r.get("boletos_cancelados"))
    perdidos = as_int(r.get("boletos_perdidos"))

    pagados = 0 if pagados is None else pagados
    cancelados = 0 if cancelados is None else cancelados
    perdidos = 0 if perdidos is None else perdidos

    if min(pagados, cancelados, perdidos) < 0:
        errors.append(("boletos_pagados", "No puede haber cantidades negativas."))

    if total is not None and pagados + cancelados + perdidos != total:
        errors.append((
            "boletos_pagados",
            f"Pagados + cancelados + perdidos debe ser exactamente {total}."
        ))

    entregados = as_int(r.get("boletos_entregados"))
    if total is not None and entregados != total:
        errors.append((
            "boletos_entregados",
            f"El total de boletos entregados debe ser {total}."
        ))

    # Gastos
    sueldo = money(r.get("sueldo"))
    gastos_operacion = money(r.get("gastos_operacion"))
    gastos_especiales = money(r.get("gastos_especiales"))

    if min(sueldo, gastos_operacion, gastos_especiales) < 0:
        errors.append(("total_nominas_gastos", "Los gastos no pueden ser negativos."))

    esperado_gastos = sueldo + gastos_operacion + gastos_especiales
    reportado_gastos = money(r.get("total_nominas_gastos"))

    if abs(reportado_gastos - esperado_gastos) > 0.01:
        errors.append((
            "total_nominas_gastos",
            f"El total correcto de nóminas y gastos es ${esperado_gastos:,.2f}."
        ))

    # Receptores
    recibe_dinero = str(r.get("recibe_dinero") or "").strip()
    if recibe_dinero and recibe_dinero not in AUTHORIZED_MONEY_RECEIVERS:
        errors.append((
            "recibe_dinero",
            f"'{recibe_dinero}' no aparece en la lista de receptores de dinero autorizados."
        ))

    recibe_reporte = str(r.get("recibe_reporte") or "").strip()
    if recibe_reporte and recibe_reporte not in AUTHORIZED_REPORT_RECEIVERS:
        errors.append((
            "recibe_reporte",
            f"'{recibe_reporte}' no aparece en la lista de receptores de reportes autorizados."
        ))

    calcular_resultados(r)
    return errors


# ============================================================
# LECTURA IA / OCR
# ============================================================

def extract_ai(photo_bytes, mime_type="image/jpeg"):
    """
    Lectura mediante Anthropic si ANTHROPIC_API_KEY está configurada.
    Si no hay API, se devuelve un resultado vacío y la aplicación permite
    capturar/revisar los datos manualmente.
    """
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return {}

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=key)
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

        prompt = """
Lee esta fotografía de un Reporte de Operación por Unidad.

Devuelve ÚNICAMENTE un objeto JSON válido.
NO inventes datos.
Si un campo no es visible o no puede leerse con seguridad, devuelve null.

Campos:
fecha, sitio, costo_unitario, folio_inicial, folio_final,
folio_inicio_block, total_boletos, boletos_pagados,
boletos_cancelados, boletos_perdidos, boletos_entregados,
gastos_operacion, lider_unidad, sueldo, operador,
gastos_especiales, total_nominas_gastos,
elabora_flujo, elabora_reporte, recibe_dinero, recibe_reporte.

Reglas especiales:
- Distingue "recibe dinero" de "recibe reporte".
- No confundas Víctor Díaz con Víctor Manuel.
- Conserva números exactamente como aparecen.
- Si aparece más de un operador, combina sus nombres en un solo texto.
- Si un nombre o número es dudoso, usa null.
"""

        b64 = base64.b64encode(photo_bytes).decode("utf-8")

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64,
                        },
                    },
                ],
            }],
        )

        text = response.content[0].text.strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        return json.loads(text)

    except Exception as exc:
        st.error(f"No fue posible completar la lectura automática: {exc}")
        return {}


# ============================================================
# EXCEL
# ============================================================

def make_excel():
    df = accepted_df()
    if df.empty:
        return None

    for col in [
        "costo_unitario",
        "total_boletos",
        "sueldo",
        "gastos_operacion",
        "gastos_especiales",
    ]:
        if col not in df:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Ingreso bruto"] = df["costo_unitario"] * df["total_boletos"]
    df["Total gastos"] = (
        df["sueldo"] + df["gastos_operacion"] + df["gastos_especiales"]
    )
    df["Utilidad"] = df["Ingreso bruto"] - df["Total gastos"]

    detalle = df.copy()

    por_sitio = (
        detalle.groupby("sitio", dropna=False)[
            ["Ingreso bruto", "Total gastos", "Utilidad"]
        ]
        .sum()
        .reset_index()
    )

    por_supervisor = (
        detalle.groupby("lider_unidad", dropna=False)[
            ["Ingreso bruto", "Total gastos", "Utilidad"]
        ]
        .sum()
        .reset_index()
    )

    resumen = pd.DataFrame([{
        "Ingreso bruto": detalle["Ingreso bruto"].sum(),
        "Sueldos": detalle["sueldo"].sum(),
        "Gastos operación": detalle["gastos_operacion"].sum(),
        "Gastos especiales": detalle["gastos_especiales"].sum(),
        "Total gastos": detalle["Total gastos"].sum(),
        "Utilidad": detalle["Utilidad"].sum(),
    }])

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resumen.to_excel(writer, index=False, sheet_name="Resumen semanal")
        detalle.to_excel(writer, index=False, sheet_name="Detalle")
        por_sitio.to_excel(writer, index=False, sheet_name="Por sitio")
        por_supervisor.to_excel(writer, index=False, sheet_name="Por supervisor")

    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# INTERFAZ MÓVIL
# ============================================================

def mobile_css():
    st.markdown("""
    <style>
        .block-container {
            max-width: 760px;
            padding-top: 1rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        h1, h2, h3 {
            letter-spacing: -0.02em;
        }

        div.stButton > button {
            width: 100%;
            min-height: 3.2rem;
            border-radius: 14px;
            font-size: 1rem;
        }

        div[data-testid="stMetric"] {
            border-radius: 14px;
            padding: 0.6rem;
        }

        .mobile-card {
            padding: 1rem;
            border-radius: 16px;
            border: 1px solid rgba(128,128,128,.25);
            margin-bottom: .7rem;
        }

        .critical {
            padding: .8rem;
            border-radius: 12px;
            border-left: 5px solid #d33;
            background: rgba(220, 50, 50, .08);
            margin: .5rem 0;
        }

        .ok {
            padding: .8rem;
            border-radius: 12px;
            border-left: 5px solid #2e8b57;
            background: rgba(46, 139, 87, .08);
            margin: .5rem 0;
        }
    </style>
    """, unsafe_allow_html=True)


def login():
    if st.session_state.get("user"):
        return True

    st.title("📋 Validador de Reportes")
    st.caption("Versión móvil — diseñada para utilizarse desde Android")

    st.info("Fotografía → lectura automática → validación → aceptación/rechazo → registro")

    user = st.selectbox("Usuario", list(USERS))
    password = st.text_input("Contraseña", type="password")

    if st.button("🔐 Entrar"):
        expected = os.getenv(USERS[user]["password_env"], "1234")
        if password == expected:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    st.caption("Prueba local: si no configuras contraseñas, la clave temporal es 1234.")
    return False


def reset_new_report():
    for key in [
        "report",
        "photo",
        "mime_type",
        "errors",
        "validated",
        "accepted_current",
    ]:
        st.session_state.pop(key, None)


def render_validation_result(r, errors):
    if errors:
        st.error(f"❌ REPORTE RECHAZADO — {len(errors)} problema(s)")

        for field, message in errors:
            st.markdown(
                f'<div class="critical"><b>❌ {field}</b><br>{message}</div>',
                unsafe_allow_html=True,
            )

        st.warning(
            "El reporte NO puede aceptarse mientras existan errores. "
            "Los errores quedan registrados."
        )
        return False

    st.success("✅ REPORTE VÁLIDO")

    c1, c2 = st.columns(2)
    c1.metric("Ingreso bruto", f"${r['_bruto']:,.2f}")
    c2.metric("Total gastos", f"${r['_total_gastos']:,.2f}")

    st.metric("Utilidad / monto neto", f"${r['_neto']:,.2f}")

    st.markdown(
        '<div class="ok"><b>Validaciones principales correctas</b><br>'
        'Folios · boletos · operaciones · gastos · resultado</div>',
        unsafe_allow_html=True,
    )
    return True


def page_home(user, role):
    st.title("🏠 Inicio")
    st.success("Sistema listo para operar desde el celular.")

    st.write(f"**Usuario:** {user}")
    st.write(f"**Rol:** {'Auditor' if role == 'auditor' else 'Usuario'}")

    st.divider()

    st.subheader("Flujo del sistema")

    cols = st.columns(2)
    with cols[0]:
        st.markdown("### 📷 1. Foto")
        st.caption("Toma la fotografía del reporte.")
    with cols[1]:
        st.markdown("### 🤖 2. Lectura")
        st.caption("La IA extrae los datos.")

    cols = st.columns(2)
    with cols[0]:
        st.markdown("### 🧮 3. Cálculo")
        st.caption("Se recalculan folios, ingresos y gastos.")
    with cols[1]:
        st.markdown("### 🔎 4. Validación")
        st.caption("Se comparan datos y autorizaciones.")

    cols = st.columns(2)
    with cols[0]:
        st.markdown("### 🟢 5. Aceptar")
        st.caption("Solo si todas las reglas son correctas.")
    with cols[1]:
        st.markdown("### 🔴 6. Rechazar")
        st.caption("Se registra el motivo del rechazo.")

    st.divider()

    if st.button("📷 NUEVO REPORTE"):
        st.session_state.page = "📷 Nuevo reporte"
        st.rerun()


def page_new_report(user):
    st.title("📷 Nuevo reporte")
    st.caption("Toma la fotografía completa, de frente y con buena iluminación.")

    photo = st.camera_inpu