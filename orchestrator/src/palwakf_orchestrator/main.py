from __future__ import annotations

import argparse
import json
import os

import uvicorn

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.config import get_settings
from palwakf_orchestrator.credentials import probe_openai_api_key, require_openai_api_key
from palwakf_orchestrator.safe_logging import configure_safe_logging
from palwakf_orchestrator.service import OrchestratorService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palwakf-orchestrator")
    parser.add_argument(
        "command",
        choices=("credential-probe", "health", "serve"),
        nargs="?",
        default="health",
    )
    parser.add_argument("--live-agents", action="store_true")
    return parser


def main() -> None:
    configure_safe_logging()
    args = build_parser().parse_args()
    if args.command == "credential-probe":
        print(json.dumps(probe_openai_api_key().as_safe_dict(), sort_keys=True))
        return
    if args.live_agents:
        require_openai_api_key()
    settings = get_settings()
    service = OrchestratorService(settings)
    if args.command == "health":
        print(json.dumps(service.health().model_dump(mode="json"), sort_keys=True))
        return

    settings.assert_safe_binding()
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        create_app(settings, service),
        host=settings.bind_host,
        port=port,
        log_level="info",
    )
