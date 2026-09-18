import ast
import unittest
from pathlib import Path

APP = Path("app.py")

def load_exact_test_command():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "is_exact_test_command"
    )
    mod = ast.Module(body=[node], type_ignores=[])
    ns = {}
    exec(compile(mod, "app.py", "exec"), ns)
    return ns["is_exact_test_command"]

class ExactTestCommandTest(unittest.TestCase):
    def test_only_literal_test_matches(self):
        fn = load_exact_test_command()
        self.assertTrue(fn("テスト"))
        self.assertFalse(fn("これはテスト"))
        self.assertFalse(fn("テストです"))
        self.assertFalse(fn(" テスト "))
        self.assertFalse(fn(""))
        self.assertFalse(fn(None))

    def test_webhook_short_circuits_before_memory_paths(self):
        src = APP.read_text(encoding="utf-8")
        gate = "if typ=='text' and is_exact_test_command(m.get('text','')):"
        reply = "reply(e.get('replyToken'),'航海テスト成功🧭')"
        remember = "remember_line_member(cid,uid,nm)"
        save = "save_msg(eid,cid,uid,nm,'user',text"
        self.assertIn(gate, src)
        self.assertIn(reply, src)
        self.assertLess(src.index(gate), src.index(remember))
        self.assertLess(src.index(gate), src.index(save))

if __name__ == "__main__":
    unittest.main()
