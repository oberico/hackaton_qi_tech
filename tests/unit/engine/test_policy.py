from src.engine import policy
from src.engine.risk_context import Flow

EXPECTED_RULE_CODES = {
    "how": {
        "HOW_NIGHT_LIMIT_EXCEEDED",
        "HOW_VELOCITY_EXCEEDED",
        "HOW_ABOVE_CUSTOMER_CEILING",
        "HOW_EARLY_MORNING_AMOUNT",
        "HOW_RETRY_AFTER_REJECTION",
        "HOW_TEST_PIX",
    },
    "who": {"WHO_DEVICE_COMPROMISED", "WHO_DEVICE_UNKNOWN", "WHO_AGGRAVATING_SIGNALS"},
    "where": {
        "WHERE_DESTINATION_NEW_ACCOUNT",
        "WHERE_UNKNOWN_PARTICIPANT",
        "WHERE_DESTINATION_FAN_IN",
        "WHERE_DESTINATION_REJECTIONS",
    },
    "floor": {"FLOOR_UNREGISTERED_DEVICE", "FLOOR_NIGHT_LIMIT"},
    "trust": {"TRUST_RECURRENT_BENEFICIARY", "TRUST_MATURE_SELF_PIX"},
}


def test_policy_version_is_declared():
    assert policy.POLICY_VERSION == "2026.10.18-1"


def test_every_catalog_rule_code_is_declared_by_axis():
    declared = {axis: set(codes) for axis, codes in policy.RULE_CODES.items()}
    assert declared == EXPECTED_RULE_CODES


def test_per_flow_parameters_are_indexed_by_all_four_flows():
    for table in (
        policy.NIGHT_LIMIT_MINOR,
        policy.UNKNOWN_DEVICE_TX_LIMIT_MINOR,
        policy.UNKNOWN_DEVICE_DAILY_LIMIT_MINOR,
        policy.VELOCITY_10MIN,
        policy.FAN_IN_CRITICAL_PAYERS_24H,
    ):
        assert set(table) == set(Flow)


def test_night_limit_applies_only_to_individual_to_individual():
    assert policy.NIGHT_LIMIT_MINOR[Flow.PF_PF] == 100000
    assert policy.NIGHT_LIMIT_MINOR[Flow.PF_PJ] is None
    assert policy.NIGHT_LIMIT_MINOR[Flow.PJ_PF] is None
    assert policy.NIGHT_LIMIT_MINOR[Flow.PJ_PJ] is None


def test_unregistered_device_limits_apply_only_to_individual_payers():
    assert policy.UNKNOWN_DEVICE_TX_LIMIT_MINOR[Flow.PF_PF] == 20000
    assert policy.UNKNOWN_DEVICE_TX_LIMIT_MINOR[Flow.PF_PJ] == 20000
    assert policy.UNKNOWN_DEVICE_TX_LIMIT_MINOR[Flow.PJ_PF] is None
    assert policy.UNKNOWN_DEVICE_DAILY_LIMIT_MINOR[Flow.PF_PF] == 100000
    assert policy.UNKNOWN_DEVICE_DAILY_LIMIT_MINOR[Flow.PJ_PJ] is None


def test_decided_parameters_match_claude_md():
    assert (policy.NIGHT_START_HOUR, policy.NIGHT_END_HOUR) == (20, 6)
    assert (policy.EARLY_MORNING_START_HOUR, policy.EARLY_MORNING_END_HOUR) == (0, 6)
    assert policy.MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS == 30
    assert (policy.HISTORY_WINDOW_DAYS, policy.HISTORY_PERCENTILE, policy.HISTORY_MARGIN, policy.SHRINKAGE_K) == (90, 0.95, 1.5, 5)
    assert policy.VELOCITY_10MIN[Flow.PF_PF] == {"suspicious": 3, "critical": 6}
    assert policy.VELOCITY_10MIN[Flow.PJ_PJ] == {"suspicious": 20, "critical": 40}
    assert policy.FAN_IN_CRITICAL_PAYERS_24H == {Flow.PF_PF: 3, Flow.PF_PJ: 10, Flow.PJ_PF: 3, Flow.PJ_PJ: 10}
    assert policy.REFERENCE_CEILING_MINOR == {"individual_new_account": 100000, "individual": 300000, "company": 2000000}
    assert policy.REFERENCE_CEILING_NEW_ACCOUNT_DAYS == 90
