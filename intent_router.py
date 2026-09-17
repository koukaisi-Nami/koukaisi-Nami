import re

# Reminder pushes are strictly opt-in. Merely mentioning a task, timing, or
# completion must never create a background reminder.
EXPLICIT_REMINDER=re.compile(r'(リマインドして|リマインドお願い|催促して|通知して|知らせて|忘れないように(?:して|通知)|忘れないで(?:通知|知らせ))',re.I)
INTERVAL=re.compile(r'(\d+)\s*分おき|毎\s*(\d+)\s*分',re.I)
QUESTION_WORDS=re.compile(r'(何|なに|どう|どこ|いつ|誰|だれ|教えて|忘れた|覚えてる|呼ぶ|ですか|\?|？)',re.I)
TASK_WORDS=re.compile(r'(タスク|お願い|やって|対応して|確認して|作って|提出して|送って)',re.I)


def classify_message(text):
    t=(text or '').strip()
    if not t:return 'chat'
    if EXPLICIT_REMINDER.search(t):return 'reminder_request'
    if QUESTION_WORDS.search(t):return 'question'
    if TASK_WORDS.search(t):return 'task_request'
    return 'chat'


def should_create_reminder(text):
    return bool(EXPLICIT_REMINDER.search((text or '').strip()))


def reminder_has_enough_context(text):
    t=(text or '').strip()
    return should_create_reminder(t) and bool(INTERVAL.search(t))


def reminder_needs_timing(text):
    return should_create_reminder(text) and not reminder_has_enough_context(text)
