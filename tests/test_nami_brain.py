import pytest
from nami_brain import NamiBrain, NamiContext


class Memory:
    def __init__(self): self.calls=[]
    def read(self, scope, scope_id, limit=30):
        self.calls.append((scope,scope_id))
        return [f"{scope}:{scope_id}"]


class Tools:
    def names(self): return ["estimate", "image_pdf", "web", "reminder"]


def test_group_uses_shared_brain_but_scoped_memory():
    mem=Memory(); brain=NamiBrain(mem,Tools())
    text=brain.system_context(NamiContext("u1","g1","group"))
    assert ("global","nami") in mem.calls
    assert ("company","steer-ship") in mem.calls
    assert ("user","u1") in mem.calls
    assert ("conversation","g1") in mem.calls
    assert "g2" not in text
    assert "estimate" in text


def test_private_chat_does_not_read_group_memory():
    mem=Memory(); brain=NamiBrain(mem,Tools())
    brain.system_context(NamiContext("u1","u1","user"))
    assert not any(scope == "conversation" for scope,_ in mem.calls)


def test_only_owner_can_write_global_rules():
    brain=NamiBrain()
    with pytest.raises(PermissionError):
        brain.writable_scope(NamiContext("u2","g1","group",is_owner=False),"global")
    scope=brain.writable_scope(NamiContext("captain","captain","user",is_owner=True),"global")
    assert (scope.scope,scope.scope_id) == ("global","nami")
