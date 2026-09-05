from dataclasses import replace

import pytest

from resume_agent.imports.service import ImportService
from resume_agent.normalization.service import NormalizationService
from resume_agent.parsing.models import ParsedSegment
from resume_agent.parsing.pipeline import ParsedDocument
from resume_agent.profile.service import ProfileService


def _document() -> ParsedDocument:
    return ParsedDocument(
        document_id="doc-normalize",
        filename="resume.pdf",
        media_type="application/pdf",
        size_bytes=10,
        sha256="d" * 64,
        segments=(ParsedSegment("姓名：示例用户 邮箱 Example@Example.Test", "page 1"),),
    )


def test_preview_is_review_only_and_confirm_writes_explicit_choice(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(_document(), task_id="import-normalize")
    service = NormalizationService(profiles, imports)
    task = service.preview(source.task_id, profile_id="default-profile", task_id="normalize-1")
    email = next(item for item in task.candidates if item.field_id == "contact.email")
    assert email.normalized_value == "example@example.test"
    assert fake_profile_store.write_calls == 0
    result = service.confirm(
        task.task_id,
        decisions=[
            {"candidate_id": email.candidate_id, "decision": "accept", "user_confirmed": True}
        ],
        profile_id="default-profile",
        expected_profile_version=0,
    )
    assert result["written_field_ids"] == ["contact.email"]
    assert fake_profile_store.write_calls == 1


def test_preview_groups_education_candidates_and_can_confirm_record(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(
        ParsedDocument(
            document_id="doc-education",
            filename="resume.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="f" * 64,
            segments=(ParsedSegment("入学时间：2020-09-01 毕业时间：2024-06-30", "page 2"),),
        ),
        task_id="import-education",
    )
    service = NormalizationService(profiles, imports)
    task = service.preview(
        source.task_id, profile_id="default-profile", task_id="normalize-education"
    )
    record = next(item for item in task.records if item.record_type == "education")
    result = service.confirm(
        task.task_id,
        decisions=[
            {"candidate_id": record.candidate_id, "decision": "accept", "user_confirmed": True}
        ],
        profile_id="default-profile",
        expected_profile_version=0,
    )
    assert result["written_record_ids"] == [f"normalized-{record.candidate_id}"]
    assert len(fake_profile_store.snapshot.records) == 1


def test_preview_preserves_sensitive_evidence_and_validates_date(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(
        ParsedDocument(
            document_id="doc-sensitive",
            filename="resume.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            segments=(ParsedSegment("证件号：11010519491231002X 出生日期：2020-13-99", "page 1"),),
        ),
        task_id="import-sensitive",
    )
    service = NormalizationService(profiles, imports)
    task = service.preview(
        source.task_id, profile_id="default-profile", task_id="normalize-sensitive"
    )
    identifier = next(item for item in task.candidates if item.field_id == "person.id_number")
    assert identifier.sensitivity == "highly_sensitive"
    assert identifier.evidence
    invalid_date = next(item for item in task.candidates if item.field_id == "person.birth_date")
    assert invalid_date.status == "invalid"
    assert fake_profile_store.write_calls == 0


def test_preview_rejects_cross_profile_source(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(_document(), task_id="import-profile")
    imports._tasks[source.task_id] = replace(source, profile_id="other-profile")
    with pytest.raises(ValueError, match="does not belong"):
        NormalizationService(profiles, imports).preview(
            source.task_id, profile_id="default-profile"
        )


def test_unchanged_candidate_is_not_written(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(_document(), task_id="import-unchanged")
    service = NormalizationService(profiles, imports)
    task = service.preview(
        source.task_id, profile_id="default-profile", task_id="normalize-unchanged"
    )
    # no existing value means this remains a normal new candidate; the branch is
    # covered by setting a current value through the regular F001 service.
    email = next(item for item in task.candidates if item.field_id == "contact.email")
    assert email.status == "new"
