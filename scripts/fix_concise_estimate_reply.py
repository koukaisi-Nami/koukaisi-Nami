from pathlib import Path
p=Path('app.py')
s=p.read_text()
old='''            if not grouped(e):\n                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",a)\n                reply(e.get("replyToken"),a)\n            continue\n'''
new='''            if not grouped(e):\n                # Keep the detailed extraction internally for the estimate tool.\n                # Do not dump raw listing analysis into LINE; the next estimate\n                # instruction renders the canonical concise estimate instead.\n                received="資料を読み取ったよ🧭 見積もり条件を送ってね。"\n                save_msg("assistant:"+eid,cid,"bot","航海士ナミ","assistant",received)\n                reply(e.get("replyToken"),received)\n            continue\n'''
if old not in s: raise SystemExit('target block not found')
s=s.replace(old,new,1)
p.write_text(s)
