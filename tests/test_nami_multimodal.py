import unittest
from nami_multimodal import MediaTask, plan_media, source_and_generated_must_not_mix


class MultimodalPolicyTests(unittest.TestCase):
    def test_pdf_analysis_keeps_source_trace(self):
        p=plan_media(has_pdf=True)
        self.assertEqual(p.task,MediaTask.ANALYZE_PDF)
        self.assertTrue(p.requires_source_trace)
        self.assertFalse(p.generated_artifact)

    def test_image_generation_is_labeled_generated(self):
        p=plan_media(wants_image=True)
        self.assertEqual(p.task,MediaTask.GENERATE_IMAGE)
        self.assertTrue(p.generated_artifact)

    def test_media_work_is_bounded(self):
        self.assertLessEqual(plan_media(has_image=True).max_files,12)
        self.assertLessEqual(plan_media(has_pdf=True).max_pages,40)

    def test_generated_and_source_are_separate(self):
        self.assertTrue(source_and_generated_must_not_mix('source_pdf','generated_pdf'))


if __name__ == '__main__':
    unittest.main()
