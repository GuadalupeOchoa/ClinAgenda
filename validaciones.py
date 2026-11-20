"""Validaciones y normalización de datos. Cada función devuelve un mensaje
de error entendible para una persona (o None si el dato está bien)."""
import re
import unicodedata
from datetime import date

EDAD_MAXIMA = 120


def limpiar_texto(valor, max_len=200):
    """Quita espacios extra y caracteres de control/emojis raros."""
    if valor is None:
        return ""
    valor = "".join(c for c in str(valor) if unicodedata.category(c)[0] != "C"
                    and unicodedata.category(c) != "So")
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor[:max_len]


def normalizar_nombre(valor):
    """'  MARÍA   lópez ' -> 'María López'."""
    return limpiar_texto(valor, 100).title()


def clave_busqueda(texto):
    """'María López' -> 'maria lopez' (para encontrar duplicados y buscar)."""
    texto = unicodedata.normalize("NFKD", limpiar_texto(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def validar_nombre(valor, campo):
    if not valor:
        return f"Escriba los {campo}."
    if len(valor) < 2:
        return f"Los {campo} son demasiado cortos."
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]+", valor):
        return f"Los {campo} solo pueden tener letras y espacios."
    return None


def validar_cedula_ecuador(cedula):
    """Cédula ecuatoriana: 10 dígitos, provincia válida y dígito verificador (módulo 10)."""
    if not cedula.isdigit():
        return "La cédula solo debe tener números (sin guiones ni letras)."
    if len(cedula) != 10:
        return f"La cédula debe tener 10 números. Usted escribió {len(cedula)}."
    provincia = int(cedula[:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        return "Los dos primeros números de la cédula no corresponden a una provincia. Revise el número."
    if int(cedula[2]) >= 6:
        return "El tercer número de la cédula no es válido para una persona. Revise el número."
    suma = 0
    for i, coef in enumerate([2, 1, 2, 1, 2, 1, 2, 1, 2]):
        p = int(cedula[i]) * coef
        suma += p - 9 if p > 9 else p
    verificador = (10 - suma % 10) % 10
    if verificador != int(cedula[9]):
        return "Esta cédula no es válida (el último dígito no coincide). Revise que esté bien escrita."
    return None


def validar_pasaporte(valor):
    if not re.fullmatch(r"[A-Z0-9]{5,20}", valor):
        return "El pasaporte debe tener entre 5 y 20 letras o números, sin espacios."
    return None


def normalizar_telefono(valor):
    return re.sub(r"[\s\-()]", "", limpiar_texto(valor, 30))


def validar_telefono(valor, obligatorio=False):
    """Celular Ecuador 09XXXXXXXX o fijo 0[2-7]XXXXXXX. Acepta +593."""
    if not valor:
        return "Escriba un teléfono." if obligatorio else None
    if valor.startswith("+593"):
        valor = "0" + valor[4:]
    if not valor.isdigit():
        return "El teléfono solo debe tener números."
    if re.fullmatch(r"09\d{8}", valor) or re.fullmatch(r"0[2-7]\d{7}", valor):
        return None
    return "El teléfono no parece correcto. Celular: 10 números empezando en 09. Fijo: 9 números (ej. 022345678)."


def validar_email(valor):
    if not valor:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", valor):
        return "El correo no parece correcto. Ejemplo: nombre@gmail.com"
    return None


def validar_fecha_nacimiento(valor, hoy):
    if not valor:
        return None, "Escriba la fecha de nacimiento."
    try:
        fecha = date.fromisoformat(valor)
    except ValueError:
        return None, "La fecha de nacimiento no es válida."
    if fecha > hoy:
        return None, "La fecha de nacimiento no puede ser en el futuro."
    if (hoy.year - fecha.year) > EDAD_MAXIMA:
        return None, f"La edad no puede ser mayor a {EDAD_MAXIMA} años. Revise el año."
    return fecha, None


def edad(fecha_nac, hoy):
    return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
