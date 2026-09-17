import unittest
from nami_memory_engine import MemoryHit, allowed_scope_ids, select_context, render_context


class MemoryEngineTests(unittest.TestCase):
    def test_scope_ids_are_isolated(self):
        self.assertEqual(allowed_scope_ids('u1','g1'), (
            ('user','u1'),('conversation','g1'),('company','company')
        ))

    def test_other_user_and_group_never_leak(self):
        hits=(
            MemoryHit('user','u1','mine',1,2),
            MemoryHit('user','u2','other-user',1,3),
            MemoryHit('conversation','g1','this-group',1,4),
            MemoryHit('conversation','g2','other-group',1,5),
            MemoryHit('company','company','company-rule',1,6),
        )
        out=select_context(hits,'u1','g1')
        text=render_context(out)
        self.assertIn('mine',text)
        self.assertIn('this-group',text)
        self.assertIn('company-rule',text)
        self.assertNotIn('other-user',text)
        self.assertNotIn('other-group',text)

    def test_context_is_hard_capped(self):
        hits=tuple(MemoryHit('user','u1','x'*1000,1,i) for i in range(20))
        out=select_context(hits,'u1','g1',max_items=3,max_chars=1500)
        self.assertLessEqual(len(out),3)
        self.assertLessEqual(sum(len(x.content) for x in out),1500)

if __name__=='__main__':
    unittest.main()
