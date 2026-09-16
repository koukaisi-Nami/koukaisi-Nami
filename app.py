# 航海士ナミ v2

## Render Environment Variables
- LINE_CHANNEL_SECRET
- LINE_CHANNEL_ACCESS_TOKEN
- OPENAI_API_KEY
- DATABASE_URL
- CRON_SECRET（自動催促を使う場合）
- OPENAI_MODEL=gpt-5.6-luna（任意）

## Render
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn app:app

## 仕様
- 個人LINE: 常時返信
- グループ: 全テキストを記録。ただし「ナミ / なみ / 航海士ナミ」と呼ばれた時だけ返信
- 明示記憶:
  - 「〇〇って覚えて」= personal
  - 「このグループだけ〇〇って覚えて」= group
  - 「会社全体で〇〇って覚えて」= global
  - 「〇〇を忘れて」= 該当記憶を無効化
- Web検索: OpenAI Responses API web_search
- 画像/図面: LINE画像を受信直後に取得し、Vision解析してDBに要約保存
- 見積: 保存済み料金ルールを根拠に概算。未確認事項を明示
- タスク:
  - タスク追加: 翔くん | 田中さんへ物件送付 | 2026-09-20T18:00:00+09:00
  - タスク一覧
  - タスク完了: 12
- 自動催促: POST /cron/reminders に Authorization: Bearer <CRON_SECRET>

## 重要
これは本番運用の強い土台ですが「完全無欠」を保証するものではありません。
見積は画像だけで確定させず、現場条件・数量・寸法・料金ルールの確認をしてください。
グループ会話を保存する運用は、参加者に明示してください。
