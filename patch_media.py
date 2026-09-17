from pathlib import Path
p=Path('app.py')
s=p.read_text()
old='''                # If LINE quotedMessageId points to an analyzed image, use it; otherwise attach latest image analysis
                quoted=image_analysis(cid,qid) if qid else None
                latest=image_analysis(cid) if re.search(r"(この|図面|画像|写真|見積)",text) else None
                chosen=quoted or latest
                extra=f"\\n【参照画像の解析】\\n{chosen}" if chosen else ""
                ans=ai(text,uid,cid,extra=extra)
'''
new='''                # Reply to an image/PDF: fetch the original quoted media and answer from actual bytes.
                quoted_saved=image_analysis(cid,qid) if qid else None
                quoted_blob=quoted_mime=None
                if qid:
                    quoted_blob,quoted_mime=content(qid)
                if quoted_blob:
                    is_quoted_pdf=(quoted_blob[:5]==b"%PDF-") or (quoted_mime and "pdf" in quoted_mime.lower())
                    media_mime="application/pdf" if is_quoted_pdf else quoted_mime
                    ans=analyze(quoted_blob,media_mime,uid,cid,question=text)
                else:
                    latest=image_analysis(cid) if re.search(r"(この|図面|画像|写真|PDF|資料|見積)",text,re.I) else None
                    chosen=quoted_saved or latest
                    extra=f"\\n【参照資料の解析】\\n{chosen}" if chosen else ""
                    ans=ai(text,uid,cid,extra=extra)
'''
if old not in s:
    raise SystemExit('target block not found')
s=s.replace(old,new,1)
p.write_text(s)
print('patched quoted media reply',len(s))
