from pathlib import Path
p=Path('app.py')
s=p.read_text()

# import helper
needle='from functools import wraps\n'
if 'from multi_property_estimate import group_attachments, estimate_instruction' not in s:
    s=s.replace(needle, needle+'from multi_property_estimate import group_attachments, estimate_instruction\n')

# DB table after images table creation block; anchor is improvement_requests table.
anchor='            c.execute("""CREATE TABLE IF NOT EXISTS improvement_requests('
table='''            c.execute("""CREATE TABLE IF NOT EXISTS estimate_batch_items(\n              id BIGSERIAL PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT NOT NULL,\n              line_message_id TEXT UNIQUE,media_type TEXT NOT NULL,analysis TEXT NOT NULL,\n              created_at TIMESTAMPTZ DEFAULT NOW())""")\n            c.execute("CREATE INDEX IF NOT EXISTS estimate_batch_recent ON estimate_batch_items(conversation_id,user_id,created_at DESC)")\n'''
if 'CREATE TABLE IF NOT EXISTS estimate_batch_items' not in s:
    s=s.replace(anchor,table+anchor)

# helper functions before image_analysis
anchor2='def image_analysis(cid,mid=None):\n'
helpers='''def save_estimate_batch_item(cid,uid,mid,mtype,analysis):\n    if not DB_URL or not uid or not mid or not analysis:return\n    try:\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("""INSERT INTO estimate_batch_items(conversation_id,user_id,line_message_id,media_type,analysis)\n                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(line_message_id) DO UPDATE SET analysis=EXCLUDED.analysis""",\n                (cid,uid,mid,mtype,analysis))\n            cn.commit()\n    except Exception as x: print("save_estimate_batch_item",repr(x),flush=True)\n\ndef recent_estimate_batch(cid,uid,minutes=15):\n    if not DB_URL:return []\n    try:\n        with db() as cn:\n            with cn.cursor() as c:\n                c.execute("""SELECT line_message_id,media_type,analysis FROM estimate_batch_items\n                  WHERE conversation_id=%s AND user_id=%s AND created_at>=NOW()-(%s*INTERVAL '1 minute')\n                  ORDER BY created_at""",(cid,uid,minutes))\n                return [{"id":r[0],"type":r[1],"analysis":r[2]} for r in c.fetchall()]\n    except Exception as x: print("recent_estimate_batch",repr(x),flush=True);return []\n\ndef clear_estimate_batch(cid,uid):\n    if not DB_URL:return\n    try:\n        with db() as cn:\n            with cn.cursor() as c:c.execute("DELETE FROM estimate_batch_items WHERE conversation_id=%s AND user_id=%s",(cid,uid))\n            cn.commit()\n    except Exception as x: print("clear_estimate_batch",repr(x),flush=True)\n\ndef multi_property_estimate_prompt(cid,uid,user_text):\n    items=recent_estimate_batch(cid,uid)\n    if len(items)<2:return None,None\n    groups,ambiguous=group_attachments(items)\n    if len(groups)<2 and not ambiguous:return None,None\n    return estimate_instruction(groups,ambiguous,user_text)\n\n'''
if 'def save_estimate_batch_item(' not in s:
    s=s.replace(anchor2,helpers+anchor2)

# Save every successfully analysed image/pdf into temporary batch.
needle3='save_image(cid,uid,mid,a)'
if needle3 in s and 'save_estimate_batch_item(cid,uid,mid' not in s:
    s=s.replace(needle3,needle3+'\n            save_estimate_batch_item(cid,uid,mid,"pdf" if is_pdf else "image",a)',1)

# Insert multi-property command before quoted media logic in text webhook.
needle4='quoted_saved=image_analysis(cid,qid) if qid else None'
insert='''multi_prompt,multi_error=(None,None)\n        if re.search(r"(見積|初期費用)",text,re.I):\n            multi_prompt,multi_error=multi_property_estimate_prompt(cid,uid,text)\n        if multi_error:\n            reply(token,multi_error);save_msg(None,cid,None,"ナミ","assistant",multi_error);continue\n        if multi_prompt:\n            ans=ask(multi_prompt,uid,cid)\n            reply(token,ans);save_msg(None,cid,None,"ナミ","assistant",ans);clear_estimate_batch(cid,uid);continue\n        '''
if needle4 in s and 'multi_property_estimate_prompt(cid,uid,text)' not in s:
    s=s.replace(needle4,insert+needle4,1)

p.write_text(s)
