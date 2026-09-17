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

def parse_customer_estimate(text):
    lines=[x.strip() for x in (text or '').splitlines() if x.strip()]
    title=''; items=[]; total=None; notes=[]
    for x in lines:
        if x.startswith('【初期費用概算】'): continue
        if not title and '：' not in x and not x.startswith('※'):
            title=x; continue
        if x.startswith('※'): notes.append(x); continue
        m=LINE_RE.match(x)
        if not m: continue
        label,value=m.groups(); ym=YEN_RE.search(value)
        amount=int(ym.group(1).replace(',','')) if ym else None
        if label=='合計': total=amount
        else: items.append((label,value,amount))
    return {'property':title or '物件名要確認','items':items,'total':total,'notes':notes}

def make_estimate_document(text):
    d=parse_customer_estimate(text); out=BytesIO(); c=canvas.Canvas(out,pagesize=A4); w,h=A4; navy=(0.035,0.12,0.20)
    c.setTitle('見積もり概算書'); c.setStrokeColorRGB(*navy); c.setLineWidth(1.4); c.line(12*mm,h-12*mm,w-12*mm,h-12*mm)
    c.setFillColorRGB(*navy); c.setFont(FONT,26); c.drawCentredString(w/2,h-31*mm,'見 積 も り 概 算 書'); c.setFont(FONT,8); c.drawRightString(w-14*mm,h-27*mm,'ESTIMATE'); c.line(12*mm,h-39*mm,w-12*mm,h-39*mm)
    y=h-55*mm; c.setFillColorRGB(*navy); c.rect(14*mm,y-8*mm,30*mm,11*mm,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10); c.drawCentredString(29*mm,y-4*mm,'物件名')
    c.setFillColorRGB(0,0,0); c.setFont(FONT,14); c.drawString(50*mm,y-4*mm,d['property'][:35]); c.setFont(FONT,8); c.drawRightString(w-14*mm,y-4*mm,datetime.now().strftime('発行日 %Y/%m/%d'))
    top=y-18*mm; left=14*mm; right=w-14*mm; col1=72*mm; col2=132*mm; rowh=11*mm
    c.setFillColorRGB(*navy); c.rect(left,top-rowh,right-left,rowh,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10)
    c.drawCentredString((left+col1)/2,top-7.5*mm,'項目'); c.drawCentredString((col1+col2)/2,top-7.5*mm,'内訳'); c.drawCentredString((col2+right)/2,top-7.5*mm,'金額（税込）')
    c.setStrokeColorRGB(.55,.58,.62); yy=top-rowh
    for label,value,amount in [x for x in d['items'] if x[1] != '－'][:13]:
        c.rect(left,yy-rowh,right-left,rowh,fill=0,stroke=1); c.line(col1,yy,col1,yy-rowh); c.line(col2,yy,col2,yy-rowh); c.setFillColorRGB(0,0,0); c.setFont(FONT,10); c.drawString(left+4*mm,yy-7.5*mm,label[:18]); c.setFont(FONT,8); c.drawString(col1+4*mm,yy-7.5*mm,'概算' if '（仮）' in label else '')
        c.setFont(FONT,11); c.drawRightString(right-4*mm,yy-7.5*mm,(f'{amount:,} 円' if amount is not None else value[:22])); yy-=rowh
    yy-=5*mm; c.setStrokeColorRGB(*navy); c.setLineWidth(1.3); c.rect(left,yy-22*mm,right-left,22*mm,fill=0,stroke=1); c.setFillColorRGB(*navy); c.setFont(FONT,20); c.drawString(left+8*mm,yy-14*mm,'合計（税込）'); c.setFont(FONT,25); c.drawRightString(right-8*mm,yy-14*mm,('要確認' if d['total'] is None else f"{d['total']:,} 円"))
    ny=yy-31*mm; c.setFillColorRGB(0,0,0); c.setFont(FONT,8)
    for n in (d['notes'] or ['※ 本書は概算の見積もりです。入居日・未確定項目により金額が変動します。'])[:3]: c.drawString(left,ny,n[:85]); ny-=5*mm
    c.setFont(FONT,8); c.drawRightString(right,14*mm,'Steer Ship株式会社'); c.showPage(); c.save(); out.seek(0); return out

def make_estimate_image(text):
    import fitz
    pdf=fitz.open(stream=make_estimate_document(text).getvalue(),filetype='pdf')
    pix=pdf[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
    return BytesIO(pix.tobytes('png'))
