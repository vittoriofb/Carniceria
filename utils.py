import json
from printer import send_to_printer
import re

sessions = {}

# Base de datos de productos (puedes moverlo a una BD real más adelante)
PRODUCTOS = {
    "pollo": 6.5,     # €/kg
    "ternera": 12.0,
    "cerdo": 9.0,
    "chorizo": 8.0,
    "morcilla": 7.0,
    "costillas": 10.0,
    "conejo": 11.0
}

# Recetas especiales con cantidades por persona
RECETAS = {
    "paella": {
        "pollo": 150,
        "conejo": 100,
        "chorizo": 50,
        "morcilla": 50
    },
    "barbacoa": {
        "costillas": 200,
        "chorizo": 100,
        "cerdo": 150
    }
}

def parse_quantity(text):
    """
    Convierte frases como '1kg de pollo' o '500g de ternera' en items de pedido.
    Devuelve lista de tuplas: [(producto, cantidad_kg)]
    """
    import re

    pattern = r"(\d+(?:[.,]?\d*)?)\s*(kg|g)?\s*(?:de\s+)?(\w+)"
    matches = re.findall(pattern, text.lower())
    items = []

    for cantidad, unidad, producto in matches:
        producto = producto.strip()
        if producto not in PRODUCTOS:
            continue
        try:
            cantidad = float(cantidad.replace(",", "."))
            if unidad == "g":
                cantidad = cantidad / 1000
            elif unidad == "kg" or unidad is None:
                pass
            else:
                continue
            items.append((producto, cantidad))
        except:
            continue

    return items

def calcular_total(lista_pedidos):
    """
    Recibe lista de tuplas [(producto, cantidad_kg)] y devuelve total y detalles
    """
    total = 0
    detalles = []

    for producto, cantidad in lista_pedidos:
        precio = PRODUCTOS.get(producto, 0)
        subtotal = precio * cantidad
        total += subtotal
        detalles.append(f"- {cantidad*1000:.0f}g de {producto}: {subtotal:.2f} €")

    return round(total, 2), detalles

def generar_pedido_receta(nombre_receta, personas):
    ingredientes = RECETAS.get(nombre_receta)
    if not ingredientes:
        return [], 0, []

    pedido = []
    for producto, cantidad_por_persona in ingredientes.items():
        total_cantidad = (cantidad_por_persona * personas) / 1000  # en kg
        pedido.append((producto, total_cantidad))

    total, detalles = calcular_total(pedido)
    return pedido, total, detalles

def process_message(data):
    user_id = data.get("user_id") or data.get("from")
    message = data.get("message") or data.get("text")
    message = message.strip().lower()
    session = sessions.get(user_id, {"step": 0})

    if message in ["cancelar", "reiniciar"]:
        sessions[user_id] = {"step": 0}
        return {"reply": "🔄 Pedido cancelado. Empecemos de nuevo. ¿Cuál es tu nombre?"}

    # Paso 0: Nombre
    if session["step"] == 0:
        session["nombre"] = message.title()
        session["step"] = 1
        sessions[user_id] = session
        return {"reply": "¿A qué hora quieres recoger tu pedido?"}

    # Paso 1: Hora
    elif session["step"] == 1:
        session["hora"] = message
        session["step"] = 2
        session["temporal_pedido"] = []
        sessions[user_id] = session
        return {
            "reply": (
                "Perfecto. Ahora puedes escribir tus productos uno a uno.\n"
                "Ejemplo: '1kg de pollo', '400g de ternera', etc.\n"
                "También puedes pedir arreglos como: 'arreglo para paella para 4 personas'.\n"
                "Cuando termines, escribe *listo*."
            )
        }

    # Paso 2: Pedido línea por línea o receta
    elif session["step"] == 2:
        if message == "listo":
            if not session["temporal_pedido"]:
                return {"reply": "No has agregado ningún producto. ¿Qué deseas pedir?"}
            session["pedido"] = session["temporal_pedido"]
            total, detalles = calcular_total(session["pedido"])
            session["total"] = total
            session["detalle_pedido"] = detalles
            session["step"] = 3
            sessions[user_id] = session

            texto_pedido = "\n".join(detalles)
            return {
                "reply": f"🧾 Este es tu pedido:\n{texto_pedido}\n\n💰 Total: {total:.2f}€\n¿Deseas confirmar el pedido? (sí/no)"
            }

        # Arreglos especiales
        elif "arreglo para" in message:
            import re
            match = re.search(r"arreglo para (\w+)(?: para (\d+))?", message)
            if match:
                receta = match.group(1)
                personas = int(match.group(2)) if match.group(2) else 2
                if receta in RECETAS:
                    pedido, total, detalles = generar_pedido_receta(receta, personas)
                    session["temporal_pedido"].extend(pedido)
                    session["receta_nombre"] = receta
                    session["personas"] = personas
                    sessions[user_id] = session
                    return {
                        "reply": f"🧂 Arreglo para {receta} añadido para {personas} personas.\n"
                                 "Puedes seguir añadiendo productos o escribir *listo*."
                    }
                else:
                    return {"reply": "❌ No tenemos esa receta. Las disponibles son: " + ", ".join(RECETAS.keys())}
            else:
                return {"reply": "❌ Formato no reconocido. Ejemplo: 'arreglo para paella para 4 personas'."}

        # Productos normales
        else:
            items = parse_quantity(message)
            if not items:
                return {
                    "reply": "❌ No entendí ese producto. Usa el formato: '1kg de pollo' o prueba con 'arreglo para paella para 4 personas'."
                }
            session["temporal_pedido"].extend(items)
            sessions[user_id] = session
            return {"reply": "✅ Producto añadido. Escribe otro o pon *listo* para terminar."}

    # Paso 3: Confirmar pedido
    elif session["step"] == 3:
        if message == "sí":
            send_to_printer(user_id, session)
            session["step"] = 4
            sessions[user_id] = session
            return {"reply": "✅ Pedido confirmado. ¡Gracias por tu compra!"}
        elif message == "no":
            sessions[user_id] = {"step": 0}
            return {"reply": "❌ Pedido cancelado. Si deseas hacer otro, escribe cualquier mensaje."}
        else:
            return {"reply": "Por favor, responde con 'sí' o 'no'."}

    # Paso 4: Finalizado
    else:
        sessions[user_id] = {"step": 0}
        return {"reply": "¿Deseas hacer otro pedido? Escribe cualquier cosa para comenzar de nuevo."}
