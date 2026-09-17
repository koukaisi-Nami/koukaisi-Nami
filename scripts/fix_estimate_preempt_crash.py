from pathlib import Path
p=Path('app.py')
s=p.read_text()
old='''        quick_task=task_command(text,uid,cid)\n        quick_doc=three_document_command(text,uid,cid,qid)\n'''
new='''        quick_task=task_command(text,uid,cid)\n        # Estimate requests must bypass the legacy document command entirely.\n        # The legacy estimate path can call obsolete helpers before the canonical\n        # structured estimate route gets a chance to run.\n        estimate_intent=bool(re.search(r"(見積|初期費用)",text,re.I) or (re.search(r"仲介.{0,8}(?:半額|無料|割引)",text,re.I) and re.search(r"(画像|PNG|PDF|作って|出して)",text,re.I)))\n        quick_doc=None if estimate_intent else three_document_command(text,uid,cid,qid)\n'''
assert old in s, 'hotfix anchor missing'
s=s.replace(old,new,1)
p.write_text(s)
