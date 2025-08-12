import logging
import re
from printer import enviar_correo

PRODUCTOS_DB = {
    "pollo": 6.50,
    "ternera": 12.00,
    "cerdo": 8.00,
    "cordero": 13.50,
    "conejo": 7.50,
    "costilla": 8.00
}

SESSIONS = {}

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

        # Comando para iniciar pedido en cualquier momento
        if "iniciar pedido" in message:
            session.clear()
            session.update({"modo": "pedido", "paso": 1, "carrito": {}})
            return {"reply": "Hola 😊. Este servicio ahora es automático: me dices lo que quieres comprar y yo lo apunto. Puedes pedirme varias cosas una a una y, cuando hayas terminado, me dices 'listo'. Vamos a empezar. ¿Cuál es tu nombre?"}

        # Si no hay modo asignado aún → mensaje inicial
        if session["modo"] is None:
            return {"reply": "Hola 😊. Bienvenido a la carnicería. Ahora tenemos un sistema muy fácil: si quieres hacer un pedido, escribe 'iniciar pedido'. Si solo quieres hablar, escríbeme lo que quieras."}

        # --- MODO CONVERSACIÓN LIBRE ---
        if session["modo"] == "conversacion":
            return {"reply": f"Me dices: {message}. Recuerda que si quieres encargar algo escribe 'iniciar pedido'."}

        # --- MODO PEDIDO ---
        if session["modo"] == "pedido":

            # Paso 1: Pedir nombre
            if session["paso"] == 1:
                session["nombre"] = message
                session["paso"] = 2
                return {"reply": f"Encantado {session['nombre']} 😊. ¿A qué hora pasarás a recoger tu pedido?"}

            # Paso 2: Hora de recogida
            if session["paso"] == 2:
                session["hora"] = message
                session["paso"] = 3
                catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                return {"reply": f"Perfecto. Estos son nuestros productos:\n{catalogo}\n\nDime qué quieres y cuántos kilos. Ejemplo: 'pollo 2 kg'. Puedes pedirme varias cosas y, cuando termines, escribe 'listo'."}

            # Paso 3: Añadir productos al carrito
            if session["paso"] == 3:
                if message == "listo":
                    if not session["carrito"]:
                        return {"reply": "No has añadido ningún producto. Por favor indica al menos uno antes de decir 'listo'."}
                    total = sum(cant * PRODUCTOS_DB[prod] for prod, cant in session["carrito"].items())
                    session["total"] = total
                    session["paso"] = 4
                    lista = "\n".join([f"{prod}: {cant} kg - {cant * PRODUCTOS_DB[prod]:.2f}€" for prod, cant in session["carrito"].items()])
                    return {"reply": f"Este es tu pedido:\n{lista}\nTotal: {total:.2f}€\nEscribe 'confirmar' para finalizar o 'cancelar' para anular."}

                # Buscar producto y cantidad
                match = re.match(r"([a-záéíóúñ ]+)\s+(\d+(?:\.\d+)?)\s*kg", message)
                if match:
                    producto = match.group(1).strip()
                    cantidad = float(match.group(2))
                    if producto in PRODUCTOS_DB:
                        session["carrito"][producto] = session["carrito"].get(producto, 0) + cantidad
                        return {"reply": f"{producto} añadido ({cantidad} kg). Puedes seguir pidiendo o escribe 'listo' para terminar."}
                    else:
                        return {"reply": "Ese producto no está en el catálogo, revisa la lista y escribe de nuevo."}
                else:
                    return {"reply": "Formato no válido. Ejemplo: 'pollo 2 kg'. Si ya has terminado, escribe 'listo'."}

            # Paso 4: Confirmación
            if session["paso"] == 4:
                if "confirmar" in message:
                    enviar_correo(user_id, session)
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
