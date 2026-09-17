from pathlib import Path
p=Path('app.py'); s=p.read_text()

def once(old,new):
    global s
    assert old in s, 'integration anchor missing: '+old[:80]
    s=s.replace(old,new,1)

once('from estimate_document import make_estimate_document, make_estimate_image\n','from estimate_document import make_estimate_document, make_estimate_image\nfrom structured_estimate_runtime import generate_text as structured_estimate\n')

old='''        estimate=ai(single_estimate_prompt(instruction)+"\\n\\n"+material,uid,cid)\n        label=p.get('name') or p.get('address') or f'{index}件目'\n        room=p.get('room') or ''\n        header=f"【{index}/{total} {label}{(' '+room) if room else ''}】"\n        answers.append(header+"\\n"+estimate)'''
new='''        label=p.get('name') or p.get('address') or f'{index}件目'\n        room=p.get('room') or ''\n        prop_name=label+((' '+room) if room else '')\n        data,estimate=structured_estimate(ai,instruction,material,uid,cid,prop_name)\n        header=f"【{index}/{total} {prop_name}】"\n        answers.append({'data':data,'text':header+"\\n"+estimate})'''
once(old,new)

old='''    for i,estimate_text in enumerate(estimates):\n        key=hashlib.sha256((str(time.time())+str(i)+estimate_text).encode()).hexdigest()[:24]\n        ESTIMATE_CACHE[key]=(time.time(),estimate_text)'''
new='''    for i,estimate in enumerate(estimates):\n        estimate_text=estimate.get('text','') if isinstance(estimate,dict) else str(estimate)\n        estimate_data=estimate.get('data') if isinstance(estimate,dict) else estimate\n        key=hashlib.sha256((str(time.time())+str(i)+estimate_text).encode()).hexdigest()[:24]\n        ESTIMATE_CACHE[key]=(time.time(),estimate_data)'''
once(old,new)

once('''    created,text=row\n    if time.time()-created>600:''','''    created,estimate=row\n    if time.time()-created>600:''')
once('''    if ext=="pdf": return send_file(make_estimate_document(text),mimetype="application/pdf",as_attachment=True,download_name="見積もり概算書.pdf")\n    if ext=="png": return send_file(make_estimate_image(text),mimetype="image/png")''','''    if ext=="pdf": return send_file(make_estimate_document(estimate),mimetype="application/pdf",as_attachment=True,download_name="見積もり概算書.pdf")\n    if ext=="png": return send_file(make_estimate_image(estimate),mimetype="image/png")''')

old='''        estimate_text=ai(single_estimate_prompt(clean)+"\\n\\n【最優先：今回のユーザー指示】\\n"+clean+"\\nこの指示（入居日、仲介手数料の金額・無料・半額・月数等）を必ず計算に反映する。\\n\\n【募集図面の読取結果】\\n"+media_summary,uid,cid)\n        marker="__ESTIMATE_BOTH__" if (wants_image and wants_pdf) else ("__ESTIMATE_IMAGE__" if wants_image else "__ESTIMATE_PDF__")\n        return (marker,estimate_text)'''
new='''        estimate_data,estimate_text=structured_estimate(ai,clean,media_summary,uid,cid)\n        marker="__ESTIMATE_BOTH__" if (wants_image and wants_pdf) else ("__ESTIMATE_IMAGE__" if wants_image else "__ESTIMATE_PDF__")\n        return (marker,estimate_data,estimate_text)'''
once(old,new)

old="""                estimate_text=quick_doc[1]\n                key=hashlib.sha256((eid+str(time.time())).encode()).hexdigest()[:24]\n                ESTIMATE_CACHE[key]=(time.time(),estimate_text)"""
new="""                estimate_data=quick_doc[1]\n                estimate_text=quick_doc[2]\n                key=hashlib.sha256((eid+str(time.time())).encode()).hexdigest()[:24]\n                ESTIMATE_CACHE[key]=(time.time(),estimate_data)"""
once(old,new)

once('''            saved_ans="\\n\\n".join(batch_answer)''','''            saved_ans="\\n\\n".join((x.get('text','') if isinstance(x,dict) else str(x)) for x in batch_answer)''')
once('''        saved_ans="\\n\\n".join(ans) if isinstance(ans,(list,tuple)) else ans''','''        saved_ans="\\n\\n".join((x.get('text','') if isinstance(x,dict) else str(x)) for x in ans) if isinstance(ans,(list,tuple)) else ans''')
once('''                reply(e.get("replyToken"),ans[0])\n                for item in ans[1:]:push_line(target,item)''','''                reply(e.get("replyToken"),ans[0].get('text','') if isinstance(ans[0],dict) else ans[0])\n                for item in ans[1:]:push_line(target,item.get('text','') if isinstance(item,dict) else item)''')

p.write_text(s)
