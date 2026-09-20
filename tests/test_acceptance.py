"""Contract tests for the normal-navigation acceptance runner, no browser mocks."""
import json
from pathlib import Path
import pytest
from frameport.engine.compiler import jsx_attrs
from scripts.check_acceptance import load_fixture

@pytest.mark.parametrize('attribute', ['rows', 'cols'])
def test_textarea_dimensions_are_numbers(attribute):
    assert jsx_attrs({attribute: '3'}) == f' {attribute}={{3}}'

def fixture(tmp_path, **changes):
    ident = 'a' * 32
    job = {'id': ident, 'status': 'completed', 'request': {'demo': True}, 'report': {}}
    job.update(changes)
    result = tmp_path / 'result.json'
    result.write_text(json.dumps(job))
    root = tmp_path / 'data' / 'jobs' / ident
    for relative in ('COMPLETE', 'model.json', 'react/dist/index.html'):
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('{}')
    return result, tmp_path / 'data', root

def test_acceptance_requires_completed_authored_fixture(tmp_path):
    result, data, root = fixture(tmp_path)
    job, loaded = load_fixture(result, data)
    assert loaded == root and job['request']['demo']

@pytest.mark.parametrize('change', [{'status': 'failed'}, {'request': {'demo': False}}, {'id': '../escape'}, {'report': {'execution': {'mode': 'offline-document-harness'}}}])
def test_acceptance_rejects_invalid_or_offline_reference(tmp_path, change):
    result, data, _ = fixture(tmp_path, **change)
    with pytest.raises(ValueError):
        load_fixture(result, data)

@pytest.mark.parametrize('relative', ['COMPLETE', 'model.json', 'react/dist/index.html'])
def test_acceptance_requires_actual_built_output(tmp_path, relative):
    result, data, root = fixture(tmp_path)
    (root / relative).unlink()
    with pytest.raises(ValueError, match='Missing'):
        load_fixture(result, data)
