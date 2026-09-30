from __future__ import annotations

import argparse
import json
from pathlib import Path

from palwakf_orchestrator.authority_issuer_v1 import (
    SignTaskEnvelopeRequestV1,
    WindowsDpapiAuthorityKeyStoreV1,
    WorkspaceAuthorityIssuerV1,
)


def _issuer(key_path: Path, key_id: str) -> WorkspaceAuthorityIssuerV1:
    return WorkspaceAuthorityIssuerV1(
        key_store=WindowsDpapiAuthorityKeyStoreV1(key_path),
        key_id=key_id,
        allowed_repositories=("firasfanon/palwakf_agenticAi_system",),
        allowed_executor_ids=("DESKTOP-S5A0JSB",),
        allowed_capability_ids=("c7r.phase_a",),
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="palwakf-c7r-authority")
    parser.add_argument("--key-path", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("public")
    sign = sub.add_parser("sign")
    sign.add_argument("--input", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    issuer = _issuer(args.key_path, args.key_id)
    if args.command == "public":
        print(issuer.public_descriptor().model_dump_json())
        return

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit("UNSIGNED_ENVELOPE_MUST_BE_OBJECT")
    result = issuer.sign(SignTaskEnvelopeRequestV1(unsigned_envelope=raw))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.signed_envelope, ensure_ascii=False, sort_keys=True),
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


if __name__ == "__main__":
    main()
