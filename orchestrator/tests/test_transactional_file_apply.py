from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.file_apply_contracts import (
    FileApplyClassification,
    FileMutationSpec,
    FilePreimageMode,
    GovernedFileApplyRequest,
)
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.transactional_file_apply import (
    GovernedTransactionalFileApply,
    canonical_existing_bytes,
    canonical_text_bytes,
    sha256_hex,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "PalWakf Test")
    git(repo, "config", "user.email", "palwakf-test@example.invalid")
    git(repo, "checkout", "-b", "agent/test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8", newline="\n")
    git(repo, "add", "seed.txt")
    git(repo, "commit", "-m", "seed")
    return repo, git(repo, "rev-parse", "HEAD")


def request(head: str, files: list[FileMutationSpec]) -> GovernedFileApplyRequest:
    return GovernedFileApplyRequest(
        task_id="PALWAKF_FILE_APPLY_TEST",
        repository="firasfanon/palwakf_workspace_manager",
        expected_branch="agent/test",
        expected_head=head,
        files=files,
    )


def existing_spec(path: str, preimage: bytes, postimage_text: str) -> FileMutationSpec:
    return FileMutationSpec(
        path=path,
        preimage_mode=FilePreimageMode.exact_canonical_sha256,
        expected_preimage_canonical_sha256=sha256_hex(canonical_existing_bytes(preimage)),
        postimage_text=postimage_text,
    )


def test_new_file_is_written_as_utf8_lf_with_exactly_one_eof_lf(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )
    spec = FileMutationSpec(
        path="src/example.py",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="print('ok')\r\n\r\n",
    )

    result = service.apply(request(head, [spec]))

    assert result.status == "VERIFIED"
    assert (repo / "src/example.py").read_bytes() == b"print('ok')\n"
    assert result.changed_paths == ["src/example.py"]
    journal = service.journal(result.run_id)
    assert journal is not None
    assert journal.status.value == "VERIFIED"


def test_reapply_is_idempotent_noop(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )
    spec = FileMutationSpec(
        path="new.txt",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="value\n",
    )

    first = service.apply(request(head, [spec]))
    second = service.apply(request(head, [spec]))

    assert first.status == "VERIFIED"
    assert second.status == "NOOP_VERIFIED"
    assert second.changed_paths == []
    assert second.classifications["new.txt"] == FileApplyClassification.already_postimage


def test_eof_bom_crlf_only_difference_is_partial_postimage_and_self_repairs(
    tmp_path: Path,
) -> None:
    repo, head = make_repo(tmp_path)
    target = repo / "candidate.py"
    target.write_bytes(b"\xef\xbb\xbfprint('x')\r\nprint('y')")
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )
    spec = FileMutationSpec(
        path="candidate.py",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="print('x')\nprint('y')\n",
    )

    plan = service.plan(request(head, [spec]))
    assert plan.blocked is False
    assert plan.items[0].classification == FileApplyClassification.partial_postimage

    result = service.apply(request(head, [spec]))
    assert result.status == "VERIFIED"
    assert target.read_bytes() == b"print('x')\nprint('y')\n"


def test_foreign_drift_fails_closed_without_mutation(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    target = repo / "seed.txt"
    before = target.read_bytes()
    spec = existing_spec("seed.txt", b"different preimage\n", "replacement\n")
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )

    plan = service.plan(request(head, [spec]))

    assert plan.blocked is True
    assert plan.items[0].classification == FileApplyClassification.foreign_drift
    with pytest.raises(GovernanceError, match="FILE_APPLY_BLOCKED"):
        service.apply(request(head, [spec]))
    assert target.read_bytes() == before


def test_unrelated_dirty_file_blocks_before_mutation(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    (repo / "unrelated.txt").write_text("dirty\n", encoding="utf-8")
    spec = FileMutationSpec(
        path="allowed.txt",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="allowed\n",
    )
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )

    with pytest.raises(GovernanceError, match="UNRELATED_WORKTREE_DRIFT"):
        service.plan(request(head, [spec]))
    assert not (repo / "allowed.txt").exists()


def test_failure_on_second_write_rolls_back_first_file_exactly(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    first = repo / "first.txt"
    second = repo / "second.txt"
    first.write_bytes(b"one\r\n")
    second.write_bytes(b"two\n")
    git(repo, "add", "first.txt", "second.txt")
    git(repo, "commit", "-m", "add files")
    head = git(repo, "rev-parse", "HEAD")
    first_before = first.read_bytes()
    second_before = second.read_bytes()
    calls = 0

    def fail_second(target: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-write failure")
        target.write_bytes(payload)

    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
        forward_writer=fail_second,
    )
    specs = [
        existing_spec("first.txt", first_before, "ONE\n"),
        existing_spec("second.txt", second_before, "TWO\n"),
    ]

    initial_plan = service.plan(request(head, specs))
    with pytest.raises(GovernanceError, match="FILE_APPLY_FAILED_ROLLED_BACK"):
        service.apply(request(head, specs))

    assert first.read_bytes() == first_before
    assert second.read_bytes() == second_before
    journal = service.journal(initial_plan.run_id)
    assert journal is not None
    assert journal.status.value == "ROLLED_BACK"


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    service = GovernedTransactionalFileApply(
        repo,
        MemoryStateStore(),
        execution_host_id="host-test",
    )
    spec = FileMutationSpec(
        path="../escape.txt",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="no\n",
    )

    with pytest.raises(GovernanceError, match="INVALID_TARGET_PATH"):
        service.plan(request(head, [spec]))


def test_repository_writer_lock_blocks_parallel_apply(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    store = MemoryStateStore()
    assert store.acquire_repository_writer(
        "firasfanon/palwakf_workspace_manager",
        "OTHER_TASK",
        "host-other",
    )
    service = GovernedTransactionalFileApply(
        repo,
        store,
        execution_host_id="host-test",
    )
    spec = FileMutationSpec(
        path="locked.txt",
        preimage_mode=FilePreimageMode.absent,
        postimage_text="locked\n",
    )

    with pytest.raises(GovernanceError, match="REPOSITORY_WRITER_BUSY"):
        service.apply(request(head, [spec]))
    assert not (repo / "locked.txt").exists()


def test_canonical_text_bytes_never_emits_bom_and_has_one_final_lf() -> None:
    assert canonical_text_bytes("a\r\n\r\n") == b"a\n"
    assert canonical_text_bytes("a") == b"a\n"
    assert not canonical_text_bytes("©\n").startswith(b"\xef\xbb\xbf")
