from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from resume_agent.imports.service import ImportService
from resume_agent.normalization.service import NormalizationService
from resume_agent.parsing.models import ParsedSegment
from resume_agent.parsing.pipeline import ParsedDocument
from resume_agent.profile.service import ProfileService


def _service(store):
    profiles = ProfileService(store)
    imports = ImportService(profiles)
    source = imports.preview(
        ParsedDocument(
            "decision-doc",
            "resume.pdf",
            "application/pdf",
            1,
            "d" * 64,
            (ParsedSegment("姓名：示例", "p1"),),
        ),
        task_id="decision-import",
    )
    service = NormalizationService(profiles, imports)
    task = service.preview(
        source.task_id, profile_id="default-profile", task_id="decision-normalize"
    )
    return service, task


def test_skip_and_cancel_do_not_write(fake_profile_store):
    service, task = _service(fake_profile_store)
    candidate = task.candidates[0]
    result = service.confirm(
        task.task_id,
        decisions=[
            {"candidate_id": candidate.candidate_id, "decision": "skip", "user_confirmed": True}
        ],
        profile_id="default-profile",
        expected_profile_version=0,
    )
    assert result["written_field_ids"] == []
    assert fake_profile_store.write_calls == 0
    service2, task2 = _service(fake_profile_store)
    assert service2.cancel(task2.task_id) is True
    assert service2.cancel(task2.task_id) is False


def test_expired_task_cannot_confirm(fake_profile_store):
    service, task = _service(fake_profile_store)
    service._tasks[task.task_id] = replace(task, created_at=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(ValueError, match="expired"):
        service.confirm(
            task.task_id,
            decisions=[],
            profile_id="default-profile",
            expected_profile_version=0,
        )
