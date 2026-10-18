from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PersonType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class RiskLevel(str, Enum):
    OK = "ok"
    SUSPICIOUS = "suspicious"
    CRITICAL = "critical"


class Decision(str, Enum):
    APPROVED = "approved"
    TWO_FACTOR_REQUIRED = "two_factor_required"
    REJECTED = "rejected"


class Flow(str, Enum):
    PF_PF = "pf_pf"
    PF_PJ = "pf_pj"
    PJ_PF = "pj_pf"
    PJ_PJ = "pj_pj"


class DeviceTrust(str, Enum):
    UNKNOWN = "unknown"
    OBSERVING = "observing"
    TRUSTED = "trusted"


@dataclass(frozen=True)
class Geolocation:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class TransactionFacts:
    amount: int
    transaction_date: datetime
    utc_offset_minutes: int
    source_person_type: PersonType
    destination_person_type: PersonType
    flow: Flow
    same_owner: bool
    destination_participant_listed: bool
    source_account_age_days: float
    destination_account_age_days: float
    device_id: str
    channel: str
    ip_address: str
    ip_is_private: bool
    geolocation: Optional[Geolocation]


@dataclass(frozen=True)
class PayerHistory:
    approved_count: int
    relationship_days: float
    approved_amounts_90d: List[int]
    transactions_last_10min: int
    night_amount_to_individuals: int
    unknown_device_amount_today: int
    small_amount_to_destination_last_15min: bool
    early_morning_share: float
    last_rejection_at: Optional[datetime]
    last_rejected_amount: Optional[int]
    known_devices_count: int
    device_trust: DeviceTrust
    known_channels: List[str]
    usually_sends_geolocation: bool
    known_geolocations: List[Geolocation]


@dataclass(frozen=True)
class BeneficiaryRelationship:
    approved_count: int
    first_approved_at: Optional[datetime]


@dataclass(frozen=True)
class DeviceHistory:
    distinct_documents_total: int
    distinct_documents_24h: int


@dataclass(frozen=True)
class DestinationHistory:
    distinct_payers_24h: int
    rejections_from_distinct_payers_24h: int


@dataclass(frozen=True)
class IpHistory:
    distinct_payers_1h: int


@dataclass(frozen=True)
class RiskContext:
    transaction: TransactionFacts
    payer: PayerHistory
    beneficiary: BeneficiaryRelationship
    device: DeviceHistory
    destination: DestinationHistory
    ip: IpHistory
    ip_country: Optional[str] = None


@dataclass(frozen=True)
class TriggeredRule:
    code: str
    axis: str
    level: RiskLevel
    observed: Dict[str, Any]
    threshold: Dict[str, Any]
    description: str
    translation: str


class RuleOutcome(str, Enum):
    FIRED = "fired"
    NOT_FIRED = "not_fired"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EvaluatedRule:
    code: str
    axis: str
    outcome: RuleOutcome
    level: Optional[RiskLevel]
    observed: Optional[Dict[str, Any]]
    threshold: Optional[Dict[str, Any]]
    description: str
    translation: str


@dataclass(frozen=True)
class AxisResult:
    level: RiskLevel
    rules: List[TriggeredRule] = field(default_factory=list)


class DecisionBasis(str, Enum):
    CRITICAL_AXIS = "critical_axis"
    TWO_SUSPICIOUS_AXES = "two_suspicious_axes"
    SINGLE_SUSPICIOUS_AXIS = "single_suspicious_axis"
    REGULATORY_FLOOR = "regulatory_floor"
    TRUST_DOWNGRADE = "trust_downgrade"
    CLEAN = "clean"


@dataclass(frozen=True)
class EngineResult:
    decision: Decision
    decision_basis: DecisionBasis
    who: AxisResult
    how: AxisResult
    where: AxisResult
    floors: List[str]
    trust_signals: List[str]
    maturity_phase: int
    policy_version: str
    evaluated_rules: List[EvaluatedRule]
