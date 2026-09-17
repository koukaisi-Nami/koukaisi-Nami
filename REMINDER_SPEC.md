# Member task reminder specification

## Default behavior
When a LINE group message assigns work to a member, Nami should create a persistent reminder task. The reminder remains active until a completion report is detected.

Examples:
- `赤崎、見積もりお願い`
- `赤崎タスク 見積もり 精算書 税務`
- `久山、契約書確認して`

## Lifecycle
1. Detect assignee + task(s) in the group context.
2. Persist the task in PostgreSQL with the LINE group/room target.
3. Remind the group using LINE Push, not only webhook replies.
4. Keep reminding the current task until completion is reported.
5. For ordered multiple tasks, completion advances to the next task.
6. Final completion stops reminders automatically.

## Completion language
Recognize task-specific completion such as `見積もり完了`, and natural completion language such as `終わった`, `できた`, `対応済み` when context identifies one active task.

## Controls
Support `リマインド停止`, `明日まで止めて`, interval changes such as `30分おきにして`, and `リマインド一覧`.

## Safety / correctness
- Do not create reminders for work assigned to Nami herself.
- Do not claim a future reminder is scheduled unless the reminder row was persisted successfully.
- Use database locking/atomic updates so multiple web workers do not send the same due reminder twice.
- Store LINE target IDs for push delivery.
- If push delivery fails, keep the task active and record the failure for retry/diagnostics.

## Initial default
If the user does not specify an interval, use a configurable company default. Explicit intervals such as `10分おき` override it.
