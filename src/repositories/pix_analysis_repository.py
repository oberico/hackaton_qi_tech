from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AnalysisStatus, DecisionBasis, PixAnalysis


class PixAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        pix_transaction_id: int,
        status: str,
        decision_basis: str,
        policy_version: str,
        payer_maturity_phase: int,
        features: dict,
        latency_ms: int,
    ) -> PixAnalysis:
        pix_analysis = PixAnalysis(
            pix_transaction_id=pix_transaction_id,
            status_id=select(AnalysisStatus.id).where(AnalysisStatus.enumerator == status).scalar_subquery(),
            decision_basis_id=select(DecisionBasis.id).where(DecisionBasis.enumerator == decision_basis).scalar_subquery(),
            policy_version=policy_version,
            payer_maturity_phase=payer_maturity_phase,
            features=features,
            latency_ms=latency_ms,
        )
        self.session.add(pix_analysis)
        self.session.flush()
        self.session.refresh(pix_analysis)
        return pix_analysis
