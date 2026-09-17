from estimate_document import parse_customer_estimate,item_breakdown,discount_breakdown

def test_prorated_breakdown():
    assert item_breakdown('当月前家賃','15日分 45,000円') == '日割り 15日分'
    assert item_breakdown('当月前家賃','45,000円') == '日割り'

def test_discount_breakdown():
    assert discount_breakdown('仲介手数料半額','68,475円',68475) == '割引額（半額）'
    assert discount_breakdown('仲介手数料割引','68,475円',68475) == '割引額'

def test_parse_discount_and_total():
    d=parse_customer_estimate('【初期費用概算】\nテスト物件\n当月前家賃：45,000円\n仲介手数料割引：68,475円\n合計：300,000円')
    assert d['total']==300000
    assert len(d['discounts'])==1
