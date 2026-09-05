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
        decisions=[{"candidate_id": email.candidate_id, "decision": "accept", "user_confirmed": True}],
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
    task = service.preview(source.task_id, profile_id="default-profile", task_id="normalize-education")
    record = next(item for item in task.records if item.record_type == "education")
    result = service.confirm(
        task.task_id,
        decisions=[{"candidate_id": record.candidate_id, "decision": "accept", "user_confirmed": True}],
        profile_id="default-profile",
        expected_profile_version=0,
    )
    assert result["written_record_ids"] == [f"normalized-{record.candidate_id}"]
    assert len(fake_profile_store.snapshot.records) == 1
