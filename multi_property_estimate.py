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
各物件を【初期費用概算】から始める。基本順は当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料。その後、図面固有の必須初期費用を図面の名目のまま追加し、最後に合計。
【表記ゆれ・意味分類】項目名の完全一致だけで判定しない。図面の文脈と意味で初期費用を分類する。敷金系は「敷金・保証金・契約保証金・預り金」等、礼金系は「礼金・契約一時金」等、保証会社系は「初回保証料・保証委託料・初回委託保証料・保証会社利用料・保証料」等、サポート系は「24時間サポート・安心サポート・緊急サポート・入居者サポート・安心入居サポート」等、鍵系は「鍵交換・鍵交換代・鍵交換費・シリンダー交換・鍵設定費」等を同義候補として読む。ただし名称だけで機械的に同一視せず、図面の説明・金額・単位・契約条件から実質が同じ場合だけ標準項目へ統合する。
特に「保証金」は敷金相当の場合と別費用の場合がある。敷金相当と読み取れる場合は「敷金」として扱い二重計上しない。敷金とは別に必要な保証金と読み取れる場合は図面の名称のまま追加費用として計上する。判断できない場合も黙って捨てず、図面の名称を残して表示する。
上記カテゴリに一致しない名称でも、契約時・入居時に支払う金銭項目が図面に記載されていれば漏らさず抽出し、図面の名称をできるだけそのまま使って追加表示する。クリーニング、退去時清掃、消毒・除菌、書類作成、契約事務、登録、Goodプレミアム等の商品・サービス、駐輪場、町会費、害虫駆除、抗菌施工、室内清掃、エアコン清掃等も対象。月額費用・退去時費用・任意費用は契約時請求かどうかを文脈で確認し、契約時に必要と明記されるものだけ初期費用合計へ含める。必須/任意や支払時期が不明なら勝手に除外・加算せず、その条件が不明であることが分かる形で表示する。同一費用の別名表記は二重計上しない。
【合計計算・最優先】見積欄に0円以外の数字を表示し、契約時支払として計上した費用は例外なくすべて合計へ加算する。当月前家賃・次月前家賃・敷金・礼金・初回保証料・仲介手数料・火災保険・24時間サポート・鍵交換・事務手数料・図面固有費用・仮計上費用を漏らさない。「－」だけは0円扱いで合計しない。表示した各計上金額を整数円へ直して足し算し、合計が各表示金額の総和と一致することを回答前に再検算する。
管理費・共益費は前家賃に含める。入居日指定なしなら当月前家賃は－。フリーレントは必ず記載し、適用月が確定した時だけ前家賃を0円にする。
初回保証料は図面記載を優先。保証委託料等の別名も保証会社の初回費用なら初回保証料として扱う。記載なしは賃料＋管理費・共益費の50%を「初回保証料（仮）」として合計に含める。
【火災保険の判定・最優先】図面上の名称が「火災保険」そのものでなくても、「損保」「損害保険」「家財保険」「家財」「住宅保険」「借家人賠償責任保険」「少額短期保険」「保険料」「保険加入」「保険会社」等、入居時の住宅・家財・借家人賠償に関する保険費用はすべて火災保険として扱う。これらの名称の近くに金額が記載されていれば、その金額を「火災保険：金額」として採用する。同じ保険費用を図面固有費用として二重計上しない。
上記の火災保険相当の記載・金額が資料のどこにも確認できない場合は、火災保険を「－」にしてはいけない。必ず「火災保険（仮）：20,000円」と表示し、20,000円を合計へ加算する。保険の加入必須だけ書かれ金額がない場合も同様に20,000円を仮計上する。
仲介手数料は今回ユーザーがその物件について明示指定した場合だけ計上。指定なしは必ず－。Markdown表・詳細解析・計算過程は禁止。
物件ごとのユーザー指定を取り違えない。
ユーザー指定: '''+(user_instruction or 'なし')+'\n\n'+'\n\n'.join(blocks)
    return prompt,None
