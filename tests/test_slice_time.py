"""Consumption-time expiry without mutating approved source snapshots."""
import copy
import json

import pytest

from ai_context_linker import cli
from ai_context_linker.core import ManifestError, facts_sha256, validate_manifest
from ai_context_linker.slicing import build_question_context, render_question_context
from ai_context_linker.state_records import make_state_record


def timed_manifest():
    records = [make_state_record(
        project_id='today', kind=kind, text=text, source_kind='approved-review',
        source_ref=f'today:approved-review:{kind}', observed_at='2026-08-28T09:00:00+08:00',
        status='open', expires_at='2026-08-29T12:00:00+08:00',
    ) for kind, text in [('attention', 'today'), ('activity', 'active'),
        ('why-now', 'The approved acceptance window closes soon.'),
        ('next-action', 'Run the priority fixture.')]]
    result = validate_manifest({
        'schema_version': '0.2', 'generated_at': '2026-08-28T12:00:00+08:00',
        'workspace': {'name': 'Time fixture', 'summary': 'Synthetic workspace.',
                      'current_focus': 'Check expiry.', 'decisions': [], 'unknowns': []},
        'projects': [{'id': 'today', 'name': 'Today', 'summary': 'Synthetic project.',
            'status': 'unknown', 'signals': [], 'constraints': [], 'risks': [],
            'open_questions': [], 'state_items': records, 'evidence': ['today:file:README.md']}],
        'relationships': [], 'skills': [],
    })
    result['facts_sha256'] = facts_sha256(result)
    return result


def test_expiry_boundary_replay_and_source_immutability():
    source = timed_manifest()
    before = copy.deepcopy(source)
    question = '今天推进什么？'
    replay = render_question_context(source, question)
    current = render_question_context(source, question, as_of='2026-08-29T11:59:59+08:00')
    expired = render_question_context(source, question, as_of='2026-08-29T12:00:00+08:00')
    assert 'Run the priority fixture.' in replay and 'Run the priority fixture.' in current
    assert 'Run the priority fixture.' not in expired
    assert 'The approved acceptance window closes soon.' not in expired
    assert source['generated_at'] in expired and '2026-08-29T12:00:00+08:00' in expired
    assert source['facts_sha256'] in expired
    assert '按快照时间回放' in replay
    assert source == before
    assert expired == render_question_context(source, question, as_of='2026-08-29T12:00:00+08:00')


@pytest.mark.parametrize('as_of', ['bad-time', '2026-08-29T12:00:00', '2026-08-27T00:00:00+00:00'])
def test_invalid_times_rejected_before_output(tmp_path, as_of):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(timed_manifest()), encoding='utf-8')
    with pytest.raises(ManifestError):
        build_question_context(path, '今天推进什么？', tmp_path / 'result', as_of=as_of)
    assert not (tmp_path / 'result').exists()


def test_resolved_action_is_not_reopened():
    source = timed_manifest()
    project = next(p for p in source['projects'] if p['id'] == 'today')
    for record in project['state_items']:
        if record['kind'] == 'next-action':
            record['status'] = 'resolved'
    text = render_question_context(source, '今天推进什么？', as_of='2026-08-29T11:00:00+08:00')
    assert 'Run the priority fixture.' not in text


def test_slice_cli_writes_reproducible_time_checked_candidate(tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(timed_manifest()), encoding='utf-8')
    before = path.read_bytes()
    arguments = ['slice', '--manifest', str(path), '--question', '今天推进什么？',
                 '--output-dir', str(tmp_path / 'result'), '--as-of', '2026-08-29T12:00:00+08:00']
    assert cli.main(arguments) == 0
    result = tmp_path / 'result/ai_context_linker.question.md'
    first = result.read_bytes()
    assert b'Run the priority fixture.' not in first
    assert cli.main(arguments) == 0
    assert result.read_bytes() == first and path.read_bytes() == before


def test_legacy_manifest_cannot_claim_lifecycle_recheck():
    source = timed_manifest()
    source['schema_version'] = '0.1'
    with pytest.raises(ManifestError, match='v0.2'):
        render_question_context(source, 'today', as_of='2026-08-29T12:00:00+08:00')
