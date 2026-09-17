import re
from collections import defaultdict

PROPERTY_PATTERNS=[re.compile(r'(?:物件名|建物名)[:：\s]*([^\n]{2,60})',re.I),re.compile(r'【([^】]{2,60})】')]
ROOM_PATTERN=re.compile(r'(?:号室|部屋番号|ROOM)[:：\s]*([A-Za-z0-9\-]+)|([0-9]{2,5})\s*号室',re.I)
ADDRESS_PATTERN=re.compile(r'(?:所在地|住所)[:：\s]*([^\n]{5,100})')

def _clean(v):return re.sub(r'\s+',' ',v or '').strip(' 　:：')

def identify_property(analysis):
    text=analysis or '';name=''
    for p in PROPERTY_PATTERNS:
        m=p.search(text)
        if m:name=_clean(m.group(1));break
    rm=ROOM_PATTERN.search(text);room=_clean((rm.group(1) or rm.group(2)) if rm else '')
    am=ADDRESS_PATTERN.search(text);address=_clean(am.group(1) if am else '')
    if not (name or address):return None
    key='|'.join(x.lower() for x in (name,room,address) if x)
    return {'key':key,'name':name or address,'room':room,'address':address}

def group_attachments(items):
    groups=defaultdict(list);ids={};ambiguous=[]
    for item in items:
        ident=identify_property(item.get('analysis',''))
        if not ident:ambiguous.append(item);continue
        groups[ident['key']].append(item);ids[ident['key']]=ident
    return [{'property':ids[k],'attachments':v} for k,v in groups.items()],ambiguous

def estimate_instruction(groups,ambiguous,user_instruction=''):
    if ambiguous:return None,'資料の一部で物件を特定できませんでした。どの物件の資料か指定してください。'
    blocks=[]
    for i,g in enumerate(groups,1):
        p=g['property'];analyses='\n---\n'.join(a.get('analysis','') for a in g['attachments'])
        blocks.append(f"[物件{i}] {p['name']} {p['room']}\n{analyses}")
    prompt='''以下の資料を物件ごとに完全に分離して見積もる。別物件の金額・条件を絶対に混ぜない。

【出力形式・最優先】複数物件でも、1件ずつ見積もりを出す時と全く同じ顧客向け形式で出力する。社内確認用の表、Markdown表、列見出し、区分、確認済み項目合計、解析結果、計算過程、最後の仲介手数料一覧、「残り○件」「要確認」一覧などは出さない。お客様へそのまま転送できる文章だけを返す。
各物件は必ず次の形で独立させ、物件と物件の間は空行＋「──────────」で区切る。
【初期費用概算】
物件名 号室

当月前家賃：金額または－
次月前家賃：金額または－
敷金：金額または－
礼金：金額または－
初回保証料：金額または－
仲介手数料：金額または－
火災保険：金額または－
24時間サポート：金額または－
鍵交換：金額または－
事務手数料：金額または－
（図面固有の追加費用があればここに名称：金額）

合計：金額

必要な注記がある場合だけ最後に「※」で1〜2行。物件番号「#①」「物件1」等は付けない。3件ならこの完成形を3つ順番に並べる。

【表記ゆれ・意味分類】項目名の完全一致だけで判定しない。図面の文脈と意味で初期費用を分類する。敷金系は「敷金・保証金・契約保証金・預り金」等、礼金系は「礼金・契約一時金」等、保証会社系は「初回保証料・保証委託料・初回委託保証料・保証会社利用料・保証料」等、サポート系は「24時間サポート・安心サポート・緊急サポート・入居者サポート・安心入居サポート」等、鍵系は「鍵交換・鍵交換代・鍵交換費・シリンダー交換・鍵設定費」等を同義候補として読む。ただし名称だけで機械的に同一視せず、図面の説明・金額・単位・契約条件から実質が同じ場合だけ標準項目へ統合する。
特に「保証金」は敷金相当の場合と別費用の場合がある。敷金相当と読み取れる場合は「敷金」として扱い二重計上しない。敷金とは別に必要な保証金と読み取れる場合は図面の名称のまま追加費用として計上する。判断できない場合も黙って捨てず、図面の名称を残して表示する。
上記カテゴリに一致しない名称でも、契約時・入居時に支払う金銭項目が図面に記載されていれば漏らさず抽出し、図面の名称をできるだけそのまま使って追加表示する。同一費用の別名表記は二重計上しない。
【合計計算・最優先】見積欄に0円以外の数字を表示し、契約時支払として計上した費用は例外なくすべて合計へ加算する。「－」だけは0円扱い。回答前に表示金額の総和と合計が一致するか再検算する。
管理費・共益費は前家賃に含める。入居日指定なしなら当月前家賃は－。フリーレントは必ず記載し、適用月が確定した時だけ前家賃を0円にする。
初回保証料は図面記載を優先。保証委託料等の別名も保証会社の初回費用なら初回保証料として扱う。記載なしは賃料＋管理費・共益費の50%を「初回保証料（仮）」として合計に含める。
【火災保険】「損保」「損害保険」「家財保険」「家財」「住宅保険」「借家人賠償責任保険」「少額短期保険」「保険料」「保険加入」「保険会社」等も住宅保険費用なら火災保険として扱う。近くに金額があれば「火災保険：金額」として採用し二重計上しない。金額が確認できない、または保険加入必須のみで金額なしの場合は必ず「火災保険（仮）：20,000円」と表示して合計へ加算する。
仲介手数料は今回ユーザーがその物件について明示指定した場合だけ計上。指定なしは必ず－。物件ごとのユーザー指定を取り違えない。
ユーザー指定: '''+(user_instruction or 'なし')+'\n\n'+'\n\n'.join(blocks)
    return prompt,None
