"""
CLUB PARK VALET Y ESTACIONAMIENTOS
Módulo: Visita Comercial  →  Propuesta económica en PDF

Flujo:
  1. La ejecutiva llena el formato de visita (secciones I a IX) desde el celular.
  2. La app sugiere el tipo de propuesta:
       - Servicio integral de valet parking (iguala mensual + tarifa por boleto o cortesía)
       - Evento (tarifa global por horas, anticipo 50 %)
       - Administración de estacionamiento (gastos fijos + reparto de utilidad)
  3. Se ajustan montos, se elige quién firma y se genera la propuesta en PDF.
  4. Se descarga el PDF y se abre WhatsApp con el mensaje listo para el cliente.

Uso solo:          streamlit run visita_comercial.py
Uso en la app unificada:
                   import visita_comercial
                   visita_comercial.render()

Requisitos: streamlit, reportlab, pandas, openpyxl
Archivo de logo:   logo_clubpark.png  (en la misma carpeta)
"""

import io
import os
import csv
import urllib.parse
from datetime import date, datetime
from xml.sax.saxutils import escape

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN GENERAL (editar aquí los datos fijos de la empresa)
# ─────────────────────────────────────────────────────────────
CARPETA = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(CARPETA, "logo_clubpark.png")
ARCHIVO_VISITAS = os.path.join(CARPETA, "visitas_comerciales.csv")

EMPRESA = {
    "razon_social": "CLUB PARK VALET Y ESTACIONAMIENTOS, S.A. DE C.V.",
    "nombre": "CLUB PARK VALET Y ESTACIONAMIENTOS",
    "nombre_corto": "Club Park Valet y Estacionamientos S.A. de C.V.",
    "correo": "clubparkvalet@gmail.com",
    "direccion": "Calle Alcanfores, No. 18 Colonia Loma Larga Nicolás Romero C.P. 54459",
    "ciudad": "Ciudad de México",
}

# Quién firma la propuesta (agregar o quitar personas aquí)
FIRMANTES = {
    "Cinthya Estela Rivera Miranda": {"puesto": "Dirección Comercial",
                                      "telefono": "+52 55 3294 9575 - 55 69692178"},
    "Jonathan Ramírez Martínez": {"puesto": "Dirección Comercial",
                                  "telefono": "55 45651227"},
}

VERDE = colors.HexColor("#1B7A3A")
AZUL = colors.HexColor("#2F4F8F")
GRIS = colors.HexColor("#555555")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

GIROS = ["Restaurante", "Hotel", "Hospital", "Plaza Comercial", "Salón de Eventos", "Bar",
         "Agencia automotriz", "Otro"]
PROBLEMAS = ["Falta de estacionamiento", "Saturación vehicular", "Quejas de clientes",
             "Problemas de seguridad", "Falta de personal", "Pérdida de clientes por estacionamiento"]
BENEFICIOS = ["Mejor atención al cliente", "Incrementar ventas", "Mayor seguridad",
              "Mejor imagen corporativa", "Optimización de espacios", "Control vehicular"]
SERVICIOS = ["Recepción y resguardo de vehículos", "Operación completa de Valet Parking",
             "Control digital de entradas y salidas", "Personal uniformado",
             "Seguro de responsabilidad", "Reportes operativos", "Servicio para eventos especiales"]
INTERES = ["Muy Interesado", "Interesado", "Requiere más información", "Sin interés por el momento"]
ACCIONES = ["Enviar cotización", "Programar segunda visita", "Presentación ejecutiva",
            "Demostración del servicio", "Llamada de seguimiento", "Pendiente decisión"]
FLUJOS = ["Menos de 20", "20 a 50", "51 a 100", "Más de 100"]
TIPOS_EST = ["Propio", "Rentado", "Convenio con terceros", "Valet Parking Actual"]

TIPO_VALET = "Servicio integral de valet parking (mensual)"
TIPO_EVENTO = "Evento"
TIPO_ADMIN = "Administración de estacionamiento"
TIPOS_PROPUESTA = [TIPO_VALET, TIPO_EVENTO, TIPO_ADMIN]

# Valets sugeridos según el flujo diario (ajustable)
VALETS_POR_FLUJO = {"Menos de 20": 1, "20 a 50": 2, "51 a 100": 3, "Más de 100": 4}

# ── Textos de las propuestas (tomados de las propuestas reales de Club Park) ──
INFRA_VALET = {
    "Control digital y foliado": "<b>Control Digital y Foliado:</b> Suministro de boletos con tecnología de control "
        "interno, código de barras/QR de seguridad y foliación consecutiva para el blindaje de la recepción y entrega vehicular.",
    "Sistema digital de boletaje": "<b>Tecnología de Control Digital:</b> Implementación de un sistema digital de boletaje "
        "mediante dispositivos móviles, permitiendo el registro de tiempos, control de inventario de daños y trazabilidad "
        "en tiempo real de cada vehículo.",
    "Podio y cajón llavero": "<b>Custodia Hermética de Activos:</b> Uso exclusivo de un módulo operativo (podio de "
        "recepción) equipado con un cajón llavero de alta seguridad para el resguardo de las llaves.",
    "Conos y señalización": "<b>Señalización y Logística Vial:</b> Delimitación del espacio asignado mediante conos de "
        "tráfico de alta resistencia con cinta reflejante y señalamientos viales corporativos que indiquen claramente "
        "la zona de Valet Parking.",
    "Pintado de zona de recepción": "<b>Delimitación de Zonas:</b> Pintado formal de las zonas de recepción y entrega de "
        "vehículos para un flujo ordenado y estético.",
    "Tótem / banner corporativo": "<b>Presencia de Marca:</b> Tótem informativo o banner de identidad corporativa en el "
        "punto de atención.",
    "Circuitos de flujo vehicular": "<b>Logística de Flujo Vehicular:</b> Diseño de circuitos internos eficientes para la "
        "recepción, acomodo y entrega inmediata de las unidades, evitando congestionamientos en la vía pública o accesos "
        "principales.",
    "Personal uniformado": "<b>Identificación Corporativa del Personal:</b> Operación ejecutada por choferes profesionales, "
        "plenamente uniformados y con gafete de identificación visible.",
    "Choferes bilingües": "<b>Choferes Bilingües:</b> Personal operativo con dominio del idioma inglés para la atención "
        "de visitantes internacionales.",
}
INFRA_VALET_DEFAULT = ["Control digital y foliado", "Podio y cajón llavero", "Conos y señalización", "Personal uniformado"]

PROTECCION_VALET = {
    "Póliza de responsabilidad civil": "<b>Póliza de Responsabilidad Civil:</b> Cobertura amplia expedida por una "
        "institución aseguradora de primer nivel, que ampara daños materiales, robo total, robo parcial y daños a "
        "terceros durante la conducción, traslado y resguardo de los vehículos.",
    "Ajustador y supervisor 24 h": "<b>Protocolo de Gestión de Siniestros:</b> Disponibilidad inmediata de un ajustador "
        "de seguros y un supervisor operativo de zona las 24 horas del día para la atención de cualquier contingencia.",
    "Inspección fotográfica al ingreso": "<b>Inspección Digital Previa (Check-in):</b> Registro fotográfico y digital del "
        "estado físico de cada vehículo al momento de la recepción para evitar controversias por daños preexistentes.",
    "Custodia blindada de llaves": "<b>Custodia Blindada de Llaves:</b> Almacenamiento obligatorio de los juegos de llaves "
        "en gavetas de seguridad reforzadas, accesibles únicamente por el supervisor asignado.",
    "Personal certificado": "<b>Personal Certificado:</b> Operadores rigurosamente seleccionados mediante exámenes de "
        "control de confianza y con licencia de conducir vigente.",
}
PROTECCION_DEFAULT = ["Póliza de responsabilidad civil", "Inspección fotográfica al ingreso", "Personal certificado"]

CAPITAL_HUMANO = [
    "<b>Filtros de Reclutamiento Rigurosos:</b> Todo nuestro personal operativo aprueba auditorías de control de "
    "confianza, exámenes toxicológicos, validación de antecedentes no penales y cuenta con licencia de conducir vigente.",
    "<b>Capacitación Especializada:</b> El equipo está capacitado en conducción defensiva, maniobras en espacios "
    "reducidos, primeros auxilios y protocolos de servicio al cliente de alta gama.",
    "<b>Monitoreo y Auditoría de Operaciones:</b> Asignación de un Coordinador de Estación que supervisará los tiempos "
    "de espera (Key-to-Key Time), auditará el estado de los vehículos recibidos y coordinará la logística durante las "
    "horas de máxima afluencia.",
]


# ─────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────
def pesos(valor: float) -> str:
    return f"${valor:,.2f} MXN"


def fecha_larga(f: date) -> str:
    return f"{f.day:02d} de {MESES[f.month - 1]} de {f.year}"


def t(texto) -> str:
    """Escapa texto para los párrafos del PDF."""
    return escape(str(texto or "")).replace("\n", "<br/>")


_UNI = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
        "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
        "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
        "veintiocho", "veintinueve"]
_DEC = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CEN = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
        "setecientos", "ochocientos", "novecientos"]


def _menor_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    partes = [_CEN[c]] if c else []
    if r < 30:
        partes.append(_UNI[r])
    else:
        d, u = divmod(r, 10)
        partes.append(_DEC[d] + (f" y {_UNI[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def _apocopar(txt: str) -> str:
    """'uno' → 'un' y 'veintiuno' → 'veintiún' antes de 'mil', 'millones' o 'pesos'."""
    if txt.endswith("veintiuno"):
        return txt[:-9] + "veintiún"
    if txt.endswith("uno"):
        return txt[:-3] + "un"
    return txt


def numero_a_letras(valor: float) -> str:
    """12500.00 → 'Doce mil quinientos pesos 00/100 M.N.'"""
    entero = int(round(valor * 100)) // 100
    centavos = int(round(valor * 100)) % 100
    if entero == 0:
        letras = "cero"
    else:
        millones, resto = divmod(entero, 1_000_000)
        miles, unidades = divmod(resto, 1000)
        partes = []
        if millones:
            partes.append("un millón" if millones == 1 else _apocopar(_menor_mil(millones)) + " millones")
        if miles:
            partes.append("mil" if miles == 1 else _apocopar(_menor_mil(miles)) + " mil")
        if unidades:
            partes.append(_apocopar(_menor_mil(unidades)))
        letras = " ".join(partes)
    de = " de" if entero and entero % 1_000_000 == 0 else ""
    texto = f"{letras}{de} pesos {centavos:02d}/100 M.N."
    return texto[0].upper() + texto[1:]


def monto_con_letra(valor: float) -> str:
    return f"{pesos(valor)} ({numero_a_letras(valor)})"


def sugerir_tipo(giro, tiene_est, tipos_est, servicios):
    if giro == "Salón de Eventos" or servicios == ["Servicio para eventos especiales"]:
        return TIPO_EVENTO
    if tiene_est == "Sí" and any(x in tipos_est for x in ("Propio", "Rentado")) \
            and giro in ("Plaza Comercial", "Hospital", "Otro"):
        return TIPO_ADMIN
    return TIPO_VALET


def siguiente_folio() -> str:
    n = 1
    if os.path.exists(ARCHIVO_VISITAS):
        with open(ARCHIVO_VISITAS, encoding="utf-8") as f:
            n = sum(1 for _ in f)  # incluye encabezado → siguiente número
    return f"VC-{date.today().year}-{n:04d}"


def guardar_visita(registro: dict):
    existe = os.path.exists(ARCHIVO_VISITAS)
    with open(ARCHIVO_VISITAS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(registro.keys()))
        if not existe:
            w.writeheader()
        w.writerow(registro)


# ─────────────────────────────────────────────────────────────
# GENERACIÓN DEL PDF
# ─────────────────────────────────────────────────────────────
def _estilos():
    base = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=colors.black)
    return {
        "normal": ParagraphStyle("normal", alignment=TA_JUSTIFY, spaceAfter=5, **base),
        "dato": ParagraphStyle("dato", alignment=TA_LEFT, **base),
        "fecha": ParagraphStyle("fecha", alignment=TA_RIGHT, **{**base, "fontName": "Helvetica-Bold"}),
        "folio": ParagraphStyle("folio", alignment=TA_RIGHT, fontName="Helvetica", fontSize=8, leading=10,
                                textColor=GRIS),
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13.5, leading=17,
                                 textColor=VERDE, spaceAfter=8),
        "sub": ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                              textColor=AZUL, spaceBefore=10, spaceAfter=5),
        "sub2": ParagraphStyle("sub2", fontName="Helvetica-Bold", fontSize=10, leading=13,
                               spaceBefore=4, spaceAfter=2),
        "vineta": ParagraphStyle("vineta", leftIndent=16, bulletIndent=5, spaceAfter=4,
                                 alignment=TA_JUSTIFY, **base),
        "firma": ParagraphStyle("firma", alignment=TA_LEFT, **{**base, "fontName": "Helvetica-Bold"}),
        "firma_dato": ParagraphStyle("firma_dato", alignment=TA_LEFT, **base),
    }


def _encabezado_pie(canvas, doc):
    canvas.saveState()
    ancho, alto = letter
    if os.path.exists(LOGO):
        canvas.drawImage(LOGO, 2 * cm, alto - 3.1 * cm, width=7 * cm, height=1.28 * cm,
                         preserveAspectRatio=True, mask="auto")
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawRightString(ancho - 2 * cm, alto - 2.95 * cm, EMPRESA["razon_social"])
    canvas.setStrokeColor(AZUL)
    canvas.setLineWidth(2)
    canvas.line(2 * cm, alto - 3.25 * cm, ancho - 2 * cm, alto - 3.25 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawCentredString(ancho / 2, 1.3 * cm, EMPRESA["direccion"])
    canvas.drawRightString(ancho - 2 * cm, 0.8 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _tabla(filas, anchos, total=False):
    tb = Table(filas, colWidths=anchos)
    estilo = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if total:
        estilo += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9.5),
                   ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F3EC"))]
    tb.setStyle(TableStyle(estilo))
    return tb


def _vinetas(lista, s):
    return [Paragraph(x, s["vineta"], bulletText="•") for x in lista]


def _diagnostico(v, s):
    """Párrafo opcional con lo detectado en la visita."""
    partes = []
    if v.get("problemas"):
        partes.append("Durante nuestra visita a sus instalaciones identificamos las siguientes áreas de oportunidad: "
                      + ", ".join(p.lower() for p in v["problemas"]) + ".")
    if v.get("beneficios"):
        partes.append("Nuestra propuesta está enfocada en lograr: "
                      + ", ".join(b.lower() for b in v["beneficios"]) + ".")
    if v.get("flujo"):
        partes.append(f"Considerando un flujo estimado de {v['flujo'].lower()} vehículos por día"
                      + (f" y mayor afluencia en el horario de {v['horario_afluencia']}" if v.get("horario_afluencia") else "")
                      + ", dimensionamos la operación para garantizar un servicio ágil.")
    return [Paragraph(t(" ".join(partes)), s["normal"])] if partes else []


def _firma(firmante, s):
    datos = FIRMANTES.get(firmante, {"puesto": "Dirección Comercial", "telefono": ""})
    bloque = [
        Spacer(1, 14),
        Paragraph("ATENTAMENTE:", s["firma"]),
        Spacer(1, 30),
        Paragraph("_______________________________", s["firma"]),
        Paragraph(t(firmante), s["firma"]),
        Paragraph(t(datos["puesto"]), s["firma_dato"]),
        Paragraph(t(EMPRESA["nombre"]), s["firma_dato"]),
        Spacer(1, 4),
    ]
    if datos.get("telefono"):
        bloque.append(Paragraph(f"Teléfono: {t(datos['telefono'])}", s["firma_dato"]))
    bloque.append(Paragraph(f"Correo electrónico: {t(EMPRESA['correo'])}", s["firma_dato"]))
    return KeepTogether(bloque)


def _encabezado_cliente(v, titulo, s):
    return [
        Paragraph(titulo, s["titulo"]),
        Paragraph(f"<b>Atención:</b> {t(v['atencion'])}", s["dato"]),
        Paragraph(f"<b>Cliente:</b> {t(v['nombre_comercial'])}", s["dato"]),
        Paragraph(f"<b>Presenta:</b> {t(EMPRESA['nombre_corto'])}", s["dato"]),
        Spacer(1, 12),
    ]


def _cuerpo_valet(v, c, s):
    cliente = v["nombre_comercial"]
    h = _encabezado_cliente(v, "PROPUESTA ECONÓMICA Y COMERCIAL: SERVICIO INTEGRAL DE VALET PARKING", s)
    h += [
        Paragraph(f"{t(v['saludo'])}:", s["dato"]),
        Spacer(1, 4),
        Paragraph(t(f"En primera instancia, expresamos nuestro más sincero agradecimiento por la confianza depositada "
                    f"en {EMPRESA['nombre_corto']} al permitirnos presentar esta propuesta comercial para la gestión, "
                    f"administración y operación integral del servicio de valet parking de su prestigiado establecimiento."),
                  s["normal"]),
        Paragraph(t(f"Nuestra organización se fundamenta en una visión estratégica orientada a elevar los estándares de "
                    f"hospitalidad y servicio de nuestros socios comerciales. Nos comprometemos a brindar a sus clientes y "
                    f"visitantes una experiencia de movilidad de categoría premium, caracterizada por la optimización "
                    f"logística, la rigurosidad en los protocolos de seguridad y un trato de excelencia que proyecte "
                    f"fielmente el prestigio de {cliente}."), s["normal"]),
    ]
    if c.get("diagnostico"):
        h += _diagnostico(v, s)
    h.append(Paragraph("A continuación, sometemos a su consideración las condiciones económicas, las especificaciones "
                       "de infraestructura y los esquemas de protección que integran nuestra solución corporativa:",
                       s["normal"]))

    # 1. Económica
    n = 1
    h.append(Paragraph(f"{n}. Propuesta Económica y Condiciones Comerciales", s["sub"]))
    eco = [f"<b>Iguala Mensual por Operación (Fee de Servicio):</b> {t(monto_con_letra(c['iguala']))} más el Impuesto "
           "al Valor Agregado (IVA). Este importe cubre en su totalidad la supervisión técnica, la administración del "
           "personal, el equipamiento base y la coordinación operativa."]
    if c["tarifa_usuario"] > 0:
        txt = (f"<b>Tarifa Comercial por Usuario / Boleto:</b> {t(monto_con_letra(c['tarifa_usuario']))} IVA incluido. "
               "Este costo será cubierto directamente por el usuario al momento de solicitar su vehículo, operando bajo "
               "la modalidad de cobro regular por boleto expedido.")
        if c.get("recauda_clubpark"):
            txt += (f" Con el fin de absorber los costos operativos y de boletaje, la totalidad del ingreso generado por "
                    f"este concepto será percibida por {t(EMPRESA['nombre_corto'])}.")
        eco.append(txt)
    else:
        eco.append("<b>Tarifa Comercial por Usuario / Boleto:</b> $0.00 MXN (Servicio de Cortesía). Con el objetivo de "
                   "alinear nuestra operación con los estándares de atención y valor agregado de su marca, el servicio no "
                   "generará ningún costo directo para sus clientes y visitantes al momento de recibir o entregar sus vehículos.")
    if c.get("valets"):
        eco.append(f"<b>Personal asignado:</b> {c['valets']} elemento(s) de valet parking"
                   + (f" en horario de {t(c['horario'])}" if c.get("horario") else "")
                   + (f", {_dias_texto(c['dias'])}" if c.get("dias") else "") + ".")
    h += _vinetas(eco, s)
    iva = c["iguala"] * 0.16
    h += [Spacer(1, 4), _tabla([
        ["Concepto", "Importe"],
        ["Iguala mensual por operación", pesos(c["iguala"])],
        ["IVA (16 %)", pesos(iva)],
        ["Total mensual", pesos(c["iguala"] + iva)],
    ], [11.5 * cm, 5 * cm], total=True)]

    # 2. Infraestructura
    if c["infraestructura"]:
        n += 1
        h.append(Paragraph(f"{n}. Infraestructura, Equipamiento y Logística Operativa", s["sub"]))
        h.append(Paragraph(t(f"Con el objetivo de garantizar un flujo vehicular ordenado, estético y de alta "
                             f"funcionalidad, {EMPRESA['nombre_corto']} absorberá en su totalidad la inversión y "
                             f"suministro de los siguientes componentes en el área de recepción:"), s["normal"]))
        h += _vinetas([INFRA_VALET[k] for k in c["infraestructura"]], s)

    # 3. Protección
    if c["proteccion"] or c.get("cobertura"):
        n += 1
        h.append(Paragraph(f"{n}. Esquema de Protección Patrimonial y Cobertura de Seguros", s["sub"]))
        h.append(Paragraph(t(f"Para garantizar la absoluta tranquilidad jurídica y patrimonial de {cliente} y de sus "
                             f"clientes, nuestra operación se encuentra respaldada por el siguiente blindaje:"), s["normal"]))
        prot = [PROTECCION_VALET[k] for k in c["proteccion"]]
        if c.get("cobertura"):
            prot.append(f"<b>Suma Asegurada:</b> cobertura global de hasta {pesos(c['cobertura'])}"
                        + (f", con un sublímite de hasta {pesos(c['sublimite'])} por vehículo" if c.get("sublimite") else "")
                        + ".")
        h += _vinetas(prot, s)

    # 4. Capital humano
    if c.get("capital_humano"):
        n += 1
        h.append(Paragraph(f"{n}. Capital Humano y Compromiso de Calidad", s["sub"]))
        h += _vinetas(CAPITAL_HUMANO, s)

    # Vigencia
    n += 1
    h.append(Paragraph(f"{n}. Vigencia y Aceptación de la Propuesta", s["sub"]))
    vig = [f"<b>Validez de la Oferta:</b> La presente propuesta mantiene una vigencia de {c['vigencia']} días naturales "
           "a partir de su fecha de emisión.",
           f"<b>Inicio de Operaciones:</b> Posterior a la aceptación se formalizará el Contrato de Prestación de Servicios "
           f"correspondiente, con un periodo de implementación de {c['dias_implementacion']} días hábiles a partir de la "
           "firma para el reclutamiento, capacitación del personal e instalación de la infraestructura."]
    if c.get("notas"):
        vig.append(t(c["notas"]))
    h += _vinetas(vig, s)

    h += [
        Spacer(1, 6),
        Paragraph(t(f"Reiteramos nuestro compromiso de convertirnos en un aliado estratégico para {cliente}. "
                    "Quedamos a su entera disposición para coordinar una sesión de trabajo, resolver dudas o realizar "
                    "los ajustes que su dirección considere pertinentes."), s["normal"]),
        Paragraph("Sin otro particular por el momento, aprovechamos la ocasión para enviarle un cordial saludo.",
                  s["normal"]),
    ]
    return h


def _cuerpo_evento(v, c, s):
    cliente = v["nombre_comercial"]
    h = [
        Paragraph("PROPUESTA TÉCNICO-COMERCIAL: SERVICIO PREMIUM DE VALET PARKING", s["titulo"]),
        Paragraph(f"<b>Atención:</b> {t(cliente)}"
                  + (f" — {t(v['contacto'])}" if v.get("contacto") else ""), s["dato"]),
        Spacer(1, 10),
        Paragraph("Estimado cliente:", s["dato"]),
        Spacer(1, 4),
        Paragraph(t(f"Es un privilegio para {EMPRESA['nombre']} someter a su consideración nuestra propuesta integral "
                    "de servicios logísticos para su próximo evento. Nuestro compromiso estratégico es proyectar la "
                    "mejor imagen desde el primer contacto, garantizando una experiencia fluida, segura y de alto nivel "
                    "para sus invitados mediante estrictos estándares de hospitalidad y control operativo."), s["normal"]),
        Paragraph("A continuación, detallamos la estructura técnica y económica diseñada a la medida de sus requerimientos.",
                  s["normal"]),
        Paragraph("1. ESPECIFICACIONES DEL SERVICIO", s["sub"]),
    ]
    esp = []
    if c.get("fecha_evento"):
        esp.append(f"<b>Fecha del evento:</b> {fecha_larga(c['fecha_evento'])}")
    if c.get("sede"):
        esp.append(f"<b>Sede de operación:</b> {t(c['sede'])}")
    esp.append(f"<b>Cobertura logística:</b> {c['horas']} horas continuas de servicio.")
    if c.get("vehiculos"):
        esp.append(f"<b>Vehículos estimados:</b> {t(c['vehiculos'])}")
    h += _vinetas(esp, s)

    h.append(Paragraph("2. ALCANCE OPERATIVO (VALOR AGREGADO INCLUIDO)", s["sub"]))
    h.append(Paragraph("Desplegamos una solución llave en mano que cubre la gestión total del flujo vehicular, la "
                       "seguridad patrimonial y la identidad corporativa:", s["normal"]))
    h.append(Paragraph("Capital Humano Especializado", s["sub2"]))
    ch = [f"{_cantidad(c['valets'])} chofer(es) operativo(s) certificado(s), rigurosamente uniformado(s) y con "
          "identificación corporativa visible."]
    if c["supervisores"]:
        ch.append(f"{_cantidad(c['supervisores'])} supervisor(es) técnico(s) en sitio, responsable(s) de coordinar la "
                  "logística de accesos, tiempos de respuesta y control de calidad del servicio.")
    h += _vinetas(ch, s)
    h.append(Paragraph("Infraestructura de Seguridad y Control", s["sub2"]))
    h += _vinetas(["Sistema de boletaje foliado y personalizado para la recepción, inventario de daños previos y "
                   "entrega de unidades.",
                   "Módulo de resguardo blindado (cajón llavero de alta seguridad) para la custodia estricta de las llaves."], s)
    h.append(Paragraph("Logística Vial y Señalización", s["sub2"]))
    h += _vinetas(["Despliegue de conos viales y vialetas tácticas para delimitar el área de Drop-off / Pick-up, "
                   "optimizando el flujo vehicular y salvaguardando la integridad de los asistentes."], s)
    if c["banners"]:
        h.append(Paragraph("Presencia de Marca", s["sub2"]))
        h += _vinetas([f"Instalación de {_cantidad(c['banners']).lower()} banner(s) institucional(es) para formalizar y "
                       "vestir elegantemente el punto de atención."], s)

    subtotal = c["tarifa_evento"]
    cobro = (f"{pesos(c['cobro_invitado'])} IVA incluido" if c["cobro_invitado"] > 0
             else "$0.00 MXN (Esquema de Cortesía)")
    filas = [["Concepto", "Inversión total"],
             [f"Tarifa global por servicio ({c['horas']} horas)", f"{pesos(subtotal)} (más IVA)"],
             ["Modalidad de cobro al invitado", cobro]]
    if c.get("hora_extra", 0) > 0:
        filas.append(["Hora adicional", f"{pesos(c['hora_extra'])} (más IVA)"])
    h += [KeepTogether([Paragraph("3. PROPUESTA ECONÓMICA", s["sub"]),
                        _tabla(filas, [9.5 * cm, 7 * cm])])]

    anticipo_pct = c["pct_anticipo"]
    notas = [f"<b>Vigencia de la propuesta:</b> Esta cotización tiene una validez de {c['vigencia']} días naturales a "
             "partir de su fecha de emisión.",
             f"<b>Condiciones de pago:</b> Se requiere un anticipo del {anticipo_pct:.0f} % "
             f"({pesos(subtotal * 1.16 * anticipo_pct / 100)} IVA incluido) para la reserva de la fecha y el "
             f"{100 - anticipo_pct:.0f} % restante liquidado al término del evento.",
             "<b>Garantía y Responsabilidad:</b> Club Park cuenta con una póliza de seguro de responsabilidad civil "
             "vigente para el resguardo de las unidades bajo nuestra custodia."]
    if c.get("notas"):
        notas.append(t(c["notas"]))
    h.append(Paragraph("Notas Comerciales y Condiciones de Contratación", s["sub2"]))
    h += _vinetas(notas, s)
    return h


def _dias_texto(dias) -> str:
    if len(dias) == 7:
        return "de lunes a domingo"
    nombres = {"Lun": "lunes", "Mar": "martes", "Mié": "miércoles", "Jue": "jueves", "Vie": "viernes",
               "Sáb": "sábado", "Dom": "domingo"}
    lista = [nombres[d] for d in dias]
    return "los días " + (", ".join(lista[:-1]) + " y " + lista[-1] if len(lista) > 1 else lista[0])


def _cantidad(n: int) -> str:
    nombres = {1: "Un (1)", 2: "Dos (2)", 3: "Tres (3)", 4: "Cuatro (4)", 5: "Cinco (5)", 6: "Seis (6)",
               7: "Siete (7)", 8: "Ocho (8)", 9: "Nueve (9)", 10: "Diez (10)"}
    return nombres.get(int(n), f"{int(n)}")


def _cuerpo_admin(v, c, s):
    cliente = v["nombre_comercial"]
    h = _encabezado_cliente(v, "PROPUESTA DE ADMINISTRACIÓN COMERCIAL Y OPERACIÓN DE ESTACIONAMIENTO", s)
    if c.get("diagnostico"):
        h += _diagnostico(v, s)
    h += [
        Paragraph("1. Modelo de Negocio y Esquema de Participación", s["sub"]),
        Paragraph("La presente propuesta plantea un modelo de administración compartida basado en resultados. El ingreso "
                  "neto mensual (ingreso bruto total por concepto de nuevas pensiones y boletaje general, menos los costos "
                  "operativos fijos descritos más adelante) se distribuirá de la siguiente manera:", s["normal"]),
    ]
    h += _vinetas([f"<b>{c['pct_propietario']:.0f} %</b> de la utilidad neta destinada en su totalidad al Propietario del "
                   "Inmueble.",
                   f"<b>{100 - c['pct_propietario']:.0f} %</b> de la utilidad neta correspondiente a Club Park por concepto "
                   "de honorarios de administración, supervisión y control operativo."], s)
    n = 2
    if c["pensiones_heredadas"]:
        h += [Paragraph(f"{n}. Régimen de Transición (Pensiones de la Administración Anterior)", s["sub"]),
              Paragraph("Con el objetivo de garantizar la continuidad operativa y una transición ordenada, las pensiones "
                        "vigentes heredadas de la gestión anterior se manejarán bajo un esquema financiero:", s["normal"])]
        h += _vinetas([f"<b>Distribución del Ingreso:</b> El ingreso bruto generado por estas pensiones preexistentes se "
                       f"distribuirá en un {c['pct_saliente']:.0f} % para la administración saliente y un "
                       f"{100 - c['pct_saliente']:.0f} % para la nueva administración (Club Park).",
                       f"<b>Destino del Recurso:</b> El {100 - c['pct_saliente']:.0f} % correspondiente a Club Park se "
                       "destinará exclusivamente a amortizar y cubrir los gastos operativos iniciales compartidos (sueldos "
                       "del personal, pólizas de seguro vigentes y la integración de los sistemas de cobro)."], s)
        n += 1

    h += [Paragraph(f"{n}. Presupuesto de Gastos Operativos Mensuales", s["sub"]),
          Paragraph("Para garantizar una operación eficiente, segura y de alta calidad, se establece la siguiente "
                    "estructura de costos fijos mensuales (valores en moneda nacional):", s["normal"])]
    filas = [["Concepto", "Importe mensual"]]
    for nombre, monto in c["gastos"]:
        filas.append([Paragraph(t(nombre), s["dato"]), pesos(monto)])
    total = sum(m for _, m in c["gastos"])
    filas.append(["Total de gastos operativos", pesos(total)])
    h.append(_tabla(filas, [11.5 * cm, 5 * cm], total=True))
    n += 1

    if c["ingreso_estimado"] > 0:
        utilidad = c["ingreso_estimado"] - total
        prop = utilidad * c["pct_propietario"] / 100
        h += [Paragraph(f"{n}. Proyección Mensual Estimada", s["sub"]),
              Paragraph("Ejemplo ilustrativo con base en el ingreso bruto estimado; las cifras reales dependerán del "
                        "comportamiento de pensiones y boletaje.", s["normal"]),
              _tabla([["Concepto", "Importe"],
                      ["Ingreso bruto estimado", pesos(c["ingreso_estimado"])],
                      ["(-) Gastos operativos", pesos(total)],
                      ["Utilidad neta", pesos(utilidad)],
                      [f"Propietario ({c['pct_propietario']:.0f} %)", pesos(prop)],
                      [f"Club Park ({100 - c['pct_propietario']:.0f} %)", pesos(utilidad - prop)]],
                     [11.5 * cm, 5 * cm])]
        n += 1

    h += [Paragraph(f"{n}. Estrategia de Crecimiento y Optimización de Ingresos", s["sub"]),
          Paragraph("Como valor agregado e incentivo comercial, Club Park asumirá de forma activa el compromiso de "
                    "incrementar la rentabilidad del inmueble mediante las siguientes líneas de acción:", s["normal"])]
    h += _vinetas(["<b>Atracción de nuevas pensiones mensuales:</b> Campañas enfocadas en residentes y trabajadores de la "
                   "zona para sustituir progresivamente el esquema de transición.",
                   "<b>Alianzas comerciales:</b> Convenios estratégicos y tarifas preferenciales con comercios, corporativos "
                   "y negocios locales colindantes para canalizar su flujo de clientes hacia el estacionamiento."], s)
    n += 1
    vig = [f"<b>Validez de la Oferta:</b> La presente propuesta mantiene una vigencia de {c['vigencia']} días naturales "
           "a partir de su fecha de emisión."]
    if c.get("notas"):
        vig.append(t(c["notas"]))
    h += [Paragraph(f"{n}. Vigencia de la Propuesta", s["sub"])] + _vinetas(vig, s)
    return h


def generar_pdf(visita: dict, tipo: str, cotiz: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=3.9 * cm, bottomMargin=2.2 * cm,
                            title=f"Propuesta {visita['nombre_comercial']}", author=EMPRESA["nombre"])
    s = _estilos()
    h = [Paragraph(f"{EMPRESA['ciudad']} a {fecha_larga(visita['fecha'])}.", s["fecha"]),
         Paragraph(f"Folio: {t(visita['folio'])}", s["folio"]),
         Spacer(1, 12)]
    if tipo == TIPO_ADMIN:
        h += _cuerpo_admin(visita, cotiz, s)
    elif tipo == TIPO_EVENTO:
        h += _cuerpo_evento(visita, cotiz, s)
    else:
        h += _cuerpo_valet(visita, cotiz, s)
    h.append(_firma(cotiz["firmante"], s))
    doc.build(h, onFirstPage=_encabezado_pie, onLaterPages=_encabezado_pie)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# INTERFAZ STREAMLIT
# ─────────────────────────────────────────────────────────────
def render():
    st.markdown("## 📋 Visita Comercial → Propuesta")
    st.caption("Llena el formato durante la visita. Al final revisa los montos y genera la propuesta en PDF.")

    if "folio_vc" not in st.session_state:
        st.session_state.folio_vc = siguiente_folio()

    # ── Encabezado
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")
    folio = c2.text_input("Folio de visita", value=st.session_state.folio_vc)
    ejecutivo = st.text_input("Ejecutivo comercial")

    # ── I. Datos generales
    with st.expander("I. Datos generales del negocio", expanded=True):
        nombre_comercial = st.text_input("Nombre comercial *", help="Así aparecerá en la propuesta. "
                                                                    "Ej. Sumo Buffet Montevideo")
        razon_social = st.text_input("Razón social")
        giro = st.selectbox("Giro del negocio", GIROS)
        giro_otro = st.text_input("¿Cuál?") if giro == "Otro" else ""
        direccion = st.text_input("Dirección (calle y número)")
        c1, c2 = st.columns(2)
        colonia = c1.text_input("Colonia")
        municipio = c2.text_input("Alcaldía / Municipio")
        c1, c2 = st.columns(2)
        cp = c1.text_input("Código postal")
        tel_negocio = c2.text_input("Teléfono del negocio")
        correo_negocio = st.text_input("Correo electrónico del negocio")
        web = st.text_input("Página web / redes sociales")

    # ── II. Contacto
    with st.expander("II. Datos del contacto", expanded=True):
        contacto = st.text_input("Nombre del responsable *")
        cargo = st.text_input("Cargo")
        c1, c2 = st.columns(2)
        tel_directo = c1.text_input("Teléfono directo")
        celular = c2.text_input("Celular (WhatsApp) *", help="10 dígitos")
        correo = st.text_input("Correo electrónico")
        horario_atencion = st.text_input("Horario de atención")

    # ── III. Estacionamiento
    with st.expander("III. Evaluación del estacionamiento", expanded=True):
        tiene_est = st.radio("¿Cuenta actualmente con estacionamiento?", ["Sí", "No"], horizontal=True)
        cajones = st.number_input("Número aproximado de cajones", min_value=0, step=1)
        tipos_est = st.multiselect("Tipo de estacionamiento", TIPOS_EST)
        flujo = st.radio("Flujo estimado de vehículos por día", FLUJOS, horizontal=True, index=1)
        horario_afluencia = st.text_input("Horario de mayor afluencia", placeholder="Ej. 14:00 a 18:00")
        obs_acceso = st.text_area("Observaciones sobre acceso vehicular")

    # ── IV. Necesidades
    with st.expander("IV. Detección de necesidades", expanded=True):
        problemas = st.multiselect("Problemas actuales detectados", PROBLEMAS)
        prob_otro = st.text_input("Otro problema")
        beneficios = st.multiselect("Beneficios de interés", BENEFICIOS)
        ben_otro = st.text_input("Otro beneficio")
    if prob_otro:
        problemas = problemas + [prob_otro]
    if ben_otro:
        beneficios = beneficios + [ben_otro]

    # ── V. Servicio
    with st.expander("V. Presentación del servicio", expanded=True):
        servicios = st.multiselect("Servicios presentados / de interés", SERVICIOS)
        serv_otro = st.text_input("Otro servicio")
    if serv_otro:
        servicios = servicios + [serv_otro]

    # ── VI y VII
    with st.expander("VI. Resultado de la visita · VII. Observaciones", expanded=True):
        interes = st.radio("Interés del prospecto", INTERES, horizontal=True)
        acciones = st.multiselect("Próxima acción", ACCIONES, default=["Enviar cotización"])
        fecha_seg = st.date_input("Fecha de seguimiento", value=None, format="DD/MM/YYYY")
        observaciones = st.text_area("Observaciones generales")

    # ── Requerimientos para la propuesta (lo que pide la propuesta formal)
    with st.expander("⭐ Requerimientos para la propuesta", expanded=True):
        st.caption("Estos datos alimentan directamente la propuesta económica.")
        servicio_req = st.radio("Servicio que requiere el cliente",
                                ["Mensual (operación continua)", "Evento", "Administración de estacionamiento",
                                 "Aún no lo define"], horizontal=True)
        dias_op = st.multiselect("Días de operación", ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
                                 default=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"])
        c1, c2 = st.columns(2)
        horario_req = c1.text_input("Horario del servicio requerido", placeholder="Ej. 13:00 a 23:00")
        choferes_req = c2.number_input("Choferes que considera necesarios (0 = no sabe)", min_value=0, step=1)
        cobro_req = st.radio("¿Cómo quiere el cobro al usuario?",
                             ["Cobro por boleto al usuario", "Cortesía (sin costo al usuario)", "No definido"],
                             horizontal=True)
        c1, c2 = st.columns(2)
        tarifa_actual = c1.number_input("Tarifa actual o deseada por boleto (IVA incluido)", min_value=0.0, step=10.0)
        presupuesto = c2.number_input("Presupuesto mensual aproximado del cliente", min_value=0.0, step=500.0)
        c1, c2 = st.columns(2)
        req_bilingue = c1.checkbox("Requiere choferes bilingües")
        req_zona = c2.checkbox("Tiene espacio para podio / zona de recepción", value=True)
        atencion_req = st.text_input("¿A quién se dirige la propuesta?", value="Dirección General / Administración",
                                     help="Aparece como 'Atención:' en la propuesta")
        if servicio_req == "Evento":
            c1, c2 = st.columns(2)
            fecha_evento_req = c1.date_input("Fecha del evento", value=None, format="DD/MM/YYYY")
            invitados_req = c2.text_input("Invitados / vehículos esperados")
        else:
            fecha_evento_req, invitados_req = None, ""

    # ── VIII. Fotos
    with st.expander("VIII. Evidencia fotográfica"):
        fotos = {}
        for etiqueta in ["Fachada", "Acceso vehicular", "Área de estacionamiento", "Con responsable"]:
            fotos[etiqueta] = st.file_uploader(etiqueta, type=["jpg", "jpeg", "png"], key=f"foto_{etiqueta}")

    # ── IX. Firmas
    with st.expander("IX. Firmas"):
        firma_resp = st.text_input("Nombre del responsable del negocio que valida la visita", value=contacto)

    st.divider()

    # ── PROPUESTA
    st.markdown("### 💰 Propuesta económica")
    mapa_req = {"Mensual (operación continua)": TIPO_VALET, "Evento": TIPO_EVENTO,
                "Administración de estacionamiento": TIPO_ADMIN}
    sugerido = mapa_req.get(servicio_req) or sugerir_tipo(giro, tiene_est, tipos_est, servicios)
    tipo = st.radio("Tipo de propuesta", TIPOS_PROPUESTA, index=TIPOS_PROPUESTA.index(sugerido))
    if tipo == sugerido:
        st.caption("Sugerido según lo que pidió el cliente o, si no lo definió, según el giro y el estacionamiento.")

    c1, c2 = st.columns(2)
    firmante = c1.selectbox("Firma la propuesta", list(FIRMANTES))
    atencion = c2.text_input("Atención a", value=atencion_req)
    saludo = st.text_input("Saludo", value="Estimados Directivos")

    valets_sug = int(choferes_req) or VALETS_POR_FLUJO.get(flujo, 2)
    if presupuesto:
        st.info(f"Presupuesto mensual que mencionó el cliente: {pesos(presupuesto)}")
    cotiz = {"firmante": firmante}

    if tipo == TIPO_VALET:
        c1, c2 = st.columns(2)
        cotiz["iguala"] = c1.number_input("Iguala mensual (más IVA)", min_value=0.0, value=12500.0, step=500.0)
        cotiz["tarifa_usuario"] = c2.number_input("Tarifa por boleto, IVA incluido (0 = cortesía)",
                                                  min_value=0.0, step=10.0,
                                                  value=0.0 if cobro_req.startswith("Cortesía") else (tarifa_actual or 100.0))
        if cotiz["tarifa_usuario"] > 0:
            cotiz["recauda_clubpark"] = st.checkbox("Aclarar que el cobro del boleto lo recibe Club Park", value=False)
        c1, c2 = st.columns(2)
        cotiz["valets"] = c1.number_input("Valets asignados (0 = no mencionar)", min_value=0,
                                          value=int(choferes_req), step=1,
                                          help=f"Según el flujo diario se sugieren {VALETS_POR_FLUJO.get(flujo, 2)}")
        cotiz["horario"] = c2.text_input("Horario del servicio", value=horario_req or horario_afluencia)
        cotiz["dias"] = dias_op
        cotiz["infraestructura"] = st.multiselect("Infraestructura incluida", list(INFRA_VALET),
                                                  default=INFRA_VALET_DEFAULT + (["Choferes bilingües"] if req_bilingue else []))
        cotiz["proteccion"] = st.multiselect("Protección y seguros", list(PROTECCION_VALET), default=PROTECCION_DEFAULT)
        with st.expander("Suma asegurada (opcional)"):
            c1, c2 = st.columns(2)
            cotiz["cobertura"] = c1.number_input("Cobertura global (0 = no mencionar)", min_value=0.0, value=0.0,
                                                 step=100_000.0)
            cotiz["sublimite"] = c2.number_input("Sublímite por vehículo", min_value=0.0, value=0.0, step=50_000.0)
        cotiz["capital_humano"] = st.checkbox("Incluir sección de Capital Humano (filtros, capacitación, coordinador)",
                                              value=False)
        c1, c2 = st.columns(2)
        cotiz["vigencia"] = c1.number_input("Vigencia (días)", min_value=1, value=30)
        cotiz["dias_implementacion"] = c2.number_input("Días hábiles de implementación", min_value=1, value=5)
        st.caption(f"Iguala en letra: {numero_a_letras(cotiz['iguala'])}")

    elif tipo == TIPO_EVENTO:
        cotiz["fecha_evento"] = st.date_input("Fecha del evento", value=fecha_evento_req, format="DD/MM/YYYY")
        sede_def = ", ".join(x for x in [nombre_comercial, direccion, colonia, municipio,
                                         f"C.P. {cp}" if cp else ""] if x)
        cotiz["sede"] = st.text_input("Sede de operación", value=sede_def)
        c1, c2, c3 = st.columns(3)
        cotiz["horas"] = c1.number_input("Horas", min_value=1, value=5)
        cotiz["valets"] = c2.number_input("Choferes", min_value=1, value=valets_sug, step=1)
        cotiz["supervisores"] = c3.number_input("Supervisores", min_value=0, value=1, step=1)
        c1, c2 = st.columns(2)
        cotiz["banners"] = c1.number_input("Banners", min_value=0, value=1, step=1)
        cotiz["vehiculos"] = c2.text_input("Vehículos estimados (opcional)", value=invitados_req)
        c1, c2 = st.columns(2)
        cotiz["tarifa_evento"] = c1.number_input("Tarifa global (más IVA)", min_value=0.0, value=6500.0, step=500.0)
        cotiz["cobro_invitado"] = c2.number_input("Cobro al invitado, IVA incluido (0 = cortesía)",
                                                  min_value=0.0, step=10.0,
                                                  value=tarifa_actual if cobro_req.startswith("Cobro") else 0.0)
        c1, c2 = st.columns(2)
        cotiz["hora_extra"] = c1.number_input("Hora adicional (0 = no mencionar)", min_value=0.0, value=0.0, step=100.0)
        cotiz["pct_anticipo"] = c2.number_input("% de anticipo", min_value=0, max_value=100, value=50)
        cotiz["vigencia"] = st.number_input("Vigencia (días)", min_value=1, value=7)

    else:  # Administración
        c1, c2 = st.columns(2)
        valets = c1.number_input("Elementos de valet", min_value=1, value=6, step=1)
        costo_valet = c2.number_input("Costo mensual por elemento", min_value=0.0, value=12000.0, step=500.0)
        seguro = st.number_input("Póliza de seguro de responsabilidad civil", min_value=0.0, value=2600.0, step=100.0)
        papeleria = st.number_input("Insumos y papelería (boletaje, folletos)", min_value=0.0, value=2000.0, step=100.0)
        limpieza = st.number_input("Mantenimiento y limpieza", min_value=0.0, value=1500.0, step=100.0)
        tecnologia = st.number_input("Infraestructura y tecnología (control de accesos, software, terminales)",
                                     min_value=0.0, value=0.0, step=100.0)
        if tecnologia == 0:
            st.warning("Infraestructura y tecnología está en $0. Si tiene costo, captúralo antes de generar.")
        cotiz["gastos"] = [
            (f"Capital Humano: {_cantidad(valets)} elementos profesionales de valet parking (sueldo base y "
             "prestaciones de ley)", valets * costo_valet),
            ("Seguridad y Cobertura: póliza de responsabilidad civil y daños a terceros", seguro),
            ("Insumos y Papelería: boletaje controlado, folletos y material administrativo", papeleria),
            ("Mantenimiento y Limpieza: suministros y servicios de limpieza del área", limpieza),
        ]
        if tecnologia > 0:
            cotiz["gastos"].append(("Infraestructura y Tecnología: control de accesos, software de boletaje en la nube "
                                    "y mantenimiento de terminales", tecnologia))
        cotiz["pct_propietario"] = st.slider("% de utilidad para el propietario", 50, 95, 80)
        cotiz["pensiones_heredadas"] = st.checkbox("Hay pensiones heredadas de la administración anterior")
        cotiz["pct_saliente"] = st.slider("% para la administración saliente", 0, 100, 60) \
            if cotiz["pensiones_heredadas"] else 60
        cotiz["ingreso_estimado"] = st.number_input("Ingreso bruto mensual estimado (opcional, para proyección)",
                                                    min_value=0.0, value=0.0, step=1000.0)
        cotiz["vigencia"] = st.number_input("Vigencia (días)", min_value=1, value=30)
        st.metric("Gastos operativos mensuales", pesos(sum(m for _, m in cotiz["gastos"])))

    if tipo != TIPO_EVENTO:
        cotiz["diagnostico"] = st.checkbox("Incluir párrafo con lo detectado en la visita (problemas y beneficios)",
                                           value=True)
    cotiz["notas"] = st.text_area("Condición o nota adicional (opcional)")

    # ── Generar
    if st.button("📄 Generar propuesta", type="primary", use_container_width=True):
        faltan = [n for n, val in [("Nombre comercial", nombre_comercial), ("Responsable", contacto)]
                  if not val.strip()]
        if faltan:
            st.error("Falta: " + ", ".join(faltan))
            return
        visita = dict(
            fecha=fecha, folio=folio, ejecutivo=ejecutivo, nombre_comercial=nombre_comercial.strip(),
            razon_social=razon_social, giro=giro_otro or giro, direccion=direccion, colonia=colonia,
            municipio=municipio, cp=cp, telefono=tel_negocio, correo_negocio=correo_negocio, web=web,
            contacto=contacto.strip(), cargo=cargo, tel_directo=tel_directo, celular=celular, correo=correo,
            horario_atencion=horario_atencion, tiene_est=tiene_est, cajones=cajones, tipos_est=tipos_est,
            flujo=flujo, horario_afluencia=horario_afluencia, obs_acceso=obs_acceso, problemas=problemas,
            beneficios=beneficios, servicios=servicios, interes=interes, acciones=acciones,
            fecha_seguimiento=fecha_seg, observaciones=observaciones, firma_responsable=firma_resp,
            atencion=atencion, saludo=saludo, servicio_requerido=servicio_req, dias_operacion=dias_op,
            horario_requerido=horario_req, choferes_requeridos=choferes_req, cobro_requerido=cobro_req,
            tarifa_actual=tarifa_actual, presupuesto_cliente=presupuesto, requiere_bilingue=req_bilingue,
            zona_recepcion=req_zona, fecha_evento=fecha_evento_req, invitados=invitados_req,
        )
        pdf = generar_pdf(visita, tipo, cotiz)
        st.session_state.pdf_vc = pdf
        st.session_state.pdf_nombre = (f"PROPUESTA ECONÓMICA {nombre_comercial.strip().upper()}.pdf")
        st.session_state.wa_vc = (celular, nombre_comercial.strip(), contacto.strip())

        registro = {k: (", ".join(v) if isinstance(v, list) else v) for k, v in visita.items()}
        registro.update(tipo_propuesta=tipo, firmante=firmante,
                        monto_principal=cotiz.get("iguala") or cotiz.get("tarifa_evento")
                        or sum(m for _, m in cotiz.get("gastos", [])),
                        tarifa_usuario=cotiz.get("tarifa_usuario", cotiz.get("cobro_invitado", "")),
                        fotos=", ".join(k for k, f in fotos.items() if f),
                        registrado=datetime.now().strftime("%Y-%m-%d %H:%M"))
        try:
            guardar_visita(registro)
        except (OSError, ValueError):
            st.warning("No se pudo guardar el registro de la visita, pero la propuesta sí se generó.")
        st.session_state.folio_vc = siguiente_folio()
        st.success("Propuesta generada ✅")

    if st.session_state.get("pdf_vc"):
        st.download_button("⬇️ Descargar PDF", st.session_state.pdf_vc, st.session_state.pdf_nombre,
                           mime="application/pdf", use_container_width=True)
        cel, negocio, nombre = st.session_state.wa_vc
        numero = "".join(ch for ch in cel if ch.isdigit())
        if numero:
            if len(numero) == 10:
                numero = "52" + numero
            msg = (f"Hola {nombre}, le comparto la propuesta económica de Club Park Valet y Estacionamientos "
                   f"para {negocio}. Quedamos atentos a cualquier duda. ¡Gracias por su tiempo!")
            st.link_button("💬 Abrir WhatsApp del cliente",
                           f"https://wa.me/{numero}?text={urllib.parse.quote(msg)}", use_container_width=True)
            st.caption("WhatsApp se abre con el mensaje listo; adjunta el PDF que descargaste.")

    # ── Historial
    if os.path.exists(ARCHIVO_VISITAS):
        with st.expander("📚 Historial de visitas"):
            import pandas as pd
            df = pd.read_csv(ARCHIVO_VISITAS, on_bad_lines="skip")
            cols = [c for c in ["folio", "fecha", "nombre_comercial", "giro", "interes", "tipo_propuesta",
                                "monto_principal", "firmante"] if c in df.columns]
            st.dataframe(df[cols].iloc[::-1], use_container_width=True, hide_index=True)
            xls = io.BytesIO()
            df.to_excel(xls, index=False, sheet_name="Visitas")
            st.download_button("⬇️ Descargar historial en Excel", xls.getvalue(), "visitas_comerciales.xlsx")


if __name__ == "__main__":
    st.set_page_config(page_title="Club Park · Visita Comercial", page_icon="🚗", layout="centered")
    render()
