"""Canonical structured estimate model for Nami.
Text, PNG and PDF must all be derived from this same object.
"""

def _money(v):
    if v is None or v == '': return None
    if isinstance(v,(int,float)): return int(v)
    s=str(v).replace(',','').replace('円','').strip()
    try: return int(float(s))
    except Exception: return None

def _clean_breakdown(value):
    s=str(value or '').strip()
    for token in ('税込','（税込）','(税込)','要確認','・税込','仮','概算'):
        s=s.replace(token,'')
    return s.strip(' ・/、()（）')

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
        rows.append({'key':str(raw.get('key') or ''),'label':str(raw.get('label') or '要確認'),'amount':amount,'original_amount':original,'discount_amount':discount,'breakdown':_clean_breakdown(raw.get('breakdown')),'status':str(raw.get('status') or ('known' if amount is not None else 'unknown'))})
    known=[r['amount'] for r in rows if r['amount'] is not None]
    total=sum(known) if known else None
    return {'property':str(data.get('property') or '物件名要確認'),'move_in':str(data.get('move_in') or ''),'items':rows,'total':total,'total_complete':bool(rows) and all(r['amount'] is not None for r in rows),'notes':[str(x) for x in (data.get('notes') or [])][:6]}

def estimate_to_text(data):
    """Compact LINE/customer text. Internal notes never leak into this output."""
    d=normalize_estimate(data); out=['【初期費用概算】',d['property']]
    if d['move_in']: out.append('入居日：'+d['move_in'])
    for r in d['items']:
        amount='要確認' if r['amount'] is None else f"{r['amount']:,}円"
        detail=('（'+r['breakdown']+'）') if r['breakdown'] else ''
        out.append(f"{r['label']}：{amount}{detail}")
        if r['discount_amount']:
            bits=[]
            if r['original_amount'] is not None: bits.append(f"通常{r['original_amount']:,}円")
            bits.append(f"割引{r['discount_amount']:,}円")
            out.append('  ↳ '+' / '.join(bits))
    total_label='合計' if d['total_complete'] else '現時点概算'
    out.append(total_label+'：'+('要確認' if d['total'] is None else f"{d['total']:,}円"))
    # No customer-facing footnotes. Unknown rows themselves communicate what remains unresolved.
    return '\n'.join(out)
