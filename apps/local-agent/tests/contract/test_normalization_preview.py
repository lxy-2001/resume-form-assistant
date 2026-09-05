from resume_agent.imports.service import ImportService
from resume_agent.normalization.service import NormalizationService
from resume_agent.parsing.models import ParsedSegment
from resume_agent.parsing.pipeline import ParsedDocument
from resume_agent.profile.service import ProfileService


def test_preview_contains_field_and_record_candidates(fake_profile_store):
    profiles = ProfileService(fake_profile_store)
    imports = ImportService(profiles)
    source = imports.preview(
        ParsedDocument(
            document_id="doc-preview",
            filename="resume.pdf",
            media_type="application/pdf",
            size_bytes=1,
            sha256="1" * 64,
            segments=(ParsedSegment("入学时间：2020-09-01", "page 1"),),
        ),
        task_id="import-preview",
    )
    task = NormalizationService(profiles, imports).preview(
        source.task_id, profile_id="default-profile", task_id="normalize-preview"
    )
    assert task.candidates
    assert task.records
