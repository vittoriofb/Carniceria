from flask import Flask, request, Response
from utils import process_message
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Recibir datos desde Twilio o curl
        from_number = request.form.get("From") or request.form.get("user_id")
        body = request.form.get("Body") or request.form.get("message")

        if not from_number or not body:
            return Response("<Response><Message>Error: datos incompletos</Message></Response>", mimetype="application/xml")

        # Llamar al procesador del mensaje
        result = process_message({
            "user_id": from_number,
            "message": body
        })

        reply_text = result.get("reply", "Error interno")

        # Responder en formato TwiML
        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply_text}</Message></Response>'
        return Response(twiml, mimetype="application/xml")

    except Exception:
        logging.exception("Error en webhook")
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Hubo un error en el servidor.</Message></Response>'
        return Response(twiml, mimetype="application/xml")
