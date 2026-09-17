import ast
s=open('scripts/post_deploy_guard.py').read()
ast.parse(s)
w=open('.github/workflows/post-deploy-guard.yml').read()
assert 'branches: [main]' in w
assert 'cancel-in-progress: false' in w
assert 'revert' in s and 'HEAD:main' in s
assert 'LINE_CHANNEL_ACCESS_TOKEN' in s
assert 'NAMI_OWNER_LINE_USER_ID' in s
assert 'DROP TABLE' not in s.upper()
assert 'DELETE FROM MEMORIES' not in s.upper()
print('rollback guard checks OK')
