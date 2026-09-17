from pathlib import Path
p=Path('app.py');s=p.read_text()
old='''        if grouped(e) and not called(m):
            proactive=manager_review(text,uid,cid)
            if proactive:
                save_msg("assistant:manager:"+eid,cid,"bot","航海士ナミ","assistant",proactive)
                reply(e.get("replyToken"),proactive)
            continue
'''
new='''        if grouped(e) and not called(m):
            # Natural continuation: after Nami has just replied to this user in this group,
            # treat a short follow-up as part of the same conversation without requiring her name again.
            continuation=False
            try:
                with db() as cn:
                    with cn.cursor() as c:
                        c.execute("""SELECT 1 FROM messages
                          WHERE conversation_id=%s AND role='assistant'
                            AND created_at > NOW()-INTERVAL '10 minutes'
                          ORDER BY created_at DESC LIMIT 1""",(cid,))
                        recent_bot=bool(c.fetchone())
                        c.execute("""SELECT 1 FROM messages
                          WHERE conversation_id=%s AND user_id=%s AND role='user'
                            AND created_at > NOW()-INTERVAL '10 minutes'
                          ORDER BY created_at DESC LIMIT 1""",(cid,uid))
                        recent_user=bool(c.fetchone())
                        continuation=recent_bot and recent_user
            except Exception as x:
                print('continuation_check',repr(x),flush=True)
            # A reply to Nami or a document/image follow-up is also an explicit continuation signal.
            if qid or re.search(r"(これ|それ|この|さっき|見積|画像|PDF|資料|図面|作って|お願い|頼む|どう|続き)",text,re.I):
                continuation=continuation or recent_bot if 'recent_bot' in locals() else continuation
            if not continuation:
                proactive=manager_review(text,uid,cid)
                if proactive:
                    save_msg("assistant:manager:"+eid,cid,"bot","航海士ナミ","assistant",proactive)
                    reply(e.get("replyToken"),proactive)
                continue
'''
if old not in s:raise SystemExit('group gate anchor missing')
s=s.replace(old,new,1)
p.write_text(s)
