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
【最重要】1物件につき1つの完成した見積もりだけを書く。複数物件を1つの表や説明文にまとめない。冒頭の挨拶、全体説明、確認済み小計、月額費用一覧、要確認一覧、最後の仲介手数料一覧は禁止。
各物件は必ずこの顧客転送用形式にする：
【初期費用概算】
物件名 号室

当月前家賃：金額または－
次月前家賃：金額または－
敷金：金額または－
礼金：金額または－
初回保証料：金額または－
仲介手数料：金額または－
火災保険：金額
24時間サポート：金額または－
鍵交換：金額または－
事務手数料：金額または－
（図面固有の追加費用があれば名称：金額）

合計：金額
※必要な注記だけ1〜2行

【LINE分割ルール】物件と物件の間には、必ずこの文字列だけを単独行で1回入れる：
<<<PROPERTY_BREAK>>>
この区切りはLINE送信時に削除され、物件ごとに別メッセージとして送信される。3件なら完成した見積もり3個を、区切り2個で返す。物件番号 #①、物件1 等は付けない。

項目名は完全一致でなく意味と文脈で分類。敷金/保証金/契約保証金/預り金、礼金/契約一時金、初回保証料/保証委託料/初回委託保証料/保証会社利用料、24時間サポート/安心サポート/緊急サポート/入居者サポート、鍵交換/鍵交換代/鍵設定費/シリンダー交換等を読み分ける。保証金は敷金相当なら敷金へ統合し二重計上しない。独立費用なら元名称で追加する。未知の契約時費用も捨てず追加する。
【合計】「－」以外に表示して契約時支払として計上した全金額を合計し、回答前に再検算する。管理費・共益費は前家賃に含める。入居日指定なしなら当月前家賃は－。
初回保証料は図面記載を優先。記載なしは賃料＋管理費・共益費の50%を「初回保証料（仮）」として合計に含める。
【火災保険】損保、損害保険、家財保険、家財、住宅保険、借家人賠償責任保険、少額短期保険、保険料、保険加入等も住宅保険なら火災保険として扱う。金額があれば採用。金額なし又は記載なしなら必ず「火災保険（仮）：20,000円」として合計へ加算し、－にしない。
仲介手数料は今回ユーザーが明示指定した場合だけ計上。指定なしは－。物件ごとの指定を取り違えない。
ユーザー指定: '''+(user_instruction or 'なし')+'\n\n'+'\n\n'.join(blocks)
    return prompt,None
