"""Real normal CLI/HTTP, native Windows claims and $5 budget; fake effects only."""
import copy
import json
import socket
import sqlite3
import threading
import time
import traceback
from contextlib import contextmanager
from decimal import Decimal
from secrets import token_hex

import pytest

from backend.adapters.inbound.cli import local_browser as cli
from backend.adapters.outbound.generation.openai.p0_normal_policy import sha
from backend.infrastructure.composition.factories import local_browser as factory
from backend.infrastructure.composition.factories import p0_manual_tests as manual_factory
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_saved_application,
)
from tests import normal_on_323a_fixture as f
from tests.test_normal_on_323a import call, terminal, text


class Control(f.Control):
    def build(self, *, secret, timeout_seconds):
        assert secret.reveal_for_transport() == f.FAKE_KEY
        assert timeout_seconds == 300.0
        self.builds += 1
        return self


def configuration(root):
    root.mkdir(parents=True, exist_ok=True)
    db = root / 'SYNTHETIC-runtime.sqlite'
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE resource(id TEXT PRIMARY KEY, resource_type TEXT, canonical_title TEXT, identity_status TEXT)')
    target = Read15RuntimeTarget(db, root, sha(db.read_bytes()))
    saved, receipts = root / 'saved', root / 'manual-receipts'
    build_saved_application(saved, create=True, word_profile='product-v7')
    receipts.mkdir()
    return target, saved, receipts


@contextmanager
def running(root, monkeypatch, control, *, existing=None, enabled=True, extra_args=(), setup=None):
    f.install_boundaries(monkeypatch, control)
    if setup is not None:
        setup(monkeypatch)
    monkeypatch.setenv('OPENAI_API_KEY', f.FAKE_KEY)
    monkeypatch.setattr(manual_factory, 'OpenAISDKResponsesTransportFactory', lambda **_: control)
    target, saved, receipts = existing or configuration(root)
    original_bind = manual_factory.ManualTestComposition.bind
    original_build = factory.build_local_read15
    errors = []

    def bind(owner, service, endpoint):
        original_bind(owner, service, endpoint)
        control.owner = owner

    def build(*args, **kwargs):
        try:
            built = original_build(*args, **kwargs)
        except Exception:
            errors.append(traceback.format_exc())
            raise
        control.server = built
        return built

    monkeypatch.setattr(manual_factory.ManualTestComposition, 'bind', bind)
    monkeypatch.setattr(cli, 'build_local_read15', build)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    args = ['--port', str(port), '--runtime', str(target.runtime_path), '--data-root', str(target.data_root),
        '--runtime-sha256', target.expected_sha256, '--saved-root', str(saved), '--word-profile', 'product-v7',
        '--observability-root', str(root / 'SYNTHETIC-observability')]
    if enabled:
        args += ['--manual-provider-tests', '--manual-test-receipts', str(receipts)]
    args += list(extra_args)
    thread = threading.Thread(target=lambda: errors.append(cli.main(args)), daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while control.server is None and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.02)
    assert control.server is not None, errors
    assert control.server.server._running.wait(5)
    try:
        yield port, (target, saved, receipts)
    finally:
        control.release.set()
        control.server.close()
        thread.join(10)
        assert not thread.is_alive()
        assert control.prompt_calls == 0


def prepare(port):
    status, metadata = call(port, 'GET', '/api/v2/p0')
    assert status == 200
    nonce = metadata['data']['transport_nonce']
    status, result = call(port, 'POST', '/api/v2/p0/prepare', {'command_id':token_hex(16),
        'context':f.context(), 'reference':{'notion_id':'notion:shared', 'passage_ref':f.SOURCE['passage_ref']}}, nonce)
    assert status == 200, result
    prepared = result['data']
    return nonce, {'command_id':token_hex(16), 'preparation_ref':prepared['preparation_ref'],
        'preparation_sha256':prepared['preparation_sha256']}


def test_two_manual_calls_save_reopen_and_both_docx_across_restart(tmp_path, monkeypatch):
    control = Control()
    with running(tmp_path / 'case', monkeypatch, control) as (port, config):
        metadata = call(port, 'GET', '/api/v2/p0')[1]['data']
        assert metadata['manual_test_session']['budget_usd'] == '5.00'
        assert control.calls == control.prompt_calls == 0
        results = []
        for _ in range(2):
            nonce, payload = prepare(port)
            status, started = call(port, 'POST', '/api/v2/p0/generate', payload, nonce)
            assert status == 202, started
            result = terminal(port, payload['command_id'])
            assert result['state'] == 'LOCAL_COMMAND_COMPLETED', result
            assert result['result']['publication']['state'] == 'APPLICATION_SAVED'
            results.append((payload, result['result']))
        assert control.calls == 2
        before = call(port, 'GET', '/api/v2/p0')[1]['data']['manual_test_session']
        assert Decimal(before['reserved_usd']) > 0
        downloaded = []
        for _, result in results:
            view = result['view']
            base = '/api/v2/productions/' + view['production_ref'] + '/versions/' + view['version_ref']
            assert call(port, 'GET', base + '/saved')[0] == 200
            for kind in ('student', 'correction'):
                status, raw = f.request(port, 'GET', base + '/word/' + kind)
                assert status == 200
                assert ('SENTINELLE_PROFESSEUR' in text(raw)) == (kind == 'correction')
                downloaded.append((base, kind, sha(raw)))
        old_payload = copy.deepcopy(results[0][0])
        for _ in range(2):
            assert call(port, 'POST', '/api/v2/p0/generate', old_payload, nonce)[0] == 202
        assert control.calls == 2
    again = Control()
    with running(tmp_path / 'case', monkeypatch, again, existing=config) as (port, _):
        metadata = call(port, 'GET', '/api/v2/p0')[1]['data']
        assert metadata['manual_test_session']['reserved_usd'] == before['reserved_usd']
        assert call(port, 'GET', '/api/v2/p0/commands/' + old_payload['command_id'])[1]['data']['phase'] == 'APPLICATION_SAVED'
        assert call(port, 'POST', '/api/v2/p0/generate', old_payload, metadata['transport_nonce'])[0] == 202
        for base, kind, pin in downloaded:
            assert sha(f.request(port, 'GET', base + '/word/' + kind)[1]) == pin
        assert again.calls == again.builds == 0


def test_slow_operation_followup_double_click_conflict_and_concurrency(tmp_path, monkeypatch):
    control = Control()
    control.release.clear()
    with running(tmp_path / 'case', monkeypatch, control) as (port, _):
        nonce, payload = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        assert control.entered.wait(10)
        assert call(port, 'GET', '/api/v2/p0/commands/' + payload['command_id'])[1]['data']['state'] == 'LOCAL_COMMAND_RUNNING'
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        assert call(port, 'POST', '/api/v2/p0/generate', dict(payload, preparation_sha256='f'*64), nonce)[0] == 409
        _, other = prepare(port)
        rejected = call(port, 'POST', '/api/v2/p0/generate', other, nonce)
        assert rejected[0] == 409 and 'OPERATION_RUNNING' in rejected[1]['error']['code']
        assert control.calls == 1
        control.release.set()
        assert terminal(port, payload['command_id'])['state'] == 'LOCAL_COMMAND_COMPLETED'


def test_budget_stops_before_transport_and_remains_after_restart(tmp_path, monkeypatch):
    control = Control()
    with running(tmp_path / 'case', monkeypatch, control) as (port, config):
        control.owner.generation.max_output_tokens = 128000
        for _ in range(3):
            nonce, payload = prepare(port)
            assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
            assert terminal(port, payload['command_id'])['state'] == 'LOCAL_COMMAND_COMPLETED'
        nonce, payload = prepare(port)
        result = call(port, 'POST', '/api/v2/p0/generate', payload, nonce)
        assert result[0] == 409 and result[1]['error']['code'] == 'P0_MANUAL_TEST_SESSION_BUDGET_EXHAUSTED'
        assert control.calls == 3
        reserved = call(port, 'GET', '/api/v2/p0')[1]['data']['manual_test_session']['reserved_usd']
        assert Decimal(reserved) <= 5
    with running(tmp_path / 'case', monkeypatch, Control(), existing=config) as (port, _):
        assert call(port, 'GET', '/api/v2/p0')[1]['data']['manual_test_session']['reserved_usd'] == reserved


@pytest.mark.parametrize('scenario', ['401', 'truncated', 'network'])
def test_uncertainty_capture_and_restart_never_replay(tmp_path, monkeypatch, scenario):
    control = Control(scenario)
    with running(tmp_path / 'case', monkeypatch, control) as (port, config):
        nonce, payload = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        result = terminal(port, payload['command_id'])
        assert result['state'] == 'LOCAL_COMMAND_UNCERTAIN', result
        assert control.calls == 1
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        before = call(port, 'GET', '/api/v2/p0')[1]['data']['manual_test_session']['reserved_usd']
        assert Decimal(before) > 0
    again = Control()
    with running(tmp_path / 'case', monkeypatch, again, existing=config) as (port, _):
        state = call(port, 'GET', '/api/v2/p0/commands/' + payload['command_id'])[1]['data']
        assert state['state'] == 'LOCAL_COMMAND_UNCERTAIN'
        nonce = call(port, 'GET', '/api/v2/p0')[1]['data']['transport_nonce']
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        assert again.calls == again.builds == 0


def test_stop_session_and_default_off_have_no_effect(tmp_path, monkeypatch):
    control = Control()
    with running(tmp_path / 'off', monkeypatch, control, enabled=False) as (port, _):
        nonce, payload = prepare(port)
        result = call(port, 'POST', '/api/v2/p0/generate', payload, nonce)
        assert result[0] == 200 and result[1]['data']['state'] == 'AUTHORIZATION_REQUIRED'
        assert control.calls == 0
    with running(tmp_path / 'on', monkeypatch, Control()) as (port, _):
        nonce, payload = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/manual-stop', {}, nonce)[0] == 200
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[1]['error']['code'] == 'P0_MANUAL_TEST_SESSION_STOPPED'


def test_missing_key_and_exclusive_selection_refuse_before_start(tmp_path, monkeypatch):
    target, saved, receipts = configuration(tmp_path / 'case')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    args = ['--port','12345','--runtime',str(target.runtime_path),'--data-root',str(target.data_root),
        '--runtime-sha256',target.expected_sha256,'--saved-root',str(saved),'--word-profile','product-v7',
        '--manual-provider-tests','--manual-test-receipts',str(receipts)]
    assert cli.main(args) == 1
    assert not list(receipts.iterdir())
    assert cli.main([*args, '--p0-normal-profile', str(tmp_path / 'unadopted.json')]) == 1


def test_forbidden_source_cannot_be_armed(tmp_path, monkeypatch):
    control = Control()
    with running(tmp_path / 'case', monkeypatch, control) as (port, _):
        nonce, payload = prepare(port)
        # The real factory's Application prepared reader rejects a substituted SHA.
        result = call(port, 'POST', '/api/v2/p0/generate', dict(payload, preparation_sha256='0'*64), nonce)
        assert result[0] == 409 and control.calls == 0


def test_error_diagnostics_never_include_sdk_message_or_key():
    from backend.adapters.outbound.openai.contracts import (
        OpenAITransportError,
        OpenAITransportErrorCode,
    )

    error = OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST, diagnostic={
        'http_status':400, 'request_id':'req_synthetic', 'param':'text.format.schema',
        'code':'invalid_json_schema', 'message':'sk-proj-SYNTHETIC_SECRET_MUST_NOT_LEAK'})
    assert 'message' not in error.diagnostic
    assert 'sk-proj-' not in json.dumps(error.diagnostic)


def test_explicit_stop_survives_restart(tmp_path, monkeypatch):
    with running(tmp_path / 'case', monkeypatch, Control()) as (port, config):
        nonce, _ = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/manual-stop', {}, nonce)[0] == 200
    control = Control()
    with running(tmp_path / 'case', monkeypatch, control, existing=config) as (port, _):
        assert call(port, 'GET', '/api/v2/p0')[1]['data']['manual_test_session']['enabled'] is False
        nonce, payload = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 409
        assert control.calls == control.builds == 0


def test_foreign_receipt_root_refused_without_writes(tmp_path):
    from backend.adapters.outbound.generation.openai.p0_manual_tests import ManualTestBudget

    root = tmp_path / 'foreign-history'
    root.mkdir()
    history = root / 'historical.DISPATCH.json'
    history.write_bytes(b'SYNTHETIC historical bytes unchanged')
    before = {p.name:p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError, match='DEDICATED_ROOT_REQUIRED'):
        ManualTestBudget(root)
    assert {p.name:p.read_bytes() for p in root.iterdir()} == before


def test_other_process_stop_blocks_an_already_loaded_session(tmp_path, monkeypatch):
    from backend.adapters.outbound.generation.openai.p0_manual_tests import ManualTestBudget

    control = Control()
    with running(tmp_path / 'case', monkeypatch, control) as (port, config):
        nonce, payload = prepare(port)
        other_process_session = ManualTestBudget(config[2])
        other_process_session.stop()
        response = call(port, 'POST', '/api/v2/p0/generate', payload, nonce)
        assert response[0] == 409
        assert response[1]['error']['code'] == 'P0_MANUAL_TEST_SESSION_STOPPED'
        assert control.calls == control.builds == 0
        assert control.owner.generation.budget.reserved() == 0
        assert not list(config[2].glob('*.RESERVED.json'))


def test_rich_course_uses_same_application_save_and_native_word(tmp_path, monkeypatch):
    from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
    from backend.adapters.outbound.openai.contracts import (
        OpenAIResponsesResponse,
        OpenAIResponseStatus,
        OpenAIResponseUsage,
    )
    from tests.support.progressive_course_fixture import progressive_course_fixture
    from tests.unit.test_p0_rich_course_content import rich_content

    class CourseControl(Control):
        def create(self, *, request):
            self.calls += 1
            assert request.max_output_tokens == 32768
            payload = json.loads(request.input_json)
            assert payload['context']['resource_type'] == 'COURSE'
            return OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED,
                canonical(progressive_course_fixture(rich_content(self.dispatch))).decode(),
                OpenAIResponseUsage(1000,0,2000,3000))

    control = CourseControl()
    with running(tmp_path / 'course', monkeypatch, control) as (port, _):
        nonce = call(port, 'GET', '/api/v2/p0')[1]['data']['transport_nonce']
        selected = f.context()
        selected.update(resource_type='COURSE', contract_id='P0-CONTEXT-COURSE-3.0', course_format='CHAPTER')
        selected['local_progression']['chapter'] = '1'
        status, shown = call(port, 'POST', '/api/v2/p0/prepare', {'command_id':token_hex(16),
            'context':selected, 'reference':{'notion_id':'notion:shared', 'passage_ref':f.SOURCE['passage_ref']}}, nonce)
        assert status == 200, shown
        preparation = shown['data']
        # Test observation of the real immutable Application preparation only.
        control.dispatch = control.owner.commands.prepared(preparation['preparation_ref'], preparation['preparation_sha256'])
        command = {'command_id':token_hex(16), 'preparation_ref':preparation['preparation_ref'],
            'preparation_sha256':preparation['preparation_sha256']}
        assert call(port, 'POST', '/api/v2/p0/generate', command, nonce)[0] == 202
        done = terminal(port, command['command_id'])
        assert done['state'] == 'LOCAL_COMMAND_COMPLETED', done
        view = done['result']['view']
        base = '/api/v2/productions/' + view['production_ref'] + '/versions/' + view['version_ref']
        for kind in ('student','correction'):
            status, raw = f.request(port, 'GET', base + '/word/' + kind)
            assert status == 200
            assert ('SENTINELLE_PROFESSEUR' in text(raw)) == (kind == 'correction')
            from io import BytesIO
            from zipfile import ZipFile
            with ZipFile(BytesIO(raw)) as archive:
                import xml.etree.ElementTree as ET
                document = ET.fromstring(archive.read('word/document.xml'))
                assert document.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl')
        assert control.calls == 1


def test_native_budget_lock_excludes_another_process(tmp_path):
    import subprocess
    import sys

    from backend.adapters.outbound.generation.openai.p0_manual_tests import (
        ManualTestBudget,
        ManualTestLease,
    )
    root = tmp_path / 'native-session'
    root.mkdir()
    ManualTestBudget(root)
    script = "from pathlib import Path; from backend.adapters.outbound.generation.openai.p0_manual_tests import ManualTestLease; lock=ManualTestLease(Path(__import__('sys').argv[1])); lock.close(); print('ACQUIRED')"
    lease = ManualTestLease(root)
    try:
        blocked = subprocess.run([sys.executable,'-B','-c',script,str(root)],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0 and 'P0_MANUAL_TEST_OPERATION_RUNNING' in blocked.stderr
    finally:
        lease.close()
    available = subprocess.run([sys.executable,'-B','-c',script,str(root)],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert available.returncode == 0 and available.stdout.strip() == 'ACQUIRED'


def test_application_preserves_closed_transport_diagnostic(tmp_path, monkeypatch):
    from backend.adapters.outbound.openai.contracts import (
        OpenAITransportError,
        OpenAITransportErrorCode,
    )

    class InvalidControl(Control):
        def create(self, *, request):
            self.calls += 1
            raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST, diagnostic={
                'http_status':400, 'request_id':'req_synthetic', 'param':'text.format.schema',
                'code':'invalid_json_schema', 'message':'SYNTHETIC_SECRET_EXCLUDED'})

    control = InvalidControl()
    with running(tmp_path / 'case', monkeypatch, control) as (port, config):
        nonce, payload = prepare(port)
        assert call(port, 'POST', '/api/v2/p0/generate', payload, nonce)[0] == 202
        result = terminal(port, payload['command_id'])
        assert result['state'] == 'LOCAL_COMMAND_UNCERTAIN'
        assert result['code'] == 'INVALID_REQUEST'
        assert result['provider_diagnostic'] == {'http_status':400, 'request_id':'req_synthetic',
            'param':'text.format.schema', 'code':'invalid_json_schema'}
        assert control.calls == 1
    with running(tmp_path / 'case', monkeypatch, Control(), existing=config) as (port, _):
        retained = call(port, 'GET', '/api/v2/p0/commands/' + payload['command_id'])[1]['data']
        assert retained['provider_diagnostic'] == result['provider_diagnostic']


def test_manual_generate_keeps_host_origin_nonce_and_intent_guards(tmp_path, monkeypatch):
    import http.client

    control = Control()
    with running(tmp_path / 'case', monkeypatch, control) as (port, _):
        nonce, payload = prepare(port)
        good = {'Host':f'127.0.0.1:{port}', 'Origin':f'http://127.0.0.1:{port}',
            'Content-Type':'application/json; charset=utf-8', 'X-Local-Intent':'conversation-v1',
            'X-R2-Nonce':nonce}
        for key, value, code in (('Host','example.invalid','HOST_REJECTED'),
                ('Origin','http://example.invalid','ORIGIN_REJECTED'),
                ('X-R2-Nonce','0'*64,'LOCAL_INTENT_REJECTED'),
                ('X-Local-Intent','','LOCAL_INTENT_REJECTED')):
            headers = dict(good, **{key:value})
            connection = http.client.HTTPConnection('127.0.0.1',port,timeout=20)
            connection.request('POST','/api/v2/p0/generate',json.dumps(payload),headers)
            response = connection.getresponse()
            body = json.loads(response.read())
            connection.close()
            assert response.status == 403 and body['error']['code'] == code, body
        assert control.calls == control.builds == 0
        assert not list(control.owner.generation.root.glob('*.RESERVED.json'))
