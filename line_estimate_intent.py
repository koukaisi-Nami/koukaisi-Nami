import re

_ESTIMATE = re.compile(r"(?:見積(?:もり)?|初期費用)", re.I)
_BATCH = re.compile(r"(?:まとめて|一括|全部|全て|すべて|全物件|複数|[0-9０-９一二三四五六七八九十]+\s*(?:件|物件)(?:分)?)", re.I)
_CONTEXTUAL = re.compile(r"(?:これ|これら|さっき|先ほど|直前|送った|添付|資料|PDF|画像|図面|やつ)", re.I)
_ACTION = re.compile(r"(?:お願い|頼む|たのむ|やって|出して|作って|見て|よろしく|進めて)", re.I)
_ADD = re.compile(r"(?:これも|追加|含めて|一緒に)", re.I)
_EXCLUDE = re.compile(r"(?:除外|抜いて|以外|だけ)", re.I)

def has_estimate_words(text):
    return bool(_ESTIMATE.search(text or ""))

def is_explicit_batch_estimate(text):
    t=text or ""
    return has_estimate_words(t) and bool(_BATCH.search(t))

def is_contextual_estimate_request(text, pending_count=0):
    """Understand ordinary LINE follow-ups when recent estimate materials exist.

    Examples: 「これ全部お願い」「さっきの5件出して」「これら見て」
    We intentionally require pending material so generic 「お願い」 never becomes
    an estimate command by itself.
    """
    t=(text or "").strip()
    if pending_count <= 0 or not t:
        return False
    if has_estimate_words(t):
        return True
    if _CONTEXTUAL.search(t) and (_BATCH.search(t) or _ACTION.search(t) or _ADD.search(t) or _EXCLUDE.search(t)):
        return True
    # After several consecutive uploads, natural short commands are common.
    if pending_count >= 2 and _BATCH.search(t) and _ACTION.search(t):
        return True
    return False

def should_batch_estimate(text, pending_count=0):
    if pending_count <= 0:
        return False
    return is_explicit_batch_estimate(text) or is_contextual_estimate_request(text,pending_count)

def requested_count(text):
    """Best-effort count for safety checks; None means the user did not specify one."""
    t=text or ""
    m=re.search(r"([0-9０-９]+)\s*(?:件|物件)",t)
    if m:
        return int(m.group(1).translate(str.maketrans("０１２３４５６７８９","0123456789")))
    jp={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    m=re.search(r"([一二三四五六七八九十])\s*(?:件|物件)",t)
    return jp.get(m.group(1)) if m else None

def needs_count_warning(text, pending_count):
    n=requested_count(text)
    return n is not None and pending_count > 0 and n != pending_count
