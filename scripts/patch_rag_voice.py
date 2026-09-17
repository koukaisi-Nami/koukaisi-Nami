#!/usr/bin/env python3
from pathlib import Path
import ast

p=Path('app.py')
s=p.read_text()

old='from nami_openai_media import wants_image_generation, image_prompt, generate_image\n'
new='from nami_openai_media import wants_image_generation, image_prompt, generate_image, transcribe\nfrom nami_rag import create_vector_store, index_pdf, file_search_tool\n'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('frontier media import anchor missing')

# Non-destructive schema extension only; never modify or delete existing memories.
rag_schema='''            c.execute("""CREATE TABLE IF NOT EXISTS rag_stores(\n              scope TEXT NOT NULL,scope_id TEXT NOT NULL,vector_store_id TEXT NOT NULL UNIQUE,\n              created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW(),\n              PRIMARY KEY(scope,scope_id))""")\n            c.execute("""CREATE TABLE IF NOT EXISTS rag_files(\n              id BIGSERIAL PRIMARY KEY,scope TEXT NOT NULL,scope_id TEXT NOT NULL,\n              conversation_id TEXT NOT NULL,line_message_id TEXT,filename TEXT DEFAULT '',\n              openai_file_id TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")\n            c.execute("CREATE INDEX IF NOT EXISTS rag_files_scope_idx ON rag_files(scope,scope_id,created_at DESC)")\n'''
anchor='            c.execute("""CREATE TABLE IF NOT EXISTS estimate_batch_items(\n'
if 'CREATE TABLE IF NOT EXISTS rag_stores' not in s:
    if anchor not in s: raise SystemExit('rag schema anchor missing')
    s=s.replace(anchor,rag_schema+anchor,1)

helpers='''\ndef rag_store_ids(uid,cid):\n    if not DB_URL:return []\n    try:\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("""SELECT vector_store_id FROM rag_stores WHERE\n                  (scope='user' AND scope_id=%s) OR (scope='conversation' AND scope_id=%s)\n                  OR (scope='company' AND scope_id='company') ORDER BY updated_at DESC LIMIT 3""",(str(uid),str(cid)))\n                return [r[0] for r in c.fetchall() if r and str(r[0]).startswith('vs_')]\n    except Exception as x:\n        print('rag_store_ids',repr(x),flush=True);return []\n\ndef rag_get_or_create(scope,sid):\n    if not DB_URL or scope not in ('user','conversation','company'):return None\n    sid='company' if scope=='company' else str(sid)\n    try:\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("SELECT vector_store_id FROM rag_stores WHERE scope=%s AND scope_id=%s",(scope,sid));row=c.fetchone()\n                if row:return row[0]\n        vs=create_vector_store('nami-'+scope+'-'+hashlib.sha256(sid.encode()).hexdigest()[:12],OPENAI_KEY,HTTP)\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("""INSERT INTO rag_stores(scope,scope_id,vector_store_id) VALUES(%s,%s,%s)\n                  ON CONFLICT(scope,scope_id) DO UPDATE SET updated_at=NOW() RETURNING vector_store_id""",(scope,sid,vs));stored=c.fetchone()[0]\n            cn.commit();return stored\n    except Exception as x:\n        print('rag_get_or_create',repr(x),flush=True);return None\n\ndef start_rag_index_pdf(cid,uid,mid,filename,blob):\n    # PDFs are isolated to the current conversation by default. Source files expire\n    # at the provider, while the local DB only stores compact IDs/metadata.\n    if not blob or not OPENAI_KEY or not DB_URL:return\n    def worker():\n        try:\n            vs=rag_get_or_create('conversation',cid)\n            if not vs:return\n            file_id,_=index_pdf(blob,filename or 'document.pdf',vs,OPENAI_KEY,HTTP,{\n                'scope':'conversation','source':'line_pdf',\n                'scope_hash':hashlib.sha256(str(cid).encode()).hexdigest()[:16]})\n            with db() as cn:\n                with cn.cursor() as c:\n                    c.execute("""INSERT INTO rag_files(scope,scope_id,conversation_id,line_message_id,filename,openai_file_id)\n                      VALUES('conversation',%s,%s,%s,%s,%s)""",(str(cid),str(cid),mid,(filename or '')[:180],file_id))\n                    c.execute("UPDATE rag_stores SET updated_at=NOW() WHERE scope='conversation' AND scope_id=%s",(str(cid),))\n                cn.commit()\n            print('RAG_INDEXED',str(cid)[:24],file_id,flush=True)\n        except Exception as x:print('rag_index_pdf',repr(x),flush=True)\n    threading.Thread(target=worker,daemon=True,name='nami-rag-index').start()\n\n'''
helper_anchor='def add_estimate_batch_item(cid,uid,mid,analysis):\n'
if 'def rag_store_ids(' not in s:
    if helper_anchor not in s:raise SystemExit('rag helper anchor missing')
    s=s.replace(helper_anchor,helpers+helper_anchor,1)

# Replace env-only file search with isolated scoped stores plus optional configured store.
old_tool='''    vector_store=os.getenv("OPENAI_VECTOR_STORE_ID","").strip()\n    if vector_store and runtime_task in ("knowledge","document","balanced"):\n        payload.setdefault("tools",[]).append({"type":"file_search","vector_store_ids":[vector_store]})\n        payload["tool_choice"]="auto"\n'''
new_tool='''    vector_stores=rag_store_ids(uid,cid)\n    configured_store=os.getenv("OPENAI_VECTOR_STORE_ID","").strip()\n    if configured_store.startswith("vs_") and configured_store not in vector_stores: vector_stores.append(configured_store)\n    rag_tool=file_search_tool(vector_stores,max_results=4)\n    if rag_tool and runtime_task in ("knowledge","document","balanced","web","chat"):\n        payload.setdefault("tools",[]).append(rag_tool)\n        payload["tool_choice"]="auto"\n'''
if old_tool in s:
    s=s.replace(old_tool,new_tool,1)
elif new_tool not in s:
    raise SystemExit('file search runtime anchor missing')

# Voice input: transcribe first, then feed the transcript through the exact same text
# routing/memory/self-improvement path. Group invocation rules therefore still apply.
s=s.replace("        if typ not in ('text','image','file'): continue\n","        if typ not in ('text','image','file','audio'): continue\n",1)
voice_anchor="        qid=m.get('quotedMessageId')\n"
voice_block='''        voice_input=False\n        if typ=='audio':\n            rawvoice,voicemime=content(mid)\n            if not rawvoice:\n                reply(e.get('replyToken'),'音声を取得できなかったよ🧭');continue\n            try:\n                voice_text=transcribe(rawvoice,'voice.m4a',OPENAI_KEY,HTTP)\n            except Exception as x:\n                print('voice_transcribe',repr(x),flush=True);reply(e.get('replyToken'),'音声の文字起こしでエラーが出たよ🧭');continue\n            if not voice_text:\n                reply(e.get('replyToken'),'音声を聞き取れなかったよ🧭');continue\n            m=dict(m);m['text']=voice_text;typ='text';voice_input=True\n'''
if 'voice_input=False' not in s:
    if voice_anchor not in s:raise SystemExit('voice anchor missing')
    s=s.replace(voice_anchor,voice_anchor+voice_block,1)

# Preserve audio provenance in message history without changing downstream behavior.
s=s.replace("        save_msg(eid,cid,uid,nm,'user',text,'text',mid,qid)\n","        save_msg(eid,cid,uid,nm,'user',text,'audio' if voice_input else 'text',mid,qid)\n",1)

# Every PDF becomes short-lived semantic knowledge for this conversation; ordinary image
# analysis remains unchanged and no cross-group store is ever queried.
pdf_anchor="            a=analyze(rawmedia,'application/pdf' if is_pdf else mime,uid,cid)\n"
if 'start_rag_index_pdf(cid,uid,mid' not in s:
    if pdf_anchor not in s:raise SystemExit('pdf index anchor missing')
    s=s.replace(pdf_anchor,pdf_anchor+"            if is_pdf: start_rag_index_pdf(cid,uid,mid,m.get('fileName') or 'document.pdf',rawmedia)\n",1)

required=(
 'CREATE TABLE IF NOT EXISTS memories','def mems(','def add_memory(',
 'awaiting and can_self_improve(uid)','CREATE TABLE IF NOT EXISTS rag_stores',
 'rag_tool=file_search_tool','voice_input=False','start_rag_index_pdf(cid,uid,mid'
)
missing=[x for x in required if x not in s]
if missing:raise SystemExit('invariant missing '+repr(missing))

ast.parse(s)
p.write_text(s)
print('rag+voice patch OK')
