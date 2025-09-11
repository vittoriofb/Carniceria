# -*- coding: utf-8 -*-
import re
from thefuzz import process, fuzz
import unicodedata
from difflib import SequenceMatcher, get_close_matches
from unidecode import unidecode
import re
from rapidfuzz import fuzz


import numpy as np
from rapidfuzz import process

from data import PRODUCTOS_DB



# --- Normalización de expresiones de fecha/hora típicas de WhatsApp ---

_H_RE = re.compile(r"\b(\d{1,2})\s*h(?:s|rs)?\b", re.I)                       # 15h -> 15:00
_AMPM_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)\b", re.I)
_Y_MEDIA_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+media\b", re.I)   # 2 y media -> 2:30
_Y_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+cuarto\b", re.I) # 2 y cuarto -> 2:15
_MENOS_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+menos\s+cuarto\b", re.I)  # 2 menos cuarto -> 1:45
_PUNTO_RE = re.compile(r"\b(\d{1,2})\.(\d{2})\b")                             # 13.30 -> 13:30
_MANANA_HH_RE = re.compile(r"\bmañana\s+(?:a\s+las\s+)?(\d{1,2})(?::(\d{2}))?\b", re.I)
_MANANA_MEDIODIA_RE = re.compile(r"\bmañana\s+al\s+mediod[ií]a\b", re.I)


# Nuevos patrones ampliados
_COMA_RE = re.compile(r"\b(\d{1,2}),(\d{2})\b")                 # 13,30 -> 13:30
_HHMM4_RE = re.compile(r"\b(\d{1,2})(\d{2})\b")                 # 1530 -> 15:30 (cauto)
_ALAS_RE = re.compile(r"\b(?:a\s+las|las)\s+(\d{1,2})(?![:\d])\b", re.I) # a las 7 -> 7:00
_EN_PUNTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+en\s+punto\b", re.I)
_Y_MINUTOS_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+(cinco|diez|veinte|veinticinco|treinta)\b", re.I)
_MENOS_MINUTOS_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+menos\s+(cinco|diez|veinte|veinticinco)\b", re.I)
_Y_PICO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+pico\b", re.I)
_MEDIODIA_RE = re.compile(r"\b(al\s+)?mediod[ií]a\b", re.I)
_MEDIANOCHE_RE = re.compile(r"\b(a\s+)?medianoche\b", re.I)
_PRIMERA_HORA_RE = re.compile(r"\b(a\s+)?primera\s+hora\b", re.I)
_MEDIA_MAÑANA_RE = re.compile(r"\b(a\s+|por\s+la\s+|de\s+)?media\s+ma(?:ñ|n)ana\b", re.I)
_TARDE_NOCHE_RE = re.compile(r"\btarde\s*[-/]\s*noche\b", re.I)
_POR_LA_MAÑANA_RE = re.compile(r"\bpor\s+la\s+ma(?:ñ|n)ana\b", re.I)
_POR_LA_TARDE_RE = re.compile(r"\bpor\s+la\s+tarde\b", re.I)
_POR_LA_NOCHE_RE = re.compile(r"\bpor\s+la\s+noche\b", re.I)

def _to_hhmm(h, m):
    h = max(0, min(23, int(h)))
    m = max(0, min(59, int(m)))
    return f"{h}:{m:02d}"

def normalizar_fecha_texto(s: str) -> str:
    """Convierte expresiones coloquiales en formatos que tu parseador ya entiende."""
    if not s:
        return s
    s = s.strip().lower()

    # Ortografía y variantes
    s = (s
         .replace("próximo", "proximo")
         .replace("míercoles", "miércoles")
         .replace("miercoles", "miércoles")
         .replace("mediodia", "mediodía"))

    # 15h -> 15:00
    s = _H_RE.sub(lambda m: _to_hhmm(m.group(1), 0), s)

    # 13.30 -> 13:30
    s = _PUNTO_RE.sub(lambda m: _to_hhmm(m.group(1), m.group(2)), s)
    # 13,30 -> 13:30
    s = _COMA_RE.sub(lambda m: _to_hhmm(m.group(1), m.group(2)), s)

    # 1530 -> 15:30 (si parece una hora pegada y no forma parte de un número más largo)
    s = re.sub(r"(?<!\d)(\d{1,2})(\d{2})(?!\d)", lambda m: _to_hhmm(m.group(1), m.group(2)), s)

    # 'a las 7' / 'las 7' -> '7:00'
    s = _ALAS_RE.sub(lambda m: _to_hhmm(m.group(1), 0), s)

    # 'en punto' -> :00
    s = _EN_PUNTO_RE.sub(lambda m: _to_hhmm(m.group(1), 0), s)

    # 'y cinco/diez/veinte/veinticinco/treinta'
    _map_min = {'cinco':5,'diez':10,'veinte':20,'veinticinco':25,'treinta':30}
    s = _Y_MINUTOS_RE.sub(lambda m: _to_hhmm(m.group(1), _map_min[m.group(2).lower()]), s)

    # 'menos cinco/diez/veinte/veinticinco'
    _map_men = {'cinco':55,'diez':50,'veinte':40,'veinticinco':35}
    def _menos(m):
        h = (int(m.group(1)) - 1) % 24
        return _to_hhmm(h, _map_men[m.group(2).lower()])
    s = _MENOS_MINUTOS_RE.sub(_menos, s)

    # 'y pico' ~ +5
    s = _Y_PICO_RE.sub(lambda m: _to_hhmm(m.group(1), 5), s)

    # Términos comunes de tramos del día a una hora concreta que tu bot entiende
    s = _MEDIODIA_RE.sub("13:00", s)
    s = _MEDIANOCHE_RE.sub("00:00", s)
    s = _PRIMERA_HORA_RE.sub("mañana", s)  # lo resolverá PERIODOS->(9:00)
    s = _MEDIA_MAÑANA_RE.sub("mañana", s)
    s = _TARDE_NOCHE_RE.sub("tarde", s)    # elegir tramo 'tarde' por defecto
    s = _POR_LA_MAÑANA_RE.sub("mañana", s)
    s = _POR_LA_TARDE_RE.sub("tarde", s)
    s = _POR_LA_NOCHE_RE.sub("noche", s)

    # 2 y media -> 2:30
    s = _Y_MEDIA_RE.sub(lambda m: _to_hhmm(m.group(1), 30), s)

    # 2 y cuarto -> 2:15
    s = _Y_CUARTO_RE.sub(lambda m: _to_hhmm(m.group(1), 15), s)

     # mañana a las 15 -> 15:00 mañana
    s = _MANANA_HH_RE.sub(lambda m: _to_hhmm(m.group(1), m.group(2) or 0) + " mañana", s)

    # mañana al mediodía -> 13:00 mañana
    s = _MANANA_MEDIODIA_RE.sub("13:00 mañana", s)

    # mañana a las 12 -> 12:00 mañana
    _MANANA_ALAS_RE = re.compile(r"\bmañana\s+a\s+las\s+(\d{1,2})(?::(\d{2}))?\b")
    s = _MANANA_ALAS_RE.sub(lambda m: _to_hhmm(m.group(1), m.group(2) or 0) + " mañana", s)

    # mañana al mediodía -> 13:00 mañana
    s = re.sub(r"\bmañana\s+al\s+mediod[ií]a\b", "13:00 mañana", s)

    # 2 menos cuarto -> 1:45
    def _menos_cuarto(m):
        h = int(m.group(1))
        h = 23 if h == 0 else h - 1
        return _to_hhmm(h, 45)
    s = _MENOS_CUARTO_RE.sub(_menos_cuarto, s)

   


    # 3pm / 3 p.m. -> 15:00
    def _ampm(m):
        h = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        tag = m.group(3).replace(".", "").lower()
        if tag == "pm" and h < 12:
            h += 12
        if tag == "am" and h == 12:
            h = 0
        return _to_hhmm(h, mm)
    s = _AMPM_RE.sub(_ampm, s)

    # Rellenos habituales que no afectan al parseo
    s = re.sub(r"\b(sobre|tipo|para|hacia)\s+las\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Extracción de productos (uno o varios) ---

# Palabras-numero comunes
_NUM_TXT = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "docena": 12,
    "trece": 13, "catorce": 14, "quince": 15, "veinte": 20,
    "medio": 0.5, "media": 0.5,
    "cuarto": 0.25, "tres cuartos": 0.75,
}

_UNIDADES_KG = ("kg", "k", "kilo", "kilos", "kgs", "kg.", "kilogramo", "kilogramos", "kgr", "kgm")
_UNIDADES_G  = ("g", "gr", "grs", "gramo", "gramos", "g.", "gr.")

# Filler words típicos delante del pedido
_FILLER_INICIO = re.compile(
    r"^(?:me\s+pones|ponme|pon|quisiera|quiero|querría|qerria|me\s+gustaría|"
    r"apúntame|apuntame|añade|anade|agrega|sumame|súmame|mete|encárgame|encargame|"
    r"para\s+llevar|para\s+hoy|para\s+mañana|para\s+manana|podrias|podrías|"
    r"me\s+añades|me\s+agregas|me\s+metes|"
    r"dame|traeme|tráeme|pásame|pasame|"
    r"quiero\s+pedir|voy\s+a\s+querer|me\s+vas\s+a\s+dar|me\s+sirves|"
    r"echame|échame|apártame|apartame|reservame|resérvame|reserva|"
    r"me\s+traes|traete|si\s+puedes|por\s+favor|porfa|porfis|"
    r"quisiera\s+encargar|quiero\s+encargar|me\s+encargas)\s+", re.I
)

_SEP = re.compile(r"\s*(?:,|;|\+|/|y|e)\s*", re.I)

# Segmento tipo: "2 kg de pollo" | "2kg pollo" | "pollo 2 kg" | "250g de chorizo" | "medio de lomo"
_PAT_QTY_DE_PROD = re.compile(
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?\s*(?:de\s+)?"
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",   # 👈 producto completo
    re.I
)

# Producto + cantidad [+ unidad]
_PAT_PROD_QTY = re.compile(
    r"(?P<prod>[a-záéíóúñü\s\-]+)\s*"  # 👈 sin lazy, acepta nombre completo
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?$",
    re.I
)

# Unidades/piezas (ej: "2 hamburguesas", "1 paella", "3 croquetas de pollo")
_PAT_UNIDADES_PIEZAS = re.compile(
    r"(?P<num>\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+"
    r"(?P<prod>[a-záéíóúñü\s\-]+s?)$",   # 👈 plural dentro del grupo
    re.I
)

# Cantidad en texto + [unidad] + de + producto
_PAT_NUM_TXT = re.compile(
    r"(?P<num>(?:un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
    r"once|doce|docena|trece|catorce|quince|veinte|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?\s*(?:de\s+)?"
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",   # 👈 producto completo
    re.I
)


def _parse_qty(qty_raw: str, unit_raw: str | None) -> float:
    q = qty_raw.strip().lower()
    q = q.replace(",", ".")
    q = re.sub(r"\s+", " ", q)

    if q in _NUM_TXT:
        qty = float(_NUM_TXT[q])
    elif q in ("1/2",):
        qty = 0.5
    elif q in ("1/4",):
        qty = 0.25
    elif q in ("3/4",):
        qty = 0.75
    else:
        try:
            qty = float(q)
        except ValueError:
            qty = 0.0

    unit = (unit_raw or "").lower().strip()
    if unit in _UNIDADES_G:
        qty = qty / 1000.0  # pasar a kg
    # si no hay unidad o es kg, ya está en kg
    return round(qty, 3)

STOPWORDS = {"de", "y", "con", "el", "la", "los", "las", "un", "una", "unos", "unas"}

def _strip_accents(text: str) -> str:
    return unidecode(text)

def _similaridad(a: str, b: str) -> float:
    """Devuelve la similitud entre dos cadenas usando ratio de difflib."""
    return SequenceMatcher(None, a, b).ratio()

def _preprocesar(texto: str) -> list[str]:
    """Convierte el texto a palabras significativas, normalizadas y sin stopwords."""
    texto = _strip_accents(texto.lower())
    palabras = [w for w in texto.split() if w not in STOPWORDS]
    return palabras

# ----------------------------
# expresiones.py (o donde esté _normalize)
# ----------------------------

def _normalize(text) -> str:
    """
    Normaliza cualquier entrada a un string seguro:
    - acepta str, bytes, list, tuple, int, etc.
    - lower, strip, elimina acentos y caracteres no alfanuméricos,
      colapsa espacios.
    """
    if text is None:
        return ""

    # bytes -> str
    if isinstance(text, (bytes, bytearray)):
        try:
            text = text.decode("utf-8")
        except Exception:
            text = str(text)

    # list/tuple -> intentar juntar elementos
    if isinstance(text, (list, tuple)):
        # si todos son str, juntamos por espacio
        if all(isinstance(x, str) for x in text):
            text = " ".join(text)
        else:
            # fallback: str() de cada elemento
            text = " ".join(str(x) for x in text)

    # cualquier otro tipo -> str()
    if not isinstance(text, str):
        text = str(text)

    # ahora sí operaciones de normalización sobre string
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # dejar solo a-z y 0-9 y espacios
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --- Inicialización ---
# 1. Índice normalizado
INDEX_NORMALIZADO = { _normalize(k): k for k in PRODUCTOS_DB }

SYNONYMS = {
    "pollo para asar": "Pollo entero",
    "pollo al horno": "Pollo entero",
    "alita de pollo": "Alas de pollo",
    "alita": "Alas de pollo",
    "muslito relleno queso": "Muslitos de pollo rellenos de queso brie, manzana  y nueces",
    "muslito relleno espinaca": "Muslitos de pollo rellenos de espinacas con queso de cabra, dátiles y cebolla confitada",
    "pechuga": "Filetes de pechuga entera",
    "pechuga pollo": "Filetes de pechuga entera",
    "chuletón de vaca": "Super chuletón de vaca gallega madurada (1kg aprox)",
    "chuleta de vaca": "Chuleta de ternera gallega",
    "croquetas casera": "Surtido de croquetas caseras 12 unidades",
    "croquetas pollo": "Croquetas de Pollo",
    "hamburguesa barbacoa": "Hamburguesa BBQ barbacoa",
    "hamburguesa de pollo": "Hamburguesa clásica de polllo",
    "hamburguesa de ternera": "Hamburguesa clásica de ternera",
    "cordero entero": "Cordero lechal entero",
    "cordero medio": "Cordero lechal medio",
    # puedes ir ampliando con lo que digan tus clientes
}

# --- Función de búsqueda ligera
def _buscar_producto_fuzzy(texto: str, catalogo=None) -> str | None:
    """Devuelve el producto más parecido o None (sin mensajes ni sugerencias)."""
    if not texto:
        return None

    norm_input = _normalize(texto)

    # 1) Exact match
    for p in catalogo or PRODUCTOS_DB:
        if norm_input == _normalize(p):
            return p

    # 2) Sinónimos
    if norm_input in SYNONYMS:
        return SYNONYMS[norm_input]

    # 3) Fuzzy
    best, score, _ = process.extractOne(texto, catalogo or PRODUCTOS_DB)
    if score >= 85:
        return best

    return None

# --------------------
# FUNCION CONVERSACIONAL (cuando hablas con cliente directamente)
# --------------------
def buscar_producto_conversacional(pedido: str, catalogo=None) -> str:
    resultado = _buscar_producto_fuzzy(pedido, catalogo or PRODUCTOS_DB)

    if resultado:
        return f"Perfecto 👍, te apunto: {resultado}"

    # Si no hay match, proponemos sugerencias
    sugerencias = [x[0] for x in process.extract(pedido, catalogo or PRODUCTOS_DB, limit=3)]
    if sugerencias:
        return f"No encontré '{pedido}'. ¿Quizás quisiste decir: {', '.join(sugerencias)}?"

    return f"No he encontrado nada parecido a '{pedido}'."
# --- Función canonicalizar producto

# extensiones.py
# ----------------------------
# extensiones.py: _canonicalizar_producto (robusta)
# ----------------------------

def _canonicalizar_producto(prod_raw, productos_db, fuzzy_threshold: int = 85) -> str | list[str] | None:
    """
    Devuelve:
      - str: producto claro (exacto / sinónimo / fuzzy claro)
      - list[str]: sugerencias si hay ambigüedad
      - None: si no hay coincidencias
    Funciona aunque prod_raw sea list/tuple/u otros tipos.
    """
    if not prod_raw:
        return None

    # Si nos pasan una tupla/lista (p. ej. extraer_productos devuelve algo raro),
    # intentamos sacar el nombre del producto:
    if isinstance(prod_raw, (list, tuple)):
        # forma común: prod_raw = ['pollo', 'relleno'] -> "pollo relleno"
        # o prod_raw = ('pollo relleno', 2, 'kg') -> usar el primer elemento si es str
        if len(prod_raw) >= 1 and isinstance(prod_raw[0], str) and len(prod_raw) > 1:
            # si parece (nombre, cantidad, unidad) escogemos el primer elemento como nombre
            prod_name_candidate = prod_raw[0]
        else:
            # en cualquier otro caso, juntamos todos los elementos como string
            prod_name_candidate = " ".join(str(x) for x in prod_raw)
    else:
        prod_name_candidate = prod_raw

    prod_norm = _normalize(prod_name_candidate)

    # 1) Exact match
    exact_matches = [p for p in productos_db if _normalize(p) == prod_norm]
    if exact_matches:
        return exact_matches[0]

    # 2) Sinónimos
    if prod_norm in SYNONYMS:
        return SYNONYMS[prod_norm]

    # 3) Coincidencia por keywords (todas deben estar presentes)
    palabras = set(prod_norm.split())
    candidatos = [p for p in productos_db if palabras and all(w in _normalize(p) for w in palabras)]
    if candidatos:
        if len(candidatos) == 1:
            return candidatos[0]  # certeza
        else:
            # Ambigüedad -> devolvemos la lista tal cual (sin priorizar por longitud)
            return candidatos

    # 4) Fuzzy matching (fallback)
    if productos_db:
        maybe = process.extractOne(prod_name_candidate, productos_db)
        if maybe:
            best_match, score, _ = maybe
            if score >= fuzzy_threshold:
                return best_match

        # Si no hay match claro, devolver top-N sugerencias con score decente
        sugerencias = [p for p, s, _ in process.extract(prod_name_candidate, productos_db, limit=3) if s >= 60]
        if sugerencias:
            return sugerencias

    return None




def extraer_productos_desde_texto(texto: str, productos_db) -> list[tuple[str, float, str]]:
    if not texto:
        return []

    raw = texto.strip().lower()

    # 0) Quitar fillers al INICIO
    prev = None
    while True:
        nuevo = _FILLER_INICIO.sub("", raw).strip()
        if nuevo == raw:
            break
        raw = nuevo

    raw = re.sub(r"(?:\s+de)?\s+\d{3,}\b$", "", raw)

    # 1) Normalización de cantidades coloquiales
    reemplazos_qty = [
        (r"\bmedio\s+kilo\b", "0.5 kg"),
        (r"\b(kilo|kg)\s+y\s+medio\b", "1.5 kg"),
        (r"\b(kilo|kg)\s+y\s+cuarto\b", "1.25 kg"),
        (r"\b(kilo|kg)\s+y\s+tres\s+cuartos\b", "1.75 kg"),
        (r"\bcuarto\s+y\s+mitad\b", "0.375 kg"),
        (r"\bun cuarto\b", "0.25 kg"),
        (r"\btres cuartos\b", "0.75 kg"),
        (r"\bmedia\b", "0.5 kg"),
    ]
    for pat, rep in reemplazos_qty:
        raw = re.sub(pat, rep, raw)

    # 2) Trocear en segmentos por separadores
    segmentos = [s for s in _SEP.split(raw) if s]
    items: list[tuple[str, float, str]] = []

    _KG_TOKENS = {"kg", "kilo", "kilos", "kgs"}
    _G_TOKENS  = {"g", "gr", "grs", "gramo", "gramos"}

    def _to_units_number(qty_raw: str) -> float:
        q = qty_raw.strip().lower().replace(",", ".")
        q = re.sub(r"\s+", " ", q)
        if q in _NUM_TXT:
            return float(_NUM_TXT[q])
        try:
            return float(q)
        except ValueError:
            return 0.0

    for seg in segmentos:
        seg = _FILLER_INICIO.sub("", seg).strip()
        if not seg:
            continue

        print(f"Procesando segmento: '{seg}'")  # 🔹 Debug

        # 1) qty + [unit] + (de) + prod
        m = _PAT_QTY_DE_PROD.match(seg)
        if m:
            qty_raw = m.group("qty")
            unit_raw = (m.group("unit") or "").lower()
            prod = m.group("prod")
            print(f"Matched _PAT_QTY_DE_PROD: prod='{prod}', qty='{qty_raw}', unit='{unit_raw}'")  # 🔹 Debug
            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(qty_raw, unit_raw)
                if qty > 0:
                    items.append((prod, qty, "kg"))
            else:
                qty = _to_units_number(qty_raw)
                if qty > 0:
                    items.append((prod, qty, "u"))
            continue

        # 2) prod + qty [+ unit]
        m = _PAT_PROD_QTY.match(seg)
        if m:
            qty_raw = m.group("qty")
            unit_raw = (m.group("unit") or "").lower()
            prod = m.group("prod")
            print(f"Matched _PAT_PROD_QTY: prod='{prod}', qty='{qty_raw}', unit='{unit_raw}'")  # 🔹 Debug
            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(qty_raw, unit_raw)
                if qty > 0:
                    items.append((prod, qty, "kg"))
            else:
                qty = _to_units_number(qty_raw)
                if qty > 0:
                    items.append((prod, qty, "u"))
            continue

        # 3) num_txt + [unit] + de + prod
        m = _PAT_NUM_TXT.match(seg)
        if m:
            num_raw = m.group("num")
            unit_raw = (m.group("unit") or "").lower()
            prod = m.group("prod")
            print(f"Matched _PAT_NUM_TXT: prod='{prod}', num='{num_raw}', unit='{unit_raw}'")  # 🔹 Debug
            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(num_raw, unit_raw)
                if qty > 0:
                    items.append((prod, qty, "kg"))
            else:
                qty = _to_units_number(num_raw)
                if qty > 0:
                    items.append((prod, qty, "u"))
            continue

        # 4) "pollo medio"
        m = re.match(
            r"(?P<prod>[a-záéíóúñü\s\-]+)\s+(?P<num>medio|media|1/2|cuarto|1/4|tres\s+cuartos|3/4)$",
            seg, re.I
        )
        if m:
            qty = _parse_qty(m.group("num"), "kg")
            prod = m.group("prod")
            print(f"Matched regex 4: prod='{prod}', qty='{qty}'")  # 🔹 Debug
            if prod and qty > 0:
                items.append((prod, qty, "kg"))
            continue

        # 5) Unidades/piezas
        m = _PAT_UNIDADES_PIEZAS.match(seg)
        if m:
            num_raw = m.group("num").lower()
            qty = float(_NUM_TXT.get(num_raw, num_raw)) if num_raw in _NUM_TXT else float(num_raw)
            prod = m.group("prod")
            print(f"Matched _PAT_UNIDADES_PIEZAS: prod='{prod}', qty='{qty}'")  # 🔹 Debug
            if prod and qty > 0:
                items.append((prod, qty, "u"))
            continue

        print(f"No match para segmento: '{seg}'")  # 🔹 Debug

    print(f"Items extraídos: {items}")  # 🔹 Debug final
    return items
