import unittest
from nami_rag import file_search_tool, safe_name, MAX_UPLOAD_BYTES


class RagTests(unittest.TestCase):
    def test_search_tool_is_bounded(self):
        tool=file_search_tool(['vs_a','vs_b','vs_c','vs_d'],99)
        self.assertEqual(tool['vector_store_ids'],['vs_a','vs_b','vs_c'])
        self.assertEqual(tool['max_num_results'],8)

    def test_invalid_store_ids_ignored(self):
        self.assertIsNone(file_search_tool(['bad','']))

    def test_safe_filename(self):
        self.assertNotIn('/',safe_name('../顧客 資料.pdf'))

    def test_upload_cap_is_reasonable(self):
        self.assertLessEqual(MAX_UPLOAD_BYTES,25*1024*1024)


if __name__=='__main__':
    unittest.main()
