"""Structured estimate generation for Nami.
AI extracts facts into JSON; deterministic model/renderers own totals and artifacts.
"""
import json,re
from datetime import date, timedelta
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
火災保険は資料に明記された金額だけを使う。記載がなければamount=null。保証料は資料の額/率を最優先し、ない時だけ賃料+管理費の50%を仮計上。\n小さい文字の費用欄も最後まで確認し、24時間サポートや鍵交換などの名称と同じ行・括弧・備考末尾にある金額を落とさない。
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
def _resolve_day_only_move_in(instruction, today=None):
    """Resolve an explicit day-only move-in instruction to the next calendar occurrence."""
    text=instruction or ''
    m=re.search(r'入居(?:日)?(?:は|：|:|を)?\s*(\d{1,2})日(?:\s*入居)?',text)
    if not m or _has_month(text): return text
    day=int(m.group(1))
    if day < 1 or day > 31: return text
    base=today or date.today()
    year,month=base.year,base.month
    for _ in range(14):
        try: candidate=date(year,month,day)
        except ValueError: candidate=None
        if candidate and candidate >= base:
            return text+f'\n【入居日の確定補助】ユーザー指定の「{day}日」は次回の{candidate.year}年{candidate.month}月{day}日として日割り計算する。図面の入居可能日を入居日として使わない。'
        month += 1
        if month == 13: year += 1; month = 1
    return text
def _apply_instruction_overrides(d,instruction,today=None):
    """Apply user-specified move-in/commission rules deterministically after AI extraction."""
    text=instruction or ''
    rows={x.get('key'):x for x in d.get('items',[])}
    rent=rows.get('next_rent',{}).get('amount')
    # next_rent may include management fee, so prefer explicit rent from material-derived breakdown when available.
    # Brokerage is legally/calculation-wise based on rent only; AI's original_amount should represent full 1.1 months.
    broker=rows.get('brokerage')
    if broker:
        full=broker.get('original_amount')
        if not isinstance(full,(int,float)) or full <= 0:
            full=broker.get('amount')
        mode=None
        if re.search(r'仲介(?:手数料)?[^。\n]*(?:無料|0円)',text): mode='free'
        elif re.search(r'仲介(?:手数料)?[^。\n]*(?:半額|0\.5(?:5)?ヶ月)',text): mode='half'
        elif re.search(r'仲介(?:手数料)?[^。\n]*(?:満額|1\.1ヶ月|1ヶ月\s*\+?\s*(?:税|消費税))',text): mode='full'
        if mode and isinstance(full,(int,float)) and full >= 0:
            # If extraction supplied a discounted amount plus full original, trust original as the full fee.
            if mode=='free': amount=0
            elif mode=='half': amount=round(full/2)
            else: amount=round(full)
            broker.update({'original_amount':round(full),'discount_amount':round(full-amount),'amount':amount,'status':'known'})
    # Force explicit day-only move-in into output and calculate current rent from extracted monthly current/next rent.
    m=re.search(r'(?:入居(?:日)?(?:は|：|:|を)?\s*(\d{1,2})日|(\d{1,2})日\s*入居)',text)
    if m and not _has_month(text):
        day=int(m.group(1) or m.group(2)); base=today or date.today(); y,mo=base.year,base.month
        try: candidate=date(y,mo,day)
        except ValueError: candidate=None
        if not candidate or candidate < base:
            mo += 1
            if mo==13: y+=1; mo=1
            try: candidate=date(y,mo,day)
            except ValueError: candidate=None
        if candidate:
            d['move_in']=f'{candidate.year}年{candidate.month}月{candidate.day}日'
            cur=rows.get('current_rent')
            monthly=rows.get('next_rent',{}).get('amount')
            if cur is not None and isinstance(monthly,(int,float)):
                import calendar
                days=calendar.monthrange(candidate.year,candidate.month)[1]
                charged=days-candidate.day+1
                amount=round(monthly/days*charged)
                cur.update({'amount':amount,'status':'known','breakdown':f'日割り{charged}日分'})
    return d

def generate(ai_call,instruction,material,uid,cid,property_name=''):
    effective_instruction=_resolve_day_only_move_in(instruction)
    req=prompt(effective_instruction,material,property_name); last=''
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
            return normalize_estimate(d)
        except Exception as x:
            print("ESTIMATE_JSON_RETRY",repr(x),str(last)[:500],flush=True)
    raise ValueError('estimate JSON invalid after repair')
def generate_text(ai_call,instruction,material,uid,cid,property_name=''):
    data=generate(ai_call,instruction,material,uid,cid,property_name); return data,estimate_to_text(data)
