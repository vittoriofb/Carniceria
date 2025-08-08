from flask import Flask, request, jsonify
from utils import process_message

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Esto recogerá los datos correctamente desde Twilio
    data = request.form.to_dict()
    user_id = data.get("From", "unknown")
    message = data.get("Body", "")
    
    # Simulamos la estructura como si viniera de tu curl
    fake_data = {"user_id": user_id, "message": message}
    
    response = process_message(fake_data)
    
    # Twilio necesita una respuesta en texto plano
    return response["reply"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
