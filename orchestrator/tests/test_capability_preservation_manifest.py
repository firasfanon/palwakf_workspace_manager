from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = Path(__file__).with_name("capability_preservation_parity_manifest.json")
EXPECTED_SOURCE_SHA = "9656cd44d8cad85a356910305129d5e983cf3d4a"
EXPECTED_IDS = {
    "PT-FLD-001",
    "PT-FLD-002",
    "PT-REL-001",
    "PT-REL-002",
    "PT-SEM-001",
    "PT-SEM-002",
    "PT-ENG-001",
    "PT-ENG-002",
    "PT-ENG-003",
    "PT-STATE-001",
    "PT-STATE-002",
    "PT-STATE-003",
    "PT-STATE-004",
    "PT-STATE-005",
    "PT-ENG-004",
    "PT-STATE-006",
    "PT-OP-001",
    "PT-OP-002",
    "PT-OP-003",
    "PT-OP-004",
    "PT-OP-005",
    "PT-OP-006",
    "PT-OP-007",
    "PT-OP-008",
    "PT-OP-009",
    "PT-OP-010",
    "PT-OP-011",
    "PT-MAN-001",
    "PT-MAN-002",
    "PT-TOOL-001",
    "PT-TOOL-002",
    "PT-HIST-001",
    "PT-DATA-001",
    "PT-COMPAT-001",
    "PT-COMPAT-002",
    "PT-UI-001",
    "PT-UI-002",
    "PT-DASH-001",
    "PT-RESUME-001",
    "PT-NEG-001",
    "PT-NEG-002",
}
ALLOWED_PHASES = {
    "baseline_new",
    "existing_reused",
    "future_consolidation",
    "scope_guard",
}


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_pinned_to_authoritative_wip() -> None:
    manifest = _manifest()
    assert manifest["source_sha"] == EXPECTED_SOURCE_SHA
    assert manifest["no_feature_loss"] is True
    assert manifest["no_data_loss"] is True
    assert manifest["production_source_mutation_authorized"] is False


def test_manifest_covers_exactly_the_41_accepted_parity_cases() -> None:
    manifest = _manifest()
    cases = manifest["cases"]
    assert isinstance(cases, list)
    ids = [case["id"] for case in cases]
    assert len(ids) == 41
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_IDS


def test_every_parity_case_has_an_enforcement_phase_and_target() -> None:
    manifest = _manifest()
    for case in manifest["cases"]:
        assert case["phase"] in ALLOWED_PHASES
        assert str(case["target"]).strip()
        if case["phase"] == "future_consolidation":
            assert str(case.get("blocking_until", "")).strip()
