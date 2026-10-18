from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List

from tests.utils.random_generator import RandomGenerator

LISTED_PARTICIPANTS = ["60701190", "60746948", "00000000", "00360305"]
OLD_OPENING_DATE = "2024-01-15T08:00:00-03:00"
BRASILIA_TZ = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class Persona:
    code: str
    name: str
    kind: str
    description: str
    generator: Callable[[str], List[dict]]


def deterministic_cpf(seed: int) -> str:
    base = [int(c) for c in f"{abs(seed) % 1000000000:09d}"]
    for n in (9, 10):
        total = sum(d * w for d, w in zip(base, range(n + 1, 1, -1)))
        base.append((total * 10 % 11) % 10)
    s = "".join(map(str, base))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def deterministic_cnpj(seed: int) -> str:
    base = [int(c) for c in f"{abs(seed) % 100000000:08d}"] + [0, 0, 0, 1]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        total = sum(d * w for d, w in zip(base, weights))
        rest = total % 11
        base.append(0 if rest < 2 else 11 - rest)
    s = "".join(map(str, base))
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


def generate_salaried_individual_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    payer_cpf = deterministic_cpf(seed_int)
    payer_account = f"{(seed_int % 900000000 + 100000000):010d}"
    device_id = f"dvc-salaried-{seed}"

    destinations = [
        (
            deterministic_cpf(seed_int + 1000 + i * 37),
            f"{(seed_int + 5000 + i * 19) % 900000000 + 100000000:010d}",
            LISTED_PARTICIPANTS[i % len(LISTED_PARTICIPANTS)],
        )
        for i in range(5)
    ]

    base_date = datetime(2026, 10, 12, 10, 30, tzinfo=BRASILIA_TZ)
    amounts = [4500, 7800, 12000, 18500, 19900]

    payloads = []
    for i in range(5):
        tx_date = base_date + timedelta(days=i, hours=i % 3, minutes=15 * i)
        dest_doc, dest_acct, ispb = destinations[i]
        payloads.append({
            "id": f"pix-salaried-{seed}-{i}",
            "amount": amounts[i],
            "transaction_date": tx_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": payer_account,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": payer_cpf},
            },
            "destination_account": {
                "participant": ispb,
                "branch": "3675",
                "account_number": dest_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": dest_doc},
            },
            "source": {
                "device_id": device_id,
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        })

    return payloads
