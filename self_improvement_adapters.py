"""Adapter contracts for self improvement.

Production implementations use existing GitHub credentials from environment;
credentials must never be included in AI prompts.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PatchProposal:
    files: dict[str,str]
    summary: str
    tests: list[str]


class SafeCoder:
    """Turns an owner instruction into a constrained proposal.

    repo_reader and ai are injected so this module never needs secrets itself.
    """
    def __init__(self, repo_reader, ai):
        self.repo_reader=repo_reader
        self.ai=ai

    def prepare_patch(self, instruction: str, branch: str):
        context=self.repo_reader.relevant_files(instruction)
        prompt=f"""既存機能を維持したまま航海士ナミを改善する。
変更は必要最小限。既存の見積/画像/PDF/記憶/LINE処理を削除しない。
mainへ直接書かない。テスト可能な変更だけ提案する。
秘密鍵・APIトークン・環境変数の値は要求/出力しない。
指示: {instruction}
関連コード:\n{context}
変更ファイル全文とテストを構造化して返す。"""
        return self.ai.propose_patch(prompt)


class GitAdapterContract:
    """Expected interface for the existing GitHub integration."""
    def create_improvement_branch(self, improvement_id: int): raise NotImplementedError
    def apply_patch(self, branch: str, patch): raise NotImplementedError
    def open_pr(self, branch: str, instruction: str) -> int: raise NotImplementedError
    def merge_pr(self, pr_number: int) -> str: raise NotImplementedError
