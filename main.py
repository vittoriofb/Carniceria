from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from utils import process_message
import logging
import os

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.form.to_dict()
        logging.info(f"Datos recibidos: {data}")

        user_id = data.get("From", "unknown")
        message = data.get("Body", "")

        if not message.strip():
            logging.warning("Mensaje vacío recibido")
            reply_text = "No entendí tu mensaje, ¿puedes repetirlo?"
        else:
            try:
                fake_data = {"user_id": user_id, "message": message}
                response_data = process_message(fake_data)
                reply_text = response_data.get("reply", "No tengo respuesta para eso.")
            except Exception as e:
                logging.exception("Error en process_message")
                reply_text = "Lo siento, hubo un error procesando tu mensaje."

        # Construir respuesta Twilio
        twiml_response = MessagingResponse()
        twiml_response.message(reply_text)

        return str(twiml_response), 200, {"Content-Type": "application/xml"}

    except Exception as e:
        logging.exception("Error inesperado en webhook")
        twiml_response = MessagingResponse()
        twiml_response.message("Error interno. Inténtalo más tarde.")
        return str(twiml_response), 500, {"Content-Type": "application/xml"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
