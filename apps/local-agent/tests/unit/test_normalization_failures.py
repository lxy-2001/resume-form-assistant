from resume_agent.normalization.errors import NormalizationErrorCode


def test_normalization_error_codes_are_stable():
    assert NormalizationErrorCode.TASK_EXPIRED.value == "TASK_EXPIRED"
    assert NormalizationErrorCode.STORAGE_FAILURE.value == "STORAGE_FAILURE"
