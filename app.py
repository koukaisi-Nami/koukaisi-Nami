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
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return "航海士ナミ、航海中🏴‍☠️"


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

                ai_reply = ask_nami(text)

                reply_message(
                    reply_token,
                    ai_reply
                )

    return "OK"


def ask_nami(text):
    if not OPENAI_API_KEY:
        return "OpenAI APIキーが設定されていません。"

    url = "https://api.openai.com/v1/responses"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-5.6-luna",
        "instructions": """
あなたは「航海士ナミ」というAIアシスタントです。
LINE上でユーザーと自然に会話してください。

・日本語で話す
・親しみやすく、分かりやすく答える
・基本は簡潔に答える
・必要な場合は詳しく説明する
・分からないことを適当に断定しない
""",
        "input": text
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", "")

        return "うまく返事を作れませんでした！"

    except Exception as e:
        print("OpenAI error:", e, flush=True)
        return "ごめん、今ちょっと考えられなかった！"
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
