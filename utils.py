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
        return "Carrito vacío."
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

PERIODOS = {"mañana": (9,0), "manana": (9,0), "mediodia": (13,0), "mediodía": (13,0), "tarde": (16,0), "noche": (20,0)}

# --- funciones auxiliares de fecha (igual que antes, no las toco) ---
def _proxima_semana(dow_target, hora, minuto): ...
def _fecha_dia_mes(day, hour, minute): ...
def parse_dia_hora(texto: str): ...
def extraer_nombre(raw_text: str) -> str: ...

def process_message(data):
    try:
        user_id = data.get("user_id")
        raw_message = data.get("message", "").strip()
        msg = raw_message.lower()
        if not user_id: return "Error: usuario no identificado."

        if user_id not in SESSIONS:
            SESSIONS[user_id] = {"modo": None, "paso": 0, "carrito": {}, "msg_count": 0}
        session = SESSIONS[user_id]

        # VOLVER ATRÁS
        if "volver atras" in msg and session["modo"] == "pedido":
            if session["paso"] > 1:
                if session["paso"] == 2:
                    session.pop("nombre", None); session["paso"] = 1
                    return "↩️ Volvemos atrás. ¿Cuál es tu nombre?"
                elif session["paso"] == 3:
                    session.pop("hora", None); session["paso"] = 2
                    return "↩️ Volvemos atrás. Indica el *día y hora* de recogida."
                elif session["paso"] == 4:
                    session["paso"] = 3
                    return f"↩️ Volvemos atrás. Carrito actual:\n{mostrar_carrito(session)}"
            else:
                return "Ya estás al inicio del pedido."

        # INICIAR PEDIDO
        if "iniciar pedido" in msg:
            session.clear(); session.update({"modo":"pedido","paso":1,"carrito":{},"msg_count":0})
            return "Genial 👍. Empecemos.\n¿Cuál es tu nombre?"

        # MODO LIBRE
        if session["modo"] is None:
            session["msg_count"] += 1
            if session["msg_count"] == 1:
                return ("Hola 😊 Bienvenido a la carnicería.\n"
                        "🕘 Horario: Lunes a Sábado 9:00-14:00 / 17:00-20:00.\n"
                        "Escribe *'iniciar pedido'* para encargar.")
            elif session["msg_count"] % 3 == 0:
                return "Recuerda: para pedir escribe *'iniciar pedido'*."
            else:
                return "Estoy aquí para ayudarte 😊."

        # MODO PEDIDO
        if session["modo"] == "pedido":
            # Paso 1: Nombre
            if session["paso"] == 1:
                session["nombre"] = extraer_nombre(raw_message)
                session["paso"] = 2
                return f"Perfecto, {session['nombre']} 😊. ¿Qué día y hora recogerás tu pedido?"

            # Paso 2: Día y hora
            if session["paso"] == 2:
                try:
                    fecha = parse_dia_hora(msg)
                    session["hora"] = fecha; session["paso"] = 3
                    catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                    return (f"Perfecto. Lo programé para *{formatear_fecha(session['hora'])}*.\n\n"
                            f"Catálogo:\n{catalogo}\n\n"
                            "Dime qué productos y cuántos kilos quieres. Ej: 'pollo 2 kg'.\n"
                            "Cuando termines, escribe 'listo'.")
                except ValueError as e:
                    return (f"{str(e)}\n"
                            "Formato no válido. Ejemplos:\n"
                            "- martes 15:00\n- 13/08 15:00\n- mañana 12:30")

            # Paso 3: Productos
            if session["paso"] == 3:
                if msg.startswith("eliminar "):
                    producto = msg.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return f"{producto} eliminado.\nCarrito:\n{mostrar_carrito(session)}"
                    else:
                        return f"No tienes {producto} en tu carrito."

                if msg == "listo":
                    if not session["carrito"]:
                        return "Aún no has añadido nada."
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total; session["paso"] = 4
                    return (f"Resumen del pedido para *{formatear_fecha(session['hora'])}*:\n"
                            f"{mostrar_carrito(session)}\n"
                            f"Total: {total:.2f}€\n"
                            "Escribe 'confirmar' o 'cancelar'.")

                encontrados = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if encontrados:
                    for prod, cantidad in encontrados:
                        if prod in PRODUCTOS_DB:
                            session["carrito"][prod] = session["carrito"].get(prod, 0) + float(cantidad)
                    añadido = ", ".join(f"{p} ({c} kg)" for p, c in encontrados)
                    return f"{añadido} añadido.\nCarrito:\n{mostrar_carrito(session)}"

                match = re.match(r"([a-záéíóúñü ]+)\s+(\d+(?:\.\d+)?)\s*kg", msg)
                if match:
                    producto, cantidad = match.group(1).strip(), float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return f"{producto} añadido ({cantidad} kg).\nCarrito:\n{mostrar_carrito(session)}"
                    else:
                        return "Ese producto no está en el catálogo."

                unico = extraer_productos_desde_texto(msg, PRODUCTOS_DB)
                if len(unico) == 1:
                    producto, cantidad = unico[0]
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + float(cantidad)
                        return f"{producto} añadido ({cantidad} kg).\nCarrito:\n{mostrar_carrito(session)}"

                return "No entendí. Ejemplo: 'pollo 2 kg'."

            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in msg:
                    resumen = (f"✅ Pedido confirmado\n"
                               f"👤 {session['nombre']}\n"
                               f"🕒 {formatear_fecha(session['hora'])}\n"
                               f"🛒 {mostrar_carrito(session)}\n"
                               f"💰 {session['total']:.2f}€")
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return resumen
                elif "cancelar" in msg:
                    SESSIONS.pop(user_id, None)
                    return "Pedido cancelado ❌."
                else:
                    return "Escribe 'confirmar' o 'cancelar'."

        return "No entendí tu mensaje 🤔."

    except Exception:
        logging.exception("Error en process_message")
        return "Hubo un error interno."
