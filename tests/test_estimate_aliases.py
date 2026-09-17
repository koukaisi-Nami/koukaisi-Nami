from multi_property_estimate import estimate_instruction

g=[{'property':{'name':'TEST','room':'101','address':''},'attachments':[{'analysis':'保証金 100000円\n家財保険 18000円\n保証委託料 50000円'}]}]
p,e=estimate_instruction(g,[],'見積もり')
assert e is None
for word in ['保証金','家財保険','保証委託料','火災保険（仮）：20,000円','二重計上しない','表記ゆれ・意味分類']:
    assert word in p, word
print('ok')
