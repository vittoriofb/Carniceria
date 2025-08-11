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

        # Crear sesión si no existe
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {"modo": None, "paso": 0}

        session = SESSIONS[user_id]

        # Comando para iniciar pedido en cualquier momento
        if "iniciar pedido" in message:
            session["modo"] = "pedido"
            session["paso"] = 1
            session.clear()
            session.update({"modo": "pedido", "paso": 1})
            return {"reply": "Perfecto, vamos a iniciar tu pedido. ¿Cuál es tu nombre?"}

        # Si no hay modo asignado aún → pregunta inicial
        if session["modo"] is None:
            if "pedido" in message:
                session["modo"] = "pedido"
                session["paso"] = 1
                return {"reply": "Perfecto, vamos a iniciar tu pedido. ¿Cuál es tu nombre?"}
            elif "conversar" in message:
                session["modo"] = "conversacion"
                return {"reply": "Claro, conversemos 😊. Puedes escribirme lo que quieras, y si en algún momento quieres iniciar un pedido escribe 'iniciar pedido'."}
            else:
                return {"reply": "Bienvenido a la carnicería 🥩. ¿Quieres 'iniciar pedido' o 'conversar'?"}

        # Modo conversación libre
        if session["modo"] == "conversacion":
            return {"reply": f"Entiendo, me dices: {message}. Recuerda que puedes escribir 'iniciar pedido' en cualquier momento para hacer un pedido."}

        # Modo pedido paso a paso
        if session["modo"] == "pedido":
            # Paso 1: Nombre
            if session["paso"] == 1:
                session["nombre"] = message
                session["paso"] = 2
                return {"reply": f"Encantado {session['nombre']}. ¿A qué hora pasarás a recoger tu pedido?"}

            # Paso 2: Hora de recogida
            if session["paso"] == 2:
                session["hora"] = message
                session["paso"] = 3
                catalogo = "\n".join([f"- {prod} ({precio}€/kg)" for prod, precio in PRODUCTOS_DB.items()])
                return {"reply": f"Perfecto. Estos son nuestros productos:\n{catalogo}\n\nIndica el producto que quieres."}

            # Paso 3: Selección de producto
            if session["paso"] == 3:
                if message in PRODUCTOS_DB:
                    session["producto"] = message
                    session["paso"] = 4
                    return {"reply": f"Has elegido {message}. ¿Cuántos kilos quieres? (Ejemplo: '2 kg')"}
                else:
                    return {"reply": "Ese producto no está en el catálogo, por favor elige uno de la lista."}

            # Paso 4: Cantidad
            if session["paso"] == 4:
                match_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg", message)
                if match_kg:
                    kilos = float(match_kg.group(1))
                    producto = session["producto"]
                    total = kilos * PRODUCTOS_DB[producto]
                    session["cantidad"] = kilos
                    session["total"] = total
                    session["paso"] = 5
                    return {"reply": f"El total será {total:.2f}€. Escribe 'confirmar' para finalizar el pedido o 'cancelar' para anularlo."}
                else:
                    return {"reply": "Por favor indica la cantidad en kilos. Ejemplo: '1.5 kg'"}

            # Paso 5: Confirmación
            if session["paso"] == 5:
                if "confirmar" in message:
                    send_to_printer(user_id, session)
                    SESSIONS.pop(user_id, None)
                    return {"reply": "Pedido confirmado ✅. Te hemos enviado el ticket por correo."}
                elif "cancelar" in message:
                    SESSIONS.pop(user_id, None)
                    return {"reply": "Pedido cancelado ❌. Puedes iniciar otro cuando quieras."}
                else:
                    return {"reply": "Responde con 'confirmar' o 'cancelar'."}

        # Si no entra en nada
        return {"reply": "No entendí tu mensaje, ¿puedes repetirlo?"}

    except Exception:
        logging.exception("Error en process_message")
        return {"reply": "Hubo un error interno procesando tu mensaje."}
