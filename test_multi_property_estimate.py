from multi_property_estimate import identify_property, group_attachments, estimate_instruction


def test_identifies_room_separately():
    a=identify_property('物件名：アクシア日本橋\n号室：1201\n所在地：東京都中央区')
    b=identify_property('物件名：アクシア日本橋\n号室：1202\n所在地：東京都中央区')
    assert a['key'] != b['key']


def test_different_properties_never_mix():
    items=[
      {'id':'1','analysis':'物件名：Aレジデンス\n号室：101\n所在地：東京都港区\n賃料10万円'},
      {'id':'2','analysis':'物件名：Aレジデンス\n号室：101\n所在地：東京都港区\n鍵交換2万円'},
      {'id':'3','analysis':'物件名：Bタワー\n号室：202\n所在地：東京都中央区\n賃料20万円'},
    ]
    groups,amb=group_attachments(items)
    assert len(groups)==2
    assert not amb
    assert sorted(len(x['attachments']) for x in groups)==[1,2]


def test_ambiguous_is_not_guessed():
    groups,amb=group_attachments([{'id':'x','analysis':'鍵交換 22,000円'}])
    assert groups==[] and len(amb)==1


def test_prompt_requires_brokerage_dash():
    groups,amb=group_attachments([{'id':'1','analysis':'物件名：A\n号室：101\n所在地：東京都港区'}])
    prompt,err=estimate_instruction(groups,amb)
    assert err is None
    assert '仲介手数料' in prompt and '必ず「－」' in prompt
