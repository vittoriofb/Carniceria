from flask import Flask, request, Response, jsonify
from utils import process_message
import logging
import os
import html
import threading

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def procesar_en_segundo_plano(datos):
    """Procesa el mensaje sin bloquear la respuesta a Twilio."""
    try:
        process_message(datos)
    except Exception:
        logging.exception("❌ Error en procesamiento en segundo plano")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Detectar origen Twilio o curl
        from_number = request.form.get("From") or request.form.get("user_id")
        body = request.form.get("Body") or request.form.get("message")

        logging.info(f"📩 Mensaje recibido: {body} de {from_number}")

        if not from_number or not body:
            logging.warning("⚠️ Datos incompletos recibidos en webhook")
            return Response(
                '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Error: datos incompletos</Message></Response>',
                mimetype="application/xml"
            )

        # Si viene de Twilio (WhatsApp), responder rápido y procesar después
        if request.form.get("From") and request.form.get("Body"):
            # Respuesta fija inicial para que el usuario no espere
            safe_text = html.escape("Procesando tu pedido...")
            twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_text}</Message></Response>'

            # Procesar en segundo plano
            threading.Thread(target=procesar_en_segundo_plano, args=({
                "user_id": from_number,
                "message": body
            },)).start()

            return Response(twiml, mimetype="application/xml")

        # Si viene de curl, procesar normalmente y devolver JSON
        result = process_message({
            "user_id": from_number,
            "message": body
        })

        return jsonify(result)

    except Exception:
        logging.exception("❌ Error en webhook")
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Hubo un error en el servidor.</Message></Response>',
            mimetype="application/xml"
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚀 Servidor iniciando en 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
