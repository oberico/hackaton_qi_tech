import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from src.engine import trust
from src.engine.analyzers import how, where, who
from src.engine.risk_context import (
    BeneficiaryRelationship,
    DestinationHistory,
    DeviceHistory,
    DeviceTrust,
    Flow,
    IpHistory,
    PayerHistory,
    PersonType,
    RiskContext,
    RiskLevel,
    TransactionFacts,
)
from src.engine.rules import fired

DEFAULT_UTC_OFFSET_MINUTES = -180
ANALYZERS = {"who": who, "how": how, "where": where}


def local_datetime(hour, minute=0, utc_offset_minutes=DEFAULT_UTC_OFFSET_MINUTES, day=17):
    zone = timezone(timedelta(minutes=utc_offset_minutes))
    return datetime(2026, 10, day, hour, minute, tzinfo=zone)


def build_default_context():
    return RiskContext(
        transaction=TransactionFacts(
            amount=5000,
            transaction_date=local_datetime(14),
            utc_offset_minutes=DEFAULT_UTC_OFFSET_MINUTES,
            source_person_type=PersonType.INDIVIDUAL,
            destination_person_type=PersonType.INDIVIDUAL,
            flow=Flow.PF_PF,
            same_owner=False,
            destination_participant_listed=True,
            source_account_age_days=400,
            destination_account_age_days=400,
            device_id="device-1",
            channel="mobile",
            ip_address="200.10.10.10",
            ip_is_private=False,
            geolocation=None,
        ),
        payer=PayerHistory(
            approved_count=0,
            relationship_days=0,
            approved_amounts_90d=[],
            transactions_last_10min=0,
            night_amount_to_individuals=0,
            unknown_device_amount_today=0,
            small_amount_to_destination_last_15min=False,
            early_morning_share=0.0,
            last_rejection_at=None,
            last_rejected_amount=None,
            known_devices_count=0,
            device_trust=DeviceTrust.UNKNOWN,
            known_channels=[],
            usually_sends_geolocation=False,
            known_geolocations=[],
        ),
        beneficiary=BeneficiaryRelationship(approved_count=0, first_approved_at=None),
        device=DeviceHistory(distinct_documents_total=0, distinct_documents_24h=0),
        destination=DestinationHistory(distinct_payers_24h=0, rejections_from_distinct_payers_24h=0),
        ip=IpHistory(distinct_payers_1h=0),
    )


def make_context(**overrides):
    context = build_default_context()
    for section, changes in overrides.items():
        if dataclasses.is_dataclass(getattr(context, section)):
            context = dataclasses.replace(context, **{section: dataclasses.replace(getattr(context, section), **changes)})
        else:
            context = dataclasses.replace(context, **{section: changes})
    return context


def stub_rules(axis, level):
    if level == RiskLevel.OK:
        return []
    return [fired(f"{axis.upper()}_STUB", axis, level, {}, {}, "stub", "stub")]


def rule_of(result, code):
    matches = [rule for rule in result.evaluated_rules if rule.code == code]
    assert len(matches) == 1, f"{code} was not evaluated exactly once"
    return matches[0]


@pytest.fixture
def stub_axes(monkeypatch):
    def apply(who_level, how_level, where_level):
        for axis, level in (("who", who_level), ("how", how_level), ("where", where_level)):
            monkeypatch.setattr(ANALYZERS[axis], "analyze", lambda context, axis=axis, level=level: stub_rules(axis, level))

    return apply


@pytest.fixture
def stub_trust_signals(monkeypatch):
    def apply(signals):
        monkeypatch.setattr(trust, "detect_signals", lambda context: list(signals))

    return apply
