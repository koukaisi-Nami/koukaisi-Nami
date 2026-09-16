import os
import base64
import hashlib
import hmac
import json
import re
import requests
import psycopg

from flask import Flask, request, abort

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set", flush=True)
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGSERIAL PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        user_id TEXT,
                        user_name TEXT,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, created_at DESC)
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memories_user
                    ON memories(user_id, created_at DESC)
                """)

            conn.commit()

        print("Database initialized", flush=True)

    except Exception as e:
        print("Database initialization error:", repr(e), flush=True)


def save_message(conversation_id, user_id, user_name, role, content):
    if not DATABASE_URL:
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messages
                    (conversation_id, user_id, user_name, role, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (conversation_id, user_id, user_name, role, content)
                )
            conn.commit()
    except Exception as e:
        print("save_message error:", repr(e), flush=True)


def get_recent_messages(conversation_id, limit=40):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, user_name, content
                    FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (conversation_id, limit)
                )
                rows = cur.fetchall()

        rows.reverse()
        return rows

    except Exception as e:
        print("get_recent_messages error:", repr(e), flush=True)
        return []


def save_memory(user_id, content):
    if not DATABASE_URL or not user_id:
        return False

    content = content.strip()
    if not content:
        return False

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM memories
                    WHERE user_id = %s
                    AND LOWER(content) = LOWER(%s)
                    LIMIT 1
                    """,
                    (user_id, content)
                )

                if cur.fetchone():
                    return True

                cur.execute(
                    """
                    INSERT INTO memories (user_id, content)
                    VALUES (%s, %s)
                    """,
                    (user_id, content)
                )
            conn.commit()

        return True

    except Exception as e:
        print("save_memory error:", repr(e), flush=True)
        return False


def get_memories(user_id, limit=50):
    if not DATABASE_URL or not user_id:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content
                    FROM memories
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                rows = cur.fetchall()

        return [row[0] for row in rows]

    except Exception as e:
        print("get_memories error:", repr(e), flush=True)
        return []


def delete_matching_memory(user_id, keyword):
    if not DATABASE_URL or not user_id:
        return 0

    keyword = keyword.strip()
    if not keyword:
        return 0

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM memories
                    WHERE user_id = %s
                    AND content ILIKE %s
                    """,
                    (user_id, f"%{keyword}%")
                )
                deleted = cur.rowcount
            conn.commit()

        return deleted

    except Exception as e:
        print("delete memory error:", repr(e), flush=True)
        return 0


def verify_signature(body, signature):
    if not CHANNEL_SECRET:
        return False

    digest = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")


def get_conversation_id(event):
    source = event.get("source", {})
    source_type = source.get("type")

    if source_type == "group":
        return "group:" + source.get("groupId", "unknown")

    if source_type == "room":
        return "room:" + source.get("roomId", "unknown")

    return "user:" + source.get("userId", "unknown")


def get_user_id(event):
    return event.get("source", {}).get("userId", "unknown")


def get_user_name(event):
    source = event.get("source", {})
    user_id = source.get("userId")

    if not user_id or not CHANNEL_ACCESS_TOKEN:
        return "ユーザー"

    source_type = source.get("type")

    if source_type == "group":
        group_id = source.get("groupId")
        if not group_id:
            return "ユーザー"
        url = f"https://api.line.me/v2/bot/group/{group_id}/member/{user_id}"

    elif source_type == "room":
        room_id = source.get("roomId")
        if not room_id:
            return "ユーザー"
        url = f"https://api.line.me/v2/bot/room/{room_id}/member/{user_id}"

    else:
        url = f"https://api.line.me/v2/bot/profile/{user_id}"

    headers = {"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.ok:
            return response.json().get("displayName", "ユーザー")
    except Exception as e:
        print("profile error:", repr(e), flush=True)

    return "ユーザー"


def reply_message(reply_token, text):
    if not CHANNEL_ACCESS_TOKEN or not reply_token:
        return

    text = str(text or "").strip()
    if not text:
        text = "うまく返事を作れなかった！"

    text = text[:4900]

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print("LINE reply:", response.status_code, response.text, flush=True)
    except Exception as e:
        print("LINE reply error:", repr(e), flush=True)


def extract_memory_command(text):
    patterns = [
        r"(.+?)って覚えて(?:おいて)?[！!。.]?$",
        r"(.+?)を覚えて(?:おいて)?[！!。.]?$",
        r"覚えて(?:おいて)?[：:]\s*(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text.strip())
        if match:
            memory = match.group(1).strip()
            memory = re.sub(r"^(ナミ|なみ)[、,\s]*", "", memory).strip()
            if memory:
                return memory

    return None


def extract_forget_command(text):
    patterns = [
        r"(.+?)を忘れて(?:ください)?[！!。.]?$",
        r"(.+?)って忘れて(?:ください)?[！!。.]?$",
        r"忘れて[：:]\s*(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text.strip())
        if match:
            keyword = match.group(1).strip()
            keyword = re.sub(r"^(ナミ|なみ)[、,\s]*", "", keyword).strip()
            if keyword:
                return keyword

    return None


def is_group_event(event):
    return event.get("source", {}).get("type") in ("group", "room")


def is_nami_called(text):
    normalized = text.lower().strip()
    return any(word in normalized for word in ["ナミ", "なみ", "nami"])


def remove_nami_call(text):
    cleaned = re.sub(
        r"(ナミ|なみ|nami)[、,！!？?\s]*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    return cleaned or text


def build_history(conversation_id):
    rows = get_recent_messages(conversation_id, limit=40)

    if not rows:
        return "まだ会話履歴はありません。"

    lines = []
    for role, user_name, content in rows:
        if role == "assistant":
            lines.append(f"航海士ナミ: {content}")
        else:
            lines.append(f"{user_name or 'ユーザー'}: {content}")

    return "\n".join(lines)


def build_memory_text(user_id):
    memories = get_memories(user_id, limit=50)

    if not memories:
        return "保存された長期記憶はまだありません。"

    return "\n".join(f"- {memory}" for memory in memories)


def ask_nami(text, conversation_id, user_id, user_name):
    if not OPENAI_API_KEY:
        return "OpenAI APIキーが設定されていません。"

    history = build_history(conversation_id)
    memories = build_memory_text(user_id)

    instructions = """
あなたはLINE上で働くAIアシスタント「航海士ナミ」です。

役割:
・優秀な営業アシスタント
・営業マンの右腕
・会話内容を整理する
・文章を作成する
・過去の会話と記憶を踏まえて回答する

会話スタイル:
・日本語
・親しみやすい
・自然なLINE口調
・基本は簡潔
・必要な場合だけ詳しく説明する
・分からないことを適当に断定しない
・過去の会話を知っている場合は自然に活用する
・毎回「記憶しています」など不自然な説明をしない

重要:
以下にはこのユーザーの長期記憶と、このトークルームの最近の会話履歴が含まれます。
回答に必要な場合のみ利用してください。
同じグループ内の他人の発言と、現在話しているユーザー本人の長期記憶を混同しないでください。
"""

    prompt = f"""
【現在話している人】
{user_name}

【この人の長期記憶】
{memories}

【このトークルームの最近の会話】
{history}

【今回のメッセージ】
{text}

上記を踏まえて自然に返答してください。
"""

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENAI_MODEL,
        "instructions": instructions,
        "input": prompt
    }

    try:
        response = requests.post(
            OPENAI_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if not response.ok:
            print("OpenAI HTTP error:", response.status_code, response.text, flush=True)
            return "ごめん、今ちょっと考えられなかった！"

        data = response.json()

        output_text = data.get("output_text")
        if output_text:
            return output_text.strip()

        for item in data.get("output", []):
            if item.get("type") != "message":
                continue

            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    answer = content.get("text", "")
                    if answer:
                        return answer.strip()

        return "うまく返事を作れなかった！"

    except Exception as e:
        print("OpenAI error:", repr(e), flush=True)
        return "ごめん、今ちょっと考えられなかった！"


@app.route("/", methods=["GET"])
def home():
    return "航海士ナミ、航海中🏴‍☠️"


@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "database": bool(DATABASE_URL),
        "openai": bool(OPENAI_API_KEY),
        "line": bool(CHANNEL_SECRET and CHANNEL_ACCESS_TOKEN)
    }


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(raw_body, signature):
        abort(400)

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        abort(400)

    for event in data.get("events", []):
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "").strip()
        if not text:
            continue

        reply_token = event.get("replyToken")
        conversation_id = get_conversation_id(event)
        user_id = get_user_id(event)
        user_name = get_user_name(event)

        # Save every text message, even when Nami stays silent.
        save_message(conversation_id, user_id, user_name, "user", text)

        memory = extract_memory_command(text)

        if memory:
            success = save_memory(user_id, memory)
            reply = (
                f"覚えておくね！🧭\n「{memory}」"
                if success
                else "ごめん、記憶の保存に失敗した！"
            )

            save_message(conversation_id, "nami", "航海士ナミ", "assistant", reply)
            reply_message(reply_token, reply)
            continue

        forget_keyword = extract_forget_command(text)

        if forget_keyword:
            deleted = delete_matching_memory(user_id, forget_keyword)

            reply = (
                f"「{forget_keyword}」に関する記憶を忘れたよ🧭"
                if deleted
                else f"「{forget_keyword}」に関する記憶は見つからなかったよ。"
            )

            save_message(conversation_id, "nami", "航海士ナミ", "assistant", reply)
            reply_message(reply_token, reply)
            continue

        # In groups Nami listens to all text, but only answers when called.
        if is_group_event(event):
            if not is_nami_called(text):
                continue
            text_for_ai = remove_nami_call(text)
        else:
            text_for_ai = text

        ai_reply = ask_nami(
            text_for_ai,
            conversation_id,
            user_id,
            user_name
        )

        save_message(
            conversation_id,
            "nami",
            "航海士ナミ",
            "assistant",
            ai_reply
        )

        reply_message(reply_token, ai_reply)

    return "OK"


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
