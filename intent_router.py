import re

REMINDER_WORDS=re.compile(r'(リマインド|催促|通知|知らせて|忘れないよう|忘れないで|毎\s*\d+\s*分|\d+\s*分おき|完了報告.*まで)',re.I)
QUESTION_WORDS=re.compile(r'(何|なに|どう|どこ|いつ|誰|だれ|教えて|忘れた|覚えてる|呼ぶ|ですか|\?|？)',re.I)
TASK_WORDS=re.compile(r'(タスク|お願い|やって|対応して|確認して|作って|提出して|送って)',re.I)


def classify_message(text):
    t=(text or '').strip()
    if not t:return 'chat'
    if REMINDER_WORDS.search(t):return 'reminder_request'
    if QUESTION_WORDS.search(t):return 'question'
    if TASK_WORDS.search(t):return 'task_request'
    return 'chat'


def should_create_reminder(text):
    # A task assignment by itself is not permission to schedule repeated push messages.
    return classify_message(text)=='reminder_request'


def reminder_has_enough_context(text):
    t=(text or '').strip()
    if not should_create_reminder(t):return False
    has_interval=bool(re.search(r'\d+\s*分おき|毎\s*\d+\s*分|毎日|毎朝|毎晩|完了報告.*まで',t))
    has_task=bool(re.search(r'(タスク|見積|精算|税務|契約|確認|対応|提出|送付|作成|完了)',t))
    return has_interval and has_task
