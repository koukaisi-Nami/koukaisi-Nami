import re
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

FONT='HeiseiKakuGo-W5'
pdfmetrics.registerFont(UnicodeCIDFont(FONT))
LINE_RE=re.compile(r'^([^：\n]{1,40})：\s*(.+)$')
YEN_RE=re.compile(r'([0-9][0-9,]*)\s*円')
DISCOUNT_RE=re.compile(r'(割引|値引|安く|サービス|OFF|オフ|無料|半額|減額|キャンペーン|特典)',re.I)
MOVEIN_RE=re.compile(r'^(?:入居日|入居予定日|入居予定|契約開始日)$')
CURRENT_RE=re.compile(r'当月前家賃|当月家賃|日割り家賃|日割家賃')

def parse_customer_estimate(text):
    lines=[x.strip() for x in (text or '').splitlines() if x.strip()]
    title=''; items=[]; total=None; notes=[]; move_in=''; discounts=[]
    for x in lines:
        if x.startswith('【初期費用概算】'): continue
        if not title and '：' not in x and not x.startswith('※'):
            title=x; continue
        if x.startswith('※'):
            notes.append(x)
            if not move_in:
                m=re.search(r'([0-9]{1,2})日入居',x)
                if m: move_in=m.group(1)+'日'
            continue
        m=LINE_RE.match(x)
        if not m: continue
        label,value=m.groups(); ym=YEN_RE.search(value)
        amount=int(ym.group(1).replace(',','')) if ym else None
        if label=='合計': total=amount; continue
        if MOVEIN_RE.match(label): move_in=value; continue
        row=(label,value,amount)
        if DISCOUNT_RE.search(label+' '+value): discounts.append(row)
        else: items.append(row)
    return {'property':title or '物件名要確認','items':items,'discounts':discounts,'total':total,'notes':notes,'move_in':move_in}

def item_detail(label,value):
    if CURRENT_RE.search(label):
        m=re.search(r'(日割り[^）\n]*)',value)
        return m.group(1) if m else '日割り賃料'
    return '概算' if '（仮）' in label or '仮' in value else ''

def discount_detail(label,value,amount):
    condition=''
    if '半額' in label+value: condition='・半額'
    elif '無料' in label+value: condition='・無料'
    return (('割引額 '+f'{amount:,}円') if amount is not None else '割引額')+condition

def make_estimate_document(text):
    d=parse_customer_estimate(text); out=BytesIO(); c=canvas.Canvas(out,pagesize=A4); w,h=A4
    navy=(0.035,0.12,0.20); red=(0.78,0.08,0.08)
    c.setTitle('見積もり概算書'); c.setStrokeColorRGB(*navy); c.setLineWidth(1.4); c.line(12*mm,h-12*mm,w-12*mm,h-12*mm)
    c.setFillColorRGB(*navy); c.setFont(FONT,26); c.drawCentredString(w/2,h-31*mm,'見 積 も り 概 算 書'); c.setFont(FONT,8); c.drawRightString(w-14*mm,h-27*mm,'ESTIMATE'); c.line(12*mm,h-39*mm,w-12*mm,h-39*mm)
    y=h-55*mm; c.setFillColorRGB(*navy); c.rect(14*mm,y-8*mm,30*mm,11*mm,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10); c.drawCentredString(29*mm,y-4*mm,'物件名')
    c.setFillColorRGB(0,0,0); c.setFont(FONT,14); c.drawString(50*mm,y-4*mm,d['property'][:35]); c.setFont(FONT,8); c.drawRightString(w-14*mm,y-4*mm,datetime.now().strftime('発行日 %Y/%m/%d'))
    if d['move_in']:
        c.setFillColorRGB(*navy); c.setFont(FONT,10); c.drawString(50*mm,y-10*mm,'入居日：'+d['move_in'][:24])
    top=y-(22*mm if d['move_in'] else 18*mm); left=14*mm; right=w-14*mm; col1=72*mm; col2=132*mm; rowh=10*mm
    c.setFillColorRGB(*navy); c.rect(left,top-rowh,right-left,rowh,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10)
    c.drawCentredString((left+col1)/2,top-7*mm,'項目'); c.drawCentredString((col1+col2)/2,top-7*mm,'内訳'); c.drawCentredString((col2+right)/2,top-7*mm,'金額（税込）')
    c.setStrokeColorRGB(.55,.58,.62); yy=top-rowh
    rows=[x for x in d['items'] if x[1] != '－']
    for label,value,amount in rows[:15]:
        c.rect(left,yy-rowh,right-left,rowh,fill=0,stroke=1); c.line(col1,yy,col1,yy-rowh); c.line(col2,yy,col2,yy-rowh); c.setFillColorRGB(0,0,0); c.setFont(FONT,9); c.drawString(left+4*mm,yy-6.8*mm,label[:20]); c.setFont(FONT,8); c.drawString(col1+4*mm,yy-6.8*mm,item_detail(label,value)[:24]); c.setFont(FONT,10); c.drawRightString(right-4*mm,yy-6.8*mm,(f'{amount:,} 円' if amount is not None else value[:22])); yy-=rowh
    if d['discounts']:
        yy-=3*mm; c.setFillColorRGB(*red); c.setFont(FONT,11); c.drawString(left,yy,'割引・特典'); yy-=5*mm
        for label,value,amount in d['discounts'][:5]:
            c.setStrokeColorRGB(*red); c.rect(left,yy-rowh,right-left,rowh,fill=0,stroke=1); c.line(col1,yy,col1,yy-rowh); c.line(col2,yy,col2,yy-rowh); c.setFillColorRGB(*red); c.setFont(FONT,9); c.drawString(left+4*mm,yy-6.8*mm,label[:20]); c.setFont(FONT,8); c.drawString(col1+4*mm,yy-6.8*mm,discount_detail(label,value,amount)[:24]); c.setFont(FONT,10); c.drawRightString(right-4*mm,yy-6.8*mm,(f'▲ {amount:,} 円' if amount is not None else value[:22])); yy-=rowh
    yy-=5*mm; c.setStrokeColorRGB(*navy); c.setLineWidth(1.5); c.rect(left,yy-22*mm,right-left,22*mm,fill=0,stroke=1); c.setFillColorRGB(*navy); c.setFont(FONT,18); c.drawString(left+8*mm,yy-14*mm,'お支払い概算合計'); c.setFont(FONT,24); c.drawRightString(right-8*mm,yy-14*mm,('要確認' if d['total'] is None else f"{d['total']:,} 円"))
    ny=yy-30*mm; c.setFillColorRGB(0,0,0); c.setFont(FONT,8)
    for n in (d['notes'] or ['※ 本書は概算の見積もりです。入居日・未確定項目により金額が変動します。'])[:4]: c.drawString(left,ny,n[:85]); ny-=5*mm
    c.setFont(FONT,8); c.drawRightString(right,14*mm,'Steer Ship株式会社'); c.showPage(); c.save(); out.seek(0); return out

def make_estimate_image(text):
    import fitz
    pdf=fitz.open(stream=make_estimate_document(text).getvalue(),filetype='pdf')
    pix=pdf[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False)
    return BytesIO(pix.tobytes('png'))
