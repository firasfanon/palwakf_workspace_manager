from __future__ import annotations

import argparse
import json
import os

import uvicorn

from palwakf_orchestrator.api import create_app
from palwakf_orchestrator.config import get_settings
from palwakf_orchestrator.service import OrchestratorService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palwakf-orchestrator")
    parser.add_argument("command", choices=("health", "serve"), nargs="?", default="health")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    service = OrchestratorService(settings)
    if args.command == "health":
        print(json.dumps(service.health().model_dump(mode="json"), sort_keys=True))
        return

    settings.assert_local_only()
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        create_app(settings, service),
        host=settings.bind_host,
        port=port,
        log_level="info",
    )
