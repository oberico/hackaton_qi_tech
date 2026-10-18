from scripts.farm import (
    build_farm_report,
    evaluate_persona_results,
    format_farm_report_table,
    run_farm,
)


def test_evaluate_persona_results_legitimate_pass():
    responses = [
        {"status": "approved", "metadata": {"policy_version": "2026.10.18-1", "reasons": []}}
        for _ in range(10)
    ]
    res = evaluate_persona_results("salaried", "Assalariada", "legitimate", responses)
    assert res.total == 10
    assert res.approved == 10
    assert res.two_factor == 0
    assert res.rejected == 0
    assert res.budget_passed is True


def test_evaluate_persona_results_legitimate_fail_on_rejection():
    responses = [
        {"status": "approved", "metadata": {"reasons": []}},
        {"status": "rejected", "metadata": {"reasons": [{"code": "HOW_NIGHT_LIMIT_EXCEEDED"}]}},
    ]
    res = evaluate_persona_results("salaried", "Assalariada", "legitimate", responses)
    assert res.rejected == 1
    assert res.budget_passed is False
    assert "rejeição indevida" in res.budget_notes.lower()


def test_evaluate_persona_results_legitimate_fail_on_high_2fa():
    responses = [
        {"status": "approved", "metadata": {"reasons": []}} for _ in range(8)
    ] + [
        {"status": "two_factor_required", "metadata": {"reasons": []}} for _ in range(2)
    ]
    res = evaluate_persona_results("salaried", "Assalariada", "legitimate", responses)
    assert res.two_factor == 2
    assert res.budget_passed is False
    assert "2fa acima do limite" in res.budget_notes.lower()


def test_format_farm_report_table():
    res1 = evaluate_persona_results("salaried", "Assalariada", "legitimate", [
        {"status": "approved", "metadata": {"reasons": []}} for _ in range(5)
    ])
    res2 = evaluate_persona_results("fan_in", "Fan-in", "fraud", [
        {"status": "approved", "metadata": {"reasons": []}},
        {"status": "approved", "metadata": {"reasons": []}},
        {"status": "rejected", "metadata": {"reasons": [{"code": "WHERE_DESTINATION_FAN_IN"}]}},
    ])
    report = build_farm_report(policy_version="2026.10.18-1", personas_results=[res1, res2])
    table = format_farm_report_table(report)

    assert "2026.10.18-1" in table
    assert "Assalariada" in table
    assert "Fan-in" in table
    assert "TOTAL" in table
    assert "WHERE_DESTINATION_FAN_IN" in table


def test_run_farm_against_live_api():
    report = run_farm(base_url="http://localhost:8001", token="internal-token-dev")
    assert report.total_transactions > 0
    assert report.policy_version.startswith("2026.10.18")
    legitimate_results = [p for p in report.personas if p.kind == "legitimate"]
    for p in legitimate_results:
        assert p.rejected == 0, f"Persona {p.name} had rejections: {p}"
        assert p.budget_passed is True
