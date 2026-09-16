import os
import base64
import hashlib
import hmac
import json
import requests
import psycopg

from flask import Flask, request, abort

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set", flush=True)
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    user_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_id
                ON conversations (conversation_id, created_at)
            """)

        conn.commit()


def get_conversation_id(event):
    source = event.get("source", {})

    if source.get("type") == "group":
        return "group:" + source.get("groupId", "unknown")

    if source.get("type") == "room":
        return "room:" + source.get("roomId", "unknown")

    return "user:" + source.get("userId", "unknown")


def save_message(conversation_id, user_id, role, content):
    if not DATABASE_URL:
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations
                    (conversation_id, user_id, role, content)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conversation_id, user_id, role, content)
                )
            conn.commit()

    except Exception as e:
        print("DB save error:", e, flush=True)


def get_history(conversation_id, limit=20):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content
                    FROM conversations
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (conversation_id, limit)
                )

                rows = cur.fetchall()

        rows.reverse()

        return [
            {
                "role": role,
                "content": content
            }
            for role, content in rows
        ]

    except Exception as e:
        print("DB history error:", e, flush=True)
        return []


@app.route("/", methods=["GET"])
def home():
    return "航海士ナミ、記憶しながら航海中！🏴‍☠️"


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature", "")

    if CHANNEL_SECRET:
        hash_value = hmac.new(
            CHANNEL_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).digest()

        expected_signature = base64.b64encode(
            hash_value
        ).decode("utf-8")

        if not hmac.compare_digest(
            expected_signature,
            signature
        ):
            abort(400)

    data = json.loads(body)

    for event in data.get("events", []):
        if event.get("type") != "message":
            continue

        message = event.get("message", {})

        if message.get("type") != "text":
            continue

        text = message.get("text", "")
        reply_token = event.get("replyToken")

        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        conversation_id = get_conversation_id(event)

        history = get_history(conversation_id)

        ai_reply = ask_nami(
            text,
            history
        )

        save_message(
            conversation_id,
            user_id,
            "user",
            text
        )

        save_message(
            conversation_id,
            None,
            "assistant",
            ai_reply
        )

        reply_message(
            reply_token,
            ai_reply
        )

    return "OK"


def ask_nami(text, history):
    if not OPENAI_API_KEY:
        return "OpenAI APIキーが設定されていません。"

    url = "https://api.openai.com/v1/responses"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    conversation_text = ""

    for message in history:
        if message["role"] == "user":
            name = "ユーザー"
        else:
            name = "ナミ"

        conversation_text += (
            f"{name}: {message['content']}\n"
        )

    prompt = f"""
これまでの会話:
{conversation_text}

今回のユーザーの発言:
{text}
"""

    payload = {
        "model": "gpt-5.6-luna",
        "instructions": """
あなたは「航海士ナミ🧭」というAIアシスタントです。

LINE上でユーザーと自然に会話してください。

役割:
・仕事と日常を支える有能な航海士
・過去の会話を踏まえて話す
・情報を整理して分かりやすく伝える
・文章作成や相談にも対応する

会話ルール:
・日本語で話す
・親しみやすい
・基本は結論から簡潔に話す
・必要なら詳しく説明する
・知らないことを勝手に作らない
・過去の会話と矛盾しないようにする
""",
        "input": prompt
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
                "text": text[:5000]
            }
        ]
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10
    )

    print(
        "LINE:",
        response.status_code,
        response.text,
        flush=True
    )


try:
    init_db()
except Exception as e:
    print("DB initialization error:", e, flush=True)


if __name__ == "__main__":
    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
