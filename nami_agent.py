"""General planning layer for Nami.

Keeps natural-language understanding separate from deterministic tools.  The
planner never executes privileged actions; app.py remains responsible for
permissions, validation and execution.
"""
import json
import re

ALLOWED_TOOLS = {
    "chat", "estimate", "estimate_batch", "reminder", "memory",
    "image_analysis", "url_summary", "invoice", "quote", "case_task",
    "self_improve"
}
ALLOWED_OUTPUTS = {"text", "image", "pdf"}


def _json_object(raw):
    raw=(raw or "").strip()
    raw=re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I|re.S)
    start=raw.find("{"); end=raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("planner returned no JSON object")
    return json.loads(raw[start:end+1])


def normalize_plan(data, text=""):
    data=data if isinstance(data,dict) else {}
    tool=data.get("tool","chat")
    if tool not in ALLOWED_TOOLS: tool="chat"
    outputs=data.get("outputs") or ["text"]
    if isinstance(outputs,str): outputs=[outputs]
    outputs=[x for x in outputs if x in ALLOWED_OUTPUTS] or ["text"]
    # Preserve order without duplicates.
    outputs=list(dict.fromkeys(outputs))
    return {
        "tool":tool,
        "outputs":outputs,
        "batch":bool(data.get("batch",False)),
        "needs_recent_media":bool(data.get("needs_recent_media",False)),
        "instruction":str(data.get("instruction") or text or "")[:4000],
        "confidence":max(0.0,min(1.0,float(data.get("confidence",0.5) or 0.5))),
    }


def planning_prompt(text, has_recent_media=False):
    return f'''あなたはLINE業務AI「航海士ナミ」の意図ルーター。
ユーザーの言い回しをキーワード一致ではなく意味で理解し、実行計画をJSONだけで返す。
使えるtool: {sorted(ALLOWED_TOOLS)}
outputs: text/image/pdf の複数指定可。
複数物件・全部・まとめて等なら batch=true。見積資料が必要なら needs_recent_media=true。
普通の会話や既存toolに当てはまらない依頼は tool=chat。曖昧でも勝手に金額・期限・人物を作らない。
最近の画像/PDFあり: {bool(has_recent_media)}
ユーザー: {text}
形式: {{"tool":"chat","outputs":["text"],"batch":false,"needs_recent_media":false,"instruction":"元の意図を保った指示","confidence":0.9}}'''


def plan_with_ai(ai_call, text, uid, cid, has_recent_media=False):
    """Use the existing Nami AI call, with a safe chat fallback."""
    try:
        raw=ai_call(planning_prompt(text,has_recent_media),uid,cid)
        return normalize_plan(_json_object(raw),text)
    except Exception:
        return normalize_plan({"tool":"chat","instruction":text,"confidence":0.0},text)
