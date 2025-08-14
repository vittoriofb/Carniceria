# -*- coding: utf-8 -*-
import re

# --- Normalización de expresiones de fecha/hora típicas de WhatsApp ---

_H_RE = re.compile(r"\b(\d{1,2})\s*h(?:s|rs|oras)?\b", re.I)  # 15h, 15hs, 15 horas
_AMPM_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm|de\s+la\s+mañana|de\s+la\s+tarde|de\s+la\s+noche|de\s+la\s+madrugada)\b", re.I)
_Y_MEDIA_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+(?:media|30|minutos\s+)?\b", re.I)
_Y_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+y\s+(?:cuarto|15|minutos\s+)?\b", re.I)
_MENOS_CUARTO_RE = re.compile(r"\b(?:a\s+las\s+)?(\d{1,2})\s+menos\s+(?:cuarto|15|minutos\s+)?\b", re.I)
_PUNTO_RE = re.compile(r"\b(\d{1,2})[.:](\d{2})\b")

def _to_hhmm(h, m):
    h = max(0, min(23, int(h)))
    m = max(0, min(59, int(m)))
    return f"{h}:{m:02d}"

def normalizar_fecha_texto(s: str) -> str:
    if not s:
        return s
    s = s.strip().lower()

    # Ortografía y variantes
    s = (s
         .replace("próximo", "proximo")
         .replace("míercoles", "miércoles")
         .replace("miercoles", "miércoles")
         .replace("mediodia", "mediodía"))

    # 15h / 15 horas -> 15:00
    s = _H_RE.sub(lambda m: _to_hhmm(m.group(1), 0), s)

    # 13.30 / 13:30
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

    # AM/PM y expresiones con "de la mañana/tarde/noche"
    def _ampm(m):
        h = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        tag = m.group(3).replace(".", "").lower()
        if tag in ("pm", "de la tarde", "de la noche") and h < 12:
            h += 12
        if tag in ("am", "de la mañana", "de la madrugada") and h == 12:
            h = 0
        return _to_hhmm(h, mm)
    s = _AMPM_RE.sub(_ampm, s)

    # Rellenos habituales
    s = re.sub(r"\b(sobre|tipo|para|hacia|aprox(?:imadamente)?)\s+las\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Extracción de productos (uno o varios) ---

_NUM_TXT = {
    "un": 1, "una": 1, "uno": 1, "y uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "medio": 0.5, "media": 0.5,
    "cuarto": 0.25, "tres cuartos": 0.75,
    "y medio": 0.5  # ej: "uno y medio"
}

_UNIDADES_KG = ("kg", "k", "kilo", "kilos", "kgs", "kg.", "kilogramo", "kilogramos")
_UNIDADES_G  = ("g", "gr", "grs", "gramo", "gramos")

_FILLER_INICIO = re.compile(
    r"^(?:me\s+pones|ponme|pon|quisiera|quiero|querría|qerria|me\s+gustaría|"
    r"apúntame|apuntame|añade|anade|agrega|sumame|súmame|mete|encárgame|encargame|"
    r"para\s+llevar|para\s+hoy|para\s+mañana|para\s+manana|podrias|podrías|"
    r"me\s+añades|me\s+agregas|me\s+metes|me\s+sumas|pon\s+por\s+favor|tráeme|traeme|"
    r"añademe|agregame|apuntame\s+por\s+favor)\s+", re.I
)

_SEP = re.compile(r"\s*(?:,|;|\s+y\s+|\s+e\s+|con\s+)\s*", re.I)

_PAT_QTY_DE_PROD = re.compile(
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos|un\s+y\s+medio))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?|kilogramos?)?\s*(?:de\s+)?"
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",
    re.I
)

_PAT_PROD_QTY = re.compile(
    r"(?P<prod>[a-záéíóúñü\s\-]+?)\s*"
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos|un\s+y\s+medio))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?|kilogramos?)$",
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
    elif q in ("un y medio",):
        qty = 1.5
    else:
        try:
            qty = float(q)
        except ValueError:
            return 0.0

    unit = (unit_raw or "").strip().lower()
    if unit in _UNIDADES_G:
        qty = qty / 1000.0
    return round(qty, 3)

def _canonicalizar_producto(prod_raw: str, productos_db_keys) -> str | None:
    prod = re.sub(r"[^a-záéíóúñü\s\-]", "", prod_raw.lower()).strip()
    if not prod:
        return None
    keys = list(productos_db_keys)
    if prod in keys:
        return prod
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
    if not texto:
        return []
    keys = productos_db.keys() if hasattr(productos_db, "keys") else list(productos_db)
    raw = texto.strip().lower()

    segmentos = _SEP.split(raw)
    items: list[tuple[str, float]] = []

    for seg in segmentos:
        if not seg:
            continue
        seg = _FILLER_INICIO.sub("", seg).strip()

        m = _PAT_QTY_DE_PROD.match(seg)
        if m:
            qty = _parse_qty(m.group("qty"), m.group("unit"))
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        m = _PAT_PROD_QTY.match(seg)
        if m:
            qty = _parse_qty(m.group("qty"), m.group("unit"))
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        m = re.match(
            r"(?P<num>(?:un(?:a)?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|medio|media|cuarto|tres\s+cuartos|un\s+y\s+medio))\s+"
            r"(?:kilo|kilos|kg|kilogramos?)\s*(?:de\s+)?(?P<prod>[a-záéíóúñü\s\-]+)$", seg, re.I)
        if m:
            qty = _parse_qty(m.group("num"), "kg")
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

        m = re.match(
            r"(?P<prod>[a-záéíóúñü\s\-]+)\s+(?P<num>medio|media|1/2|cuarto|1/4|tres\s+cuartos|3/4|un\s+y\s+medio)$",
            seg, re.I)
        if m:
            qty = _parse_qty(m.group("num"), "kg")
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty))
            continue

    return items
