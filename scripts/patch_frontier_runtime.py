#!/usr/bin/env python3
from pathlib import Path
import ast
import re

p = Path("app.py")
s = p.read_text()

IMPORT = "from nami_frontier import model_for_task, reasoning_for_task, task_for_text\n"
MEDIA_IMPORT = "from nami_openai_media import wants_image_generation, image_prompt, generate_image\n"
ANCHOR = "from owner_guard import can_self_improve\n"
if IMPORT not in s:
    if ANCHOR not in s:
        raise SystemExit("owner guard import anchor missing")
    s = s.replace(ANCHOR, ANCHOR + IMPORT, 1)
if MEDIA_IMPORT not in s:
    if IMPORT not in s:
        raise SystemExit("frontier import anchor missing")
    s = s.replace(IMPORT, IMPORT + MEDIA_IMPORT, 1)

old_model = 'MODEL=os.getenv("OPENAI_MODEL","gpt-5.6-luna")'
new_model = 'MODEL=os.getenv("OPENAI_MODEL") or model_for_task("chat")'
if old_model in s:
    s = s.replace(old_model, new_model, 1)
elif new_model not in s:
    raise SystemExit("MODEL anchor missing")

if "GENERATED_IMAGE_CACHE={}" not in s:
    anchor = "HTTP=requests.Session()\n"
    if anchor not in s:
        raise SystemExit("HTTP session anchor missing")
    s = s.replace(anchor, anchor + "GENERATED_IMAGE_CACHE={}\nGENERATED_IMAGE_TTL=900\n", 1)


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
    # Optional OpenAI hosted RAG. It activates only when a vector store ID is configured.
    if 'OPENAI_VECTOR_STORE_ID' not in block:
        anchor3 = '    if needs_web:\n        payload["tools"]=[{"type":"web_search"}]\n        payload["tool_choice"]="auto"\n'
        if anchor3 in block:
            repl = anchor3 + '    vector_store=os.getenv("OPENAI_VECTOR_STORE_ID","").strip()\n    if vector_store and runtime_task in ("knowledge","document","balanced"):\n        payload.setdefault("tools",[]).append({"type":"file_search","vector_store_ids":[vector_store]})\n        payload["tool_choice"]="auto"\n'
            block = block.replace(anchor3, repl, 1)
    return block

s = patch_function(s, "ai", patch_ai)


def patch_ctx(block):
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

# Add a bounded image-generation delivery layer without touching existing estimate images.
if "def start_frontier_image_generation(" not in s:
    marker = '@app.get("/")\n'
    if marker not in s:
        raise SystemExit("health endpoint anchor missing")
    helpers = '''def push_generated_image(target,url,caption=""):\n    msgs=[{"type":"image","originalContentUrl":url,"previewImageUrl":url}]\n    if caption: msgs.append({"type":"text","text":caption[:4900]})\n    try:\n        r=HTTP.post("https://api.line.me/v2/bot/message/push",headers={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json"},json={"to":target,"messages":msgs[:5]},timeout=25)\n        if not r.ok: print("LINE generated image",r.status_code,r.text[:1000],flush=True)\n        return r.ok\n    except Exception as x:\n        print("push_generated_image",repr(x),flush=True); return False\n\n@app.get("/generated-image/<key>.png")\ndef generated_image_file(key):\n    row=GENERATED_IMAGE_CACHE.get(key)\n    if not row:return "not found",404\n    created,blob=row\n    if time.time()-created>GENERATED_IMAGE_TTL:\n        GENERATED_IMAGE_CACHE.pop(key,None); return "expired",404\n    return Response(blob,mimetype="image/png",headers={"Cache-Control":"public, max-age=600"})\n\ndef start_frontier_image_generation(cid,target,prompt,base):\n    def worker():\n        try:\n            blob=generate_image(prompt,OPENAI_KEY,HTTP)\n            key=hashlib.sha256((cid+str(time.time())+prompt[:200]).encode()).hexdigest()[:28]\n            GENERATED_IMAGE_CACHE[key]=(time.time(),blob)\n            url=f"{base}/generated-image/{key}.png"\n            push_generated_image(target,url,"画像できたよ🧭")\n            save_msg("imagegen:"+key,cid,"bot","航海士ナミ","assistant","[生成画像] "+prompt[:500])\n        except Exception as x:\n            print("frontier_image_generation",repr(x),flush=True)\n            push_line(target,"画像生成でエラーが出たよ。既存機能には影響していないよ。")\n    threading.Thread(target=worker,daemon=True,name="nami-image-gen").start()\n\n'''
    s = s.replace(marker, helpers + marker, 1)


def patch_webhook(block):
    if "wants_image_generation(text)" not in block:
        anchor = "        if (text or '').strip()=='おやすみ':\n"
        if anchor not in block:
            raise SystemExit("webhook text anchor missing")
        insert = '''        if wants_image_generation(text):\n            base=os.getenv('PUBLIC_BASE_URL','https://koukaisi-nami.onrender.com').rstrip('/')\n            reply(e.get('replyToken'),'画像を作り始めたよ🧭 完成したらここに送るね。')\n            start_frontier_image_generation(cid,line_target(e),image_prompt(text),base)\n            continue\n'''
        block = block.replace(anchor, insert + anchor, 1)
    return block

s = patch_function(s, "webhook", patch_webhook)

required = (
    'CREATE TABLE IF NOT EXISTS memories',
    'def add_memory(',
    'def mems(',
    'from owner_guard import can_self_improve',
    'awaiting and can_self_improve(uid)',
    'def start_frontier_image_generation(',
    'wants_image_generation(text)',
)
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit("runtime invariant missing: " + repr(missing))

ast.parse(s)
p.write_text(s)
print("frontier runtime patch OK")
