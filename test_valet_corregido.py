# -*- coding: utf-8 -*-
"""
Pruebas automatizadas para valet_corregido.py (Club Park).

Se ejecutan con pytest (pytest test_valet_corregido.py) o directamente:
    python3 test_valet_corregido.py
(ajusta la ruta del archivo con la variable de entorno VALET_PY si hace falta).

Cubre:
  1. Que no existan tokens de acceso fijos en el código (retiro de TOKENS_POR_DEFECTO).
  2. Que la app se bloquee con aviso si no hay ninguna fuente de credenciales.
  3. Que importes inválidos o vacíos no rompan construir_reporte.
  4. Que construir_comparativo deduplique sucursales repetidas sin fallar.
  5. Que la detección de pagos duplicados revise TODO el libro, no solo los últimos 500.
  6. Que un cobro sin conexión de un folio de otra sucursal se rechace (bug Sipirily/Ryoshi).
  7. Que el resguardo enviado al celular y la app sin conexión embebida queden aislados por sucursal.
"""
import base64
import datetime
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

RUTA_VALET = Path(os.environ.get("VALET_PY", Path(__file__).with_name("valet_corregido.py")))
FUENTE = RUTA_VALET.read_text(encoding="utf-8")

NOMBRES_DIA = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]


def extraer(nombre):
    """Extrae el bloque de una función de nivel superior del archivo valet."""
    m = re.search(rf"^def {re.escape(nombre)}\(.*$", FUENTE, flags=re.M)
    assert m, f"No se encontró la función {nombre} en {RUTA_VALET.name}"
    lineas = [m.group(0)]
    for linea in FUENTE[m.end() + 1:].splitlines():
        if linea.strip() and not linea[0].isspace() and not linea.startswith(")"):
            break
        lineas.append(linea)
    return "\n".join(lineas)


def cargar(funciones, **globales):
    """Ejecuta las funciones extraídas en un namespace con los apoyos indicados."""
    g = {"pd": pd, "datetime": datetime}
    g.update(globales)
    for f in funciones:
        exec(extraer(f), g)
    return g


# ---------------------------------------------------------------------
# 1. Sin tokens fijos en el código
# ---------------------------------------------------------------------
def test_no_hay_tokens_por_defecto_en_el_codigo():
    assert "TOKENS_POR_DEFECTO" not in FUENTE, "El diccionario de tokens fijos sigue en el código"
    assert "CPV-GLOBAL-" not in FUENTE, "Queda un token global escrito en el código"
    claves = re.findall(r'"(CPV-[A-Z0-9\-]+)":\s*\{', FUENTE)
    assert not claves, f"Credenciales fijas en el código: {claves}"


def test_sin_credenciales_la_app_arranca_bloqueada_con_aviso():
    tmp = tempfile.mkdtemp()
    avisos = []
    st = SimpleNamespace(secrets={}, warning=lambda m: avisos.append(m), error=lambda m: avisos.append(m))
    g = cargar(["cargar_accesos_protegidos"], st=st, os=os, json=__import__("json"),
               CREDENCIALES_FILE=Path(tmp) / "credenciales_qr.json")
    os.environ.pop("CLUBPARK_TOKENS_JSON", None)
    accesos, fuente = g["cargar_accesos_protegidos"]()
    assert accesos == {} and fuente == "sin_credenciales"
    assert any("CLUBPARK_TOKENS_JSON" in a for a in avisos), "El aviso no explica cómo configurar las credenciales"


def test_con_secrets_carga_las_credenciales():
    import json
    tmp = tempfile.mkdtemp()
    json_cred = json.dumps({"CPV-TEST-UNO": {"nombre": "Prueba", "sucursal": "X", "rol": "Líder de Sucursal"}})
    st = SimpleNamespace(secrets={"CLUBPARK_TOKENS_JSON": json_cred}, warning=lambda m: None, error=lambda m: None)
    g = cargar(["cargar_accesos_protegidos"], st=st, os=os, json=json,
               CREDENCIALES_FILE=Path(tmp) / "credenciales_qr.json")
    accesos, fuente = g["cargar_accesos_protegidos"]()
    assert fuente == "secrets" and "CPV-TEST-UNO" in accesos


# ---------------------------------------------------------------------
# 2. Importes inválidos no rompen el reporte
# ---------------------------------------------------------------------
def _fecha_flexible_prueba(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(v).strip(), formato).date()
        except ValueError:
            pass
    return None


def test_importes_invalidos_no_rompen_construir_reporte():
    filas = [
        # fila normal
        {"Sitio / Unidad": "SIPIRILY COAPA", "Fecha": "01/11/2026", "Ingreso Bruto": 250.0, "Total Gastos": 80.0},
        # vacíos y no numéricos: antes provocaban ValueError y tumbaban la sección
        {"Sitio / Unidad": "SIPIRILY COAPA", "Fecha": "01/11/2026", "Ingreso Bruto": "", "Total Gastos": None},
        {"Sitio / Unidad": "SIPIRILY COAPA", "Fecha": "01/11/2026", "Ingreso Bruto": "N/D", "Total Gastos": "—"},
        {"Sitio / Unidad": "RYOSHI", "Fecha": "02/11/2026", "Ingreso Bruto": 100.5, "Total Gastos": "sin dato"},
        # claves ausentes por completo
        {"Sitio / Unidad": "RYOSHI", "Fecha": "02/11/2026"},
    ]
    g = cargar(["construir_reporte", "_flotante_seguro"],
               registros_flujo_periodo=lambda *a, **k: filas,
               fecha_flexible=_fecha_flexible_prueba,
               NOMBRES_DIA=NOMBRES_DIA,
               dinero=lambda v: float(v or 0),
               _leer_lista_json=lambda ruta: [],
               GASTOS_FILE_RF="gastos_operativos.json",
               timedelta=datetime.timedelta)
    rep = g["construir_reporte"](datetime.date(2026, 11, 1), datetime.date(2026, 11, 2), ["SIPIRILY COAPA", "RYOSHI"])
    assert abs(rep["ventas_total"] - 350.5) < 0.01, rep["ventas_total"]
    assert abs(rep["gastos_total"] - 80.0) < 0.01, rep["gastos_total"]
    resumen = rep["resumen"]
    sip = resumen[resumen["Sucursal"] == "SIPIRILY COAPA"].iloc[0]
    assert abs(sip["Ventas"] - 250.0) < 0.01 and abs(sip["Gastos"] - 80.0) < 0.01


# ---------------------------------------------------------------------
# 3. Sucursales duplicadas se deduplican en el comparativo
# ---------------------------------------------------------------------
def _rep_con_sucursales(filas, dias=2):
    return {"resumen_total": pd.DataFrame(filas, columns=["Sucursal", "Ventas", "Gastos", "Utilidad"]),
            "utilidad_diaria": pd.DataFrame(
                [{"Fecha": f"0{i}/11/2026", "Día": NOMBRES_DIA[i], "Ventas": 10.0 + i, "Gastos": 1.0,
                  "Utilidad": 9.0 + i, "Utilidad acumulada": 9.0 + i} for i in range(dias)])}


def test_sucursales_duplicadas_se_deduplican_en_comparativo():
    # La misma sucursal aparece dos veces (dato repetido): antes .loc devolvía una serie y float() fallaba
    actual = _rep_con_sucursales([
        {"Sucursal": "RYOSHI", "Ventas": 100.0, "Gastos": 20.0, "Utilidad": 80.0},
        {"Sucursal": "RYOSHI", "Ventas": 999.0, "Gastos": 1.0, "Utilidad": 998.0},
        {"Sucursal": "SIPIRILY COAPA", "Ventas": 300.0, "Gastos": 60.0, "Utilidad": 240.0},
    ])
    anterior = _rep_con_sucursales([{"Sucursal": "RYOSHI", "Ventas": 90.0, "Gastos": 10.0, "Utilidad": 80.0}])
    g = cargar(["construir_comparativo", "_variacion_pct"])
    comp = g["construir_comparativo"](actual, anterior)
    resumen = comp["resumen"].set_index("Sucursal")
    assert len(resumen) == 2, resumen.index.tolist()
    assert abs(resumen.loc["RYOSHI", "Ventas actual"] - 100.0) < 0.01  # se conserva la primera aparición
    assert abs(resumen.loc["RYOSHI", "Ventas anterior"] - 90.0) < 0.01
    assert resumen.loc["SIPIRILY COAPA", "Ventas anterior"] == 0.0  # no estaba en el periodo anterior
    assert len(comp["diario"]) == 2


# ---------------------------------------------------------------------
# 4. Pagos duplicados: revisión de todo el libro
# ---------------------------------------------------------------------
def test_pago_duplicado_se_detecta_en_todo_el_libro():
    escrituras, llamadas = [], []
    libro = [{"id_pago": f"ANTIGUO-{i}"} for i in range(800)]
    libro.append({"id_pago": "P-DUPLICADO"})  # índice 800: fuera de la ventana vieja de 500

    g = cargar(["guardar_pago_respaldo"],
               cargar_pagos_respaldo=lambda: list(libro),
               _candado_bd=contextmanager(lambda: (yield)),
               _rotar_a_archivo_mensual=lambda pagos, n, pref, campo: pagos,
               _escribir_json_seguro=lambda ruta, datos, compacto=False: escrituras.append(list(datos)),
               PAYMENTS_FILE="pagos.json",
               st=SimpleNamespace(error=lambda *a, **k: llamadas.append(a)))
    assert g["guardar_pago_respaldo"]({"id_pago": "P-DUPLICADO"}, {"id": "F-1"}) is True
    assert len(libro) == 801 and not escrituras, "El pago duplicado no debe insertarse ni reescribir el libro"

    assert g["guardar_pago_respaldo"]({"id_pago": "P-NUEVO"}, {"id": "F-2"}) is True
    assert len(escrituras) == 1 and escrituras[0][0]["id_pago"] == "P-NUEVO"


# ---------------------------------------------------------------------
# 5. Bug Sipirily/Ryoshi: cobro sin conexión de otra sucursal se rechaza
# ---------------------------------------------------------------------
def _entorno_salida_offline():
    incidencias = []
    reg_ryoshi = {"id": "CP-RYO-000002", "sucursal": "RYOSHI", "estado": "En Resguardo",
                  "tarifa": 80.0, "modalidad_tarifa": "fija", "pagos": []}
    st = SimpleNamespace(session_state={})
    g = cargar(["_procesar_salida_offline"],
               codigo_sucursal=lambda s: {"RYOSHI": "RYO", "SIPIRILY COAPA": "SIP"}[s],
               cargar_bd_rapido=lambda: [reg_ryoshi],
               tarifa_de=lambda s: {},
               minutos_estancia=lambda r, m: 1765,
               calcular_cobro=lambda *a, **k: 80.0,
               crear_ticket=lambda r: "TICKET",
               ahora_mx=lambda: datetime.datetime(2026, 11, 1, 16, 40),
               METODO_SELLADO="Sellado",
               _incidencia_offline=lambda tipo, item, detalle: incidencias.append((tipo, detalle)),
               fecha_operativa_actual=lambda s: datetime.date(2026, 11, 1),
               st=st, datetime=datetime.datetime)
    return g, incidencias


def _item_salida(uid, folio):
    return {"uid": uid, "tipo": "salida", "folio": folio,
            "pago": {"importe": 80.0, "importe_calculado": 80.0, "metodo": "Efectivo",
                     "fecha_hora": "2026-11-01 16:40:00", "fecha_hora_iso": "2026-11-01T16:40:00",
                     "modalidad_tarifa": "fija", "usuario": "Líder Sipirily"}}


def test_cobro_sin_conexion_de_otra_sucursal_se_rechaza():
    g, incidencias = _entorno_salida_offline()
    ctx = {"regs": {}, "pagos": [], "eventos": [], "incid": []}
    res = g["_procesar_salida_offline"](_item_salida("UID1", "CP-RYO-000002"),
                                        "SIPIRILY COAPA", "D708A6783", 1, ctx)
    assert res == "hecho", "El cobro de otra sucursal no debe quedar pendiente de aplicar"
    assert any(t == "COBRO DE OTRA SUCURSAL" for t, _ in incidencias), incidencias
    assert not ctx["pagos"], "No debe registrarse ningún pago"


def test_cobro_sin_conexion_de_mi_sucursal_se_aplica():
    g, incidencias = _entorno_salida_offline()
    registro = {"id": "CP-SIP-000001", "sucursal": "SIPIRILY COAPA", "estado": "En Resguardo",
                "tarifa": 80.0, "modalidad_tarifa": "fija", "pagos": []}
    ctx = {"regs": {"CP-SIP-000001": registro}, "pagos": [], "eventos": [], "incid": []}
    res = g["_procesar_salida_offline"](_item_salida("UID2", "CP-SIP-000001"),
                                        "SIPIRILY COAPA", "D708A6783", 1, ctx)
    assert res == "pendiente" and registro["estado"] == "Entregado"
    assert registro["pagos"][0]["sucursal"] == "SIPIRILY COAPA"
    assert not incidencias


# ---------------------------------------------------------------------
# 6. Resguardo y app del celular aislados por sucursal
# ---------------------------------------------------------------------
def test_resguardo_offline_solo_trae_mi_sucursal():
    bd = [
        {"id": "CP-SIP-000001", "sucursal": "SIPIRILY COAPA", "estado": "En Resguardo"},
        {"id": "CP-RYO-000002", "sucursal": "RYOSHI", "estado": "En Resguardo"},
        {"id": "CP-SIP-000003", "sucursal": "SIPIRILY COAPA", "estado": "Entregado"},
    ]
    g = cargar(["_resguardo_offline"], cargar_bd_rapido=lambda: bd)
    lista = g["_resguardo_offline"]("SIPIRILY COAPA")
    assert [r["id"] for r in lista] == ["CP-SIP-000001"]


def test_app_offline_embebida_aisla_por_sucursal():
    """La app.html embebida en _ARCHIVOS_OFFLINE debe filtrar el resguardo por sucursal."""
    bloque = FUENTE[FUENTE.index("_ARCHIVOS_OFFLINE = {"): FUENTE.index("def _carpeta_offline")]
    m = re.search(r"'app\.html':\s*\((.*?)\)\s*,", bloque, flags=re.S)
    assert m, "No se encontró app.html en _ARCHIVOS_OFFLINE"
    html = base64.b64decode("".join(re.findall(r"'([A-Za-z0-9+/=]+)'", m.group(1)))).decode("utf-8")
    assert "deMiSucursal" in html, "enResguardo() no filtra por sucursal"
    assert html.count("conf.sucursal") >= 3, "Faltan los filtros de sucursal en la app del celular"
    assert "solo se cobran vehículos de" in html, "Falta el aviso al cobrar un folio de otra sucursal"


if __name__ == "__main__":
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallidas = 0
    for prueba in pruebas:
        try:
            prueba()
            print(f"✅ {prueba.__name__}")
        except AssertionError as exc:
            fallidas += 1
            print(f"❌ {prueba.__name__}: {exc}")
    print(f"\n{len(pruebas) - fallidas}/{len(pruebas)} pruebas pasaron sobre {RUTA_VALET.name}")
    raise SystemExit(1 if fallidas else 0)
