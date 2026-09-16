import os
import base64
import hashlib
import hmac
import json
import re
import requests
import psycopg

from flask import Flask, request, abort
from datetime import datetime, timezone

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

OPENAI_URL = "https://api.openai.com/v1/responses"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set", flush=True)
        return

    with get_db() as conn:
        with conn.cursor() as cur:

            # 会話履歴
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

            # メンバー
            cur.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    notes TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # 長期記憶
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT,
                    user_id TEXT,
                    category TEXT DEFAULT 'general',
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # タスク
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


# =========================================================
# LINE IDENTIFICATION
# =========================================================

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
    if not user_id or user_id == "unknown":
        return None

    if not CHANNEL_ACCESS_TOKEN:
        return None

    url = f"https://api.line.me/v2/bot/profile/{user_id}"

    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
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
                cur.execute(
                    """
                    INSERT INTO members (user_id, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        display_name = COALESCE(
                            EXCLUDED.display_name,
                            members.display_name
                        ),
                        updated_at = NOW()
                    """,
                    (user_id, display_name)
                )

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
                    """
                    SELECT display_name, notes
                    FROM members
                    WHERE user_id = %s
                    """,
                    (user_id,)
                )

                row = cur.fetchone()

        if row:
            return {
                "display_name": row[0],
                "notes": row[1]
            }

    except Exception as e:
        print("Member lookup error:", e, flush=True)

    return None


# =========================================================
# CONVERSATION MEMORY
# =========================================================

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
                    (
                        conversation_id,
                        user_id,
                        role,
                        content
                    )
                )

            conn.commit()

    except Exception as e:
        print("Conversation save error:", e, flush=True)


def get_history(conversation_id, limit=30):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, user_id
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
                "role": row[0],
                "content": row[1],
                "user_id": row[2]
            }
            for row in rows
        ]

    except Exception as e:
        print("History error:", e, flush=True)
        return []


# =========================================================
# LONG-TERM MEMORY
# =========================================================

def save_memory(
    conversation_id,
    user_id,
    content,
    category="general"
):
    if not DATABASE_URL:
        return False

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memories
                    (conversation_id, user_id, category, content)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        conversation_id,
                        user_id,
                        category,
                        content
                    )
                )

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
                cur.execute(
                    """
                    SELECT category, content
                    FROM memories
                    WHERE
                        conversation_id = %s
                        OR user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (
                        conversation_id,
                        user_id,
                        limit
                    )
                )

                rows = cur.fetchall()

        return [
            {
                "category": row[0],
                "content": row[1]
            }
            for row in rows
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


# =========================================================
# TASKS
# =========================================================

def create_task(
