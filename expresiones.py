# -*- coding: utf-8 -*-
import re
from thefuzz import process, fuzz
import unicodedata
from difflib import SequenceMatcher, get_close_matches
from unidecode import unidecode
import re
from rapidfuzz import fuzz


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
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",
    re.I
)
_PAT_PROD_QTY = re.compile(
    r"(?P<prod>[a-záéíóúñü\s\-]+?)\s*"
    r"(?P<qty>(?:\d+(?:[.,]\d+)?|(?:1/2|1/4|3/4)|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?$",
    re.I
)

# Nuevo: detectar unidades tipo "2 hamburguesas", "1 paella"
_PAT_UNIDADES_PIEZAS = re.compile(
    r"(?P<num>\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+"
    r"(?P<prod>[a-záéíóúñü\s\-]+?)(?:s)?$", re.I
)


_PAT_NUM_TXT = re.compile(
    r"(?P<num>(?:un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
    r"once|doce|docena|trece|catorce|quince|veinte|medio|media|cuarto|tres\s+cuartos))\s*"
    r"(?P<unit>kg|kilos?|kgs?|g|grs?|gramos?)?\s*(?:de\s+)?"
    r"(?P<prod>[a-záéíóúñü\s\-]+)$",
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

# Normalización robusta
def _normalize(text: str) -> str:
    if not text:
        return ""
    t = unidecode(text.lower())
    # dejamos letras, números, espacios y guiones
    t = re.sub(r"[^a-z0-9\s\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# Extraer "head" (lo principal antes de preposiciones/complements)
def _get_head(product_name: str) -> str:
    if not product_name:
        return ""
    s = _normalize(product_name)
    # cortar en conjunciones/preposiciones habituales para quedarse con la parte principal
    parts = re.split(r'\b(?:de|del|con|rellen[ao]s?|relleno|al|a la|a los|a las|en|para|con\s+salsa)\b', s, flags=re.I)
    left = parts[0].strip()
    if not left:
        left = s
    head = left.split()[0] if left.split() else left
    return head

# Versión mejorada y robusta de búsqueda
def _buscar_producto_fuzzy(texto: str, productos_db) -> str | None:
    from main import INDEX_NORMALIZADO  # 👈 importa el índice global
    norm_input_full = _normalize(texto)

    # 0) Coincidencia exacta con índice
    if norm_input_full in INDEX_NORMALIZADO:
        return INDEX_NORMALIZADO[norm_input_full]
    # acepta dict o lista de keys
    keys = list(productos_db.keys()) if hasattr(productos_db, "keys") else list(productos_db)

    if not texto:
        return None

    norm_input_full = _normalize(texto)                     # para coincidencia exacta
    input_tokens = [w for w in norm_input_full.split() if w and w not in STOPWORDS]  # tokens limpios
    input_join = " ".join(input_tokens)

    # 0) Match exacto (normalizado) => 100% seguro
    # build an index rápido (podrías cachearlo fuera de la función)
    for k in keys:
        if _normalize(k) == norm_input_full:
            return k

    # 0.1) también chequeo sin espacios extras / accents directos
    for k in keys:
        if unidecode(k.lower()).strip() == unidecode(texto.lower()).strip():
            return k

    # 1) Si el usuario escribió una sola palabra: buscar por "head" (la palabra principal del producto)
    if len(input_tokens) == 1:
        token = input_tokens[0]
        candidates = [k for k in keys if _get_head(k) == token]
        if candidates:
            # elegir el producto con menos palabras (más genérico / corto)
            candidates.sort(key=lambda x: len(_preprocesar(x)))
            return candidates[0]

    # 2) Coincidencia por inclusión de todas las palabras (si el input tiene varias palabras)
    if input_tokens:
        exact_word_matches = []
        for k in keys:
            p_words = set(_preprocesar(k))
            if set(input_tokens) <= p_words:
                exact_word_matches.append(k)
        if exact_word_matches:
            exact_word_matches.sort(key=lambda x: len(_preprocesar(x)))  # preferir nombres más cortos
            return exact_word_matches[0]

    # 3) Fallback fuzzy (rapidfuzz) con penalización por "palabras extra"
    mejor = None
    mejor_score = 0.0
    for k in keys:
        p_norm = " ".join(_preprocesar(k))
        if not p_norm:
            continue

        # uso token_set_ratio para ignorar orden y duplicados
        base = fuzz.token_set_ratio(input_join, p_norm, score_cutoff=0) / 100.0

        # penalizar si el producto tiene muchas palabras que NO están en la query
        p_words = _preprocesar(k)
        extra = len(set(p_words) - set(input_tokens))
        # Factor de penalización: cuanto más extra, más baja la puntuación.
        penal = 1.0 / (1.0 + extra * 0.6)   # ajustable
        score = base * penal

        # pequeño bonus si el producto empieza por la token buscada (ayuda en casos 'pollo' vs 'muslitos...')
        if len(input_tokens) == 1 and _preprocesar(k):
            if _preprocesar(k)[0] == input_tokens[0]:
                score += 0.12

        # preferir productos cortos cuando el input es corto
        if len(input_tokens) <= 2:
            score *= 1.0 / (1.0 + max(0, len(p_words) - len(input_tokens)) * 0.15)

        if score > mejor_score:
            mejor_score = score
            mejor = k

    # cutoff final (ajustable). 0.40 es un punto de partida razonable
    if mejor_score >= 0.40:
        return mejor
    return None



def _canonicalizar_producto(prod_raw: str, productos_db_keys) -> str | None:
    """
    Devuelve la clave de producto más probable:
    1) match exacto sin tildes,
    2) coincidencia por subcadena (más larga),
    3) fuzzy matching como fallback.
    """
    prod = re.sub(r"[^a-záéíóúñü\s\-]", "", prod_raw.lower()).strip()
    if not prod:
        return None

    keys = list(productos_db_keys)
    prod_norm = _strip_accents(prod)

    # 1) match exacto (sin tildes)
    for k in keys:
        if _strip_accents(k.lower()) == prod_norm:
            return k

    # 2) coincidencia por subcadena (más larga)
    best = None
    best_len = -1
    for k in keys:
        k_norm = _strip_accents(k.lower())
        if k_norm in prod_norm or prod_norm in k_norm:
            if len(k_norm) > best_len:
                best = k
                best_len = len(k_norm)
    if best:
        return best

    # 3) fallback fuzzy
    return _buscar_producto_fuzzy(prod_raw, productos_db_keys)


def extraer_productos_desde_texto(texto: str, productos_db) -> list[tuple[str, float, str]]:
    """
    Extrae [(producto, cantidad, unidad), ...] desde un mensaje libre.
    - unidad: "kg" si el cliente dijo kg/g (se convierte a kg), "u" si habló de piezas.
    - Si NO se menciona 'kg'/'g', se asume unidades ("u").
    """
    if not texto:
        return []

    keys = productos_db.keys() if hasattr(productos_db, "keys") else list(productos_db)
    raw = texto.strip().lower()

    # 0) Quitar fillers al INICIO (repetidos)
    prev = None
    while True:
        nuevo = _FILLER_INICIO.sub("", raw).strip()
        if nuevo == raw:
            break
        raw = nuevo

    # 0.1) Limpiar posible ruido numérico al final
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

    # Ayudas locales de unidad
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

        # 1) qty + [unit] + (de) + prod
        m = _PAT_QTY_DE_PROD.match(seg)
        if m:
            qty_raw = m.group("qty")
            unit_raw = (m.group("unit") or "").lower()
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if not prod:
                continue

            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(qty_raw, unit_raw)   # kg normalizados
                if qty > 0:
                    items.append((prod, qty, "kg"))
            else:
                # Sin unidad explícita -> tratamos como unidades/piezas
                qty = _to_units_number(qty_raw)
                if qty > 0:
                    items.append((prod, qty, "u"))
            continue

        # 2) prod + qty [+ unit]
        m = _PAT_PROD_QTY.match(seg)
        if m:
            qty_raw = m.group("qty")
            unit_raw = (m.group("unit") or "").lower()
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if not prod:
                continue

            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(qty_raw, unit_raw)   # kg
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
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if not prod:
                continue

            if unit_raw in _KG_TOKENS or unit_raw in _G_TOKENS:
                qty = _parse_qty(num_raw, unit_raw)   # kg
                if qty > 0:
                    items.append((prod, qty, "kg"))
            else:
                # Si no pone unidad aquí, casi siempre ya lo normalizamos antes (e.g. 0.5 kg),
                # pero por coherencia: interpretamos como unidades.
                qty = _to_units_number(num_raw)
                if qty > 0:
                    items.append((prod, qty, "u"))
            continue

        # 4) "pollo medio" -> asumimos kg (ya lo estabas forzando con _parse_qty(..., "kg"))
        m = re.match(
            r"(?P<prod>[a-záéíóúñü\s\-]+)\s+(?P<num>medio|media|1/2|cuarto|1/4|tres\s+cuartos|3/4)$",
            seg, re.I
        )
        if m:
            qty = _parse_qty(m.group("num"), "kg")   # kg
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty, "kg"))
            continue

        # 5) Unidades/piezas: "2 hamburguesas", "1 paella", "dos filetes"
        m = _PAT_UNIDADES_PIEZAS.match(seg)
        if m:
            num_raw = m.group("num").lower()
            qty = float(_NUM_TXT.get(num_raw, num_raw)) if num_raw in _NUM_TXT else float(num_raw)
            prod = _canonicalizar_producto(m.group("prod"), keys)
            if prod and qty > 0:
                items.append((prod, qty, "u"))
            continue

    return items
