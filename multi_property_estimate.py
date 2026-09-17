import re
from collections import defaultdict

UNKNOWN = "－"

PROPERTY_PATTERNS = [
    re.compile(r"(?:物件名|建物名)[:：\s]*([^\n]{2,60})", re.I),
    re.compile(r"【([^】]{2,60})】"),
]
ROOM_PATTERN = re.compile(r"(?:号室|部屋番号|ROOM)[:：\s]*([A-Za-z0-9\-]+)|([0-9]{2,5})\s*号室", re.I)
ADDRESS_PATTERN = re.compile(r"(?:所在地|住所)[:：\s]*([^\n]{5,100})")


def _clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip(" 　:：")


def identify_property(analysis):
    """Extract conservative property identity from an attachment analysis.
    Returns None when there is not enough identity to safely group documents.
    """
    text = analysis or ""
    name = ""
    for p in PROPERTY_PATTERNS:
        m = p.search(text)
        if m:
            name = _clean(m.group(1))
            break
    rm = ROOM_PATTERN.search(text)
    room = _clean((rm.group(1) or rm.group(2)) if rm else "")
    am = ADDRESS_PATTERN.search(text)
    address = _clean(am.group(1) if am else "")
    if not (name or address):
        return None
    # Room number is part of identity so different rooms in one building never mix.
    key = "|".join(x.lower() for x in (name, room, address) if x)
    return {"key": key, "name": name or address, "room": room, "address": address}


def group_attachments(attachments):
    """Group attachment analyses by explicit property identity only.
    Ambiguous items are returned separately and must not be guessed into a group.
    """
    groups = defaultdict(list)
    identities = {}
    ambiguous = []
    for item in attachments:
        ident = identify_property(item.get("analysis", ""))
        if not ident:
            ambiguous.append(item)
            continue
        groups[ident["key"]].append(item)
        identities[ident["key"]] = ident
    return [
        {"property": identities[k], "attachments": v}
        for k, v in groups.items()
    ], ambiguous


def estimate_instruction(groups, ambiguous, user_instruction=""):
    """Build a strict prompt for the existing vision/estimate model."""
    if ambiguous:
        return None, "資料の一部で物件を特定できませんでした。どの物件の資料か指定してください。"
    blocks = []
    for i, g in enumerate(groups, 1):
        p = g["property"]
        analyses = "\n---\n".join(a.get("analysis", "") for a in g["attachments"])
        blocks.append(f"[物件{i}] {p['name']} {p['room']}\n{analyses}")
    prompt = f'''以下の資料を物件ごとに完全に分離して初期費用を計算してください。別物件の金額を絶対に混ぜないでください。
表示順は必ず、当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料、合計。
管理費・共益費は前家賃に含め、独立表示しません。入居日指定なしなら当月前家賃は「－」。未確定項目は「－」。
仲介手数料は今回ユーザーが明示指定した物件だけ計上し、指定がなければ図面等に記載があっても必ず「－」。推測禁止。
Markdown表や計算過程、仲介手数料の内訳は不要です。各物件を【初期費用概算】から始めてください。
ユーザー指定: {user_instruction or 'なし'}

''' + "\n\n".join(blocks)
    return prompt, None
