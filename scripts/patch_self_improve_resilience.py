from pathlib import Path
p=Path('app.py'); s=p.read_text()
start=s.index('def targeted_candidate(req_text,current):')
end=s.index('\ndef codegen_improvement(', start)
new=r'''def _response_text(d):
    out=(d.get("output_text") or "").strip()
    if out:return out
    xs=[]
    for item in d.get("output",[]):
        if item.get("type")=="message":
            for z in item.get("content",[]):
                if z.get("type") in ("output_text","text") and z.get("text"):xs.append(z.get("text",""))
    return "\n".join(xs).strip()

def targeted_candidate(req_text,current,feedback=""):
    targets=improvement_targets(req_text,current)
    if not targets: raise RuntimeError("対象機能を特定できなかった")
    instruction="""本番稼働中のLINE Bot『航海士ナミ』を安全に部分改修する。
渡された関数だけを変更対象にし、それ以外の機能・記憶・DBデータは絶対に削除しない。
要求が既存関数の小変更で実現可能なら必ず具体的なreplacementを1件以上返す。
秘密情報をコードへ埋め込まない。DB変更は後方互換のALTER/CREATE IF NOT EXISTSだけ。
出力はJSONのみ: {"replacements":[{"function":"関数名","new":"関数を丸ごと置換するPythonコード"}],"summary":"短い説明"}。
functionは渡された関数名だけ。変更不能なら空配列ではなくsummaryに理由を明記する。"""
    selected="\n\n".join(f"【{name}】\n{body}" for name,body in targets.items())
    last=""
    # Generation itself gets bounded retries. Empty/malformed output is not an immediate dead-end.
    for generation_attempt in range(1,4):
        extra=("\n【前回失敗】\n"+last if last else "")+("\n【レビュー/安全チェック指示】\n"+feedback if feedback else "")
        payload={"model":MODEL,"instructions":instruction,"input":[{"role":"user","content":[{"type":"input_text","text":"【改修要求】\n"+req_text+extra+"\n\n【変更可能な関数だけ】\n"+selected}]}],"max_output_tokens":4000}
        try:
            r=HTTP.post(OA,headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json=payload,timeout=150)
            if not r.ok:
                last=f"AI codegen HTTP {r.status_code}"
                if r.status_code not in (408,429,500,502,503,504):break
                continue
            out=re.sub(r"^```(?:json)?\s*|\s*```$","",_response_text(r.json()).strip())
            if not out:
                last="AIの出力が空だった。必ずJSONとreplacementを返すこと"
                continue
            try:data=json.loads(out)
            except Exception as x:
                last="JSON不正: "+str(x)+" / 出力先頭: "+out[:300]
                continue
            replacements=data.get("replacements") or []
            if not replacements:
                last="replacementが0件だった。要求を実現する具体的な関数置換を返すこと。理由: "+str(data.get("summary","")[:500])
                continue
            candidate=current
            bad=None
            for item in replacements:
                name=str(item.get("function","")).strip(); code=str(item.get("new","")).strip(); old=targets.get(name)
                if not old or not code.startswith("def "+name+"("):
                    bad="許可外または不正な関数置換"; break
                if candidate.count(old)!=1:
                    bad="変更元関数を安全に特定できなかった"; break
                candidate=candidate.replace(old,code+"\n",1)
            if bad:
                last=bad; continue
            if candidate==current:
                last="候補コードが現行と同一だった"; continue
            return candidate
        except Exception as x:
            last="codegen exception: "+repr(x)
    raise RuntimeError("変更案生成を3回試したが完了できなかった: "+last[:800])
'''
s=s[:start]+new+s[end:]
# Ensure review repairs pass feedback separately and preserve original request for target selection.
s=s.replace('targeted_candidate(req_text+"\\n【前回の安全チェックエラー】\\n"+"\\n".join(errors[:10]),current)', 'targeted_candidate(req_text,current,"安全チェックエラー:\\n"+"\\n".join(errors[:10]))')
s=s.replace('targeted_candidate(req_text+"\\n【上位AIレビュー修正指示】\\n"+feedback,current)', 'targeted_candidate(req_text,current,feedback)')
p.write_text(s)
print('patched resilient self-improvement generation')
