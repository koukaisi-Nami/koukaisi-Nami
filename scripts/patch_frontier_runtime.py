#!/usr/bin/env python3
from pathlib import Path
import ast
import re

p = Path("app.py")
s = p.read_text()

IMPORT = "from nami_frontier import model_for_task, reasoning_for_task, task_for_text\n"
ANCHOR = "from owner_guard import can_self_improve\n"
if IMPORT not in s:
    if ANCHOR not in s:
        raise SystemExit("owner guard import anchor missing")
    s = s.replace(ANCHOR, ANCHOR + IMPORT, 1)

old_model = 'MODEL=os.getenv("OPENAI_MODEL","gpt-5.6-luna")'
new_model = 'MODEL=os.getenv("OPENAI_MODEL") or model_for_task("chat")'
if old_model in s:
    s = s.replace(old_model, new_model, 1)
elif new_model not in s:
    raise SystemExit("MODEL anchor missing")


def function_span(source, name):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines(keepends=True)
            start = sum(len(x) for x in lines[: node.lineno - 1])
            end = sum(len(x) for x in lines[: node.end_lineno])
            return start, end
    raise SystemExit(f"function not found: {name}")


def patch_function(source, name, transform):
    start, end = function_span(source, name)
    block = source[start:end]
    new = transform(block)
    if new == block:
        # Idempotent runs are accepted only if frontier routing is already present.
        if "model_for_task(" not in block and name in {
            "group_attachments", "semantic_intent_route", "targeted_candidate",
            "supervisor_review", "media_ai", "manager_review", "ai",
        }:
            raise SystemExit(f"frontier patch made no change: {name}")
    return source[:start] + new + source[end:]


def replace_model(block, task):
    return block.replace('"model":MODEL', f'"model":model_for_task("{task}",OPENAI_KEY,HTTP)', 1)


for name, task in (
    ("group_attachments", "document"),
    ("semantic_intent_route", "chat"),
    ("targeted_candidate", "self_improvement"),
    ("supervisor_review", "code_review"),
    ("media_ai", "document"),
    ("manager_review", "manager"),
):
    s = patch_function(s, name, lambda block, task=task: replace_model(block, task))


def patch_ai(block):
    if "runtime_task=task_for_text(text)" not in block:
        anchor = '    needs_web=bool(re.search(r"(最新|今日|現在|ニュース|天気|相場|営業時間|公式|検索して|調べて|web|ネット)",text or "",re.I))\n'
        if anchor not in block:
            raise SystemExit("ai needs_web anchor missing")
        insert = (
            anchor
            + '    runtime_task=task_for_text(text)\n'
            + '    if img: runtime_task="vision"\n'
            + '    elif needs_web and runtime_task=="chat": runtime_task="web"\n'
            + '    runtime_model=model_for_task(runtime_task,OPENAI_KEY,HTTP)\n'
            + '    runtime_reasoning=reasoning_for_task(runtime_task)\n'
        )
        block = block.replace(anchor, insert, 1)
    block = block.replace('payload={"model":MODEL,"instructions":SYSTEM', 'payload={"model":runtime_model,"instructions":SYSTEM', 1)
    if 'payload["reasoning"]={"effort":runtime_reasoning}' not in block:
        anchor2 = '    if needs_web:\n'
        if anchor2 not in block:
            raise SystemExit("ai web anchor missing")
        block = block.replace(anchor2, '    if runtime_reasoning != "none":\n        payload["reasoning"]={"effort":runtime_reasoning}\n' + anchor2, 1)
    return block

s = patch_function(s, "ai", patch_ai)


def patch_ctx(block):
    # Ordinary chat must not carry the code-change safety manual on every request.
    # Self-improvement has dedicated guards in targeted_candidate/reviewed_candidate.
    if '【コード改善PRの安全手順】' in block:
        block = re.sub(
            r'\n    safety=\(.*?\n    \)\n',
            '\n    safety=""\n',
            block,
            count=1,
            flags=re.S,
        )
    return block

s = patch_function(s, "ctx", patch_ctx)

# Runtime invariants: never touch memory schema/data or owner gate in this patch.
required = (
    'CREATE TABLE IF NOT EXISTS memories',
    'def add_memory(',
    'def mems(',
    'from owner_guard import can_self_improve',
    'awaiting and can_self_improve(uid)',
)
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit("runtime invariant missing: " + repr(missing))

ast.parse(s)
p.write_text(s)
print("frontier runtime patch OK")
