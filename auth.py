
# -*- coding: utf-8 -*-
"""Credenciales y lector QR compartidos (copiados de la app de valet para que el login sea único)."""
import json
import os
import streamlit as st
from PIL import Image, ImageOps

try:
    import qrcode  # noqa: F401
except ImportError:
    qrcode = None


def secreto(nombre, defecto=""):
    """Variable de entorno primero (Render/Railway/Fly) y luego st.secrets."""
    v = os.environ.get(nombre)
    if v:
        return v
    try:
        if nombre in st.secrets:
            return str(st.secrets[nombre])
    except Exception:
        pass
    return defecto


TOKENS_POR_DEFECTO = {
    "CPV-GLOBAL-AUDITOR-2026": {
        "nombre": "Víctor (Contador)",
        "sucursal": "TODAS",
        "rol": "Contador Auditor (Máxima Jerarquía)",
    },
    "CPV-GLOBAL-JESUS-2026": {
        "nombre": "José de Jesús",
        "sucursal": "TODAS",
        "rol": "Supervisor Global",
    },
    "CPV-GLOBAL-VICTOR-2026": {
        "nombre": "Víctor Manuel",
        "sucursal": "TODAS",
        "rol": "Supervisor Global",
    },
    "CPV-QR-PAMPAS-INS": {"nombre": "Encargado Pampas Ins.", "sucursal": "PAMPAS INSURGENTES", "rol": "Supervisor de Sucursal"},
    "CPV-QR-PAMPAS-COAPA": {"nombre": "Encargado Pampas Coapa", "sucursal": "PAMPAS COAPA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-RAMMA": {"nombre": "Encargado Ramma", "sucursal": "RAMMA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-SUSHITTO": {"nombre": "Encargado Sushitto", "sucursal": "SUSHITTO", "rol": "Supervisor de Sucursal"},
    "CPV-QR-CARAJILLO": {"nombre": "Encargado Carajillo", "sucursal": "CARAJILLO POLANCO", "rol": "Supervisor de Sucursal"},
    "CPV-QR-BENINGANS": {"nombre": "Encargado Beningan's", "sucursal": "BENINGAN´S", "rol": "Supervisor de Sucursal"},
    "CPV-QR-DURANGO": {"nombre": "Encargado Sanatorio Durango", "sucursal": "SANATORIO DURANGO", "rol": "Supervisor de Sucursal"},
    "CPV-QR-BARRANCA": {"nombre": "Encargado Barranca", "sucursal": "BARRANCA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-VETERINARIA": {"nombre": "Encargado Veterinaria", "sucursal": "VETERINARIA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-ROMANCE": {"nombre": "Encargado Romance", "sucursal": "ROMANCE PALACE", "rol": "Supervisor de Sucursal"},
    "CPV-QR-TLALPAN": {"nombre": "Encargado Jungla Tlalpan", "sucursal": "JUNGLA TLALPAN", "rol": "Supervisor de Sucursal"},
    "CPV-QR-DIVISION": {"nombre": "Encargado Jungla División", "sucursal": "JUNGLA DIVISIÓN", "rol": "Supervisor de Sucursal"},
    "CPV-QR-PICACHO": {"nombre": "Encargado Jungla Picacho", "sucursal": "JUNGLA PICACHO", "rol": "Supervisor de Sucursal"},
    "CPV-QR-EMPRESA": {"nombre": "Encargado Jungla Empresa", "sucursal": "JUNGLA EMPRESA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-SIPIRILY": {"nombre": "Encargado Sipirily", "sucursal": "SIPIRILY COAPA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-SATELITE": {"nombre": "Encargado Marometa Satélite", "sucursal": "MAROMETA SATÉLITE", "rol": "Supervisor de Sucursal"},
    "CPV-QR-MARINA": {"nombre": "Encargado Marometa Marina", "sucursal": "MAROMETA MARINA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-SUMOSTA": {"nombre": "Encargado Sumo Santa Mónica", "sucursal": "SUMO STA. MONICA", "rol": "Supervisor de Sucursal"},
    "CPV-QR-CHEGARAY": {"nombre": "Encargado Sumo Echegaray", "sucursal": "SUMO ECHEGARAY", "rol": "Supervisor de Sucursal"},
    "CPV-QR-RYOSHI": {"nombre": "Encargado Ryoshi", "sucursal": "RYOSHI", "rol": "Supervisor de Sucursal"},
    "CPV-QR-ENCANTO": {"nombre": "Encargado Encanto", "sucursal": "ENCANTO", "rol": "Supervisor de Sucursal"},
    "CPV-QR-EBNI": {"nombre": "Encargado E-BNI", "sucursal": "E-BNI", "rol": "Supervisor de Sucursal"},
    "CPV-QR-CHURRAS": {"nombre": "Encargado Churrasquería", "sucursal": "CHURRASQUERIA", "rol": "Supervisor de Sucursal"},
}
# ---------------------------------------------------------------------
# CARGA PROTEGIDA DE CREDENCIALES QR
# Prioridad: 1) st.secrets  2) variable de entorno CLUBPARK_TOKENS_JSON
# 3) tokens por defecto del código (solo contingencia; la app avisa en
# pantalla para moverlos a st.secrets lo antes posible).
# ---------------------------------------------------------------------
def cargar_accesos_protegidos():
    fuente = "por_defecto"
    accesos = None
    try:
        if "CLUBPARK_TOKENS_JSON" in st.secrets:
            accesos = json.loads(str(st.secrets["CLUBPARK_TOKENS_JSON"]))
            fuente = "secrets"
        elif "CLUBPARK_TOKENS" in st.secrets:
            accesos = {clave: dict(valor) for clave, valor in st.secrets["CLUBPARK_TOKENS"].items()}
            fuente = "secrets"
    except Exception:
        accesos = None
    if not accesos:
        tokens_env = os.environ.get("CLUBPARK_TOKENS_JSON", "").strip()
        if tokens_env:
            try:
                accesos = json.loads(tokens_env)
                fuente = "entorno"
            except json.JSONDecodeError:
                print("CLUBPARK_TOKENS_JSON no contiene JSON válido; se ignoró.")
                accesos = None
    if not (isinstance(accesos, dict) and accesos):
        accesos = dict(TOKENS_POR_DEFECTO)
        fuente = "por_defecto"
    return accesos, fuente


ACCESOS, ACCESOS_FUENTE = cargar_accesos_protegidos()

try:
    APP_URL = str(st.secrets.get("CLUBPARK_APP_URL", "") or os.environ.get("CLUBPARK_APP_URL", "")).strip()
except Exception:
    APP_URL = str(os.environ.get("CLUBPARK_APP_URL", "")).strip()


def contenido_qr_para(token):
    """Contenido del QR de la credencial: si se configura CLUBPARK_APP_URL el QR
    abre la app con la sesión lista al escanearlo con la cámara del teléfono."""
    if APP_URL:
        separador = "&" if "?" in APP_URL else "?"
        return f"{APP_URL}{separador}qrscan={token}"
    return token



def leer_codigo_qr(imagen_pil):
    """Lector de QR robusto: prepara la imagen (contraste, ampliacion, binarizacion,
    inversiones y rotaciones) y prueba tres decodificadores antes de rendirse."""
    if imagen_pil is None:
        return None
    if not isinstance(imagen_pil, Image.Image):
        try:
            imagen_pil = Image.open(imagen_pil)
        except Exception:
            return None
    try:
        base = ImageOps.exif_transpose(imagen_pil).convert("RGB")
    except Exception:
        base = imagen_pil.convert("RGB")

    candidatos = [base]
    try:
        gris = ImageOps.autocontrast(base.convert("L"))
        ancho, alto = gris.size
        if max(ancho, alto) < 1100:
            factor = max(2, int(1100 / max(ancho, alto)))
            candidatos.append(gris.resize((ancho * factor, alto * factor), Image.LANCZOS))
        candidatos.append(gris)
        candidatos.append(ImageOps.invert(gris))
        candidatos.append(ImageOps.autocontrast(base))
        try:
            import cv2
            import numpy as np
            arr = np.array(gris)
            _, otsu = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            candidatos.append(Image.fromarray(otsu))
            candidatos.append(Image.fromarray(cv2.adaptiveThreshold(
                arr, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 2)))
        except Exception:
            pass
    except Exception:
        pass

    def _texto_de(resultados):
        for r in resultados or []:
            texto = getattr(r, "text", None)
            if texto is None:
                datos = getattr(r, "data", None)
                if isinstance(datos, bytes):
                    texto = datos.decode("utf-8", "replace")
                else:
                    texto = str(datos or "")
            if str(texto).strip():
                return str(texto).strip()
        return None

    # 1) zxing-cpp con TRY_HARDER y rotaciones
    try:
        import zxingcpp
        for imagen in candidatos:
            try:
                hallado = _texto_de(zxingcpp.read_barcodes(imagen, try_harder=True, try_rotate=True))
                if hallado:
                    return hallado
            except Exception:
                pass
    except Exception:
        pass

    # 2) pyzbar con rotaciones manuales
    try:
        from pyzbar.pyzbar import decode
        for imagen in candidatos:
            for angulo in (0, 90, 180, 270):
                prueba = imagen if angulo == 0 else imagen.rotate(angulo, expand=True)
                try:
                    hallado = _texto_de(decode(prueba))
                    if hallado:
                        return hallado
                except Exception:
                    pass
    except Exception:
        pass

    # 3) detector de OpenCV
    try:
        import cv2
        import numpy as np
        detector = cv2.QRCodeDetector()
        for imagen in candidatos:
            arr = cv2.cvtColor(np.array(imagen), cv2.COLOR_RGB2BGR)
            for angulo in (0, 90, 180, 270):
                prueba = arr if angulo == 0 else np.rot90(arr, angulo // 90)
                try:
                    valor, _, _ = detector.detectAndDecode(prueba)
                    if valor and valor.strip():
                        return valor.strip()
                except Exception:
                    pass
    except Exception:
        pass
    return None

def lector_qr_camara_trasera(key="lector_qr_trasero", height=390):
    """Lectura de QR con la cámara del dispositivo, sin componentes externos.
    Usa el lector robusto (preprocesamiento + 3 decodificadores) sobre la captura."""
    foto_qr = st.camera_input(
        "Capturar el código QR", key=key,
        help="La app pide permiso de cámara y abre la del teléfono. Si no abre o abre la frontal, usa «Subir foto del código QR»: al elegir Cámara en el selector de Android se usa la cámara trasera. Enfoca el QR a 10-15 cm con buena luz.",
    )
    if foto_qr is None:
        st.caption("¿La cámara no abre en tu navegador? Sube una fotografía del código QR.")
        subida = st.file_uploader("Subir foto del código QR", type=["png", "jpg", "jpeg"], key=f"{key}_subida")
        if subida is not None:
            try:
                token = leer_codigo_qr(Image.open(subida))
                return str(token).strip() if token else None
            except Exception:
                return None
        return None
    try:
        token = leer_codigo_qr(Image.open(foto_qr))
        return str(token).strip() if token else None
    except Exception:
        st.warning("No se pudo leer el QR. Acércate, mejora la luz y vuelve a tomar la foto.")
        return None
