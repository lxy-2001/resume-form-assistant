from resume_agent.normalization.merge import classify_record_status
from resume_agent.normalization.models import RecordCandidate


def test_record_merge_classification_is_conservative():
    candidate = RecordCandidate(
        candidate_id="record-1",
        record_type="education",
        fields=({"id": "education.school_name", "value": "Synthetic University"},),
        source={"kind": "import", "location": "page 1"},
        confidence=0.9,
    )
    assert classify_record_status(candidate, []) == "new"
