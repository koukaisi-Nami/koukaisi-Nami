"""Structured estimate generation for Nami.
AI extracts facts into JSON; deterministic model/renderers own totals and artifacts.
"""
import json,re
from estimate_model import normalize_estimate, estimate_to_text

FIXED=[('current_rent','当月前家賃'),('next_rent','次月前家賃'),('deposit','敷金'),('key_money','礼金'),('guarantee','初回保証料'),('brokerage','仲介手数料'),('insurance','火災保険'),('support','24時間サポート'),('key_exchange','鍵交換'),('admin','事務手数料')]

def prompt(instruction,material,property_name=''):
    schema={"property":property_name or "物件名","move_in":"15日 or empty","items":[{"key":"current_rent","label":"当月前家賃","amount":None,"original_amount":None,"discount_amount":0,"breakdown":"日割り16日分 or empty","status":"known|unknown"}],"notes":[]}
    return f'''募集図面から初期費用を計算しJSONだけ返す。推測禁止。固定項目順: {FIXED}。
管理費/共益費は前家賃に含める。当月前家賃は入居日指定時だけ日割りしbreakdownに「日割りN日分」。次月前家賃は賃料+管理費。
仲介手数料は今回のユーザー指示で明示された時だけ計上。半額/無料/○円引き/○%OFF/○円にして等、対象と値が明確なら original_amount, discount_amount, amount(割引後) を分ける。曖昧な「安くして」は金額を作らない。
火災保険は資料に金額があれば使用。金額なし/記載なしは20000円を仮計上しbreakdown="仮"。保証料の率/額がなければ賃料+管理費の50%を仮計上しbreakdown="仮"。
不明項目も必ず固定項目として amount=null,status="unknown" で残す。既存カテゴリ外の契約時必須費用は固定項目の後に追加。totalは出してもよいがサーバ側で再計算する。
形式例: {json.dumps(schema,ensure_ascii=False)}
【今回の指示】{instruction}
【資料】{material}'''

def _extract(raw):
    raw=(raw or '').strip(); raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S)
    a=raw.find('{'); b=raw.rfind('}')
    if a<0 or b<=a: raise ValueError('no json')
    return json.loads(raw[a:b+1])

def generate(ai_call,instruction,material,uid,cid,property_name=''):
    req=prompt(instruction,material,property_name)
    last=''
    for attempt in range(2):
        last=ai_call(req if attempt==0 else req+'\n前回はJSONとして不正。説明文なし・コードフェンスなしの有効なJSONオブジェクトだけ返す。',uid,cid)
        try:
            d=normalize_estimate(_extract(last))
            # Ensure all fixed rows exist and stay ordered, without inventing amounts.
            bykey={x.get('key'):x for x in d['items']}
            fixed=[]
            for key,label in FIXED:
                row=bykey.get(key) or {'key':key,'label':label,'amount':None,'original_amount':None,'discount_amount':0,'breakdown':'','status':'unknown'}
                row['label']=label; fixed.append(row)
            extras=[x for x in d['items'] if x.get('key') not in {k for k,_ in FIXED}]
            d['items']=fixed+extras
            return normalize_estimate(d)
        except Exception:
            pass
    raise ValueError('estimate JSON invalid after repair')

def generate_text(ai_call,instruction,material,uid,cid,property_name=''):
    data=generate(ai_call,instruction,material,uid,cid,property_name)
    return data,estimate_to_text(data)
