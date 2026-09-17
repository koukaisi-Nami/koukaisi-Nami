from self_improvement_adapters import SafeCoder


class Reader:
    def relevant_files(self,i): return 'def estimate(): pass'
class AI:
    def __init__(self): self.prompt=''
    def propose_patch(self,p): self.prompt=p; return {'files':{},'tests':[]}


def test_coder_prompt_preserves_existing_capabilities_and_secrets():
    ai=AI(); coder=SafeCoder(Reader(),ai)
    coder.prepare_patch('見積を改善','branch')
    assert '既存' in ai.prompt
    assert '削除しない' in ai.prompt
    assert '秘密鍵' in ai.prompt
    assert 'mainへ直接書かない' in ai.prompt
