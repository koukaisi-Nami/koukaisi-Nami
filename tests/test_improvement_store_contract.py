from improvement_store import DDL


def test_improvement_table_is_durable_and_tracks_pr_state():
    sql=DDL.lower()
    assert 'nami_improvements' in sql
    assert 'instruction' in sql
    assert 'state' in sql
    assert 'pr_number' in sql
    assert 'deploy_sha' in sql
