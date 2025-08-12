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

def extraer_nombre(raw_text: str) -> str:
    """
    Extrae el nombre del usuario a partir de frases como:
    - "mi nombre es Pablo"
    - "me llamo María José"
    - "hola, soy Ana"
    - "Pablo"
    Devuelve como máximo 3 palabras, sin emojis ni signos, capitalizadas.
    """
    if not raw_text:
        return "Cliente"

    txt = raw_text.strip()
    lower = txt.lower()

    # Patrones comunes para presentar el nombre
    patrones = [
        r"(?:^|\b)(?:mi\s+nombre\s+es)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)(?:me\s+llamo)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)(?:soy)\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
        r"(?:^|\b)hola[,!.\s]*soy\s+([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})",
    ]

    # Intentar extraer con patrones (usamos el texto en lower para encontrar posición)
    for patron in patrones:
        m = re.search(patron, lower)
        if m:
            start, end = m.span(1)
            candidato = txt[start:end]  # recorta desde el texto original para conservar acentos
            break
    else:
        # Si no coincide ningún patrón, asumimos que el primer token es el nombre
        # (por ej: "Pablo", "María José", "Luis-Alberto")
        # Limpiamos el principio de saludos frecuentes
        sin_saludo = re.sub(r"^(hola|buenas|buenos\s+días|buenas\s+tardes|buenas\s+noches)[,!\s]+", "", lower, flags=re.I)
        if sin_saludo != lower:
            # Ajustamos índices al original
            offset = len(lower) - len(sin_saludo)
            txt = txt[offset:]
            lower = sin_saludo

        # Tomar hasta 3 palabras como posible nombre
        m = re.match(r"([a-záéíóúñü]+(?:\s+[a-záéíóúñü]+){0,2})", lower)
        if m:
            start, end = m.span(1)
            candidato = txt[start:end]
        else:
            candidato = txt

    # Limpiar cualquier carácter que no sea letra, espacio o guion
    candidato = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-]", "", candidato)
    # Normalizar espacios
    candidato = re.sub(r"\s+", " ", candidato).strip()
    # Limitar a 3 palabras
    palabras = candidato.split()
    palabras = palabras[:3] if palabras else ["Cliente"]
    # Capitalizar cada palabra
    nombre = " ".join(p.capitalize() for p in palabras)
    return nombre if nombre else "Cliente"

def process_message(data):
    try:
        user_id = data.get("user_id")
        raw_message = data.get("message", "").strip()
        msg = raw_message.lower()

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
        if "volver atras" in msg and session["modo"] == "pedido":
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
        if "iniciar pedido" in msg:
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
                    "Cuando q
