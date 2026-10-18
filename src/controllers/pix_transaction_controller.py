import os
import time
from datetime import datetime

from sqlalchemy.orm import Session

from constants import SCHEMAS_DIR
from dtos import PixAnalysisDto
from engine import policy
from engine.risk_context import AxisResult, Decision, DecisionBasis, EngineResult, Flow, PersonType, RiskLevel
from repositories import (
    AccountHolderRepository,
    AccountRepository,
    PixAnalysisAxisRepository,
    PixAnalysisRepository,
    PixParticipantRepository,
    PixTransactionRepository,
)
from utils.payload_hash import payload_hash
from utils.schema_handler import validate_json

POST_SCHEMA_PATH = os.path.join(SCHEMAS_DIR, "post_pix_transaction.json")
OWN_PARTICIPANT = os.environ.get("OWN_PARTICIPANT", "99999999")


def _fake_engine_result() -> EngineResult:
    return EngineResult(
        decision=Decision.APPROVED,
        decision_basis=DecisionBasis.CLEAN,
        who=AxisResult(level=RiskLevel.OK),
        how=AxisResult(level=RiskLevel.OK),
        where=AxisResult(level=RiskLevel.OK),
        floors=[],
        trust_signals=[],
        maturity_phase=0,
        policy_version=policy.POLICY_VERSION,
        evaluated_rules=[],
    )


FLOWS = {
    (PersonType.INDIVIDUAL, PersonType.INDIVIDUAL): Flow.PF_PF,
    (PersonType.INDIVIDUAL, PersonType.COMPANY): Flow.PF_PJ,
    (PersonType.COMPANY, PersonType.INDIVIDUAL): Flow.PJ_PF,
    (PersonType.COMPANY, PersonType.COMPANY): Flow.PJ_PJ,
}


def _features(result: EngineResult, flow: Flow) -> dict:
    axes = (result.who, result.how, result.where)
    return {
        "flow": flow.value,
        "reasons": [
            {
                "code": rule.code,
                "axis": rule.axis,
                "level": rule.level.value,
                "observed": rule.observed,
                "threshold": rule.threshold,
                "description": rule.description,
                "translation": rule.translation,
            }
            for axis in axes
            for rule in axis.rules
        ],
        "floors": result.floors,
        "trust": result.trust_signals,
    }


def _person_type(document_number: str) -> PersonType:
    return PersonType.COMPANY if "/" in document_number else PersonType.INDIVIDUAL


def _utc_offset_minutes(moment: datetime) -> int:
    return int(moment.utcoffset().total_seconds() // 60)


class PixTransactionController:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.participants = PixParticipantRepository(session)
        self.holders = AccountHolderRepository(session)
        self.accounts = AccountRepository(session)
        self.transactions = PixTransactionRepository(session)
        self.analyses = PixAnalysisRepository(session)
        self.axes = PixAnalysisAxisRepository(session)

    def create(self, payload: dict) -> dict:
        started_at = time.perf_counter()
        validate_json(payload, POST_SCHEMA_PATH)

        source_account = self._upsert_account(OWN_PARTICIPANT, payload["source_account"])
        destination_account = self._upsert_account(
            payload["destination_account"]["participant"], payload["destination_account"]
        )
        transaction_date = datetime.fromisoformat(payload["transaction_date"])
        source = payload["source"]
        geolocation = source.get("geolocation") or {}
        pix_transaction = self.transactions.create(
            transaction_id=payload["id"],
            payload_hash=payload_hash(payload),
            amount_minor=payload["amount"],
            transaction_date=transaction_date,
            utc_offset_minutes=_utc_offset_minutes(transaction_date),
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            device_id=source["device_id"],
            channel=source["channel"],
            ip_address=source["ip"],
            latitude=geolocation.get("latitude"),
            longitude=geolocation.get("longitude"),
            raw_payload=payload,
        )

        flow = FLOWS[
            (
                _person_type(payload["source_account"]["owner"]["document_number"]),
                _person_type(payload["destination_account"]["owner"]["document_number"]),
            )
        ]
        result = _fake_engine_result()
        pix_analysis = self.analyses.create(
            pix_transaction_id=pix_transaction.id,
            status=result.decision.value,
            decision_basis=result.decision_basis.value,
            policy_version=result.policy_version,
            payer_maturity_phase=result.maturity_phase,
            features=_features(result, flow),
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )
        self.axes.create_all(
            pix_analysis.id,
            {"who": result.who.level.value, "how": result.how.level.value, "where": result.where.level.value},
        )
        self.session.commit()
        return self._to_dto(pix_analysis.id)

    def _to_dto(self, pix_analysis_id: int) -> dict:
        pix_analysis, status, decision_basis = self.analyses.find_by_id(pix_analysis_id)
        return PixAnalysisDto.from_records(
            pix_analysis, status, decision_basis, self.axes.levels_by_analysis(pix_analysis_id)
        )

    def _upsert_account(self, ispb: str, account_data: dict):
        participant = self.participants.find_by_ispb(ispb)
        holder = self.holders.get_or_create(
            account_data["owner"]["document_number"], _person_type(account_data["owner"]["document_number"]).value
        )
        return self.accounts.get_or_create(
            participant_id=participant.id,
            branch=account_data["branch"],
            account_number=account_data["account_number"],
            account_holder_id=holder.id,
            opening_date=datetime.fromisoformat(account_data["opening_date"]),
        )
