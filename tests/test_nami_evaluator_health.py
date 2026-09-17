import unittest
from nami_evaluator import Review, Verdict, evaluate, parse_review
from nami_health import HealthSample, DeployAction, decide


class EvaluatorHealthTests(unittest.TestCase):
    def test_fix_beats_approve(self):
        out=evaluate((Review(Verdict.APPROVE,'ok',0.9),Review(Verdict.FIX,'bug',0.8)))
        self.assertEqual(out.verdict,Verdict.FIX)

    def test_reject_beats_everything(self):
        out=evaluate((Review(Verdict.APPROVE,'ok',0.9),Review(Verdict.REJECT,'unsafe',0.9)))
        self.assertEqual(out.verdict,Verdict.REJECT)

    def test_empty_reviews_fail_closed(self):
        self.assertEqual(evaluate(()).verdict,Verdict.REJECT)

    def test_bad_review_payload_rejected(self):
        with self.assertRaises(ValueError):
            parse_review({'verdict':'maybe','confidence':1})

    def test_health_rolls_back_on_webhook_failure(self):
        s=HealthSample(True,False,0.0,100,0)
        self.assertEqual(decide(s),DeployAction.ROLLBACK)

    def test_health_holds_on_latency_spike(self):
        base=HealthSample(True,True,0.01,1000,0)
        new=HealthSample(True,True,0.01,3000,0)
        self.assertEqual(decide(new,base),DeployAction.HOLD)

if __name__=='__main__':
    unittest.main()
