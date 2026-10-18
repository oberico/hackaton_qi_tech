import time
from datetime import datetime
from typing import Tuple

from constants import OWN_PARTICIPANT
from controllers.base_controller import BaseController
from controllers.risk_context_builder import build_risk_context, person_type_of, utc_offset_minutes_of
from dtos import PixAnalysisDto
from errors import PixIdReusedWithDifferentPayload
from repositories import (
    AccountHolderRepository,
    AccountRepository,
    PixAnalysisAxisRepository,
    PixAnalysisRepository,
    PixAnalysisRuleRepository,
    PixParticipantRepository,
    PixTransactionRepository,
    RiskHistoryRepository,
)
from src.engine.engine import evaluate
from src.engine.risk_context import EngineResult, RiskContext
from utils.payload_hash import payload_hash


def _features(result: EngineResult, context: RiskContext) -> dict:
    axes = (result.who, result.how, result.where)
    return {
        "flow": context.transaction.flow.value,
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


def _transaction_fields(payload: dict) -> dict:
    transaction_date = datetime.fromisoformat(payload["transaction_date"])
    source = payload["source"]
    geolocation = source.get("geolocation") or {}
    return {
        "transaction_id": payload["id"],
        "payload_hash": payload_hash(payload),
        "amount_minor": payload["amount"],
        "transaction_date": transaction_date,
        "utc_offset_minutes": utc_offset_minutes_of(transaction_date),
        "device_id": source["device_id"],
        "channel": source["channel"],
        "ip_address": source["ip"],
        "latitude": geolocation.get("latitude"),
        "longitude": geolocation.get("longitude"),
        "raw_payload": payload,
    }


class PixTransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.participants = PixParticipantRepository(self.context)
        self.holders = AccountHolderRepository(self.context)
        self.accounts = AccountRepository(self.context)
        self.transactions = PixTransactionRepository(self.context)
        self.analyses = PixAnalysisRepository(self.context)
        self.axes = PixAnalysisAxisRepository(self.context)
        self.rules = PixAnalysisRuleRepository(self.context)
        self.history = RiskHistoryRepository(self.context)

    def create(self, payload: dict) -> Tuple[dict, bool]:
        started_at = time.perf_counter()
        source_account, _ = self._upsert_account(OWN_PARTICIPANT, payload["source_account"])
        destination_account, destination_participant = self._upsert_account(
            payload["destination_account"]["participant"], payload["destination_account"]
        )
        pix_transaction = self.transactions.create(
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            **_transaction_fields(payload),
        )
        if pix_transaction is None:
            return self._replay(payload), False
        context = build_risk_context(payload, source_account, destination_account, destination_participant, self.history)
        result = evaluate(context)
        pix_analysis = self._record_analysis(pix_transaction.id, result, context, started_at)
        self.session.commit()
        return self._to_dto(pix_analysis.id), True

    def _replay(self, payload: dict) -> dict:
        existing = self.transactions.find_by_transaction_id(payload["id"])
        if existing.payload_hash != payload_hash(payload):
            raise PixIdReusedWithDifferentPayload()
        return self._to_dto(self.analyses.find_id_by_pix_transaction_id(existing.id))

    def _record_analysis(self, pix_transaction_id: int, result: EngineResult, context: RiskContext, started_at: float):
        pix_analysis = self.analyses.create(
            pix_transaction_id=pix_transaction_id,
            status=result.decision.value,
            decision_basis=result.decision_basis.value,
            policy_version=result.policy_version,
            payer_maturity_phase=result.maturity_phase,
            features=_features(result, context),
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )
        self.axes.create_all(
            pix_analysis.id,
            {"who": result.who.level.value, "how": result.how.level.value, "where": result.where.level.value},
        )
        self.rules.create_all(pix_analysis.id, result.evaluated_rules)
        return pix_analysis

    def _to_dto(self, pix_analysis_id: int) -> dict:
        pix_analysis, status, decision_basis = self.analyses.find_by_id(pix_analysis_id)
        return PixAnalysisDto.from_records(
            pix_analysis, status, decision_basis, self.axes.levels_by_analysis(pix_analysis_id)
        )

    def _upsert_account(self, ispb: str, account_data: dict):
        participant = self.participants.get_or_create(ispb)
        holder = self.holders.get_or_create(
            account_data["owner"]["document_number"], person_type_of(account_data["owner"]["document_number"]).value
        )
        account = self.accounts.get_or_create(
            participant_id=participant.id,
            branch=account_data["branch"],
            account_number=account_data["account_number"],
            account_holder_id=holder.id,
            opening_date=datetime.fromisoformat(account_data["opening_date"]),
        )
        return account, participant
