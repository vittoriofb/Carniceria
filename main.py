from flask import Flask, request, Response, jsonify
from utils import process_message
import logging
import os
import html

from data import PRODUCTOS_DB
from expresiones import _normalize

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Crear índice normalizado ---
INDEX_NORMALIZADO = { _normalize(k): k for k in PRODUCTOS_DB }

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        from_number = request.form.get("From") or request.form.get("user_id")
        body = request.form.get("Body") or request.form.get("message")

        logging.info(f"📩 Mensaje recibido: {body} de {from_number}")

        if not from_number or not body:
            logging.warning("⚠️ Datos incompletos recibidos en webhook")
            return Response(
                '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Error: datos incompletos</Message></Response>',
                mimetype="application/xml"
            )

        # Si viene de Twilio (WhatsApp), contestar directamente con TwiML
        if request.form.get("From") and request.form.get("Body"):
            resultado = process_message({
                "user_id": from_number,
                "message": body
            })

            # Determinar texto final
            if isinstance(resultado, dict) and "respuesta" in resultado:
                final_text = resultado["respuesta"]
            else:
                final_text = str(resultado)

            # Quitar "Reply:" si aparece al inicio
            if final_text.strip().lower().startswith("reply:"):
                final_text = final_text.split(":", 1)[1].strip()

            safe_text = html.escape(final_text)
            twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_text}</Message></Response>'
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
