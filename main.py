from flask import Flask, request, Response
from utils import process_message
import logging
import os
import html  # para escapar texto

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

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

        result = process_message({
            "user_id": from_number,
            "message": body
        })

        reply_text = result.get("reply", "Error interno")

        # Escapar caracteres especiales para TwiML
        safe_text = html.escape(reply_text)

        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_text}</Message></Response>'
        return Response(twiml, mimetype="application/xml")

    except Exception:
        logging.exception("❌ Error en webhook")
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Hubo un error en el servidor.</Message></Response>'
        return Response(twiml, mimetype="application/xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚀 Servidor iniciando en 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
