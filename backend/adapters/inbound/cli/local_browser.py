"""Explicit local entry point; no environment loading or side effects on import."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import re
import sys
import tempfile
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from backend.infrastructure.composition.factories.conversation import (
    build_r2_process_job,
    load_r2_grant,
    r2_source_material,
)
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_local_read15,
    build_local_saved,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.adapters.inbound.application.lot2_saved_production import (
        Lot2SavedProductionInbound,
    )
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )


class _ProductComposition(Protocol):
    @property
    def generation(self) -> P0GenerationPort | None: ...

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint
             ) -> Callable[[Lot2SavedProductionInbound], None] | None: ...
    def close(self) -> None: ...


def _drive_literal(value: Path | None) -> bool:
    return value is not None and re.fullmatch(r"[A-Za-z]:[\\/][^%$\x00]+", str(value)) is not None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="READ-15 local : cible explicite, aucune migration.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--bind-host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--runtime-sha256")
    parser.add_argument("--saved-root", type=Path, help="Stockage R4 explicitement désigné hors dépôt")
    parser.add_argument("--create-saved", action="store_true", help="Créer une racine R4 neuve uniquement")
    parser.add_argument("--observability-root", type=Path, help="Dossier local de traces explicitement désigné")
    parser.add_argument("--saved-only", action="store_true", help="Ouvrir R4 sans bibliothèque ni fournisseur")
    parser.add_argument("--chapter-manifest", type=Path, help="Blueprint original local épinglé, saved-only sans fournisseur")
    parser.add_argument("--chapter-manifest-sha256")
    parser.add_argument("--partial-manifest", type=Path, help="Capture locale partielle épinglée, saved-only exclusivement")
    parser.add_argument("--partial-manifest-sha256")
    parser.add_argument("--partial-word-profile", choices=("captured", "stmg-format-001"), default="captured")
    parser.add_argument("--register-format-reference", action="store_true")
    parser.add_argument("--word-profile", choices=("diffusion-v5", "diffusion-v6", "product-v7"),
                        default="diffusion-v5", help="Profil explicite des exports, sans retouche des archives")
    parser.add_argument("--enable-conversation", action="store_true",
                        help="R2 volatile, sans autorisation fournisseur implicite")
    parser.add_argument("--enable-review-modify", action="store_true",
                        help="R3 volatile ; aucun provider autorisé")
    parser.add_argument("--live-authorization", type=Path,
                        help="Fichier explicite réservé au handoff live ; refusé tant que ses préconditions ne sont pas établies")
    parser.add_argument("--r5-scope", type=Path, help="Sélection R5 exacte, opt-in distinct de R2")
    parser.add_argument("--r5-authorization", type=Path, help="Accord R5 distinct ; aucun accord live implicite")
    parser.add_argument("--p0-normal-profile", type=Path,
        help="Profil P1 fermé explicitement adopté ; consentement local exact et budget requis")
    parser.add_argument("--p0-codesign-profile", type=Path)
    parser.add_argument("--p0-codesign-profile-sha256")
    parser.add_argument("--p0-codesign-mode", choices=("enabled", "disabled"), default="disabled")
    parser.add_argument("--p0-normal-mode", choices=("enabled", "prepare-only"),
        help="Préparation PROPOSED sans secret/effet, ou profil ADOPTED avec consentement exact")
    parser.add_argument("--p0-rejected-profile", type=Path)
    parser.add_argument("--p0-rejected-inspection-plan", type=Path)
    parser.add_argument("--p0-rejected-adoption", type=Path)
    parser.add_argument("--p0-rejected-mode", choices=("inspect-only", "off", "on"))
    parser.add_argument("--p0-pilot-body-scope", type=Path,
                        help="Portée exacte de projection locale OFF, sans coût ni effet")
    parser.add_argument("--p0-pilot-body-scope-sha256")
    parser.add_argument("--p0-pilot-read-scope", type=Path,
                        help="Portée propriétaire de lecture OFF révocable, distincte de l'envoi")
    parser.add_argument("--p0-pilot-read-scope-sha256")
    parser.add_argument("--p0-pilot-historical-application-root", type=Path,
                        help="Racine source historique explicite, indépendante des artefacts de preuve")
    parser.add_argument("--p0-pilot-candidate-scope", type=Path,
                        help="Candidate OFF récupérable du même pilote, distincte du corps historique")
    parser.add_argument("--p0-pilot-candidate-scope-sha256")
    parser.add_argument("--p0-pilot-effect-profile", type=Path,
                        help="Profil d'effet pilote adopté, sélection explicite et fermée")
    parser.add_argument("--p0-pilot-effect-profile-sha256")
    parser.add_argument("--p0-pilot-on-demand-profile", type=Path,
        help="Recette stable adoptée du pilote ; chargement sans autorité temporelle")
    parser.add_argument("--p0-pilot-on-demand-profile-sha256")
    parser.add_argument("--organization-captures", type=Path)
    parser.add_argument("--organization-captures-sha256")
    args = parser.parse_args(argv)
    if args.organization_captures is not None or args.organization_captures_sha256 is not None:
        if (args.saved_only or not _drive_literal(args.organization_captures)
                or not isinstance(args.organization_captures_sha256,str)
                or re.fullmatch(r"[0-9a-f]{64}",args.organization_captures_sha256) is None):
            print("P0_ORGANIZATION_CAPTURE_EXPLICIT_DESCRIPTOR_REQUIRED")
            return 1
    partial = (args.partial_manifest is not None or args.partial_manifest_sha256 is not None
        or args.partial_word_profile != "captured" or (args.register_format_reference and args.chapter_manifest is None))
    if partial and (not args.saved_only or not _drive_literal(args.partial_manifest)
            or type(args.partial_manifest_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", args.partial_manifest_sha256) is None
            or any(value for name, value in vars(args).items() if
                name.startswith(("p0_", "r5_")) or name in {"runtime", "data_root", "runtime_sha256",
                    "enable_conversation", "enable_review_modify", "live_authorization"})):
        print("PARTIAL_SAVED_ONLY_REQUIRED")
        return 1
    chapter = args.chapter_manifest is not None or args.chapter_manifest_sha256 is not None
    if chapter and (not args.saved_only or partial or not _drive_literal(args.chapter_manifest)
            or not isinstance(args.chapter_manifest_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.chapter_manifest_sha256) is None
            or any(value for name, value in vars(args).items() if
                name.startswith(("p0_", "r5_")) or name in {"runtime", "data_root", "runtime_sha256",
                    "enable_conversation", "enable_review_modify", "live_authorization"})):
        print("ASSEMBLY_SAVED_ONLY_REQUIRED")
        return 1
    rejected = any(
        value is not None
        for value in (
            args.p0_rejected_profile,
            args.p0_rejected_inspection_plan,
            args.p0_rejected_adoption,
            args.p0_rejected_mode,
        )
    )
    if rejected and (
        bool(args.p0_rejected_profile) == bool(args.p0_rejected_inspection_plan)
        or not _drive_literal(args.p0_rejected_adoption)
        or not _drive_literal(args.p0_rejected_profile or args.p0_rejected_inspection_plan)
        or args.p0_normal_profile is not None
        or args.saved_root is None
        or args.word_profile != "product-v7"
        or any(
            (
                args.saved_only,
                args.create_saved,
                args.enable_conversation,
                args.enable_review_modify,
                args.live_authorization,
                args.r5_scope,
                args.r5_authorization,
            )
        )
        or any(value is None for value in (args.runtime, args.data_root, args.runtime_sha256))
        or (
            args.p0_rejected_inspection_plan is not None and args.p0_rejected_mode != "inspect-only"
        )
        or (args.p0_rejected_profile is not None and args.p0_rejected_mode == "inspect-only")
    ):
        print("P0_REJECTED_EXPLICIT_SELECTION_REQUIRED")
        return 1
    if args.p0_normal_mode is not None and args.p0_normal_profile is None:
        print("P0_NORMAL_EXPLICIT_PROFILE_REQUIRED")
        return 1
    if (args.p0_codesign_profile is not None or args.p0_codesign_profile_sha256 is not None or args.p0_codesign_mode == "enabled") and (
            args.p0_normal_profile is None or args.p0_codesign_profile is None or args.p0_codesign_profile_sha256 is None):
        print("P0_CHAIN_EXPLICIT_PROFILE_REQUIRED")
        return 1
    if args.p0_normal_profile is not None and (args.saved_root is None or args.word_profile != "product-v7"
            or args.create_saved or any((args.saved_only, args.enable_conversation, args.enable_review_modify,
                args.live_authorization, args.r5_scope, args.r5_authorization))):
        print("P0_NORMAL_EXPLICIT_PROFILE_AND_LIBRARY_REQUIRED")
        return 1
    if args.p0_pilot_body_scope is not None or args.p0_pilot_body_scope_sha256 is not None:
        if (not _drive_literal(args.p0_pilot_body_scope)
            or not isinstance(args.p0_pilot_body_scope_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.p0_pilot_body_scope_sha256) is None
            or args.runtime is None or args.data_root is None or args.runtime_sha256 is None
            or args.saved_root is None or args.word_profile != "product-v7"
            or any((args.create_saved, args.saved_only, args.enable_conversation,
                    args.enable_review_modify, args.live_authorization, args.r5_scope,
                    args.r5_authorization, args.p0_normal_profile, rejected))):
            print("P1_PILOT_OFF_EXPLICIT_SCOPE_REQUIRED")
            return 1
    if (args.p0_pilot_read_scope is not None or args.p0_pilot_read_scope_sha256 is not None
            or args.p0_pilot_historical_application_root is not None):
        if (not _drive_literal(args.p0_pilot_read_scope)
            or not _drive_literal(args.p0_pilot_historical_application_root)
            or not isinstance(args.p0_pilot_read_scope_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.p0_pilot_read_scope_sha256) is None
            or args.p0_pilot_body_scope is None):
            print("P1_PILOT_READ_EXPLICIT_SCOPE_REQUIRED")
            return 1
    if args.p0_pilot_candidate_scope is not None or args.p0_pilot_candidate_scope_sha256 is not None:
        if (not _drive_literal(args.p0_pilot_candidate_scope)
            or not isinstance(args.p0_pilot_candidate_scope_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.p0_pilot_candidate_scope_sha256) is None
            or args.p0_pilot_body_scope is None or args.p0_pilot_read_scope is None
            or args.saved_root is None):
            print("P0_PILOT_CANDIDATE_EXPLICIT_SCOPE_REQUIRED")
            return 1
    if args.p0_pilot_effect_profile is not None or args.p0_pilot_effect_profile_sha256 is not None:
        if (not _drive_literal(args.p0_pilot_effect_profile)
            or not isinstance(args.p0_pilot_effect_profile_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.p0_pilot_effect_profile_sha256) is None
            or args.p0_pilot_candidate_scope is None
            or args.p0_pilot_read_scope is None
            or args.saved_root is None):
            print("P1_PILOT_EFFECT_EXPLICIT_PROFILE_REQUIRED")
            return 1
    if (args.p0_pilot_on_demand_profile is not None
            or args.p0_pilot_on_demand_profile_sha256 is not None):
        if (not _drive_literal(args.p0_pilot_on_demand_profile)
            or not isinstance(args.p0_pilot_on_demand_profile_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", args.p0_pilot_on_demand_profile_sha256) is None
            or args.p0_pilot_effect_profile is not None
            or args.p0_pilot_candidate_scope is None
            or args.p0_pilot_read_scope is None
            or args.saved_root is None):
            print("P1_PILOT_ON_DEMAND_EXPLICIT_PROFILE_REQUIRED")
            return 1
    if (bool(args.r5_scope) != bool(args.r5_authorization) or
            (args.r5_scope and (args.live_authorization or args.saved_only or args.enable_review_modify
                               or not args.enable_conversation))):
        print("R5_EXPLICIT_SCOPE_AND_AUTHORITY_REQUIRED")
        return 1
    if args.saved_only:
        if (args.saved_root is None or any((args.runtime, args.data_root, args.runtime_sha256,
                args.enable_conversation, args.enable_review_modify, args.live_authorization))):
            print("R4_EXPLICIT_STORE_ONLY_REQUIRED")
            return 1
        try:
            saved = build_local_saved(LocalBrowserHttpConfiguration(port=args.port, bind_host=args.bind_host),
                                      args.saved_root, create=args.create_saved, word_profile=args.word_profile,
                                      partial_manifest=args.partial_manifest,
                                      partial_manifest_sha256=args.partial_manifest_sha256,
                                      partial_word_profile=args.partial_word_profile,
                                      register_format_reference=args.register_format_reference,
                                      chapter_manifest=args.chapter_manifest,
                                      chapter_manifest_sha256=args.chapter_manifest_sha256)
        except Exception:
            print("R4_STARTUP_REJECTED")
            return 1
        try:
            print(f"R4 local : {saved.url}", flush=True)
            saved.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            saved.close()
        return 0
    if (args.runtime is None or args.data_root is None or args.runtime_sha256 is None
            or (args.create_saved and args.saved_root is None)):
        print("EXPLICIT_RUNTIME_REQUIRED")
        return 1
    if args.enable_review_modify and (not args.enable_conversation or args.live_authorization is not None):
        print("R3_SYNTHETIC_ONLY")
        return 1
    jobs = None
    secret_value = ""
    normal: _ProductComposition | None = None
    if args.r5_scope is not None:
        try:
            from backend.infrastructure.composition.factories.r5_generation import (
                build_r5_process_job,
                current_baseline,
                load_document,
            )
            if not sys.stdin.isatty():
                raise ValueError("R5_MASKED_CONSOLE_REQUIRED")
            # R5 input is deferred until the exact user request and selection pass preflight.
            def r5_masked_input() -> str:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", getpass.GetPassWarning)
                    return getpass.getpass("Clé OpenAI R5 (masquée, non conservée) : ")
            jobs = build_r5_process_job(grant=load_document(args.r5_authorization),
                scope=load_document(args.r5_scope), baseline=current_baseline(),
                target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                receipt_root=args.data_root / "r5-private-receipts", private_temp=Path(tempfile.gettempdir()),
                credential_input=r5_masked_input)
        except Exception:
            print("R5_LIVE_PREFLIGHT_NOT_READY")
            return 1
    if args.live_authorization is not None:
        try:
            if not args.enable_conversation:
                raise ValueError("R2_CONVERSATION_REQUIRED")
            grant = load_r2_grant(args.live_authorization)
            baseline, scope = r2_source_material()
            jobs = build_r2_process_job(grant=grant, scope=scope, baseline=baseline,
                target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                receipt_root=args.data_root / "r2-private-receipts",
                private_temp=Path(tempfile.gettempdir()),
                credential_input=lambda: secret_value)
            # Interactive entry is before the bounded job, after every preflight.
            # Never allow getpass's unmasked fallback on a redirected console.
            if not sys.stdin.isatty():
                raise ValueError("R2_MASKED_CONSOLE_REQUIRED")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                secret_value = getpass.getpass("Clé OpenAI locale (masquée, non conservée) : ")
        except Exception:
            print("R2_LIVE_PREFLIGHT_NOT_READY")
            return 1
    if args.p0_normal_profile is not None:
        try:
            from backend.infrastructure.composition.factories.p0_normal_profile import (
                P0NormalProductComposition,
                read_descriptor,
            )
            historical_root = None
            if args.p0_codesign_profile is not None:
                finite_document = read_descriptor({"path":str(args.p0_codesign_profile), "sha256":args.p0_codesign_profile_sha256})
                if not isinstance(finite_document, dict):
                    raise ValueError("P0_CHAIN_STARTUP_FIELDS")
                historical_root = Path(str(finite_document["historical_application_root"]))
            normal = P0NormalProductComposition(path=args.p0_normal_profile,
                target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256), saved_root=args.saved_root,
                credential_source="OPENAI_API_KEY", mode="evidence-only" if historical_root is not None else args.p0_normal_mode or "enabled",
                followup_enabled=True, **({"application_root": historical_root} if historical_root is not None else {}))
            if args.p0_codesign_profile is not None:
                from backend.infrastructure.composition.factories.p0_finite_chain import (
                    FiniteChainComposition,
                )
                normal = FiniteChainComposition(normal=normal, path=args.p0_codesign_profile,
                    expected_sha256=cast(str, args.p0_codesign_profile_sha256), mode=args.p0_codesign_mode)
        except Exception:
            print("P0_NORMAL_PROFILE_NOT_ADOPTED_OR_INVALID")
            return 1
    if rejected:
        try:
            from backend.infrastructure.composition.factories.p0_rejected_profile import (
                P0RejectedInspectionComposition,
                P0RejectedProductComposition,
            )

            target = Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256)
            if args.p0_rejected_inspection_plan is not None:
                normal = P0RejectedInspectionComposition(
                    plan_path=args.p0_rejected_inspection_plan,
                    adoption_path=args.p0_rejected_adoption,
                    target=target,
                    saved_root=args.saved_root,
                )
            else:
                normal = P0RejectedProductComposition(
                    path=args.p0_rejected_profile,
                    adoption_path=args.p0_rejected_adoption,
                    target=target,
                    saved_root=args.saved_root,
                    mode=args.p0_rejected_mode or "off",
                )
        except Exception:
            print("P0_REJECTED_COMPOSITION_NOT_ADOPTED_OR_INVALID")
            return 1
    if args.p0_pilot_body_scope is not None:
        try:
            from backend.infrastructure.composition.factories.p0_pilot_body_projection_off import (
                P0PilotBodyProjectionOffComposition,
            )
            from backend.infrastructure.composition.factories.p0_pilot_read_off import (
                P0PilotReadOffComposition,
            )
            from backend.infrastructure.composition.factories.p0_pilot_read_scope_off import (
                P0PilotReadScopeOff,
            )
            from backend.infrastructure.composition.factories.p0_rejected_profile import _document
            from backend.infrastructure.filesystem.security import read_file_nofollow

            raw = read_file_nofollow(args.p0_pilot_body_scope,
                allowed_root=args.p0_pilot_body_scope.parent, maximum_bytes=4096)
            if hashlib.sha256(raw).hexdigest() != args.p0_pilot_body_scope_sha256:
                raise ValueError("P1_PILOT_OFF_SCOPE_CHANGED")
            scope = json.loads(raw)
            historical_inspector = None
            read_scope = None
            if args.p0_pilot_read_scope is not None:
                read_scope = P0PilotReadScopeOff(path=args.p0_pilot_read_scope,
                    expected_sha256=cast(str, args.p0_pilot_read_scope_sha256),
                    pilot_body_scope_sha256=args.p0_pilot_body_scope_sha256,
                    pilot_runtime_sha256=args.runtime_sha256)
                historical_plan, _ = _document(read_scope.plan_path)
                history_runtime = historical_plan["target_runtime"]
                history_saved = historical_plan["saved_root_native_identity"]
                history_source = historical_plan["source_manifest"]
                if (not isinstance(history_runtime, dict) or not isinstance(history_saved, dict)
                    or not isinstance(history_source, dict)):
                    raise ValueError("P1_PILOT_READ_HISTORICAL_TARGET_REQUIRED")
                reader = P0PilotReadOffComposition(scope=read_scope,
                    plan_path=read_scope.plan_path,
                    adoption_path=read_scope.adoption_path,
                    expected_owner_sha256=read_scope.expected[2],
                    target=Read15RuntimeTarget(Path(str(history_runtime["path"])),
                        Path(str(history_runtime["data_root"])), str(history_runtime["sha256"])),
                    saved_root=Path(str(history_saved["path"])),
                    application_root=args.p0_pilot_historical_application_root)
                historical_inspector = reader.inspect
            if args.p0_pilot_candidate_scope is not None:
                from backend.adapters.outbound.persistence.p0_pilot_candidate_off import (
                    P0PilotCandidateOffStore,
                )
                from backend.infrastructure.composition.factories.p0_pilot_candidate_projection_off import (
                    P0PilotCandidateProjectionOffComposition,
                )
                if historical_inspector is None or read_scope is None:
                    raise ValueError("P0_PILOT_CANDIDATE_READ_REQUIRED")
                candidate_raw = read_file_nofollow(args.p0_pilot_candidate_scope,
                    allowed_root=args.p0_pilot_candidate_scope.parent, maximum_bytes=4096)
                if hashlib.sha256(candidate_raw).hexdigest() != args.p0_pilot_candidate_scope_sha256:
                    raise ValueError("P0_PILOT_CANDIDATE_SCOPE_CHANGED")
                candidate = json.loads(candidate_raw)
                if (candidate.get("previous_body_scope_sha256") != args.p0_pilot_body_scope_sha256
                    or candidate.get("read_scope_sha256") != args.p0_pilot_read_scope_sha256):
                    raise ValueError("P0_PILOT_CANDIDATE_SCOPE_BINDING")
                normal = P0PilotCandidateProjectionOffComposition(scope=candidate,
                    runtime_sha256=args.runtime_sha256,
                    read_scope_sha256=cast(str, args.p0_pilot_read_scope_sha256),
                    historical_inspector=historical_inspector,
                    store=P0PilotCandidateOffStore(cast(Path, args.saved_root)))
                if args.p0_pilot_effect_profile is not None:
                    from backend.infrastructure.composition.factories.p0_pilot_effect_startup import (
                        P0PilotEffectStartup,
                    )
                    normal = P0PilotEffectStartup(path=args.p0_pilot_effect_profile,
                        expected_sha256=cast(str, args.p0_pilot_effect_profile_sha256),
                        candidate_scope_sha256=args.p0_pilot_candidate_scope_sha256,
                        read_scope_sha256=cast(str, args.p0_pilot_read_scope_sha256),
                        candidate=normal, historical=reader,
                        target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                        saved_root=cast(Path, args.saved_root))
                elif args.p0_pilot_on_demand_profile is not None:
                    from backend.infrastructure.composition.factories.p0_pilot_on_demand_startup import (
                        P0PilotOnDemandStartup,
                    )
                    normal = P0PilotOnDemandStartup(path=args.p0_pilot_on_demand_profile,
                        expected_sha256=cast(str, args.p0_pilot_on_demand_profile_sha256),
                        candidate_scope_sha256=args.p0_pilot_candidate_scope_sha256,
                        read_scope_sha256=cast(str, args.p0_pilot_read_scope_sha256),
                        candidate=normal, historical=reader,
                        target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                        saved_root=cast(Path, args.saved_root),
                        application_root=Path(__file__).resolve().parents[4])
            else:
                normal = P0PilotBodyProjectionOffComposition(scope=scope,
                    runtime_sha256=args.runtime_sha256,
                    historical_inspector=historical_inspector,
                    read_scope_sha256=args.p0_pilot_read_scope_sha256,
                    expected_preparation_sha256=None if read_scope is None else read_scope.preparation_sha256,
                    expected_request_sha256=None if read_scope is None else read_scope.request_sha256,
                    expected_request_bytes=None if read_scope is None else read_scope.request_bytes)
        except Exception as error:
            safe = str(error)
            print("P1_PILOT_OFF_SCOPE_REJECTED:" + (safe
                if re.fullmatch(r"[A-Z0-9_]{1,80}", safe) else type(error).__name__))
            return 1
    try:
        composition = build_local_read15(
            LocalBrowserHttpConfiguration(port=args.port, bind_host=args.bind_host),
            Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
            enable_conversation=args.enable_conversation,
            generation_jobs=jobs,
            enable_review_modify=args.enable_review_modify,
            saved_root=args.saved_root, create_saved=args.create_saved,
            word_profile=args.word_profile,
            observability_root=args.observability_root,
            organization_capture_descriptor=None if args.organization_captures is None else
                {"path":str(args.organization_captures), "sha256":args.organization_captures_sha256},
            p0_generation=(None if args.p0_pilot_effect_profile is not None
                or args.p0_pilot_on_demand_profile is not None else
                normal.generation if normal is not None else None),
            p0_product_binder=normal.bind if normal is not None else None,
        )
    except Exception:
        if normal is not None:
            normal.close()
        print("LOCAL_READ15_STARTUP_REJECTED")
        return 1
    try:
        print(f"READ-15 local : {composition.url}", flush=True)
        composition.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception:
        print("LOCAL_READ15_EXECUTION_FAILED")
        return 1
    finally:
        try:
            composition.close()
        finally:
            if normal is not None:
                normal.close()
            secret_value = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
