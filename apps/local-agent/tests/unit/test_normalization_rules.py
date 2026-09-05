from resume_agent.normalization.rules import normalize_value


def test_normalize_date_and_phone():
    date, confidence, issues = normalize_value("date", " 2000年1月2日 ")
    phone, _, phone_issues = normalize_value("phone", "+86 13800138000")
    assert date == "2000-01-02"
    assert confidence > 0.9
    assert issues == ()
    assert phone == "13800138000"
    assert phone_issues == ()


def test_invalid_email_requires_manual_correction():
    value, confidence, issues = normalize_value("email", "not-an-email")
    assert value == "not-an-email"
    assert confidence == 0.0
    assert issues[0].code == "INVALID_EMAIL"
