import os
import base64
import hashlib
import hmac
import json
import requests

from flask import Flask, request, abort

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")


@app.route("/", methods=["GET"])
def home():
    return "航海士ナミ、航海中！🏴‍☠️"


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature", "")

    if CHANNEL_SECRET:
        digest = hmac.new(
            CHANNEL_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).digest()

        expected_signature = base64.b64encode(digest).decode("utf-8")

        if not hmac.compare_digest(signature, expected_signature):
            abort(400)

    data = json.loads(body)

    for event in data.get("events", []):
        if event.get("type") == "message":
            message = event.get("message", {})

            if message.get("type") == "text":
                text = message.get("text", "")
                reply_token = event.get("replyToken")

                reply_message(
                    reply_token,
                    f"航海士ナミです🧭\n\n「{text}」\n了解しました！"
                )

    return "OK"


def reply_message(reply_token, text):
    if not CHANNEL_ACCESS_TOKEN:
        return

    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

　　response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(response.status_code, response.text, flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
