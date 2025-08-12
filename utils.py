import logging
import re
from printer import send_to_printer

PRODUCTOS_DB = {
    "pollo": 6.50,
    "ternera": 12.00,
    "cerdo": 8.00,
    "cordero": 13.50,
    "conejo": 7.50,
    "costilla": 8.00
}

SESSIONS = {}

def mostrar_carrito(session):
    """Devuelve un string con el contenido actual del carrito."""
    if not session["carrito"]:
        return "Carrito vacío."
    return "\n".join([f"{prod}: {cant} kg - {cant * PRODUCTOS_DB[prod]:.2f}€"
                      for prod, cant in session["carrito"].items()])

def process_message(data):
    try:
        user_id = data.get("user_id")
        message = data.get("message", "").strip().lower()

        if not user_id:
            return {"reply": "Error: usuario no identificado."}

        # Crear sesión si no existe
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {"modo": None, "paso": 0, "carrito": {}}

        session = SESSIONS[user_id]

        # Comando para iniciar pedido
        if "iniciar pedido" in message:
            session.clear()
            session.update({"modo": "pedido", "paso": 1, "carrito": {}})
            return {"reply": "Genial 👍. Vamos a empezar tu pedido.\n¿Cuál es tu nombre?"}

        # Comando para volver atrás
        if "volver atras" in message and session["modo"] == "pedido":
            if session["paso"] > 1:
                session["paso"] -= 1
                return {"reply": f"Has vuelto al paso {session['paso']}. Vamos a repetirlo."}
            else:
                return {"reply": "No puedes retroceder más, estamos al inicio del pedido."}

        # Mensaje de bienvenida si no hay modo activo
        if session["modo"] is None:
            return {"reply": (
                "Hola 😊. Bienvenido a la carnicería.\n"
                "⏰ *Horario*: Lunes a Sábado de 9:00 a 14:00 y de 17:00 a 20:00.\n"
                "Puedes escribirme lo que quieras sin necesidad de iniciar un pedido y te escribiremos lo antes posible ante cualquier duda.\n"
                "Cuando quieras encargar algo, simplemente escribe *'iniciar pedido'*."
            )}

        # --- MODO PEDIDO ---
        if session["modo"] == "pedido":

            # Paso 1: Pedir nombre
            if session["paso"] == 1:
                session["nombre"] = message
                session["paso"] = 2
                return {"reply": f"Encantado {session['nombre']} 😊. ¿A qué hora pasarás a recoger tu pedido? (Formato HH:MM, 24h)"}

            # Paso 2: Validar hora
            if session["paso"] == 2:
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", message):
                    session["hora"] = message
                    session["paso"] = 3
                    catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                    return {"reply": f"Perfecto. Estos son nuestros productos:\n{catalogo}\n\nDime qué quieres y cuántos kilos. Ejemplo: 'pollo 2 kg'.\nPara eliminar un producto: 'eliminar pollo'.\nCuando termines, escribe 'listo'."}
                else:
                    return {"reply": "Formato de hora no válido. Ejemplo correcto: 15:00 (usa formato 24h)."}

            # Paso 3: Añadir o eliminar productos
            if session["paso"] == 3:

                # Eliminar producto
                if message.startswith("eliminar "):
                    producto = message.replace("eliminar ", "").strip()
                    if producto in session["carrito"]:
                        session["carrito"].pop(producto)
                        return {"reply": f"{producto} eliminado del carrito.\nCarrito actual:\n{mostrar_carrito(session)}"}
                    else:
                        return {"reply": f"No tienes {producto} en tu carrito."}

                # Finalizar pedido
                if message == "listo":
                    if not session["carrito"]:
                        return {"reply": "No has añadido ningún producto. Por favor indica al menos uno antes de decir 'listo'."}
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    return {"reply": f"Este es tu pedido:\n{mostrar_carrito(session)}\nTotal: {total:.2f}€\nEscribe 'confirmar' para finalizar o 'cancelar' para anular."}

                # Añadir producto
                match = re.match(r"([a-záéíóúñ ]+)\s+(\d+(?:\.\d+)?)\s*kg", message)
                if match:
                    producto = match.group(1).strip()
                    cantidad = float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return {"reply": f"{producto} añadido ({cantidad} kg).\nCarrito actual:\n{mostrar_carrito(session)}"}
                    else:
                        return {"reply": "Ese producto no está en el catálogo. Revisa la lista y escribe de nuevo."}

                return {"reply": "Formato no válido. Ejemplo correcto: 'pollo 2 kg'. Si ya has terminado, escribe 'listo'."}

            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in message:
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return {"reply": "Pedido confirmado ✅. Te hemos enviado el ticket por correo."}
                elif "cancelar" in message:
                    SESSIONS.pop(user_id, None)
                    return {"reply": "Pedido cancelado ❌. Puedes iniciar otro cuando quieras."}
                else:
                    return {"reply": "Responde con 'confirmar' o 'cancelar'."}

        return {"reply": "No entendí tu mensaje, ¿puedes repetirlo?"}

    except Exception:
        logging.exception("Error en process_message")
        return {"reply": "Hubo un error interno procesando tu mensaje."}
