"""Steer Ship standard document definitions used by Nami.
Based on the three approved examples: AD invoice, brokerage fee settlement, move-in estimate.
"""

COMPANY = {
    "name": "Steer Ship株式会社",
    "tel": "03-6722-6177",
    "fax": "03-6722-6178",
    "bank": "PayPay銀行",
    "branch": "ビジネス営業部支店(005)",
    "account_type": "普通",
    "account_number": "6269242",
    "account_name": "ステアシップ（カ",
    "invoice_registration": "T7010401166721",
}

DOCUMENT_TYPES = {
    "ad": {
        "title": "請求書",
        "aliases": ["AD", "AD請求", "AD請求書", "広告料", "業務委託料"],
        "required": ["client", "property_name", "room", "base_amount", "payment_deadline"],
        "items": ["業務委託料", "消費税(10%)", "合計金額"],
    },
    "brokerage": {
        "title": "仲介手数料精算書",
        "aliases": ["中手", "仲介手数料", "仲介手数料精算書"],
        "required": ["client", "property_name", "room", "brokerage_fee", "payment_deadline"],
        "items": ["仲介手数料", "合計"],
    },
    "estimate": {
        "title": "見積り書",
        "aliases": ["見積", "見積もり", "初期費用", "入居計算書"],
        "required": ["property_name", "room"],
        "items": [
            "当月家賃（日割り）", "次月家賃", "管理費・共益費", "敷金", "礼金",
            "初回保証料", "仲介手数料", "契約時クリーニング費用", "鍵交換費用",
            "火災保険料", "24時間サポート", "その他費用", "合計",
        ],
    },
}


def classify_document_command(text):
    t=(text or "").lower()
    for key,spec in DOCUMENT_TYPES.items():
        if any(a.lower() in t for a in spec["aliases"]):
            return key
    return None


def missing_fields(kind, data):
    spec=DOCUMENT_TYPES[kind]
    return [k for k in spec["required"] if data.get(k) in (None, "")]


def ad_totals(base_amount):
    base=int(base_amount or 0)
    tax=round(base*0.10)
    return {"base_amount":base, "tax":tax, "total":base+tax}
