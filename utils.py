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
        "descripcion": "Arreglo clásico para cocido madrileño"
    }
}

sessions = {}

def parse_quantity(text):
    pattern = r"(?P<cantidad>\d+\.?\d*\s?(?:kg|kilos|gr|g|gramos|medio kilo|1/2 kilo)?)\s*(?:de\s)?(?P<producto>\w+)"
    matches = re.findall(pattern, text.lower())

    items = []
    for cantidad_text, producto in matches:
        cantidad_text = cantidad_text.replace(",", ".").strip()

        if "medio" in cantidad_text or "1/2" in cantidad_text:
            cantidad = 0.5
        elif "kg" in cantidad_text or "kilo" in cantidad_text:
            cantidad = float(re.sub(r"[^\d.]", "", cantidad_text))
        elif "g" in cantidad_text or "gramo" in cantidad_text:
            cantidad = float(re.sub(r"[^\d.]", "", cantidad_text)) / 1000
        else:
            continue

        items.append({
            "producto": producto,
            "cantidad": cantidad
        })

    return items

def calcular_total(pedido_items):
    total = 0
    detalles = []
    for item in pedido_items:
        producto = item["producto"]
        cantidad = item["cantidad"]
        if producto in PRODUCTOS_DB:
            precio_kg = PRODUCTOS_DB[producto]
            subtotal = cantidad * precio_kg
            total += subtotal
            detalles.append(f"- {producto.capitalize()}: {cantidad:.2f} kg x {precio_kg:.2f}€/kg = {subtotal:.2f}€")
        else:
            detalles.append(f"- {producto} no está disponible.")
    return total, detalles

def process_message(data):
    user_id = data.get("user_id") or data.get("from")
    message = data.get("message") or data.get("text")
    mensaje = message.lower().strip()
    session = sessions.get(user_id, {"step": 0})

    if session["step"] == 0:
        session["nombre"] = message
        session["step"] += 1
        sessions[user_id] = session
        return {"reply": f"Hola {session['nombre']} 👋 ¿A qué hora quieres recoger tu pedido?"}

    elif session["step"] == 1:
        session["hora"] = message
        session["step"] += 1
        session["pedido"] = []
        sessions[user_id] = session

        productos_list = "\n".join([f"- {p.capitalize()} ({v:.2f}€/kg)" for p, v in PRODUCTOS_DB.items()])
        recetas_list = "\n".join([f"- {r}" for r in RECETAS_ESPECIALES])
        return {"reply": f"Estos son los productos disponibles:\n{productos_list}\n\nTambién puedes pedir recetas como:\n{recetas_list}\n\nPuedes escribir tus productos uno a uno. Escribe *listo* cuando termines."}

    elif session["step"] == 2:
        # Si se escribe "listo", pasar al resumen y confirmación
        if mensaje == "listo":
            if not session["pedido"]:
                return {"reply": "❌ Aún no has añadido ningún producto. Por favor indica qué deseas pedir."}
            total, detalles = calcular_total(session["pedido"])
            session["total"] = total
            session["detalle_pedido"] = detalles
            session["step"] = 3
            sessions[user_id] = session
            detalle_texto = "\n".join(detalles)
            return {
                "reply": f"🧾 Este es tu pedido:\n{detalle_texto}\n\n💰 Total: {total:.2f}€\n¿Deseas confirmar el pedido? (sí/no)"
            }

        # Si es una receta especial
        if mensaje in RECETAS_ESPECIALES:
            session["receta_nombre"] = mensaje
            session["step"] = "receta_personas"
            sessions[user_id] = session
            return {"reply": f"🥘 {RECETAS_ESPECIALES[mensaje]['descripcion']}\n\n¿Cuántas personas van a comer?"}

        # Si son productos sueltos
        items = parse_quantity(mensaje)
        if not items:
            return {
                "reply": "❌ No entendí tu pedido. Usa un formato como:\n'1kg de pollo' o prueba con 'arreglo para paella'."
            }

        # Agregar los nuevos productos al pedido acumulado
        if "pedido" not in session:
            session["pedido"] = []
        session["pedido"].extend(items)

        total, detalles = calcular_total(session["pedido"])
        sessions[user_id] = session
        return {
            "reply": f"✅ Producto añadido.\n💰 Total actual: {total:.2f}€\nEscribe otro producto o pon *listo* para finalizar."
        }

    elif session["step"] == "receta_personas":
        try:
            personas = int(message.strip())
            if personas <= 0:
                raise ValueError
        except ValueError:
            return {"reply": "Por favor, indica un número válido de personas (ejemplo: 4)."}

        receta = RECETAS_ESPECIALES[session["receta_nombre"]]
        items = []

        for item in receta["por_persona"]:
            items.append({
                "producto": item["producto"],
                "cantidad": item["cantidad"] * personas
            })

        if "pedido" not in session:
            session["pedido"] = []
        session["pedido"].extend(items)

        total, detalles = calcular_total(session["pedido"])
        session["total"] = total
        session["detalle_pedido"] = detalles
        session["step"] = 3
        sessions[user_id] = session

        detalle_texto = "\n".join(detalles)
        return {
            "reply": f"🧾 Pedido para {personas} personas:\n{detalle_texto}\n\n💰 Total: {total:.2f}€\n¿Deseas confirmar el pedido? (sí/no)"
        }

    elif session["step"] == 3:
        if mensaje in ["sí", "si"]:
            if session.get("impreso"):
                return {"reply": "✅ El pedido ya fue confirmado e impreso. Gracias."}
            send_to_printer(user_id, session)
            session["impreso"] = True
            session["step"] = 4
            sessions[user_id] = session
            return {"reply": "✅ Pedido confirmado e impreso. ¡Gracias por tu compra!"}
        elif mensaje == "no":
            sessions.pop(user_id, None)
            return {"reply": "❌ Pedido cancelado. Si deseas hacer otro pedido, escribe cualquier mensaje."}
        else:
            return {"reply": "❓ Por favor responde con 'sí' para confirmar o 'no' para cancelar."}

    else:
        sessions.pop(user_id, None)
        return {"reply": "¿Deseas hacer otro pedido? Escribe cualquier cosa para comenzar de nuevo."}
