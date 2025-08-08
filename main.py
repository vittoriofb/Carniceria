from flask import Flask, request, jsonify
from utils import process_message
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    response = process_message(data)
    return jsonify(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)