from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from utils import process_message

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.form.to_dict()
    user_id = data.get("From", "unknown")
    message = data.get("Body", "")
    
    # Procesas el mensaje (tu lógica propia)
    fake_data = {"user_id": user_id, "message": message}
    response_data = process_message(fake_data)
    
    # Construyes una respuesta TwiML válida
    twiml_response = MessagingResponse()
    twiml_response.message(response_data["reply"])  # o simplemente el texto que quieras enviar
    
    return str(twiml_response), 200, {"Content-Type": "application/xml"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
