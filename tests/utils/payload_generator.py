import json
from pathlib import Path

CHALLENGE_EXAMPLE_PATH = Path(__file__).parent.parent / "fixtures" / "challenge_example_payload.json"


class PayloadGenerator:
    @staticmethod
    def challenge_example(**overrides) -> dict:
        payload = json.loads(CHALLENGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
        payload.update(overrides)
        return payload
