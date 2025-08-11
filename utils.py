import logging
import re
from printer import send_to_printer

# Productos disponibles y precios por kg
PRODUCTOS_DB = {
    "pollo": 6.50,
    "ternera": 12.00,
    "cerdo": 8.00,
    "cordero": 13.50,
    "conejo": 7.50,
    "costilla": 8.00
}

# Recetas especiales por persona
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

# Sesiones temporales de usuarios
SESSIONS = {}

def process_message(data):
    """
    Procesa el mensaje del usuario y devuelve un diccionario con 'reply'.
    """
    try:
        user_id = data.get("user_id")
        message = data.get("message", "").strip().lower()

        if not user_id:
            return {"reply": "Error: no se pudo identificar al usuario."}

        # Inicializar sesión si no existe
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {}

        session = SESSIONS[user_id]

        # Ejemplo simple de flujo
        if "hola" in message:
            return {"reply": "¡Hola! ¿Qué producto te interesa hoy?"}

        elif message in PRODUCTOS_DB:
            precio = PRODUCTOS_DB[message]
            session["producto"] = message
            return {"reply": f"El precio del {message} es {precio}€/kg. ¿Cuántos kilos quieres?"}

        # Capturar cantidad en kg
        match_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg", message)
        if match_kg and "producto" in session:
            kilos = float(match_kg.group(1))
            producto = session["producto"]
            total = kilos * PRODUCTOS_DB[producto]
            session["cantidad"] = kilos
            session["total"] = total
            return {"reply": f"Perfecto. El total será {total:.2f}€. ¿Quieres confirmar el pedido?"}

        if "confirmar" in message and "producto" in session:
            send_to_printer(user_id, session)
            return {"reply": "Pedido confirmado. Te hemos enviado el ticket por correo."}

        return {"reply": "No entendí tu mensaje, ¿puedes repetirlo?"}

    except Exception as e:
        logging.exception("Error en process_message")
        return {"reply": "Hubo un error interno procesando tu mensaje."}
