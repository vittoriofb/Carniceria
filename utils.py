# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta

from printer import send_to_printer
from data import PRODUCTOS_DB

# >>> NUEVO: utilidades de expresiones (no cambian la lógica, solo amplían la comprensión)
from expresiones import normalizar_fecha_texto, extraer_productos_desde_texto
# <<<

SESSIONS = {}

def mostrar_carrito(session):
    if not session["carrito"]:
        return "Carrito vacío."
    lineas = []
    for prod, cant in session["carrito"].items():
        lineas.append(f"• {prod.capitalize()}: {cant} kg")
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

                    catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                    return (
                        f"Perfecto. Programado para *{formatear_fecha(session['hora'])}*.\n\n"
                        f"Estos son nuestros productos:\n{catalogo}\n\n"
                        "Dime qué quieres y la cantidad.\n"
                        "Para eliminar un producto: 'eliminar pollo'.\n"
                        "Cuando termines, escribe 'listo'."
                    )
                except ValueError as e:
                    return (f"{str(e)}\n"
                            "Por favor, indica *día y hora* con uno de estos formatos:\n"
                            "• martes 15:00\n"
                            "• 13/08 15:00\n"
                            "• mañana 12:30\n"
                            "• este viernes por la tarde\n"
                            "• el 20 por la tarde\n"
                            "• pasado mañana 10:00")

            # Paso 3: Añadir o eliminar productos
            if session["paso"] == 3:

                if msg.startswith("eliminar "):
                    producto = msg.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return f"{producto} eliminado del carrito.\nCarrito actual:\n{mostrar_carrito(session)}"
                    else:
                        return f"No tienes {producto} en tu carrito."

                if msg == "listo":
                    if not session["carrito"]:
                        return "No has añadido ningún producto. Añade al menos uno antes de decir 'listo'."
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    return (f"Este es tu pedido para *{formatear_fecha(session['hora'])}*:\n"
                            f"{mostrar_carrito(session)}\n"
                            "Escribe 'confirmar' para finalizar o 'cancelar' para anular.")

                # >>> NUEVO: detectar múltiples productos en un solo mensaje
                encontrados = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if encontrados:
                    for prod, cantidad in encontrados:
                        if prod in PRODUCTOS_DB:
                            session["carrito"][prod] = session["carrito"].get(prod, 0) + float(cantidad)
                    if encontrados:
                        añadido = ", ".join(f"{p} ({c} kg)" for p, c in encontrados)
                        return f"{añadido} añadido.\nCarrito actual:\n{mostrar_carrito(session)}"

                # Tu patrón original
                match = re.match(r"([a-záéíóúñü ]+)\s+(\d+(?:\.\d+)?)\s*kg", msg)
                if match:
                    producto = match.group(1).strip()
                    cantidad = float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return f"{producto} añadido ({cantidad} kg).\nCarrito actual:\n{mostrar_carrito(session)}"
                    else:
                        return "Ese producto no está en el catálogo."

                # Último intento con producto único flexible
                unico = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if len(unico) == 1:
                    producto, cantidad = unico[0]
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + float(cantidad)
                        return f"{producto} añadido ({cantidad} kg).\nCarrito actual:\n{mostrar_carrito(session)}"

                return "Formato no válido. Ejemplo: 'pollo 2 kg'. O escribe 'listo' si has terminado."

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