from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from resume_agent.imports.service import ImportService
from resume_agent.parsing.models import ParsedSegment
from resume_agent.parsing.pipeline import ParsedDocument
from resume_agent.profile.service import ProfileService


def _document() -> ParsedDocument:
    return ParsedDocument(
        document_id="doc-1",
        filename="resume.pdf",
        media_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        segments=(ParsedSegment("姓名：示例用户 邮箱 example@example.test", "page 1"),),
    )


def test_preview_is_confirmable_and_does_not_write_profile(fake_profile_store) -> None:
    service = ImportService(ProfileService(fake_profile_store))

    task = service.preview(_document(), task_id="task-1")

    assert {candidate["field_id"] for candidate in task.candidates} == {
        "person.full_name",
        "contact.email",
    }
    assert all(candidate["requires_confirmation"] for candidate in task.candidates)
    assert fake_profile_store.write_calls == 0


def test_preview_extracts_labeled_date_and_marks_sensitive_identifier(fake_profile_store) -> None:
    service = ImportService(ProfileService(fake_profile_store))
    document = ParsedDocument(
        document_id="doc-sensitive",
        filename="resume.pdf",
        media_type="application/pdf",
        size_bytes=10,
        sha256="b" * 64,
        segments=(ParsedSegment("出生日期：2000-01-02 身份证：11010519491231002X", "page 2"),),
    )

    candidates = service.preview(document, task_id="task-sensitive").candidates

    date = next(
        candidate for candidate in candidates if candidate["field_id"] == "person.birth_date"
    )
    identifier = next(
        candidate for candidate in candidates if candidate["field_id"] == "person.id_number"
    )
    assert date["value"] == "2000-01-02"
    assert identifier["sensitivity"] == "highly_sensitive"
    assert identifier["requires_confirmation"] is True


def test_confirm_writes_only_accepted_candidates(fake_profile_store) -> None:
    profiles = ProfileService(fake_profile_store)
    service = ImportService(profiles)
    task = service.preview(_document(), task_id="task-2")
    email = next(
        candidate for candidate in task.candidates if candidate["field_id"] == "contact.email"
    )

    result = service.confirm(
        task.task_id,
        decisions=[
            {
                "candidate_id": email["candidate_id"],
                "decision": "accept",
                "target_scope": "global",
                "user_confirmed": True,
            }
        ],
        profile_id="default-profile",
        expected_profile_version=0,
    )

    assert result["written_field_ids"] == ["contact.email"]
    assert [field.id for field in fake_profile_store.snapshot.fields] == ["contact.email"]


@pytest.mark.parametrize(
    "decision",
    [
        {"decision": "modify", "user_confirmed": True},
        {"decision": "accept", "user_confirmed": False},
        {"decision": "unknown", "user_confirmed": True},
    ],
)
def test_confirm_rejects_invalid_decisions_without_writing(fake_profile_store, decision) -> None:
    profiles = ProfileService(fake_profile_store)
    service = ImportService(profiles)
    task = service.preview(_document(), task_id="task-invalid")
    email = next(
        candidate for candidate in task.candidates if candidate["field_id"] == "contact.email"
    )

    with pytest.raises(ValueError):
        service.confirm(
            task.task_id,
            decisions=[{"candidate_id": email["candidate_id"], **decision}],
            profile_id="default-profile",
            expected_profile_version=0,
        )

    assert fake_profile_store.write_calls == 0


def test_confirm_rejects_stale_preview_version(fake_profile_store) -> None:
    profiles = ProfileService(fake_profile_store)
    service = ImportService(profiles)
    task = service.preview(_document(), task_id="task-stale")
    email = next(
        candidate for candidate in task.candidates if candidate["field_id"] == "contact.email"
    )

    with pytest.raises(ValueError, match="profile version"):
        service.confirm(
            task.task_id,
            decisions=[
                {
                    "candidate_id": email["candidate_id"],
                    "decision": "accept",
                    "user_confirmed": True,
                }
            ],
            profile_id="default-profile",
            expected_profile_version=1,
        )

    assert fake_profile_store.write_calls == 0


def test_expired_task_and_cancel_cannot_write(fake_profile_store) -> None:
    profiles = ProfileService(fake_profile_store)
    service = ImportService(profiles, task_ttl=timedelta(seconds=1))
    task = service.preview(_document(), task_id="task-expired")
    service._tasks[task.task_id] = replace(
        task, created_at=datetime.now(UTC) - timedelta(seconds=2)
    )

    with pytest.raises(ValueError, match="expired"):
        service.confirm(
            task.task_id,
            decisions=[],
            profile_id="default-profile",
            expected_profile_version=0,
        )
    task2 = service.preview(_document(), task_id="task-cancelled")
    service.cancel(task2.task_id)
    with pytest.raises(ValueError, match="unavailable"):
        service.confirm(
            task2.task_id,
            decisions=[],
            profile_id="default-profile",
            expected_profile_version=0,
        )
    assert fake_profile_store.write_calls == 0
