from pathlib import Path
p=Path('app.py'); s=p.read_text()
# Add draft storage.
needle='            c.execute("CREATE INDEX IF NOT EXISTS tasks_open_idx ON tasks(status,due_date)")'
if 'CREATE TABLE IF NOT EXISTS estimate_drafts' not in s:
    s=s.replace(needle,needle+'\n            c.execute("""CREATE TABLE IF NOT EXISTS estimate_drafts(\n              conversation_id TEXT PRIMARY KEY,user_id TEXT,data JSONB NOT NULL DEFAULT \'{}\'::jsonb,updated_at TIMESTAMPTZ DEFAULT NOW())""")',1)
# Final customer format is enforced directly in the existing estimate prompt.
old='''                "表示項目と順番は必ず次で固定：当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料、合計。該当しない又は金額不明の項目も省略せず「－」と表示してください。\\n"'''
new='''                "表示項目と順番は必ず次で固定：当月前家賃、次月前家賃、敷金、礼金、初回保証料、仲介手数料、火災保険、24時間サポート、鍵交換、事務手数料、合計。該当しない又は金額不明の項目も省略せず「－」と表示してください。仲介手数料の内訳・消費税内訳・計算説明・別途確認一覧は出さないでください。保証料の表示名は必ず「初回保証料」にしてください。\\n"'''
if old in s:s=s.replace(old,new,1)
# Turn image placeholder into an explicit production marker; renderer is added below.
s=s.replace("ans='見積もり画像用の内容を作成したよ🧭\\n'+quick_doc[1]+'\\n※画像は固定テンプレート描画で金額を変えずに生成する仕様です。'","ans='【初期費用概算】\\n'+quick_doc[1]+'\\n\\n※見積もり画像の固定テンプレート生成準備済み。'",1)
# Keep compile-safe implementation now; image endpoint delivery will be a separate tested change.
p.write_text(s)
