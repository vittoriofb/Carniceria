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

RECETAS_ESPECIALES = {
    "arreglo para paella": {
        "por_persona": [
            {"producto": "pollo", "cantidad": 0.15},
            {"producto": "conejo", "cantidad": 0.10},
            {"producto": "costilla", "cantidad": 0.10}
        ],
        "descripcion": "Arreglo típico para paella valenciana"
    },
    "arreglo para cocido": {
        "por_persona": [
            {"producto": "ternera", "cantidad": 0.20},
            {"producto": "pollo", "cantidad": 0.15},
            {"producto": "cerdo", "cantidad": 0.15}
        ],
        "descripcion": "Arreglo típico para cocido"
    }
}

SESSIONS = {}

def process_message(data):
    try:
        user_id = data.get("user_id")
        message = data.get("message", "").strip().lower()

        if not user_id:
            return {"reply": "Error: usuario no identificado."}

        if user_id not in SESSIONS:
            SESSIONS[user_id] = {"step": "welcome"}

        session = SESSIONS[user_id]

        # Paso 1: Bienvenida
        if session["step"] == "welcome":
            session["step"] = "ask_name"
            return {"reply": "👋 ¡Bienvenido a la Carnicería El Buen Corte!\nPor favor, escribe tu nombre de la forma:\n\nNombre: Juan Pérez"}

        # Paso 2: Guardar nombre
        if session["step"] == "ask_name":
            match_name = re.match(r"(nombre\s*:\s*)(.+)", message)
            if match_name:
                session["nombre"] = match_name.group(2).strip().title()
                session["step"] = "ask_hour"
                return {"reply": f"Gracias {session['nombre']} 😊\nAhora, indica la hora de recogida así:\n\nHora: 13:30"}
            else:
                return {"reply": "Por favor, escribe tu nombre con el formato:\nNombre: Juan Pérez"}

        # Paso 3: Guardar hora
        if session["step"] == "ask_hour":
            match_hour = re.match(r"(hora\s*:\s*)(\d{1,2}:\d{2})", message)
            if match_hour:
                session["hora"] = match_hour.group(2)
                session["step"] = "ask_product"
                catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                return {"reply": f"Perfecto, recogerás tu pedido a las {session['hora']} ⏰\n\nAquí tienes nuestro catálogo:\n{catalogo}\n\nEscribe el nombre del producto tal cual aparece para continuar."}
            else:
                return {"reply": "Formato incorrecto. Ejemplo válido:\nHora: 13:30"}

        # Paso 4: Elegir producto
        if session["step"] == "ask_product":
            if message in PRODUCTOS_DB:
                session["producto"] = message
                session["step"] = "ask_quantity"
                precio = PRODUCTOS_DB[message]
                return {"reply": f"El precio del {message} es {precio}€/kg.\nEscribe la cantidad así:\n\n2 kg"}
            else:
                return {"reply": "Producto no válido. Elige uno del catálogo enviado."}

        # Paso 5: Cantidad
        if session["step"] == "ask_quantity":
            match_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg", message)
            if match_kg:
                kilos = float(match_kg.group(1))
                producto = session["producto"]
                total = kilos * PRODUCTOS_DB[producto]
                session["cantidad"] = kilos
                session["total"] = total
                session["step"] = "confirm"
                return {"reply": f"Perfecto. El total será {total:.2f}€.\nEscribe 'Confirmar' para finalizar tu pedido."}
            else:
                return {"reply": "Formato incorrecto. Ejemplo válido:\n2 kg"}

        # Paso 6: Confirmar
        if session["step"] == "confirm":
            if "confirmar" in message:
                send_to_printer(user_id, session)
                session["step"] = "done"
                return {"reply": "✅ Pedido confirmado. Te hemos enviado el ticket por correo."}
            else:
                return {"reply": "Para confirmar, escribe:\nConfirmar"}

        # Conversación finalizada
        if session["step"] == "done":
            return {"reply": "Tu pedido ya fue confirmado. Si quieres hacer otro, escribe 'Hola'."}

        return {"reply": "No entendí tu mensaje, ¿puedes repetirlo?"}

    except Exception:
        logging.exception("Error en process_message")
        return {"reply": "Hubo un error interno procesando tu mensaje."}
