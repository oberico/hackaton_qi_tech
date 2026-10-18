from typing import Dict

from models import PixAnalysis


class PixAnalysisDto:
    @staticmethod
    def from_records(pix_analysis: PixAnalysis, status: str, decision_basis: str, axes: Dict[str, str]) -> dict:
        features = pix_analysis.features
        return {
            "key": str(pix_analysis.analysis_key),
            "status": status,
            "metadata": {
                "policy_version": pix_analysis.policy_version,
                "flow": features["flow"],
                "payer_maturity_phase": pix_analysis.payer_maturity_phase,
                "decision_basis": decision_basis,
                "axes": axes,
                "reasons": features["reasons"],
                "floors": features["floors"],
                "trust": features["trust"],
            },
        }
