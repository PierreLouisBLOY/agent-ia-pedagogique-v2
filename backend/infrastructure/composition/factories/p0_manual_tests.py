"""Selected by the normal CLI only, with a persistent $5 manual-test budget."""
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.application.lot2_saved_production import Lot2SavedProductionInbound
from backend.adapters.outbound.generation.openai.p0_manual_tests import (
    ManualTestCommands,
    ManualTestGeneration,
)
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.infrastructure.composition.factories.p0_normal_profile import build_p0_secret_resolver
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
from backend.modules.knowledge_reference.application.queries.owner_local_chapter_links import (
    ReadOwnerLocalChapterLinks,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService


class ManualTestComposition:
    def __init__(self, *, receipt_root: Path, saved_root: Path, max_output_tokens: int = 32768,
                 local_admission_path: Path | None = None, local_admission_sha256: str | None = None) -> None:
        self.local_admission: ReadOwnerLocalChapterLinks | None = None
        if local_admission_path is not None or local_admission_sha256 is not None:
            from backend.adapters.outbound.generation.openai.p0_normal_policy import sha
            from backend.adapters.outbound.generation.openai.p0_normal_receipt import decode
            from backend.infrastructure.filesystem import read_file_nofollow
            if local_admission_path is None:
                raise ValueError('OWNER_LOCAL_CHAPTER_FILE_REQUIRED')
            raw = read_file_nofollow(local_admission_path, allowed_root=local_admission_path.parent, maximum_bytes=32000)
            if sha(raw) != local_admission_sha256:
                raise ValueError('OWNER_LOCAL_CHAPTER_FILE_CHANGED')
            self.local_admission = ReadOwnerLocalChapterLinks(decode(raw))
        self.saved_root = saved_root
        self.resolver = build_p0_secret_resolver(ProviderCredentialRef('openai.p0.manual-tests'),
            credential_source='OPENAI_API_KEY')
        # Validate local configuration now; no provider call or console fallback.
        self.resolver.resolve(self.resolver.ref)
        self.generation = ManualTestGeneration(root=receipt_root, resolver=self.resolver,
            credential_ref=self.resolver.ref,
            transport=OpenAISDKResponsesTransportFactory(r2_destination=True, environment_key_allowed=True),
            max_output_tokens=max_output_tokens)

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        from backend.infrastructure.composition.factories.local_browser import (
            build_saved_application,
        )

        if service.generation is not self.generation:
            raise ValueError('P0_MANUAL_TEST_GENERATION_BINDING')
        self.generation.course_thread_reader = service.course_thread_reader
        saved = build_saved_application(self.saved_root, source=service.saved_source, word_profile='product-v7')
        if not isinstance(saved, Lot2SavedProductionInbound):
            raise ValueError('P0_MANUAL_TEST_SAVED_APPLICATION_REQUIRED')

        def publish(production: str, version: str, bundle: str) -> Mapping[str, object]:
            saved.execute('save', body={'production_ref':production, 'version_ref':version}, correlation='manual-test-save')
            record = saved.read_local_p0(production, version)
            if record.p0_bundle is None or record.p0_bundle.sha256 != bundle:
                raise ValueError('P0_MANUAL_TEST_PUBLICATION_BINDING')
            return {'state':'APPLICATION_SAVED', 'production_ref':production, 'version_ref':version,
                'bundle_sha256':bundle, 'record_sha256':record.sha256}

        def prepared(ref: str, checksum: str) -> Mapping[str, object]:
            request = service.prepared.get(ref)
            if request is None or fingerprint(request) != checksum:
                raise ValueError('P0_PREPARATION_CHANGED')
            return request

        if self.local_admission is not None:
            service.institutional_context_admission = self.local_admission.execute
        service.publish_generated = publish
        self.commands = commands = ManualTestCommands(generation=self.generation, prepared=prepared, execute=service.execute)
        endpoint.manual_test_start = commands.start
        endpoint.manual_test_read = commands.read

        def stop(payload: Mapping[str, object]) -> dict[str, object]:
            if payload:
                raise ValueError('P0_MANUAL_TEST_STOP_FIELDS')
            self.generation.budget.stop()
            self.generation.active = False
            return {'state':'MANUAL_TEST_SESSION_STOPPED', 'in_flight':'PRESERVED_NO_RETRY'}

        endpoint.manual_test_stop = stop
        endpoint.manual_test_metadata = lambda: cast(dict[str, object], {
            'enabled':self.generation.active, 'max_output_tokens':self.generation.max_output_tokens,
            'model':'gpt-5.6-terra', 'retry':0, 'per_call_ceiling_usd':None,
            **self.generation.budget.snapshot()})

    def close(self) -> None:
        self.generation.active = False
        self.resolver.close()
