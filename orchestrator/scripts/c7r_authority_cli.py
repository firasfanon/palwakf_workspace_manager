from __future__ import annotations

import argparse
import json
from pathlib import Path

from palwakf_orchestrator.authority_issuer_v1 import (
    RemoteIntentV1,
    SignTaskEnvelopeRequestV1,
    WindowsDpapiAuthorityKeyStoreV1,
    WorkspaceAuthorityIssuerV1,
)

ALLOWED_REPOSITORIES = (
    "firasfanon/palwakf_workspace_manager",
    "firasfanon/palwakf_mind_assistant",
    "firasfanon/palwakf_agenticAi_system",
)

ALLOWED_CAPABILITIES = (
    "device.info",
    "device.hostname",
    "file.read",
    "git.readback",
    "audit.readback",
    "git.create_task_branch",
    "git.stage_paths",
    "git.commit",
    "git.push_task_branch",
    "git.remote_sha_readback",
    "engineering.codex.patch_proposal",
    "source.apply_patch_bounded",
    "workspace_drive.read",
    "workspace_drive.write_bounded",
    "workspace_drive.write_learning_candidate",
    "workspace_drive.write_memory_candidate",
    "playwright.uat",
    "service.health",
    "service.restart_bounded",
    "c7r.phase_a",
)


def _issuer(
    key_path: Path,
    key_id: str,
    *,
    machine_scope_key: bool = False,
) -> WorkspaceAuthorityIssuerV1:
    return WorkspaceAuthorityIssuerV1(
        key_store=WindowsDpapiAuthorityKeyStoreV1(
            key_path,
            machine_scope=machine_scope_key,
        ),
        key_id=key_id,
        allowed_repositories=ALLOWED_REPOSITORIES,
        allowed_executor_ids=("Futuer-IT",),
        allowed_capability_ids=ALLOWED_CAPABILITIES,
    )


def _write_result(args: argparse.Namespace, result: object) -> None:
    signed = result.signed_envelope
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(signed, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "key_id": result.key.key_id,
                "public_key_sha256": result.key.public_key_sha256,
                "envelope_hash": result.envelope_hash,
                "private_key_exported": False,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="palwakf-workspace-authority")
    parser.add_argument("--key-path", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--machine-scope-key", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("public")
    for name in ("sign", "authorize-intent"):
        command = sub.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    issuer = _issuer(
        args.key_path,
        args.key_id,
        machine_scope_key=args.machine_scope_key,
    )
    if args.command == "public":
        print(issuer.public_descriptor().model_dump_json())
        return
    raw = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise SystemExit("AUTHORITY_INPUT_MUST_BE_OBJECT")
    if args.command == "authorize-intent":
        result = issuer.authorize_remote_intent(RemoteIntentV1.model_validate(raw))
    else:
        result = issuer.sign(SignTaskEnvelopeRequestV1(unsigned_envelope=raw))
    _write_result(args, result)


if __name__ == "__main__":
    main()
