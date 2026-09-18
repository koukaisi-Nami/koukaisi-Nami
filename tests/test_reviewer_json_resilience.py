import unittest
from nami_supervisor import parse_reviewer_json


class ReviewerJsonResilienceTests(unittest.TestCase):
    def valid(self, action="answer", scope="none"):
        return ('{"action":"%s","corrected_answer":"ok","memory_scope":"%s",'
                '"memory_text":"","improvement_request":"","reason":"checked"}') % (action, scope)

    def test_valid_json(self):
        self.assertEqual(parse_reviewer_json(self.valid())["action"], "answer")

    def test_fenced_json(self):
        self.assertEqual(parse_reviewer_json("```json\n" + self.valid() + "\n```")["action"], "answer")

    def test_empty_and_truncated_are_rejected(self):
        self.assertIsNone(parse_reviewer_json(""))
        self.assertIsNone(parse_reviewer_json(self.valid()[:-8]))

    def test_invalid_action_is_rejected(self):
        self.assertIsNone(parse_reviewer_json(self.valid("approve")))

    def test_memory_scope_contract(self):
        self.assertIsNone(parse_reviewer_json(self.valid("memory", "none")))
        self.assertIsNotNone(parse_reviewer_json(self.valid("memory", "user")))
        self.assertIsNone(parse_reviewer_json(self.valid("answer", "user")))

    def test_non_object_is_rejected(self):
        self.assertIsNone(parse_reviewer_json("[]"))


if __name__ == "__main__":
    unittest.main()
