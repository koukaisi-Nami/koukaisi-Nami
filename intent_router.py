import re

# Reminder creation is opt-in only. Words that merely appear in normal business
# conversation must never schedule background pushes.
EXPLICIT_REMINDER=re.compile(r'(リマインドして|リマインドお願い|催促して|通知して|知らせて|忘れないように(?:して|通知)|忘れないで(?:通知|知らせ))',re.I)
QUESTION_WORDS=re.compile(r'(何|なに|どう|どこ|いつ|誰|だれ|教えて|忘れた|覚えてる|呼ぶ|ですか|\?|？)',re.I)
TASK_WORDS=re.compile(r'(タスク|お願い|やって|対応して|確認して|作って|提出して|送って)',re.I)
TIMING=re.compile(r'(\d+\s*分おき|毎\s*\d+\s*分|\d+\s*時(?:\d+\s*分)?|今日|明日|毎日|毎朝|毎晩|完了報告.*まで)',re.I)


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
    if not should_create_reminder(t):return False
    # Never invent a default cadence. The user must specify when/how often.
    return bool(TIMING.search(t))


def reminder_needs_timing(text):
    return should_create_reminder(text) and not reminder_has_enough_context(text)
