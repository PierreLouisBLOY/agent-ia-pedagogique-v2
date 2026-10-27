"""Read-only diagnosis selects the same explicit secret factory as the pilot."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from backend.adapters.outbound.openai.model_metadata import OpenAIModelMetadataReader
from backend.infrastructure.composition.factories.p0_normal_profile import (
    OpenAIEnvironmentSecretResolver,
    build_p0_secret_resolver,
    strict_document,
)
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
from backend.infrastructure.filesystem import hash_file_nofollow, read_file_nofollow
from backend.modules.work_orchestration.application.queries.inspect_p0_authentication import (
    InspectP0Authentication,
)


def compose_p0_authentication_diagnostic(*, profile_path: Path,
        expected_sha256: str, model: str,
        environment: Mapping[str, str] | None = None,
        ) -> tuple[InspectP0Authentication, OpenAIEnvironmentSecretResolver]:
    if (not profile_path.is_absolute()
            or hash_file_nofollow(profile_path, allowed_root=profile_path.parent) != expected_sha256):
        raise ValueError("P0_AUTHENTICATION_PROFILE_CHANGED")
    profile = strict_document(read_file_nofollow(profile_path,
        allowed_root=profile_path.parent, maximum_bytes=131072))
    if profile.get("schema") != "P0-NORMAL-PROFILE-1.0" or profile.get("credential_ref") != "openai.p0.normal":
        raise ValueError("P0_AUTHENTICATION_PROFILE_REJECTED")
    resolver = cast(OpenAIEnvironmentSecretResolver, build_p0_secret_resolver(
        ProviderCredentialRef(str(profile["credential_ref"])),
        credential_source="OPENAI_API_KEY", environment=environment))
    reader = OpenAIModelMetadataReader(resolver, resolver.ref, model=model)
    return InspectP0Authentication(reader), resolver
