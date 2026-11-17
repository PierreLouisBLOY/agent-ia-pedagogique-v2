"""Manual tests: persistent $5 session budget, no per-call quota or P1 renewal.

Canonical P0/AG03 content, institutional guards and append-only claims remain.
The dedicated session root never reads or resets a historical campaign.
"""
from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_agents import (
    agent_preparation,
    guard_and_bind,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    pinned_receipt_root,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponsesTransportFactory,
    OpenAITransportError,
)
from backend.adapters.outbound.openai.parameters import response_parameters
from backend.agent_runtime.agents.generation.generation_agent import GeneratorAgent
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortRequest,
    GenerationPortResult,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
)
from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
    RealCourseThread,
    thread_from_context,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data

BUDGET = Decimal('5.00')
_SESSION_NAMESPACE = sha(b'P0-MANUAL-TEST-SESSION-5USD-1.0')


class ManualTestLease:
    """Nonblocking process lock, solely in the new test root."""

    def __init__(self, root: Path) -> None:
        import msvcrt

        self.fd = -1
        with pinned_receipt_root(root):
            path = root / 'manual-test-session.LOCK'
            if not capture_secure_path(path, allowed_root=root).exists:
                temporary = private_temporary_file(root, allowed_root=root, prefix='manual-lock-', suffix='.tmp')
                with temporary.open('wb') as stream:
                    stream.write(b'\x00')
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    atomic_publish_fresh(temporary, path, allowed_root=root)
                except Exception:
                    if not capture_secure_path(path, allowed_root=root).exists:
                        raise
            before = capture_secure_path(path, allowed_root=root)
            fd = os.open(path, os.O_RDWR | os.O_BINARY)
            try:
                opened = os.fstat(fd)
                if (opened.st_dev, opened.st_ino) != (before.device, before.inode):
                    raise ValueError('P0_MANUAL_TEST_LOCK_CHANGED')
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except Exception:
                os.close(fd)
                raise ValueError('P0_MANUAL_TEST_OPERATION_RUNNING') from None
            self.fd = fd

    def close(self) -> None:
        import msvcrt

        if self.fd >= 0:
            try:
                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(self.fd)
                self.fd = -1


class ManualTestBudget:
    """An explicit owner-selected $5 budget, retained across restarts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        session = P0NormalReceipt(root, _SESSION_NAMESPACE)
        if not session.exists('DISPATCH') and any(root.iterdir()):
            raise ValueError('P0_MANUAL_TEST_DEDICATED_ROOT_REQUIRED')
        lease = ManualTestLease(root)
        try:
            if not session.exists('DISPATCH'):
                session.publish('DISPATCH', {'schema':'P0-MANUAL-TEST-SESSION-1.0', 'budget_usd':'5.00',
                    'model':'gpt-5.6-terra', 'input_usd_per_million':'2.00', 'input_multiplier':'1.25',
                    'output_usd_per_million':'12.00', 'opened_at_utc':datetime.now(UTC).isoformat()})
            policy = session.read('DISPATCH')
            expected = {'schema':'P0-MANUAL-TEST-SESSION-1.0', 'budget_usd':'5.00', 'model':'gpt-5.6-terra',
                'input_usd_per_million':'2.00', 'input_multiplier':'1.25', 'output_usd_per_million':'12.00'}
            if set(policy) != set(expected) | {'opened_at_utc'} or any(policy[k] != v for k,v in expected.items()):
                raise ValueError('P0_MANUAL_TEST_SESSION_POLICY_CHANGED')
            self.policy_sha256 = sha(canonical(policy))
            self.stopped = session.exists('CONSUMED')
            if self.stopped and session.read('CONSUMED').get('schema') != 'P0-MANUAL-TEST-STOPPED-1.0':
                raise ValueError('P0_MANUAL_TEST_STOP_CHANGED')
        finally:
            lease.close()

    def stop(self) -> None:
        session = P0NormalReceipt(self.root, _SESSION_NAMESPACE)
        if not session.exists('CONSUMED'):
            session.publish('CONSUMED', {'schema':'P0-MANUAL-TEST-STOPPED-1.0',
                'session_sha256':self.policy_sha256, 'stopped_at_utc':datetime.now(UTC).isoformat()})
        self.stopped = True

    def require_active(self) -> None:
        # A different process may have stopped the same persistent session.
        session = P0NormalReceipt(self.root, _SESSION_NAMESPACE)
        if session.exists('CONSUMED'):
            self.stopped = True
        if self.stopped:
            raise ValueError('P0_MANUAL_TEST_SESSION_STOPPED')

    @staticmethod
    def bound(wire: OpenAIResponsesRequest) -> Decimal:
        upper = len(canonical(response_parameters(wire))) + 10000
        if upper > 272000:
            raise ValueError('P0_MANUAL_TEST_LONG_CONTEXT_REFUSED')
        return (Decimal(upper) * Decimal('2.50') + Decimal(wire.max_output_tokens) * Decimal('12')) / Decimal(1000000)

    def reserved(self) -> Decimal:
        total = Decimal(0)
        for path in self.root.glob('*.RESERVED.json'):
            if re.fullmatch('[0-9a-f]{64}\\.RESERVED\\.json', path.name) is None:
                raise ValueError('P0_MANUAL_TEST_CLAIM_NAME')
            receipt = P0NormalReceipt(self.root, path.name.split('.')[0])
            data = receipt.read('RESERVED')
            if data.get('schema') != 'P0-MANUAL-TEST-CLAIM-1.0' or data.get('session_sha256') != self.policy_sha256:
                raise ValueError('P0_MANUAL_TEST_SESSION_CLAIM_CHANGED')
            body_bytes, output_tokens = data.get('request_bytes'), data.get('max_output_tokens')
            if (type(body_bytes) is not int or not 1 <= body_bytes <= 262000
                    or type(output_tokens) is not int or not 4096 <= output_tokens <= 128000
                    or re.fullmatch('[0-9a-f]{64}', str(data.get('request_sha256'))) is None):
                raise ValueError('P0_MANUAL_TEST_CLAIM_BINDING')
            amount = Decimal(str(data.get('reserved_usd')))
            expected = (Decimal(body_bytes + 10000) * Decimal('2.50') + Decimal(output_tokens) * 12) / 1000000
            if amount != expected:
                raise ValueError('P0_MANUAL_TEST_CLAIM_BOUND_CHANGED')
            if not amount.is_finite() or amount <= 0:
                raise ValueError('P0_MANUAL_TEST_BUDGET_RECORD')
            total += amount
        if total > BUDGET:
            raise ValueError('P0_MANUAL_TEST_BUDGET_RECORD')
        return total

    def snapshot(self) -> dict[str, object]:
        reserved = self.reserved()
        return {'budget_usd':'5.00', 'reserved_usd':str(reserved), 'remaining_usd':str(BUDGET-reserved),
            'observed_at_utc':datetime.now(UTC).isoformat(), 'actual_billed_cost':'UNKNOWN', 'automatic_refund':False}


class ManualTestGeneration:
    def __init__(self, *, root: Path, resolver: ProviderSecretResolver,
                 credential_ref: ProviderCredentialRef, transport: OpenAIResponsesTransportFactory,
                 max_output_tokens: int = 32768) -> None:
        if type(max_output_tokens) is not int or not 4096 <= max_output_tokens <= 128000:
            raise ValueError('P0_MANUAL_TEST_OUTPUT_LIMIT')
        self.root, self.resolver, self.ref, self.transport = root, resolver, credential_ref, transport
        self.budget = ManualTestBudget(root)
        self.max_output_tokens = max_output_tokens
        self.active = not self.budget.stopped
        self.course_thread_reader: Callable[[Mapping[str, object]], Mapping[str, object]] | None = None
        self.progress: Callable[[str, Mapping[str, object]], None] = lambda _p, _e: None
        self.armed: tuple[str, P0NormalReceipt, OpenAIResponsesTransport] | None = None
        self.controls: dict[str, dict[str, object]] = {}

    def wire(self, request: Mapping[str, object]) -> OpenAIResponsesRequest:
        context = cast(Mapping[str, object], request['context'])
        resolution = cast(Mapping[str, object], context.get('institutional_resolution', {}))
        scope = cast(Mapping[str, object], resolution.get('reference_scope', {}))
        if resolution.get('status') != 'RESOLVED_ADMITTED' or scope.get('status') != 'CANONICAL_NOTION_ONLY':
            raise ValueError('P0_MANUAL_TEST_CANONICAL_SOURCE_REQUIRED')
        refs = cast(list[Mapping[str, object]], request['references'])
        thread = thread_from_context(context)
        expected = [] if thread is None else thread.references()
        if (len(refs) != 1 + len(expected) or as_plain(refs[1:]) != expected
                or refs[0].get('source_ref') != scope.get('object_ref')
                or refs[0].get('locator') != scope.get('passage_ref')):
            raise ValueError('P0_MANUAL_TEST_SOURCE_CHANGED')
        if thread is not None:
            if self.course_thread_reader is None:
                raise ValueError('P0_REAL_ORGANIZATION_REVALIDATOR_REQUIRED')
            current = RealCourseThread(self.course_thread_reader({
                'organization_id':thread.organization_id, 'dossier_sha256':thread.sha256}))
            if current.sha256 != thread.sha256:
                raise ValueError('P0_REAL_ORGANIZATION_CHANGED')
            evidence = object_data(request['evidence'])
            if any(evidence.get(key) != value for key,value in current.evidence().items()):
                raise ValueError('P0_REAL_ORGANIZATION_CHANGED')
        return replace(build_p0_content_request(request, max_input_bytes=65536, progressive_chapters=True), max_output_tokens=self.max_output_tokens)

    def prepare_transport(self, request: Mapping[str, object]) -> OpenAIResponsesTransport:
        if not self.active:
            raise ValueError('P0_MANUAL_TEST_SESSION_STOPPED')
        self.budget.require_active()
        self.wire(request)
        # Resolve and construct outside the operation LOCK, before claiming.
        secret = self.resolver.resolve(self.ref)
        return self.transport.build(secret=secret, timeout_seconds=300.0)

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        if not self.active or self.armed is None or self.armed[0] != sha(canonical(as_plain(request))):
            raise ValueError('P0_MANUAL_TEST_EXPLICIT_COMMAND_REQUIRED')
        self.wire(request)
        return True

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        self.authorize(request=request)
        assert self.armed is not None
        _, receipt, transport = self.armed
        self.armed = None
        now, wire, owner = datetime.now(UTC), self.wire(request), self

        class Port:
            def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
                if request != GenerationCoordinator(self).prepare(request=preparation).port_request:
                    raise ValueError('P0_MANUAL_TEST_CANONICAL_BINDING')
                if not owner.active:
                    raise ValueError('P0_MANUAL_TEST_SESSION_STOPPED')
                if sha(canonical(response_parameters(wire))) != receipt.read('DISPATCH').get('request_sha256'):
                    raise ValueError('P0_MANUAL_TEST_DISPATCH_CHANGED')
                receipt.publish('PROVIDER_ATTEMPTED', {'schema':'P0-MANUAL-TEST-ATTEMPT-1.0', 'request_sha256':sha(canonical(response_parameters(wire))), 'retry':0})
                owner.progress('TRANSPORT_ENTERED', {'provider_attempts':1})
                try:
                    response = transport.create(request=wire)
                except OpenAITransportError as error:
                    # Preserve closed SDK metadata before Application wraps the exception.
                    receipt.publish('UNKNOWN', {'schema':'P0-MANUAL-TEST-UNKNOWN-1.0',
                        'code':error.code.value, 'provider_diagnostic':dict(error.diagnostic),
                        'retry':0, 'actual_billed_cost':'UNKNOWN'})
                    raise
                receipt.publish('RESULT', {'schema':'P0-MANUAL-TEST-CAPTURE-1.0', 'response_status':response.status.value,
                    'output_text':response.output_text, 'usage':asdict(response.usage), 'actual_billed_cost':'UNKNOWN'})
                owner.progress('RESPONSE_CAPTURED', {'response_status':response.status.value, 'provider_attempts':1})
                if response.status is not OpenAIResponseStatus.COMPLETED or response.output_text is None:
                    raise ValueError('P0_MANUAL_TEST_RESPONSE_INCOMPLETE')
                result = NormalP0GenerationAdapter.technical_result(dispatch, response.output_text)
                if object_data(dispatch["context"]).get("course_format") == "CHAPTER":
                    chapter = object_data(result.structured_payload.get("course_chapter"))
                    if not isinstance(chapter.get("transfer"), (tuple, list)):
                        raise ValueError("COURSE_PROGRESSIVE_ACTIVITIES_REQUIRED")
                return result

        dispatch = request
        preparation = agent_preparation(request, now)
        coordinator = GenerationCoordinator(Port())
        _, result = GeneratorAgent(coordinator).generate_production(request=preparation)

        def observe(value: Mapping[str, object]) -> None:
            self.controls[str(request['version_ref'])] = cast(dict[str, object], as_plain(value))

        output = guard_and_bind(request, coordinator, preparation, result, observer=observe)
        receipt.publish('PARSED', {'schema':'P0-MANUAL-TEST-PARSED-1.0', 'version_ref':request['version_ref']})
        return output

    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]:
        value = self.controls.get(str(request['version_ref']))
        if value is None or value['bundle_sha256'] != bundle_sha256 or value['context_sha256'] != request['context_sha256']:
            raise ValueError('P0_MANUAL_TEST_CONTROLS_BINDING')
        return cast(dict[str, object], as_plain(value))


class ManualTestCommands:
    """Multiple explicit commands; budget and idempotence persist across restarts."""

    def __init__(self, *, generation: ManualTestGeneration,
                 prepared: Callable[[str, str], Mapping[str, object]],
                 execute: Callable[[str, Mapping[str, object]], dict[str, object]]) -> None:
        self.generation, self.prepared, self.execute = generation, prepared, execute
        self.mutex = threading.Lock()
        self.views: dict[str, dict[str, object]] = {}
        self.payloads: dict[str, dict[str, object]] = {}

    def receipt(self, command: str) -> P0NormalReceipt:
        if re.fullmatch('[0-9a-f]{32}', command) is None:
            raise ValueError('P0_COMMAND_ID')
        return P0NormalReceipt(self.generation.root, sha(canonical({'mode':'MANUAL_TESTS', 'command_id':command})))

    def start(self, payload: Mapping[str, object]) -> dict[str, object]:
        if set(payload) != {'command_id','preparation_ref','preparation_sha256'}:
            raise ValueError('P0_MANUAL_TEST_COMMAND_FIELDS')
        command = payload.get('command_id')
        if not isinstance(command, str):
            raise ValueError('P0_COMMAND_ID')
        receipt = self.receipt(command)
        pin = sha(canonical(dict(payload)))
        with self.mutex:
            if receipt.exists('RESERVED'):
                if receipt.read('RESERVED').get('payload_sha256') != pin:
                    raise ValueError('P0_IDEMPOTENCY_CONFLICT')
                return self._read(command, receipt)
            request = self.prepared(str(payload['preparation_ref']), str(payload['preparation_sha256']))
            transport = self.generation.prepare_transport(request)
            lease = ManualTestLease(self.generation.root)
            try:
                self.generation.budget.require_active()
                wire = self.generation.wire(request)
                body = canonical(response_parameters(wire))
                bound = self.generation.budget.bound(wire)
                if self.generation.budget.reserved() + bound > BUDGET:
                    raise ValueError('P0_MANUAL_TEST_SESSION_BUDGET_EXHAUSTED')
                receipt.publish('RESERVED', {'schema':'P0-MANUAL-TEST-CLAIM-1.0', 'command_id':command,
                    'payload_sha256':pin, 'preparation_sha256':sha(canonical(as_plain(request))),
                    'session_sha256':self.generation.budget.policy_sha256, 'reserved_usd':str(bound),
                    'request_bytes':len(body), 'max_output_tokens':wire.max_output_tokens, 'request_sha256':sha(body), 'retry':0})
                wire = self.generation.wire(request)
                receipt.publish('DISPATCH', {'schema':'P0-MANUAL-TEST-DISPATCH-1.0', 'command_id':command,
                    'request_sha256':sha(canonical(response_parameters(wire))),
                    'body':canonical(response_parameters(wire)).decode('utf-8'), 'dispatch':as_plain(request)})
                self.generation.armed = sha(canonical(as_plain(request))), receipt, transport
                self.payloads[command] = dict(payload)
                self.views[command] = {'state':'LOCAL_COMMAND_RUNNING', 'command_id':command, 'phase':'PREPARED'}
                threading.Thread(target=self._run, args=(command, receipt, lease), daemon=True,
                    name='v2-manual-test-command').start()
            except Exception:
                lease.close()
                self.generation.armed = None
                raise
            return dict(self.views[command])

    def _run(self, command: str, receipt: P0NormalReceipt, lease: ManualTestLease) -> None:
        def progress(phase: str, evidence: Mapping[str, object]) -> None:
            with self.mutex:
                self.views[command].update(phase=phase, evidence=dict(evidence))

        self.generation.progress = progress
        view: dict[str, object]
        try:
            result = self.execute('generate', self.payloads[command])
            if result.get('state') != 'CANDIDATE' or not isinstance(result.get('publication'), Mapping):
                raise ValueError('P0_MANUAL_TEST_SAVED_RESULT_REQUIRED')
            publication = cast(Mapping[str, object], result['publication'])
            receipt.publish('CONSUMED', {'schema':'P0-MANUAL-TEST-SAVED-1.0', 'command_id':command, 'publication':dict(publication)})
            view = {'state':'LOCAL_COMMAND_COMPLETED', 'command_id':command, 'phase':'APPLICATION_SAVED', 'result':result}
        except Exception as error:
            code = error.code.value if isinstance(error, OpenAITransportError) else str(error)
            if re.fullmatch(r'(?:P0|P1|R4|COURSE|EXERCISE)_[A-Z0-9_]{1,100}', code) is None:
                code = error.code.value if isinstance(error, OpenAITransportError) else 'P0_MANUAL_TEST_OUTCOME_UNKNOWN'
            record: dict[str, object] = {'schema':'P0-MANUAL-TEST-UNKNOWN-1.0', 'command_id':command,
                'code':code, 'retry':0, 'actual_billed_cost':'UNKNOWN'}
            if isinstance(error, OpenAITransportError):
                record['provider_diagnostic'] = dict(error.diagnostic)
            try:
                if receipt.exists('UNKNOWN'):
                    record = receipt.read('UNKNOWN')
                    code = str(record['code'])
                else:
                    receipt.publish('UNKNOWN', record)
            except Exception:
                pass
            view = {'state':'LOCAL_COMMAND_UNCERTAIN', 'command_id':command, 'code':code,
                'phase':'OUTCOME_UNCONFIRMED', 'retry':0, 'provider_diagnostic':record.get('provider_diagnostic', {})}
        finally:
            self.generation.armed = None
            lease.close()
        with self.mutex:
            self.views[command] = view

    def _read(self, command: str, receipt: P0NormalReceipt) -> dict[str, object]:
        if command in self.views:
            return cast(dict[str, object], as_plain(self.views[command]))
        if receipt.exists('CONSUMED'):
            return {'state':'LOCAL_COMMAND_COMPLETED', 'command_id':command, 'phase':'APPLICATION_SAVED',
                'result':{'state':'APPLICATION_SAVED', 'publication':receipt.read('CONSUMED')['publication']}, 'retry':0}
        if receipt.exists('RESERVED'):
            error = receipt.read('UNKNOWN') if receipt.exists('UNKNOWN') else {}
            return {'state':'LOCAL_COMMAND_UNCERTAIN', 'command_id':command, 'phase':'RETAINED_NO_REPLAY',
                'code':error.get('code','P0_MANUAL_TEST_INTERRUPTED'), 'provider_diagnostic':error.get('provider_diagnostic', {}), 'retry':0}
        return {'state':'LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE', 'command_id':command}

    def read(self, command: str) -> dict[str, object]:
        with self.mutex:
            return self._read(command, self.receipt(command))
