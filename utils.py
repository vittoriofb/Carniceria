# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta

from printer import send_to_printer
from data import PRODUCTOS_DB

# >>> NUEVO: utilidades de expresiones (no cambian la lógica, solo amplían la comprensión)
from expresiones import normalizar_fecha_texto, extraer_productos_desde_texto, _buscar_producto_fuzzy, _canonicalizar_producto
# <<<

SESSIONS = {}

def formatear_item_simple(prod: str, cantidad: float, unidad: str) -> str:
    """Formatea una sola línea (p.ej. al añadir): respeta kg vs unidades."""
    if unidad == "kg":
        cantidad_fmt = f"{cantidad:.2f}".rstrip("0").rstrip(".")
        return f"{prod.capitalize()}: {cantidad_fmt} kg"
    else:
        unidades = int(round(cantidad))
        return f"{prod.capitalize()}: {unidades} unidad{'es' if unidades != 1 else ''}"


def formatear_item(prod: str, cantidades: dict) -> str:
    """
    Formatea la línea del carrito para un producto que puede tener kg y/o unidades:
    ej: "Pollo: 1.5 kg + 2 unidades"
    """
    partes = []
    kg = float(cantidades.get("kg", 0.0))
    u = int(cantidades.get("u", 0))
    if kg > 0:
        kg_str = f"{kg:.2f}".rstrip("0").rstrip(".")
        partes.append(f"{kg_str} kg")
    if u > 0:
        partes.append(f"{u} unidad{'es' if u != 1 else ''}")
    if not partes:
        partes.append("0")
    return f"{prod.capitalize()}: " + " + ".join(partes)


def agregar_item_carrito(session, prod: str, cantidad: float, unidad: str):
    """
    Suma en el carrito respetando la unidad indicada por el cliente.
    Estructura interna: session['carrito'][prod] = {'kg': float, 'u': int}
    """
    entry = session["carrito"].setdefault(prod, {"kg": 0.0, "u": 0})
    if unidad == "kg":
        entry["kg"] = round(entry["kg"] + float(cantidad), 3)
    else:
        entry["u"] = int(entry["u"] + int(round(cantidad)))


def mostrar_carrito(session):
    if not session["carrito"]:
        return "Carrito vacío."
    lineas = []
    for prod, cantidades in session["carrito"].items():
        # Retrocompatibilidad: si fuese un número suelto antiguo, lo tratamos como kg
        if not isinstance(cantidades, dict):
            cantidades = {"kg": float(cantidades), "u": 0}
        lineas.append("• " + formatear_item(prod, cantidades))
    return "\n".join(lineas)

def formatear_fecha(dt):
    """Devuelve fecha en formato 'martes 13 de agosto - 15:00' (siempre en español)."""
    meses = [
        "enero","febrero","marzo","abril","mayo","junio",
        "julio","agosto","septiembre","octubre","noviembre","diciembre"
    ]
    dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    try:
        return f"{dias[dt.weekday()]} {dt.day} de {meses[dt.month-1]} - {dt.strftime('%H:%M')}"
    except Exception:
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year} {dt.strftime('%H:%M')}"

# Mapa de tramos del día a hora por defecto
PERIODOS = {
    "mañana": (9, 0),
    "manana": (9, 0),      # sin tilde
    "mediodia": (13, 0),
    "mediodía": (13, 0),
    "tarde": (16, 0),
    "noche": (20, 0),
}

def _proxima_semana(dow_target, hora, minuto):
    ahora = datetime.now()
    base = ahora.replace(second=0, microsecond=0)
    delta = (dow_target - base.weekday()) % 7
    fecha = base.replace(hour=hora, minute=minuto) + timedelta(days=delta)
    # si es hoy y ya pasó la hora, saltar a la semana siguiente
    if fecha <= ahora:
        fecha += timedelta(days=7)
    return fecha

def _fecha_dia_mes(day, hour, minute):
    """Devuelve datetime para 'el 20 a las 13', usando mes y año actuales; si ya pasó, siguiente mes."""
    ahora = datetime.now()
    y, m = ahora.year, ahora.month
    # intentar mes actual
    try:
        fecha = datetime(y, m, day, hour, minute)
    except ValueError:
        raise ValueError("Fecha inválida para este mes.")
    if fecha <= ahora:
        # siguiente mes
        m2 = m + 1
        y2 = y + 1 if m2 == 13 else y
        m2 = 1 if m2 == 13 else m2
        try:
            fecha = datetime(y2, m2, day, hour, minute)
        except ValueError:
            raise ValueError("Fecha inválida para el mes siguiente.")
    return fecha

def parse_dia_hora(texto: str):
    """
    Acepta:
      - hoy 15:00 / mañana 12:30 / pasado mañana 10 / hoy 9
      - hoy a las 15 / mañana a las 12:00 / pasado mañana al mediodía
      - (este|próximo|el)? viernes (a las)? 14(:30)? / viernes por la tarde
      - lunes 15:00 / miércoles 9 / miércoles por la mañana
      - 13/08 15:00 / 13-08 15 / 13/08/2025 15:00
      - el 20 a las 13(:30)? / el 20 por la tarde
    Devuelve datetime futuro. Lanza ValueError si no puede parsear o si es pasado.
    """
    s = texto.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # normalizar 'próximo' a 'proximo' por si acaso
    s = s.replace("próximo", "proximo").replace("míercoles", "miércoles").replace("mediodia", "mediodía")

    # OJO: tu normalizador puede convertir "mañana a las 12" en "12:00 mañana"
    s = normalizar_fecha_texto(s)

    ahora = datetime.now()

    def _hhmm(hh, mm=None):
        h = int(hh)
        m = int(mm) if mm is not None else 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Hora inválida.")
        return h, m

    # Caso especial: "a las HH(:MM)?" sin día explícito
    m = re.match(r"^a\s+las\s+(\d{1,2})(?::([0-5]\d))?$", s)
    if m:
        hh, mm = m.groups()
        hh, mm = _hhmm(hh, mm)
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        # si ya pasó hoy, lo ponemos mañana
        if fecha <= ahora:
            fecha += timedelta(days=1)
        return fecha


    # 0) hoy/mañana/pasado mañana con tramo del día (incluye 'por la' y 'al')
    m = re.match(r"^(hoy|mañana|pasado mañana)(?:\s+(?:por\s+la|al))?\s+(mañana|tarde|noche|mediod[ií]a)$", s)
    if m:
        when, periodo = m.groups()
        h, mi = PERIODOS[periodo.replace("í", "i")]
        dias_sumar = 0 if when == "hoy" else (1 if when == "mañana" else 2)
        fecha = ahora.replace(second=0, microsecond=0, hour=h, minute=mi) + timedelta(days=dias_sumar)
        if fecha <= ahora:
            raise ValueError("La fecha y hora deben ser futuras.")
        return fecha

    # 1) hoy/mañana/pasado mañana (a las)? HH(:MM)?
    m = re.match(r"^(hoy|mañana|pasado mañana)(?:\s+(?:a\s+las)?)?\s+(\d{1,2})(?::([0-5]\d))?$", s)
    if m:
        palabra, hh, mm = m.groups()
        hh, mm = _hhmm(hh, mm)
        dias = 0 if palabra == "hoy" else (1 if palabra == "mañana" else 2)
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=dias)
        if fecha <= ahora:
            raise ValueError("La fecha y hora deben ser futuras.")
        return fecha

    # 1bis) HH(:MM)? (hoy|mañana|pasado mañana)  <-- por la normalización "12:00 mañana"
    m = re.match(r"^(\d{1,2})(?::([0-5]\d))?\s+(hoy|mañana|pasado mañana)$", s)
    if m:
        hh, mm, palabra = m.groups()
        hh, mm = _hhmm(hh, mm)
        dias = 0 if palabra == "hoy" else (1 if palabra == "mañana" else 2)
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=dias)
        if fecha <= ahora:
            raise ValueError("La fecha y hora deben ser futuras.")
        return fecha

    # Diccionario días de la semana
    dias = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
    }

    # 2a) (este|proximo|el)? <dia_semana> (a las)? HH(:MM)?
    m = re.match(
        r"^(?:este|proximo|el)?\s*(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)"
        r"(?:\s*(?:a\s+las)?)?\s+(\d{1,2})(?::([0-5]\d))?$", s
    )
    if m:
        dia_txt, hh, mm = m.groups()
        hh, mm = _hhmm(hh, mm)
        return _proxima_semana(dias[dia_txt], hh, mm)

    # 2b) (este|proximo|el)? <dia_semana> (por la|al)? <periodo>
    m = re.match(
        r"^(?:este|proximo|el)?\s*(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)"
        r"(?:\s+(?:por\s+la|al))?\s+(mañana|tarde|noche|mediod[ií]a)$", s
    )
    if m:
        dia_txt, periodo = m.groups()
        h, mi = PERIODOS[periodo.replace("í", "i")]
        return _proxima_semana(dias[dia_txt], h, mi)

    # 3) dd/mm(/yyyy)? HH(:MM)?  o con guiones
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\s+(\d{1,2})(?::([0-5]\d))?$", s)
    if m:
        dd, mm_, yyyy, hh, mm2 = m.groups()
        hh, mm_2 = _hhmm(hh, mm2)
        year = int(yyyy) if yyyy else ahora.year
        try:
            fecha = datetime(int(year), int(mm_), int(dd), hh, mm_2)
        except ValueError:
            raise ValueError("Fecha inválida. Revisa día/mes.")
        if fecha <= ahora:
            raise ValueError("La fecha y hora deben ser futuras.")
        return fecha

    # 4a) el <día_mes> (a las)? HH(:MM)?
    m = re.match(r"^el\s+(\d{1,2})(?:\s*(?:a\s+las)?)?\s+(\d{1,2})(?::([0-5]\d))?$", s)
    if m:
        dia_mes, hh, mm = m.groups()
        hh, mm = _hhmm(hh, mm)
        return _fecha_dia_mes(int(dia_mes), hh, mm)

    # 4b) el <día_mes> (por la|al)? <periodo>
    m = re.match(r"^el\s+(\d{1,2})(?:\s+(?:por\s+la|al))?\s+(mañana|tarde|noche|mediod[ií]a)$", s)
    if m:
        dia_mes, periodo = m.groups()
        h, mi = PERIODOS[periodo.replace("í", "i")]
        return _fecha_dia_mes(int(dia_mes), h, mi)
    
        # 5) Solo hora suelta (ej: "20", "20:30") -> hoy a esa hora (si pasó, mañana)
    m = re.match(r"^(\d{1,2})(?::([0-5]\d))?$", s)
    if m:
        hh, mm = m.groups()
        hh, mm = _hhmm(hh, mm)
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if fecha <= ahora:
            fecha += timedelta(days=1)  # si ya pasó hoy, pasa a mañana
        return fecha


    raise ValueError("Formato no reconocido.")

    


    

def extraer_nombre(raw_text: str) -> str:
    """
    Extrae el nombre del usuario a partir de frases como:
    - "mi nombre es Pablo"
    - "me llamo María José"
    - "hola, soy Ana"
    - "Pablo"
    Devuelve como máximo 3 palabras, sin signos, capitalizadas.
    """
    if not raw_text:
        return "Cliente"
    txt = raw_text.strip()
    lower = txt.lower()

    patrones = [
        r"(?:^|\b)(?:mi\s+nombre\s+es)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)(?:me\s+llamo)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)(?:soy)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)hola[,!.\s]*soy\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)hola[,!.\s]*me\s+llamo\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)buenas[,!.\s]*soy\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
    ]

    for patron in patrones:
        m = re.search(patron, lower)
        if m:
            start, end = m.span(1)
            candidato = txt[start:end]
            break
    else:
        sin_saludo = re.sub(r"^(hola|buenas|buenos\s+días|buenas\s+tardes|buenas\s+noches)[,!\s]+", "", lower, flags=re.I)
        if sin_saludo != lower:
            offset = len(lower) - len(sin_saludo)
            txt = txt[offset:]
            lower = sin_saludo
        m = re.match(r"([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})", lower)
        candidato = txt[m.start(1):m.end(1)] if m else txt

    candidato = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-]", "", candidato)
    candidato = re.sub(r"\s+", " ", candidato).strip()
    palabras = candidato.split()
    palabras = palabras[:3] if palabras else ["Cliente"]
    nombre = " ".join(p.capitalize() for p in palabras)
    return nombre if nombre else "Cliente"

def process_message(data):
    try:
        user_id = data.get("user_id")
        raw_message = data.get("message", "").strip()
        msg = raw_message.lower()

        if not user_id:
            return "Error: usuario no identificado."

        # Crear sesión si no existe
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {
                "modo": None,
                "paso": 0,
                "carrito": {},
                "msg_count": 0
            }

        session = SESSIONS[user_id]

        # --- VOLVER ATRÁS ---
        if "volver atras" in msg and session["modo"] == "pedido":
            if session["paso"] > 1:
                if session["paso"] == 2:
                    session.pop("nombre", None)
                    session["paso"] = 1
                    return "Has vuelto atrás ↩️. Vamos de nuevo.\n¿Cuál es tu nombre?"
                elif session["paso"] == 3:
                    session.pop("hora", None)
                    session["paso"] = 2
                    return ("Has vuelto atrás ↩️. Por favor, indícanos *día y hora*.\n"
                            "Ejemplos: 'martes 15:00', '13/08 15:00', 'mañana 12:30', 'este viernes a las 14', 'el 20 por la tarde', 'pasado mañana 10:00'.")
                elif session["paso"] == 4:
                    session["paso"] = 3
                    return f"Has vuelto atrás ↩️. Lista actual:\n{mostrar_carrito(session)}\nDime si quieres añadir o quitar algo."
            else:
                return "No puedes retroceder más, estamos al inicio del pedido."
            

        # --- INICIAR PEDIDO ---
        if "iniciar pedido" in msg:
            session.clear()
            session.update({"modo": "pedido", "paso": 1, "carrito": {}, "msg_count": 0})
            return "Genial 👍. Vamos a empezar tu pedido.\n¿Cuál es tu nombre?"

        # --- MODO LIBRE ---
        if session["modo"] is None:
            session["msg_count"] += 1
            if session["msg_count"] == 1:
                return (
                    "Hola 😊. Bienvenido a la carnicería.\n"
                    "⏰ *Horario*: Lunes a Sábado de 9:00 a 14:00 y de 17:00 a 20:00.\n"
                    "Puedes escribirme lo que quieras y te atenderemos lo antes posible.\n"
                    "Cuando quieras encargar algo, simplemente escribe *'iniciar pedido'*."
                )
            elif session["msg_count"] % 3 == 0:
                return "Recuerda que para encargar algo debes escribir *'iniciar pedido'*."
            

        # --- MODO PEDIDO ---
        if session["modo"] == "pedido":

            # Paso 1: Nombre
            if session["paso"] == 1:
                session["nombre"] = extraer_nombre(raw_message)
                session["paso"] = 2
                return ("Perfecto, {nombre} 😊. ¿Cuándo pasarás a recoger tu pedido?\n"
                        ).format(nombre=session["nombre"])

            # Paso 2: Día y hora
            if session["paso"] == 2:
                try:
                    fecha = parse_dia_hora(msg)
                    session["hora"] = fecha  # guardamos datetime completo
                    session["paso"] = 3

                    # ✅ PRODUCTOS_DB es lista, no dict
                    catalogo = "\n".join([f"- {prod}" for prod in PRODUCTOS_DB])
                    return (
                        f"Perfecto. Programado para *{formatear_fecha(session['hora'])}*.\n\n"
                        "Dime qué quieres y la cantidad.\n"
                        "Para eliminar un producto: 'eliminar pollo'.\n"
                        "Cuando termines, escribe 'listo'."
                    )
                except ValueError as e:
                    return (f"{str(e)}\n"
                            "Por favor, indica *día y hora* con uno de estos formatos:\n"
                            "• martes a las 15:00\n"
                            "• 13/08 15:00\n"
                            "• mañana a las 12:30\n"
                            "• este viernes por la tarde\n")

            # utils.py (ejemplo de flujo de añadir/eliminar productos al carrito)
            if session["paso"] == 3:
                # 🔹 Extraer productos del mensaje
                encontrados = extraer_productos_desde_texto(msg, PRODUCTOS_DB)  # [(prod_crudo, cantidad, unidad), ...]

                # Acumuladores para respuesta compuesta
                añadidos = []          # strings formateados para confirmar adición
                ambiguos = []          # [(prod_crudo, opciones_list), ...]
                no_encontrados = []    # [(prod_crudo, sugerencias_list), ...]

                if encontrados:
                    for prod, cantidad, unidad in encontrados:
                        if isinstance(prod, (list, tuple)):
                            prod = " ".join(str(x) for x in prod)

                        # 🔹 Canonicalización + normalización
                        prod_real = _canonicalizar_producto(prod, PRODUCTOS_DB)

                        # Caso 1: coincidencia clara
                        if isinstance(prod_real, str):
                            try:
                                cantidad_num = float(cantidad)
                            except Exception:
                                cantidad_num = float(_NUM_TXT.get(str(cantidad).strip().lower(), 0))

                            agregar_item_carrito(session, prod_real, cantidad_num, unidad)
                            añadidos.append(formatear_item_simple(prod_real, cantidad_num, unidad))

                        # Caso 2: ambigüedad -> devolver opciones al final
                        elif isinstance(prod_real, list):
                            opciones = []
                            def _flatten(x):
                                if x is None:
                                    return
                                if isinstance(x, str):
                                    opciones.append(x)
                                elif isinstance(x, (list, tuple)):
                                    for e in x:
                                        _flatten(e)
                                else:
                                    opciones.append(str(x))
                            _flatten(prod_real)
                            opciones = [o for o in opciones if o]
                            if opciones:
                                ambiguos.append((prod, opciones))
                            else:
                                sugerencias = [x[0] for x in process.extract(prod, PRODUCTOS_DB, limit=3)]
                                no_encontrados.append((prod, sugerencias))

                        # Caso 3: no encontrado -> sugerencias fuzzy
                        else:
                            sugerencias = [x[0] for x in process.extract(prod, PRODUCTOS_DB, limit=3)]
                            no_encontrados.append((prod, sugerencias))

                # Construir respuesta compuesta si hubo actividad de añadir
                partes = []
                if añadidos:
                    partes.append(f"{', '.join(añadidos)} añadido(s).\nCarrito actual:\n{mostrar_carrito(session)}")

                for prod_crudo, opciones in ambiguos:
                    partes.append(f"No estoy seguro sobre '{prod_crudo}'. ¿Te refieres a alguno de estos?: {', '.join(opciones)}")

                for prod_crudo, sugest in no_encontrados:
                    if sugest:
                        partes.append(f"No encontré '{prod_crudo}'. ¿Quizás quisiste decir: {', '.join(sugest)}?")
                    else:
                        partes.append(f"No he encontrado nada parecido a '{prod_crudo}'.")

                if partes:
                    return "\n".join(partes)

                # >>> Manejar eliminar productos (soporta varios items en la misma frase)
                if re.match(r"^(eliminar|elimina|quita|borra)\b", msg):
                    texto_eliminar = re.sub(r"^(eliminar|elimina|quita|borra)\s+", "", msg).strip()
                    items_a_eliminar = extraer_productos_desde_texto(texto_eliminar, PRODUCTOS_DB)

                    if not items_a_eliminar:
                        return "No entendí qué producto quieres eliminar."

                    eliminados_ok = []        # productos eliminados
                    not_in_cart = []          # productos que no estaban en carrito
                    ambiguos_elim = []        # productos ambiguos
                    no_encontrados_elim = []  # productos no encontrados

                    for prod, cantidad, unidad in items_a_eliminar:
                        if isinstance(prod, (list, tuple)):
                            prod = " ".join(str(x) for x in prod)

                        prod_real = _canonicalizar_producto(prod, PRODUCTOS_DB)

                        # Ambigüedad -> sugerir
                        if isinstance(prod_real, list):
                            opciones = []
                            def _flatten2(x):
                                if x is None:
                                    return
                                if isinstance(x, str):
                                    opciones.append(x)
                                elif isinstance(x, (list, tuple)):
                                    for e in x:
                                        _flatten2(e)
                                else:
                                    opciones.append(str(x))
                            _flatten2(prod_real)
                            opciones = [o for o in opciones if o]
                            ambiguos_elim.append((prod, opciones))
                            continue

                        # No encontrado
                        if not prod_real:
                            sugerencias = [x[0] for x in process.extract(prod, PRODUCTOS_DB, limit=3)]
                            no_encontrados_elim.append((prod, sugerencias))
                            continue

                        if prod_real not in session.get("carrito", {}):
                            not_in_cart.append(prod_real)
                            continue

                        try:
                            cantidad_num = float(cantidad)
                        except Exception:
                            cantidad_num = float(_NUM_TXT.get(str(cantidad).strip().lower(), 0))

                        current_qty, current_unit = session["carrito"][prod_real]

                        try:
                            current_qty = float(current_qty)
                        except Exception:
                            try:
                                current_qty = float(str(current_qty).replace(",", "."))
                            except Exception:
                                current_qty = 0.0

                        if current_unit != unidad:
                            session["carrito"].pop(prod_real, None)
                            eliminados_ok.append(f"{prod_real} (todo)")
                        else:
                            if cantidad_num <= 0 or cantidad_num >= current_qty:
                                session["carrito"].pop(prod_real, None)
                                eliminados_ok.append(f"{prod_real} (todo)")
                            else:
                                nueva = round(current_qty - cantidad_num, 3)
                                session["carrito"][prod_real] = (nueva, current_unit)
                                eliminados_ok.append(f"{prod_real} ({cantidad_num}{current_unit})")

                    partes_del = []
                    if eliminados_ok:
                        partes_del.append(f"{', '.join(eliminados_ok)} eliminado(s) del carrito.\nCarrito actual:\n{mostrar_carrito(session)}")
                    if not_in_cart:
                        partes_del.append(f"No tenías en el carrito: {', '.join(not_in_cart)}")
                    for prod, opciones in ambiguos_elim:
                        partes_del.append(f"No estoy seguro sobre '{prod}' al eliminar. ¿Te refieres a alguno de estos?: {', '.join(opciones)}")
                    for prod, sugest in no_encontrados_elim:
                        if sugest:
                            partes_del.append(f"No encontré '{prod}'. ¿Quizás quisiste decir: {', '.join(sugest)}?")
                        else:
                            partes_del.append(f"No he encontrado nada parecido a '{prod}'.")

                    return "\n".join(partes_del)

                # >>> Manejar "listo"
                if msg == "listo":
                    if not session["carrito"]:
                        return "No has añadido ningún producto. Añade al menos uno antes de decir 'listo'."
                    session["paso"] = 4
                    carrito_formateado = mostrar_carrito(session)
                    return (f"Este es tu pedido para *{formatear_fecha(session['hora'])}*:\n"
                            f"{carrito_formateado}\n"
                            "Escribe 'confirmar' para finalizar o 'cancelar' para anular.")

                return "Formato no válido. Ejemplo: '2 kilos de pollo' o '2 hamburguesas'."








            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in msg:
                    resumen = (
                        f"✅ *Pedido confirmado*\n"
                        f"👤 Cliente: {session['nombre']}\n"
                        f"🕒 Hora: {formatear_fecha(session['hora'])}\n"
                        f"🛒 Carrito:\n{mostrar_carrito(session)}\n"
                    )
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return resumen
                elif "cancelar" in msg:
                    SESSIONS.pop(user_id, None)
                    return "Pedido cancelado ❌."
                else:
                    return "Responde con 'confirmar' o 'cancelar'."

        return "No entendí tu mensaje 🤔."

    except Exception:
        logging.exception("Error en process_message")
        return "Hubo un error interno procesando tu mensaje."