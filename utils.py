import logging
import re
from printer import send_to_printer
from data import PRODUCTOS_DB

SESSIONS = {}

def mostrar_carrito(session):
    """Devuelve un string con el contenido actual del carrito."""
    if not session["carrito"]:
        return "Carrito vacío."
    return "\n".join([
        f"• {prod.capitalize()}: {cant} kg — {cant * PRODUCTOS_DB[prod]:.2f}€"
        for prod, cant in session["carrito"].items()
    ])

def process_message(data):
    try:
        user_id = data.get("user_id")
        message = data.get("message", "").strip().lower()

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
        if "volver atras" in message and session["modo"] == "pedido":
            if session["paso"] > 1:
                if session["paso"] == 2:
                    session.pop("nombre", None)
                    session["paso"] = 1
                    return "Has vuelto atrás ↩️. Vamos de nuevo.\n¿Cuál es tu nombre?"
                elif session["paso"] == 3:
                    session.pop("hora", None)
                    session["paso"] = 2
                    return "Has vuelto atrás ↩️. Por favor, indícanos la hora en formato HH:MM (ej. 15:00)."
                elif session["paso"] == 4:
                    session["paso"] = 3
                    return f"Has vuelto atrás ↩️. Lista actual:\n{mostrar_carrito(session)}\nDime si quieres añadir o quitar algo."
            else:
                return "No puedes retroceder más, estamos al inicio del pedido."

        # --- INICIAR PEDIDO ---
        if "iniciar pedido" in message:
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
                session["nombre"] = message
                session["paso"] = 2
                return f"Encantado {session['nombre'].capitalize()} 😊. ¿A qué hora pasarás a recoger tu pedido? (Formato HH:MM, 24h)"

            # Paso 2: Hora
            if session["paso"] == 2:
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", message):
                    session["hora"] = message
                    session["paso"] = 3
                    catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                    return (
                        f"Perfecto. Estos son nuestros productos:\n{catalogo}\n\n"
                        "Dime qué quieres y cuántos kilos. Ejemplo: 'pollo 2 kg'.\n"
                        "Para eliminar un producto: 'eliminar pollo'.\n"
                        "Cuando termines, escribe 'listo'."
                    )
                else:
                    return "Formato de hora no válido. Ejemplo correcto: 15:00 (usa formato 24h)."

            # Paso 3: Añadir o eliminar productos
            if session["paso"] == 3:

                if message.startswith("eliminar "):
                    producto = message.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return f"{producto} eliminado del carrito.\nCarrito actual:\n{mostrar_carrito(session)}"
                    else:
                        return f"No tienes {producto} en tu carrito."

                if message == "listo":
                    if not session["carrito"]:
                        return "No has añadido ningún producto. Añade al menos uno antes de decir 'listo'."
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    return f"Este es tu pedido:\n{mostrar_carrito(session)}\n💰 Total: {total:.2f}€\nEscribe 'confirmar' para finalizar o 'cancelar' para anular."

                match = re.match(r"([a-záéíóúñ ]+)\s+(\d+(?:\.\d+)?)\s*kg", message)
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
                if "confirmar" in message:
                    resumen = (
                        f"✅ *Pedido confirmado*\n"
                        f"👤 Cliente: {session['nombre'].capitalize()}\n"
                        f"🕒 Hora: {session['hora']}\n"
                        f"🛒 Carrito:\n{mostrar_carrito(session)}\n"
                        f"💰 Total Estimado: {session['total']:.2f}€"
                    )
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return resumen
                elif "cancelar" in message:
                    SESSIONS.pop(user_id, None)
                    return "Pedido cancelado ❌."
                else:
                    return "Responde con 'confirmar' o 'cancelar'."

        return "No entendí tu mensaje 🤔."

    except Exception:
        logging.exception("Error en process_message")
        return "Hubo un error interno procesando tu mensaje."
