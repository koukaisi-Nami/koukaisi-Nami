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
管理費・共益費は前家賃に含める。入居日指定なしなら当月前家賃は－。フリーレントは必ず記載し、適用月が確定した時だけ前家賃を0円にする。
初回保証料は図面記載を優先。記載なしは賃料＋管理費・共益費の50%を「初回保証料（仮）」として合計に含める。火災保険は図面記載を優先、記載なしは「火災保険（仮）：20,000円」を合計に含める。
仲介手数料は今回ユーザーがその物件について明示指定した場合だけ計上。指定なしは必ず－。Markdown表・詳細解析・計算過程は禁止。
物件ごとのユーザー指定を取り違えない。
ユーザー指定: '''+(user_instruction or 'なし')+'\n\n'+'\n\n'.join(blocks)
    return prompt,None
