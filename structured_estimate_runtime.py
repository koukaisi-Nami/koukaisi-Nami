"""Structured estimate generation for Nami.
AI extracts facts into JSON; deterministic model/renderers own totals and artifacts.
"""
import json,re
from estimate_model import normalize_estimate, estimate_to_text
FIXED=[('current_rent','当月前家賃'),('next_rent','次月前家賃'),('deposit','敷金'),('key_money','礼金'),('guarantee','初回保証料'),('brokerage','仲介手数料'),('insurance','火災保険'),('support','24時間サポート'),('key_exchange','鍵交換'),('admin','事務手数料')]
def prompt(instruction,material,property_name=''):
    schema={"property":property_name or "物件名","move_in":"15日 or empty","items":[{"key":"current_rent","label":"当月前家賃","amount":None,"original_amount":None,"discount_amount":0,"breakdown":"","status":"known|unknown"}],"notes":[]}
    return f'''募集図面から初期費用を計算しJSONだけ返す。推測禁止。固定項目順: {FIXED}。
最重要：図面の「その他費用」「契約時費用」「入居時費用」「備考」「特約」「諸費用」を省略せず最後まで読む。名称が違っても意味で分類する。
鍵交換費/鍵交換代/鍵設定費/シリンダー交換/鍵登録費→key_exchange。24Hサポート/24時間サポート/安心サポート/緊急サポート/入居者サポート/Goodプレミアムα等の生活サポート→support。住宅総合保険/火災保険/家財保険/損保/少額短期保険→insurance。登録料/事務手数料/契約事務手数料→admin。ただし別個の費用なら固定項目後に別行で残す。
資料記載額を最優先しfallbackで上書き禁止。税込はそのまま。税抜は消費税10%を加えた税込額をamountにする（3000円税抜→3300円）。
管理費/共益費は前家賃に含める。当月前家賃は入居月の日数が確定できる時だけ日割り。月不明なら30日/31日を仮定せずamount=null。次月前家賃は賃料+管理費。
仲介手数料は今回の指示で指定がなければ賃料1ヶ月分+消費税10%（1.1ヶ月）を満額計上する。半額/無料/値引/OFF/料率指定等が明確ならその指定を優先し、original_amount,discount_amount,amountを分ける。
火災保険は資料額を最優先。資料に額がない時だけ20000円を仮計上。保証料も資料の額/率を最優先し、ない時だけ賃料+管理費の50%を仮計上。
不明項目はamount=null。既存カテゴリ外の契約時必須費用は固定項目後に追加。breakdownは日割り日数、賃料+管理費、保証率、割引など必要情報だけ。「税込」「要確認」「概算」は入れない。
形式例: {json.dumps(schema,ensure_ascii=False)}
【今回の指示】{instruction}
【資料】{material}'''
def _extract(raw):
    raw=(raw or '').strip()
    raw=re.sub(r'^\`\`\`(?:json)?\\s*|\\s*\`\`\`$','',raw,flags=re.I|re.S)
    a=raw.find('{'); b=raw.rfind('}')
    if a<0 or b<=a: raise ValueError('no json')
    candidate=raw[a:b+1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        candidate=(candidate.replace('“','"').replace('”','"').replace('„','"')
                            .replace('’',"'").replace('‘',"'"))
        candidate=re.sub(r',\\s*([}\\]])',r'\\1',candidate)
        candidate=''.join(ch if ch in '\\t\\n\\r' or ord(ch)>=32 else ' ' for ch in candidate)
        return json.loads(candidate)
def _has_month(t): return bool(re.search(r'(?:\d{4}[年/\-.])?\d{1,2}月|\d{4}[-/]\d{1,2}[-/]\d{1,2}',t or ''))
def generate(ai_call,instruction,material,uid,cid,property_name=''):
    req=prompt(instruction,material,property_name); last=''
    attempts=[
        req,
        req+'\n前回はJSONとして壊れていた。説明・Markdown・絵文字・末尾文字を一切付けず、有効なJSONオブジェクトだけ返す。全項目を短くする。',
        req+'\n最終再生成。必ずJSON.parse可能なJSONだけ返す。notesとbreakdownは必要最小限。文字列内改行禁止。出力を途中で切らない。'
    ]
    for attempt_req in attempts:
        last=ai_call(attempt_req,uid,cid)
        try:
            d=normalize_estimate(_extract(last)); bykey={x.get('key'):x for x in d['items']}; fixed=[]
            for key,label in FIXED:
                row=bykey.get(key) or {'key':key,'label':label,'amount':None,'original_amount':None,'discount_amount':0,'breakdown':'','status':'unknown'}; row['label']=label; fixed.append(row)
            d['items']=fixed+[x for x in d['items'] if x.get('key') not in {k for k,_ in FIXED}]
            if re.search(r'\d{1,2}日(?:入居)?',instruction or '') and not _has_month(instruction):
                r=d['items'][0]; r.update({'amount':None,'original_amount':None,'discount_amount':0,'breakdown':'','status':'unknown'})
            return normalize_estimate(d)
        except Exception as x:
            print("ESTIMATE_JSON_RETRY",repr(x),str(last)[:500],flush=True)
    raise ValueError('estimate JSON invalid after repair')
def generate_text(ai_call,instruction,material,uid,cid,property_name=''):
    data=generate(ai_call,instruction,material,uid,cid,property_name); return data,estimate_to_text(data)
