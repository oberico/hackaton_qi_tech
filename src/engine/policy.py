from src.engine.risk_context import Flow

POLICY_VERSION = "2026.10.18-1"

RULE_CODES = {
    "how": (
        "HOW_NIGHT_LIMIT_EXCEEDED",
        "HOW_VELOCITY_EXCEEDED",
        "HOW_ABOVE_CUSTOMER_CEILING",
        "HOW_EARLY_MORNING_AMOUNT",
        "HOW_RETRY_AFTER_REJECTION",
        "HOW_TEST_PIX",
    ),
    "who": ("WHO_DEVICE_COMPROMISED", "WHO_DEVICE_UNKNOWN", "WHO_AGGRAVATING_SIGNALS"),
    "where": (
        "WHERE_DESTINATION_NEW_ACCOUNT",
        "WHERE_UNKNOWN_PARTICIPANT",
        "WHERE_DESTINATION_FAN_IN",
        "WHERE_DESTINATION_REJECTIONS",
    ),
    "floor": ("FLOOR_UNREGISTERED_DEVICE", "FLOOR_NIGHT_LIMIT"),
    "trust": ("TRUST_RECURRENT_BENEFICIARY", "TRUST_MATURE_SELF_PIX"),
}

NIGHT_START_HOUR = 20
NIGHT_END_HOUR = 6
NIGHT_LIMIT_MINOR = {
    Flow.PF_PF: 100000,
    Flow.PF_PJ: None,
    Flow.PJ_PF: None,
    Flow.PJ_PJ: None,
}

UNKNOWN_DEVICE_TX_LIMIT_MINOR = {
    Flow.PF_PF: 20000,
    Flow.PF_PJ: 20000,
    Flow.PJ_PF: None,
    Flow.PJ_PJ: None,
}
UNKNOWN_DEVICE_DAILY_LIMIT_MINOR = {
    Flow.PF_PF: 100000,
    Flow.PF_PJ: 100000,
    Flow.PJ_PF: None,
    Flow.PJ_PJ: None,
}

EARLY_MORNING_START_HOUR = 0
EARLY_MORNING_END_HOUR = 6

MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS = 30

REFERENCE_CEILING_NEW_ACCOUNT_DAYS = 90
REFERENCE_CEILING_MINOR = {
    "individual_new_account": 100000,
    "individual": 300000,
    "company": 2000000,
}

HISTORY_WINDOW_DAYS = 90
HISTORY_PERCENTILE = 0.95
HISTORY_MARGIN = 1.5
SHRINKAGE_K = 5

VELOCITY_10MIN = {
    Flow.PF_PF: {"suspicious": 3, "critical": 6},
    Flow.PF_PJ: {"suspicious": 3, "critical": 6},
    Flow.PJ_PF: {"suspicious": 20, "critical": 40},
    Flow.PJ_PJ: {"suspicious": 20, "critical": 40},
}

FAN_IN_CRITICAL_PAYERS_24H = {
    Flow.PF_PF: 3,
    Flow.PF_PJ: 10,
    Flow.PJ_PF: 3,
    Flow.PJ_PJ: 10,
}

MATURE_PAYER_MIN_APPROVED = 5
MATURE_PAYER_MIN_RELATIONSHIP_DAYS = 30

TRUST_DOWNGRADE_AXIS_ORDER = ("where", "how", "who")
