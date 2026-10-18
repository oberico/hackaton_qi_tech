from models import PixAnalysis


class PixAnalysisDto:
    @staticmethod
    def from_analysis(pix_analysis: PixAnalysis, status: str) -> dict:
        return {"key": str(pix_analysis.analysis_key), "status": status}
