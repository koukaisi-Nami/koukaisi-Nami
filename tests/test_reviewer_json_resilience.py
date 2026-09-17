import unittest
from nami_supervisor import parse_reviewer_json


class ReviewerJsonResilienceTests(unittest.TestCase):
    def valid(self, action="answer", scope="none"):
        return ('{"action":"%s","corrected_answer":"ok","memory_scope":"%s",'
                '"memory_text":"","improvement_request":"","reason":"checked"}') % (action, scope)

    def test_valid_json(self):
        result = parse_reviewer_json(self.valid())
        self.assertEqual(result["action"], "answer")

    def test_fenced_json(self):
        result = parse_reviewer_json("```json\n" + self.valid() + "\n```")
        self.assertEqual(result["action"], "answer")

    def test_empty_json_is_rejected(self):
        self.assertIsNone(parse_reviewer_json(""))

    def test_truncated_json_is_rejected(self):
        raw = self.valid()[:-8]
        self.assertIsNone(parse_reviewer_json(raw))

    def test_invalid_action_is_rejected(self):
        self.assertIsNone(parse_reviewer_json(self.valid("approve")))

    def test_memory_requires_scope(self):
        self.assertIsNone(parse_reviewer_json(self.valid("memory", "none")))
        self.assertIsNotNone(parse_reviewer_json(self.valid("memory", "user")))

    def test_non_memory_cannot_set_scope(self):
        self.assertIsNone(parse_reviewer_json(self.valid("answer", "user")))

    def test_non_object_json_is_rejected(self):
        self.assertIsNone(parse_reviewer_json("[]"))


if __name__ == "__main__":
    unittest.main()
