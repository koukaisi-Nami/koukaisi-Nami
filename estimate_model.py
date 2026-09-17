"""Canonical structured estimate model for Nami.
Text, PNG and PDF must all be derived from this same object.
"""

def _money(v):
    if v is None or v == '': return None
    if isinstance(v,(int,float)): return int(v)
    s=str(v).replace(',','').replace('円','').strip()
    try: return int(float(s))
    except Exception: return None

def normalize_estimate(data):
    data=data if isinstance(data,dict) else {}
    rows=[]
    for raw in data.get('items') or []:
        if not isinstance(raw,dict): continue
        original=_money(raw.get('original_amount'))
        discount=max(0,_money(raw.get('discount_amount')) or 0)
        amount=_money(raw.get('amount'))
        if amount is None and original is not None:
            amount=max(0,original-discount)
        rows.append({
            'key':str(raw.get('key') or ''),
            'label':str(raw.get('label') or '要確認'),
            'amount':amount,
            'original_amount':original,
            'discount_amount':discount,
            'breakdown':str(raw.get('breakdown') or ''),
            'status':str(raw.get('status') or ('known' if amount is not None else 'unknown')),
        })
    known=[r['amount'] for r in rows if r['amount'] is not None]
    total=sum(known) if known else None
    return {
        'property':str(data.get('property') or '物件名要確認'),
        'move_in':str(data.get('move_in') or ''),
        'items':rows,
        'total':total,
        'total_complete':bool(rows) and all(r['amount'] is not None for r in rows),
        'notes':[str(x) for x in (data.get('notes') or [])][:6],
    }

def estimate_to_text(data):
    d=normalize_estimate(data)
    out=['【初期費用概算】',d['property']]
    if d['move_in']: out.append('入居日：'+d['move_in'])
    for r in d['items']:
        amount='要確認' if r['amount'] is None else f"{r['amount']:,}円"
        detail=('（'+r['breakdown']+'）') if r['breakdown'] else ''
        out.append(f"{r['label']}：{amount}{detail}")
        if r['discount_amount']:
            original=r['original_amount']
            bits=[]
            if original is not None: bits.append(f"通常{original:,}円")
            bits.append(f"割引{r['discount_amount']:,}円")
            out.append('  ↳ '+' / '.join(bits))
    out.append('合計：'+('要確認' if d['total'] is None else f"{d['total']:,}円"))
    if not d['total_complete']: out.append('※ 未確定項目があるため、確定時に合計が変動します。')
    out.extend(d['notes'])
    return '\n'.join(out)
