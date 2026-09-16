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
                CREATE TABLE IF NOT EXISTS members (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    notes TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT,
                    user_id TEXT,
                    category TEXT DEFAULT 'general',
                    scope TEXT DEFAULT 'personal',
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE memories
                ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'personal'
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    creator_user_id TEXT,
                    assignee_name TEXT,
                    title TEXT NOT NULL,
                    due_at TIMESTAMPTZ,
                    status TEXT DEFAULT 'open',
                    reminder_count INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_lookup
                ON conversations (conversation_id, created_at)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_lookup
                ON memories (conversation_id, user_id, created_at)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_lookup
                ON tasks (conversation_id, status, due_at)
            """)
        conn.commit()

    print("Database initialized", flush=True)


def get_source(event):
    return event.get("source", {})


def get_user_id(event):
    return get_source(event).get("userId", "unknown")


def get_conversation_id(event):
    source = get_source(event)
    source_type = source.get("type")

    if source_type == "group":
        return "group:" + source.get("groupId", "unknown")
    if source_type == "room":
        return "room:" + source.get("roomId", "unknown")
    return "user:" + source.get("userId", "unknown")


def get_line_display_name(user_id):
    if not user_id or user_id == "unknown" or not CHANNEL_ACCESS_TOKEN:
        return None

    try:
        response = requests.get(
            f"https://api.line.me/v2/bot/profile/{user_id}",
            headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("displayName")
    except Exception as e:
        print("LINE profile error:", e, flush=True)

    return None


def upsert_member(user_id, display_name=None):
    if not DATABASE_URL or not user_id or user_id == "unknown":
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO members (user_id, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        display_name = COALESCE(EXCLUDED.display_name, members.display_name),
                        updated_at = NOW()
                """, (user_id, display_name))
            conn.commit()
    except Exception as e:
        print("Member save error:", e, flush=True)


def get_member(user_id):
    if not DATABASE_URL:
        return None

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT display_name, notes FROM members WHERE user_id = %s",
                    (user_id,)
                )
                row = cur.fetchone()

        if row:
            return {"display_name": row[0], "notes": row[1]}
    except Exception as e:
        print("Member lookup error:", e, flush=True)

    return None


def save_message(conversation_id, user_id, role, content):
    if not DATABASE_URL:
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversations
                    (conversation_id, user_id, role, content)
                    VALUES (%s, %s, %s, %s)
                """, (conversation_id, user_id, role, content))
            conn.commit()
    except Exception as e:
        print("Conversation save error:", e, flush=True)


def get_history(conversation_id, limit=30):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT role, content, user_id
                    FROM conversations
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (conversation_id, limit))
                rows = cur.fetchall()

        rows.reverse()
        return [
            {"role": role, "content": content, "user_id": user_id}
            for role, content, user_id in rows
        ]
    except Exception as e:
        print("History error:", e, flush=True)
        return []


def save_memory(
    conversation_id,
    user_id,
    content,
    category="general",
    scope="personal"
):
    if not DATABASE_URL:
        return False

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memories
                    (conversation_id, user_id, category, scope, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (conversation_id, user_id, category, scope, content))
            conn.commit()
        return True
    except Exception as e:
        print("Memory save error:", e, flush=True)
        return False


def get_memories(conversation_id, user_id, limit=50):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT category, scope, content
                    FROM memories
                    WHERE
                        (scope = 'personal' AND user_id = %s)
                        OR (scope = 'group' AND conversation_id = %s)
                        OR scope = 'global'
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, conversation_id, limit))
                rows = cur.fetchall()

        return [
            {"category": category, "scope": scope, "content": content}
            for category, scope, content in rows
        ]
    except Exception as e:
        print("Memory lookup error:", e, flush=True)
        return []


def detect_memory_command(text):
    patterns = [
        r"(.+?)って覚えて",
        r"(.+?)を覚えて",
        r"覚えておいて[、,:：]?\s*(.+)",
        r"記憶して[、,:：]?\s*(.+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    return None


def create_task(conversation_id, creator_user_id, title, assignee_name=None, due_at=None):
    if not DATABASE_URL:
        return None

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks
                    (conversation_id, creator_user_id, assignee_name, title, due_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    conversation_id,
                    creator_user_id,
                    assignee_name,
                    title,
                    due_at
                ))
                task_id = cur.fetchone()[0]
            conn.commit()
        return task_id
    except Exception as e:
        print("Task create error:", e, flush=True)
        return None


def get_open_tasks(conversation_id):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, assignee_name, title, due_at
                    FROM tasks
                    WHERE conversation_id = %s AND status = 'open'
                    ORDER BY due_at NULLS LAST, created_at
                    LIMIT 30
                """, (conversation_id,))
                return cur.fetchall()
    except Exception as e:
        print("Task lookup error:", e, flush=True)
        return []


def complete_task(task_id):
    if not DATABASE_URL:
        return False

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE tasks
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = %s
                """, (task_id,))
            conn.commit()
        return True
    except Exception as e:
        print("Task complete error:", e, flush=True)
        return False


def format_tasks(tasks):
    if not tasks:
        return "未完了タスクはありません。"

    lines = []
    for task_id, assignee, title, due_at in tasks:
        assignee_text = assignee or "担当者未設定"
        due_text = due_at.isoformat() if due_at else "期限未設定"
        lines.append(f"#{task_id} / {assignee_text} / {title} / {due_text}")

    return "\n".join(lines)


def extract_output_text(data):
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")

    return ""


def ask_nami(text, history, memories, member, tasks):
    if not OPENAI_API_KEY:
        return "OpenAI APIキーが設定されていません。"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history_text = ""
    for message in history:
        speaker = "ナミ" if message["role"] == "assistant" else "ユーザー"
        history_text += f"{speaker}: {message['content']}\n"

    memory_text = "\n".join(
        f"- [{memory['category']}] {memory['content']}"
        for memory in memories
    ) or "長期記憶なし"

    member_name = member.get("display_name") if member else None
    member_notes = member.get("notes") if member else None

    prompt = f"""
【現在話しているメンバー】
名前: {member_name or "未登録"}
補足: {member_notes or "なし"}

【長期記憶】
{memory_text}

【現在の未完了タスク】
{format_tasks(tasks)}

【直近の会話】
{history_text}

【今回の発言】
{text}
"""

    payload = {
        "model": "gpt-5.6-luna",
        "instructions": """
あなたは「航海士ナミ🧭」というLINE上のAIアシスタントです。
日本語で自然に話し、親しみやすく、基本は結論から簡潔に答えてください。
会話履歴と長期記憶を踏まえて回答してください。
複数人のグループでは誰の話かを意識してください。
最新情報が必要ならWeb検索を使ってください。
知らないことは作らないでください。
タスクが完了したと勝手に判断しないでください。
""",
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
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
            print("OpenAI status:", response.status_code, response.text, flush=True)

        response.raise_for_status()
        answer = extract_output_text(response.json())
        return answer or "うまく返事を作れなかった！"
    except Exception as e:
        print("OpenAI error:", e, flush=True)
        return "ごめん、今ちょっと考えられなかった！"


def reply_message(reply_token, text):
    if not CHANNEL_ACCESS_TOKEN or not reply_token:
        return

    try:
        response = requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text[:5000]}]
            },
            timeout=10
        )
        print("LINE:", response.status_code, response.text, flush=True)
    except Exception as e:
        print("LINE reply error:", e, flush=True)


@app.route("/", methods=["GET"])
def home():
    return "航海士ナミ、航海中！🧭🏴‍☠️"


def is_group_conversation(event):
    return get_source(event).get("type") in ("group", "room")


def is_nami_called(text):
    normalized = re.sub(r"[\\s　]+", "", text).lower()
    call_names = (
        "ナミ",
        "なみ",
        "航海士ナミ",
        "航海士なみ"
    )
    return any(name.lower() in normalized for name in call_names)


def remove_nami_call(text):
    cleaned = text
    for name in ("航海士ナミ", "航海士なみ", "ナミ", "なみ"):
        cleaned = cleaned.replace(name, "")
    cleaned = cleaned.lstrip("、,。！!？?:： 　")
    return cleaned.strip()


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
        expected_signature = base64.b64encode(hash_value).decode("utf-8")

        if not hmac.compare_digest(expected_signature, signature):
            abort(400)

    data = json.loads(body)

    for event in data.get("events", []):
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "").strip()
        if not text:
            continue

        # In groups/rooms, Nami stays quiet unless someone explicitly calls her.
        # Uncalled group messages are not saved to conversation history or memory.
        if is_group_conversation(event):
            if not is_nami_called(text):
                continue

            text = remove_nami_call(text)
            if not text:
                text = "呼んだ？"

        reply_token = event.get("replyToken")
        user_id = get_user_id(event)
        conversation_id = get_conversation_id(event)

        member = get_member(user_id)
        if not member:
            display_name = get_line_display_name(user_id)
            upsert_member(user_id, display_name)
            member = get_member(user_id)

        memory_content = detect_memory_command(text)

        if memory_content:
            if save_memory(conversation_id, user_id, memory_content, "explicit"):
                save_message(conversation_id, user_id, "user", text)
                answer = f"覚えたよ🧠✨\n「{memory_content}」"
                save_message(conversation_id, None, "assistant", answer)
                reply_message(reply_token, answer)
                continue

        if text in ["タスク一覧", "タスク見せて", "未完了タスク", "やること一覧"]:
            tasks = get_open_tasks(conversation_id)
            answer = "📋 未完了タスク\n\n" + format_tasks(tasks)
            save_message(conversation_id, user_id, "user", text)
            save_message(conversation_id, None, "assistant", answer)
            reply_message(reply_token, answer)
            continue

        history = get_history(conversation_id, limit=30)
        memories = get_memories(conversation_id, user_id, limit=50)
        tasks = get_open_tasks(conversation_id)

        ai_reply = ask_nami(text, history, memories, member, tasks)

        save_message(conversation_id, user_id, "user", text)
        save_message(conversation_id, None, "assistant", ai_reply)
        reply_message(reply_token, ai_reply)

    return "OK"


try:
    init_db()
except Exception as e:
    print("DB initialization error:", e, flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
