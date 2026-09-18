from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def kb(name):
    return (ROOT/"knowledge"/name).read_text(encoding="utf-8")

def test_rental_cost_items_are_covered():
    text=kb("rental_operations.md")+kb("estimate_quality.md")
    for term in ["日割","保証会社","火災保険","鍵交換","24時間","仲介手数料","税込","必須"]:
        assert term in text

def test_sales_core_is_covered():
    text=kb("sales_operations.md")
    for term in ["登記","ローン特約","契約不適合責任","決済","仲介手数料","利回り"]:
        assert term in text

def test_no_guessing_policy_exists():
    text=kb("real_estate_core.md")+kb("estimate_quality.md")
    assert "推測" in text
    assert "未記載" in text
    assert "再計算" in text

def test_runtime_wires_property_knowledge():
    app=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "def real_estate_knowledge(text):" in app
    assert "【不動産専門Knowledge Base】" in app
    assert "knowledge/rental_operations.md" in app
    assert "knowledge/sales_operations.md" in app
