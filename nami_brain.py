"""Shared Nami Brain foundation.

One intelligence for every LINE room, with memory separated by scope.
This module is intentionally independent from existing estimate/media tools so
current production behaviour can be migrated without breaking those tools.
"""
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class NamiContext:
    user_id: str
    conversation_id: str
    conversation_type: str = "user"  # user | group | room
    company_id: str = "steer-ship"
    is_owner: bool = False


@dataclass(frozen=True)
class MemoryScope:
    scope: str
    scope_id: str


class NamiBrain:
    """Builds the common brain context used from every LINE conversation.

    Intelligence/tools/policies are global. Private context is loaded only from
    explicitly permitted scopes, preventing one LINE room from leaking another
    room's conversation into a response.
    """

    def __init__(self, memory_store=None, tool_registry=None):
        self.memory_store = memory_store
        self.tool_registry = tool_registry

    def readable_scopes(self, ctx: NamiContext) -> list[MemoryScope]:
        scopes = [
            MemoryScope("global", "nami"),
            MemoryScope("company", ctx.company_id),
            MemoryScope("user", ctx.user_id),
        ]
        if ctx.conversation_type in {"group", "room"}:
            scopes.append(MemoryScope("conversation", ctx.conversation_id))
        return scopes

    def writable_scope(self, ctx: NamiContext, requested: str = "conversation") -> MemoryScope:
        if requested == "global":
            if not ctx.is_owner:
                raise PermissionError("Only the owner can change Nami-wide memory/rules")
            return MemoryScope("global", "nami")
        if requested == "company":
            if not ctx.is_owner:
                raise PermissionError("Only the owner can change company-wide memory/rules")
            return MemoryScope("company", ctx.company_id)
        if requested == "user":
            return MemoryScope("user", ctx.user_id)
        return MemoryScope("conversation", ctx.conversation_id)

    def memory_context(self, ctx: NamiContext, limit: int = 30) -> str:
        if not self.memory_store:
            return ""
        chunks = []
        for scope in self.readable_scopes(ctx):
            values = self.memory_store.read(scope.scope, scope.scope_id, limit=limit) or []
            chunks.extend(str(v) for v in values)
        return "\n".join(chunks)

    def available_tools(self) -> Iterable[str]:
        if not self.tool_registry:
            return ()
        return self.tool_registry.names()

    def system_context(self, ctx: NamiContext) -> str:
        tools = ", ".join(self.available_tools())
        memory = self.memory_context(ctx)
        return f"""あなたは航海士ナミ。全LINEで同じ共通知能を使う。
会話ごとの情報は混ぜず、許可された記憶スコープだけを参照する。
自然言語の意味から必要なツールを選び、固定キーワードだけに依存しない。
既存の業務ツールを壊さず、使える場合は会話だけで代替せずツールを使う。
ナミ全体・会社全体のルール変更は船長だけが承認できる。
利用可能ツール: {tools or '未接続'}
関連記憶:\n{memory or 'なし'}"""
