import re
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from estimate_model import normalize_estimate, _customer_detail

FONT='HeiseiKakuGo-W5'; pdfmetrics.registerFont(UnicodeCIDFont(FONT))

def _detail(row):
    # Keep image/PDF annotations identical to the canonical LINE text policy.
    return _customer_detail(row)

def make_estimate_document(payload):
    d=normalize_estimate(payload); out=BytesIO(); c=canvas.Canvas(out,pagesize=A4); w,h=A4
    navy=(0.035,0.12,0.20); red=(0.78,0.08,0.08)
    c.setTitle('見積もり概算書'); c.setStrokeColorRGB(*navy); c.setLineWidth(1.4); c.line(12*mm,h-12*mm,w-12*mm,h-12*mm)
    c.setFillColorRGB(*navy); c.setFont(FONT,26); c.drawCentredString(w/2,h-31*mm,'見 積 も り 概 算 書'); c.setFont(FONT,8); c.drawRightString(w-14*mm,h-27*mm,'ESTIMATE'); c.line(12*mm,h-39*mm,w-12*mm,h-39*mm)
    y=h-55*mm; c.setFillColorRGB(*navy); c.rect(14*mm,y-8*mm,30*mm,11*mm,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10); c.drawCentredString(29*mm,y-4*mm,'物件名')
    c.setFillColorRGB(0,0,0); c.setFont(FONT,14); c.drawString(50*mm,y-4*mm,d['property'][:35]); c.setFont(FONT,8); c.drawRightString(w-14*mm,y-4*mm,datetime.now().strftime('発行日 %Y/%m/%d'))
    if d.get('move_in'): c.setFillColorRGB(*navy); c.setFont(FONT,10); c.drawString(50*mm,y-10*mm,'入居日：'+d['move_in'][:24])
    top=y-(22*mm if d.get('move_in') else 18*mm); left=14*mm; right=w-14*mm; col1=72*mm; col2=132*mm; rowh=10*mm
    c.setFillColorRGB(*navy); c.rect(left,top-rowh,right-left,rowh,fill=1,stroke=0); c.setFillColorRGB(1,1,1); c.setFont(FONT,10); c.drawCentredString((left+col1)/2,top-7*mm,'項目'); c.drawCentredString((col1+col2)/2,top-7*mm,'内訳'); c.drawCentredString((col2+right)/2,top-7*mm,'金額')
    yy=top-rowh
    for row in d.get('items',[])[:15]:
        discounted=bool(row.get('discount_amount')); c.setStrokeColorRGB(*(red if discounted else (.55,.58,.62))); c.rect(left,yy-rowh,right-left,rowh,fill=0,stroke=1); c.line(col1,yy,col1,yy-rowh); c.line(col2,yy,col2,yy-rowh)
        c.setFillColorRGB(*(red if discounted else (0,0,0))); c.setFont(FONT,9); c.drawString(left+4*mm,yy-6.8*mm,row.get('label','')[:20]); c.setFont(FONT,7.5); c.drawString(col1+3*mm,yy-6.8*mm,_detail(row)[:30])
        amount=row.get('amount'); value='－' if amount is None else f'{amount:,} 円'; c.setFont(FONT,10); c.drawRightString(right-4*mm,yy-6.8*mm,value); yy-=rowh
    yy-=5*mm; c.setStrokeColorRGB(*navy); c.setLineWidth(1.5); c.rect(left,yy-22*mm,right-left,22*mm,fill=0,stroke=1); c.setFillColorRGB(*navy); c.setFont(FONT,18); c.drawString(left+8*mm,yy-14*mm,'初期費用合計'); c.setFont(FONT,24); c.drawRightString(right-8*mm,yy-14*mm,('－' if d.get('total') is None else f"{d['total']:,} 円"))
    c.setFont(FONT,8); c.drawRightString(right,14*mm,'Steer Ship株式会社'); c.showPage(); c.save(); out.seek(0); return out

def make_estimate_image(payload):
    import fitz
    pdf=fitz.open(stream=make_estimate_document(payload).getvalue(),filetype='pdf'); pix=pdf[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False); return BytesIO(pix.tobytes('png'))
