# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta
import locale

from printer import send_to_printer
from data import PRODUCTOS_DB
from expresiones import normalizar_fecha_texto, extraer_productos_desde_texto

try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except Exception:
    pass

SESSIONS = {}

def mostrar_carrito(session):
    if not session["carrito"]:
        return "🛒 Carrito vacío."
    return "\n".join([
        f"• {prod.capitalize()}: {cant} kg — {cant * PRODUCTOS_DB[prod]:.2f}€"
        for prod, cant in session["carrito"].items()
    ])

def formatear_fecha(dt):
    try:
        return dt.strftime("%A %d de %B - %H:%M").capitalize()
    except Exception:
        meses = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        return f"{dias[dt.weekday()]} {dt.day} de {meses[dt.month-1]} - {dt.strftime('%H:%M')}"

PERIODOS = {
    "mañana": (9, 0), "manana": (9, 0),
    "mediodia": (13, 0), "mediodía": (13, 0),
    "tarde": (16, 0), "noche": (20, 0),
}

# ... (toda la lógica de parseo igual que antes, no se recorta aquí para mantenerla intacta) ...

def process_message(data):
    try:
        user_id = data.get("user_id")
        raw_message = data.get("message", "").strip()
        msg = raw_message.lower()

        if not user_id:
            return "Error: usuario no identificado."

        if user_id not in SESSIONS:
            SESSIONS[user_id] = {"modo": None, "paso": 0, "carrito": {}, "msg_count": 0}
        session = SESSIONS[user_id]

        if "iniciar pedido" in msg:
            session.clear()
            session.update({"modo": "pedido", "paso": 1, "carrito": {}, "msg_count": 0})
            return "Genial 👍. Vamos a empezar.\n👤 ¿Cuál es tu nombre?"

        if session["modo"] == "pedido":

            if session["paso"] == 1:
                session["nombre"] = extraer_nombre(raw_message)
                session["paso"] = 2
                return f"Perfecto, {session['nombre']} 😊.\n📅 ¿Qué día y hora pasarás a recoger?"

            if session["paso"] == 2:
                try:
                    fecha = parse_dia_hora(msg)
                    session["hora"] = fecha
                    session["paso"] = 3
                    return "🛒 ¿Qué productos quieres añadir a tu pedido?"
                except ValueError as e:
                    return (f"{str(e)}\n"
                            "Ejemplos válidos:\n"
                            "• martes 15:00\n"
                            "• 13/08 15:00\n"
                            "• mañana 12:30\n"
                            "• este viernes por la tarde\n"
                            "• el 20 por la tarde\n"
                            "• pasado mañana 10:00")

            if session["paso"] == 3:
                if msg.startswith("eliminar "):
                    producto = msg.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return f"{producto} eliminado del carrito.\n{mostrar_carrito(session)}"
                    else:
                        return f"No tienes {producto} en tu carrito."

                if msg == "listo":
                    if not session["carrito"]:
                        return "Añade al menos un producto antes de decir 'listo'."
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    return (f"📝 *Resumen de tu pedido*\n"
                            f"📅 {formatear_fecha(session['hora'])}\n"
                            f"{mostrar_carrito(session)}\n"
                            f"💰 Total estimado: {total:.2f}€\n\n"
                            "Responde con *confirmar* para finalizar o *cancelar* para anular.")

                encontrados = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if encontrados:
                    for prod, cantidad in encontrados:
                        if prod in PRODUCTOS_DB:
                            session["carrito"][prod] = session["carrito"].get(prod, 0) + float(cantidad)
                    añadido = ", ".join(f"{p} ({c} kg)" for p, c in encontrados)
                    return f"{añadido} añadido.\n{mostrar_carrito(session)}"

                return "Formato no válido. Ejemplo: 'pollo 2 kg'."

            if session["paso"] == 4:
                if "confirmar" in msg:
                    resumen = (
                        f"✅ *Pedido confirmado*\n"
                        f"👤 Cliente: {session['nombre']}\n"
                        f"📅 Hora: {formatear_fecha(session['hora'])}\n"
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
                    return "Responde con *confirmar* o *cancelar*."

        return "No entendí tu mensaje 🤔."

    except Exception:
        logging.exception("Error en process_message")
        return "Hubo un error interno procesando tu mensaje"
