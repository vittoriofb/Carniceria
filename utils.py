# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta
import locale

from printer import send_to_printer
from data import PRODUCTOS_DB

# >>> NUEVO: utilidades de expresiones (no cambian la lógica, solo amplían la comprensión)
from expresiones import normalizar_fecha_texto, extraer_productos_desde_texto
# <<<

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

def formatear_fecha(dt):
    """Devuelve fecha en formato español 'martes 13 de agosto - 15:00'."""
    try:
        # Con locale en español
        return dt.strftime("%A %d de %B - %H:%M").capitalize()
    except Exception:
        # Fallback manual
        meses = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
        dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        return f"{dias[dt.weekday()]} {dt.day} de {meses[dt.month-1]} - {dt.strftime('%H:%M')}"

# Mapa de tramos del día a hora por defecto
PERIODOS = {
    "mañana": (9, 0),
    "manana": (9, 0),      # sin tilde
    "mediodia": (13, 0),
    "mediodía": (13, 0),
    "tarde": (16, 0),
    "noche": (20, 0),
}

# ... (no se cambia nada del parser ni demás funciones) ...

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
                    return "↩️ Volvemos. ¿Cuál es tu nombre?"
                elif session["paso"] == 3:
                    session.pop("hora", None)
                    session["paso"] = 2
                    return "↩️ Volvemos. Indica día y hora para recoger el pedido."
                elif session["paso"] == 4:
                    session["paso"] = 3
                    return f"↩️ Volvemos. Carrito actual:\n{mostrar_carrito(session)}\n¿Quieres añadir o quitar algo?"
            else:
                return "Ya estamos al inicio del pedido."

        # --- INICIAR PEDIDO ---
        if "iniciar pedido" in msg:
            session.clear()
            session.update({"modo": "pedido", "paso": 1, "carrito": {}, "msg_count": 0})
            return "👍 Empezamos tu pedido.\n¿Cuál es tu nombre?"

        # --- MODO LIBRE ---
        if session["modo"] is None:
            session["msg_count"] += 1
            if session["msg_count"] == 1:
                return (
                    "Hola 👋 Bienvenido a la carnicería.\n"
                    "Horario: L-S 9:00-14:00 y 17:00-20:00.\n"
                    "Para encargar algo escribe *iniciar pedido*."
                )
            elif session["msg_count"] % 3 == 0:
                return "Recuerda: escribe *iniciar pedido* para encargar algo."
            else:
                return "¿En qué te ayudo? 😊"

        # --- MODO PEDIDO ---
        if session["modo"] == "pedido":

            # Paso 1: Nombre
            if session["paso"] == 1:
                session["nombre"] = extraer_nombre(raw_message)
                session["paso"] = 2
                return f"Perfecto, {session['nombre']} 😊.\n¿Cuándo pasarás a recoger tu pedido?"

            # Paso 2: Día y hora
            if session["paso"] == 2:
                try:
                    fecha = parse_dia_hora(msg)
                    session["hora"] = fecha
                    session["paso"] = 3

                    catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                    return (
                        f"👌 Anotado para *{formatear_fecha(session['hora'])}*.\n"
                        f"Productos disponibles:\n{catalogo}\n\n"
                        "Dime qué quieres y cuántos kilos (ej: pollo 2 kg).\n"
                        "Cuando termines, escribe *listo*."
                    )
                except ValueError as e:
                    return f"{str(e)}\nIndica día y hora de nuevo, por favor."

            # Paso 3: Añadir o eliminar productos
            if session["paso"] == 3:

                if msg.startswith("eliminar "):
                    producto = msg.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return f"❌ {producto} eliminado.\nCarrito:\n{mostrar_carrito(session)}"
                    else:
                        return f"No tienes {producto} en el carrito."

                if msg == "listo":
                    if not session["carrito"]:
                        return "No has añadido nada aún. Agrega al menos un producto."
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    return (
                        f"📝 Pedido para *{formatear_fecha(session['hora'])}*:\n"
                        f"{mostrar_carrito(session)}\n"
                        f"Total: {total:.2f}€\n"
                        "Escribe *confirmar* para cerrar el pedido o *cancelar* para anular."
                    )

                encontrados = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if encontrados:
                    for prod, cantidad in encontrados:
                        if prod in PRODUCTOS_DB:
                            session["carrito"][prod] = session["carrito"].get(prod, 0) + float(cantidad)
                    if encontrados:
                        añadido = ", ".join(f"{p} ({c} kg)" for p, c in encontrados)
                        return f"✅ {añadido} añadido.\nCarrito:\n{mostrar_carrito(session)}"

                match = re.match(r"([a-záéíóúñü ]+)\s+(\d+(?:\.\d+)?)\s*kg", msg)
                if match:
                    producto = match.group(1).strip()
                    cantidad = float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return f"✅ {producto} añadido ({cantidad} kg).\nCarrito:\n{mostrar_carrito(session)}"
                    else:
                        return "Ese producto no está en el catálogo."

                unico = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if len(unico) == 1:
                    producto, cantidad = unico[0]
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + float(cantidad)
                        return f"✅ {producto} añadido ({cantidad} kg).\nCarrito:\n{mostrar_carrito(session)}"

                return "Formato no válido. Ejemplo: pollo 2 kg. O escribe *listo*."

            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in msg:
                    resumen = (
                        f"✅ Pedido confirmado\n"
                        f"👤 {session['nombre']}\n"
                        f"🕒 {formatear_fecha(session['hora'])}\n"
                        f"🛒\n{mostrar_carrito(session)}\n"
                        f"Total: {session['total']:.2f}€"
                    )
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return resumen
                elif "cancelar" in msg:
                    SESSIONS.pop(user_id, None)
                    return "❌ Pedido cancelado."
                else:
                    return "Responde con *confirmar* o *cancelar*."

        return "No entendí tu mensaje 🤔."

    except Exception:
        logging.exception("Error en process_message")
        return "Hubo un error interno procesando tu mensaje."
