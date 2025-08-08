import json
from printer import send_to_printer

sessions = {}

def process_message(data):
    user_id = data.get("user_id") or data.get("from")
    message = data.get("message") or data.get("text")
    session = sessions.get(user_id, {"step": 0})

    steps = [
        "Hola 👋 Bienvenido a la carnicería. ¿Cuál es tu nombre?",
        "¿A qué hora quieres recoger tu pedido?",
        "Estos son los productos disponibles: \n- Pollo\n- Ternera\n- Cerdo\n¿Qué deseas pedir?",
        "Perfecto. El total de tu pedido es 25€. ¿Deseas confirmar el pedido? (sí/no)",
        "✅ Pedido confirmado. Muchas gracias. ¡Nos vemos pronto!"
    ]

    if session["step"] < len(steps):
        if session["step"] == 3 and message.lower() == "sí":
            send_to_printer(user_id, session)
            session["step"] += 1
        elif session["step"] == 3 and message.lower() == "no":
            return {"reply": "❌ Pedido cancelado. Si deseas empezar de nuevo, escribe cualquier mensaje."}
        else:
            session[f"step_{session['step']}"] = message
            session["step"] += 1
        sessions[user_id] = session
        return {"reply": steps[session["step"] - 1]}
    else:
        return {"reply": "¿Deseas hacer otro pedido? Escribe cualquier cosa para comenzar de nuevo."}