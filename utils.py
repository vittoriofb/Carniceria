import logging
import re
from datetime import datetime, timedelta
import locale
from printer import send_to_printer
from data import PRODUCTOS_DB

# Intentar locale español para nombres de día/mes
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except Exception:
    pass

SESSIONS = {}

def mostrar_carrito(session):
    """Devuelve un string con el contenido actual del carrito."""
    if not session["carrito"]:
        return "Carrito vacío."
    return "\n".join([
        f"• {prod.capitalize()}: {cant} kg — {cant * PRODUCTOS_DB[prod]:.2f}€"
        for prod, cant in session["carrito"].items()
    ])

def formatear_fecha(dt: datetime) -> str:
    """Devuelve fecha en formato 'martes 13 de agosto - 15:00'."""
    try:
        return dt.strftime("%A %d de %B - %H:%M").capitalize()
    except Exception:
        # Fallback si no hay locale
        meses = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        return f"{dias[dt.weekday()]} {dt.day} de {meses[dt.month-1]} - {dt.strftime('%H:%M')}"

def parse_dia_hora(texto: str) -> datetime:
    """
    Acepta:
      - 'martes 15:00' (día de semana + hora)
      - 'hoy 15:00', 'mañana 12:30'
      - '13/08 15:00', '13-08 15:00', '13/08/2025 15:00'
    Devuelve datetime en el futuro.
    Lanza ValueError si no puede parsear o si es pasado.
    """
    s = texto.strip().lower()

    # Normalizar separadores
    s = re.sub(r"\s+", " ", s)

    ahora = datetime.now()

    # 1) hoy/mañana
    m = re.match(r"^(hoy|mañana)\s+(\d{1,2}):([0-5]\d)$", s)
    if m:
        palabra, hh, mm = m.groups()
        hh, mm = int(hh), int(mm)
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if palabra == "mañana":
            fecha += timedelta(days=1)
        # si es hoy y ya pasó, error (pedir futuro)
        if fecha <= ahora:
            raise ValueError("La hora debe ser futura.")
        return fecha

    # 2) día de la semana + hora
    dias = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
    }
    m = re.match(r"^(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s+(\d{1,2}):([0-5]\d)$", s)
    if m:
        dia_txt, hh, mm = m.groups()
        objetivo = dias[dia_txt]
        hh, mm = int(hh), int(mm)

        # Próxima ocurrencia de ese día
        delta_dias = (objetivo - ahora.weekday()) % 7
        fecha = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        fecha += timedelta(days=delta_dias)

        # Si es hoy y ya pasó la hora, ir a la semana siguiente
        if fecha <= ahora:
            fecha += timedelta(days=7)
        return fecha

    # 3) fecha dd/mm(/yyyy)? + hora
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\s+(\d{1,2}):([0-5]\d)$", s)
    if m:
        dd, mm, yyyy, hh = m.group(1), m.group(2), m.group(3), m.group(4)
        min_str = m.group(5) if m.lastindex >= 5 else s[-2:]  # robustez
        dd, mm, hh, min_ = int(dd), int(mm), int(hh), int(min_str)
        year = int(yyyy) if yyyy else ahora.year

        try:
            fecha = datetime(year, mm, dd, hh, min_)
        except ValueError:
            raise ValueError("Fecha inválida. Usa formato válido (p. ej. 13/08 15:00).")

        if fecha <= ahora:
            raise ValueError("La fecha y hora deben ser futuras.")
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
                            "Ejemplos: 'martes 15:00', '13/08 15:00', 'mañana 12:30'.")
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
                    "Puedes escribirme lo que quieras sin necesidad de iniciar un pedido.\n"
                    "Cuando quieras encargar algo, simplemente escribe *'iniciar pedido'*."
                )
            elif session["msg_count"] % 3 == 0:
                return "Recuerda que para encargar algo debes escribir *'iniciar pedido'*."
            else:
                return "Estoy aquí para ayudarte 😊."

        # --- MODO PEDIDO ---
        if session["modo"] == "pedido":

            # Paso 1: Nombre
            if session["paso"] == 1:
                session["nombre"] = extraer_nombre(raw_message)
                session["paso"] = 2
                return ("Perfecto, {nombre} 😊. ¿Qué *día y hora* pasarás a recoger tu pedido?\n"
                        "Ejemplos: 'martes 15:00', '13/08 15:00', 'mañana 12:30'."
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
                        "Dime qué quieres y cuántos kilos. Ejemplo: 'pollo 2 kg'.\n"
                        "Para eliminar un producto: 'eliminar pollo'.\n"
                        "Cuando termines, escribe 'listo'."
                    )
                except ValueError as e:
                    return (f"{str(e)}\n"
                            "Por favor, indica *día y hora* con uno de estos formatos:\n"
                            "• martes 15:00\n"
                            "• 13/08 15:00\n"
                            "• mañana 12:30")

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
                            f"💰 Total: {total:.2f}€\n"
                            "Escribe 'confirmar' para finalizar o 'cancelar' para anular.")

                match = re.match(r"([a-záéíóúñü ]+)\s+(\d+(?:\.\d+)?)\s*kg", msg)
                if match:
                    producto = match.group(1).strip()
                    cantidad = float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return f"{producto} añadido ({cantidad} kg).\nCarrito actual:\n{mostrar_carrito(session)}"
                    else:
                        return "Ese producto no está en el catálogo."

                return "Formato no válido. Ejemplo: 'pollo 2 kg'. O escribe 'listo' si has terminado."

            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in msg:
                    resumen = (
                        f"✅ *Pedido confirmado*\n"
                        f"👤 Cliente: {session['nombre']}\n"
                        f"🕒 Hora: {formatear_fecha(session['hora'])}\n"
                        f"🛒 Carrito:\n{mostrar_carrito(session)}\n"
                        f"💰 Total Estimado: {session['total']:.2f}€"
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
