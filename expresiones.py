# -*- coding: utf-8 -*-
import re

# --- Normalización de expresiones de fecha/hora típicas de WhatsApp ---

_H_RE = re.compile(r"\b(\d{1,2})\s*h(?:s|rs)?\b", re.I)                       # 15h -> 15:00
_AMPM_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)\b", re.I)
_Y_MEDIA_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+media\b", re.I)   # 2 y media -> 2:30
_Y_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+cuarto\b", re.I) # 2 y cuarto -> 2:15
_MENOS_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+menos\s+cuarto\b", re.I)  # 2 menos cuarto -> 1:45
_PUNTO_RE = re.compile(r"\b(\d{1,2})\.(\d{2})\b")                             # 13.30 -> 13:30
_HORA_SIMPLE_RE = re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.I)                # 3 pm -> 15:00
_EN_PUNTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+en\s+punto\b", re.I) # 5 en punto -> 5:00
_MEDIODIA_RE = re.compile(r"\bmediod[ií]a\b", re.I)                           # mediodía -> 12:00
_MEDIA_NOCHE_RE = re.compile(r"\bmedia\s+noche\b", re.I)                      # medianoche -> 00:00

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

    # 2 y media -> 2:30
    s = _Y_MEDIA_RE.sub(lambda m: _to_hhmm(m.group(1), 30), s)

    # 2 y cuarto -> 2:15
    s = _Y_CUARTO_RE.sub(lambda m: _to_hhmm(m.group(1), 15), s)

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

    # 3 pm (sin minutos)
    def _hora_simple(m):
        h = int(m.group(1))
        tag = m.group(2).lower()
        if tag == "pm" and h < 12:
            h += 12
        if tag == "am" and h == 12:
            h = 0
        return _to_hhmm(h, 0)
    s = _HORA_SIMPLE_RE.sub(_hora_simple, s)

    # 5 en punto
    s = _EN_PUNTO_RE.sub(lambda m: _to_hhmm(m.group(1), 0), s)

    # mediodía -> 12:00
    s = _MEDIODIA_RE.sub("12:00", s)

    # medianoche -> 00:00
    s = _MEDIA_NOCHE_RE.sub("00:00", s)

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
    "medio": 0.5, "media": 0.5,
    "cuarto": 0.25, "tres cuartos": 0.75,
}

_UNIDADES_KG = ("kg", "k", "kilo", "kilos", "kgs", "kg.")
_UNIDADES_G  = ("g", "gr", "grs", "gramo", "gramos")

# Filler words típicos delante del pedido
_FILLER_INICIO = re.compile(
    r"^(?:me\s+pones|ponme|pon|quisiera|quiero|querría|qerria|me\s+gustaría|"
    r"apúntame|apuntame|añade|anade|agrega|sumame|súmame|mete|encárgame|encargame|"
    r"para\s+llevar|para\s+hoy|para\s+mañana|para\s+manana|podrias|podrías|"
    r"me\s+añades|me\s+agregas|me\s+metes|tráeme|traeme|sírveme|sirveme|"
    r"dame|colócame|colocame|prepárame|preparame|resérvame|reservame|"
    r"apártame|apartame|guárdame|guardame)\s+", re.I
)

_SEP = re.compile(r"\s*(?:,|;|\s+y\s+|\s+e\s+|\s+con\s+)\s*", re.I)

# Segmentos de cantidad + producto
_PAT_QTY_DE_PROD = re.compile(
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?\s*(?:de\s+)?"
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",
    re.I
)
_PAT_PROD_QTY = re.compile(
    r"(?P<prod>[a-záéíóúñü\s\-]+?)\s*"
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)$",
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
            return 0.0

    unit = (unit_raw or "").strip().lower()
    if unit in _UNIDADES_G:
        qty = qty / 1000.0  # pasar a kg
    # si no hay unidad o es kg, ya está en kg
    return round(qty, 3)

def _canonicalizar_producto(prod_raw: str, productos_db_keys) -> str | None:
    """Devuelve la clave de producto existente más probable por coincidencia de subcadena."""
    prod = re.sub(r"[^a-záéíóúñü\s\-]", "", prod_raw.lower()).strip()
    if not prod:
        return None

    keys = list(productos_db_keys)
    if prod in keys:
        return prod

    # Mejor coincidencia por subcadena (la más larga)
    best = None
    best_len = -1
    for k in keys:
        k_l = k.lower()
        if k_l in prod or prod in k_l:
            if len(k_l) > best_len:
                best = k
                best_len = len(k_l)
    return best

def extraer_productos_desde_texto(texto: str, productos_db) -> list[tuple[str, float]]:
    """
    Extrae [(producto, cantidad_kg), ...] desde un mensaje libre.
    Acepta múltiples items separados por ',', ';', 'y', 'e', 'con'.
    """
    if not texto:
        return []
    keys = productos_db.keys() if hasattr(productos_db, "keys") else list(productos_db)
    raw = texto.strip().lower()

    # Trocear en segmentos
    segmentos = _SEP.split(raw)
    items: list[tuple[str, float]] = []

    for seg in segmentos:
        if not seg:
            continue
        seg = _FILLER_INICIO.sub("", seg).strip()

        # Intento 1: "2 kg de pollo" / "250g chorizo" / "medio de lomo"
        m = _PAT_QTY_DE_PROD.match(seg)
        if m:
            qty = _parse_qty(m.group("qty"), m.group("unit"))
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        # Intento 2: "pollo 2 kg"
        m = _PAT_PROD_QTY.match(seg)
        if m:
            qty = _parse_qty(m.group("qty"), m.group("unit"))
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        # Intento 3: "un kilo de pollo", "dos kilos de ternera"
        m = re.match(
            r"(?P<num>(?:un(?:a)?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|medio|media|cuarto|tres\s+cuartos))\s+"
            r"(?:kilo|kilos|kg)\s*(?:de\s+)?(?P<prod>[a-záéíóúñü\s\-]+)$", seg, re.I)
        if m:
            qty = _parse_qty(m.group("num"), "kg")
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        # Intento 4: "pollo medio" (asumir kg)
        m = re.match(
            r"(?P<prod>[a-záéíóúñü\s\-]+)\s+(?P<num>medio|media|1/2|cuarto|1/4|tres\s+cuartos|3/4)$",
            seg, re.I)
        if m:
            qty = _parse_qty(m.group("num"), "kg")
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

    return items
