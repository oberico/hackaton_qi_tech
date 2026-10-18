from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List

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


def generate_destination_fan_in_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    dest_doc = deterministic_cpf(seed_int + 99999)
    dest_acct = f"{(seed_int % 800000000 + 200000000):010d}"
    dest_opening_date = "2026-10-10T08:00:00-03:00"

    base_date = datetime(2026, 10, 17, 14, 0, tzinfo=BRASILIA_TZ)
    payloads = []

    for i in range(3):
        payer_doc = deterministic_cpf(seed_int + 1000 + i * 53)
        payer_acct = f"{(seed_int + 10000 + i * 31) % 800000000 + 100000000:010d}"
        device_id = f"dvc-fanin-{seed}-{i}"
        tx_date = base_date + timedelta(minutes=10 * i)

        payloads.append({
            "id": f"pix-fanin-{seed}-{i}",
            "amount": 4000 + i * 500,
            "transaction_date": tx_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": payer_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": payer_doc},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": dest_acct,
                "opening_date": dest_opening_date,
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


def generate_company_payroll_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    company_cnpj = deterministic_cnpj(seed_int)
    company_acct = f"{(seed_int % 800000000 + 300000000):010d}"
    device_id = f"dvc-company-{seed}"

    base_date = datetime(2026, 10, 15, 10, 0, tzinfo=BRASILIA_TZ)
    payloads = []

    for i in range(10):
        employee_cpf = deterministic_cpf(seed_int + 2000 + i * 29)
        employee_acct = f"{(seed_int + 30000 + i * 47) % 800000000 + 100000000:010d}"
        ispb = LISTED_PARTICIPANTS[i % len(LISTED_PARTICIPANTS)]
        amount = 180000 + (i * 15000)
        tx_date = base_date + timedelta(minutes=2 * i)

        payloads.append({
            "id": f"pix-payroll-{seed}-{i}",
            "amount": amount,
            "transaction_date": tx_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": company_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": company_cnpj},
            },
            "destination_account": {
                "participant": ispb,
                "branch": "3675",
                "account_number": employee_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": employee_cpf},
            },
            "source": {
                "device_id": device_id,
                "channel": "web",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        })

    return payloads


def generate_mature_self_pix_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    owner_cpf = deterministic_cpf(seed_int + 777)
    source_acct = f"{(seed_int % 800000000 + 400000000):010d}"
    dest_acct = f"{(seed_int % 800000000 + 400000001):010d}"
    device_id = f"dvc-self-{seed}"

    base_date = datetime(2026, 10, 14, 14, 0, tzinfo=BRASILIA_TZ)
    payloads = []

    for i in range(3):
        tx_date = base_date + timedelta(days=i, minutes=10 * i)
        payloads.append({
            "id": f"pix-self-{seed}-{i}",
            "amount": 8000 + i * 2000,
            "transaction_date": tx_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": source_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": owner_cpf},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": dest_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": owner_cpf},
            },
            "source": {
                "device_id": device_id,
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        })

    return payloads


def generate_device_compromised_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    shared_device = f"dvc-compromised-{seed}"
    base_date = datetime(2026, 10, 16, 10, 0, tzinfo=BRASILIA_TZ)

    payloads = []
    for i in range(3):
        payer_cpf = deterministic_cpf(seed_int + 5000 + i * 67)
        payer_acct = f"{(seed_int + 60000 + i * 41) % 800000000 + 100000000:010d}"
        dest_cpf = deterministic_cpf(seed_int + 7000 + i * 13)
        dest_acct = f"{(seed_int + 80000 + i * 17) % 800000000 + 100000000:010d}"
        tx_date = base_date + timedelta(hours=i * 2)

        payloads.append({
            "id": f"pix-dvc-comp-{seed}-{i}",
            "amount": 4000,
            "transaction_date": tx_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": payer_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": payer_cpf},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": dest_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": dest_cpf},
            },
            "source": {
                "device_id": shared_device,
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        })

    return payloads


def generate_probe_after_rejection_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    payer_cpf = deterministic_cpf(seed_int + 888)
    payer_acct = f"{(seed_int % 800000000 + 500000000):010d}"
    device_id = f"dvc-probe-{seed}"

    # Pix 1: Night PF->PF R$ 1.500 to new account (< 30 days) -> rejected
    # Pix 2: 3 minutes later, same payer sends R$ 150 to old account -> retry after rejection (suspicious)
    dest_new_doc = deterministic_cpf(seed_int + 8881)
    dest_new_acct = f"{(seed_int + 12345) % 800000000 + 100000000:010d}"
    dest_old_doc = deterministic_cpf(seed_int + 8882)
    dest_old_acct = f"{(seed_int + 54321) % 800000000 + 100000000:010d}"

    tx1_date = datetime(2026, 10, 17, 22, 15, tzinfo=BRASILIA_TZ)
    tx2_date = datetime(2026, 10, 17, 22, 18, tzinfo=BRASILIA_TZ)

    return [
        {
            "id": f"pix-probe-{seed}-0",
            "amount": 150000,
            "transaction_date": tx1_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": payer_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": payer_cpf},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": dest_new_acct,
                "opening_date": "2026-10-10T08:00:00-03:00",
                "owner": {"document_number": dest_new_doc},
            },
            "source": {
                "device_id": device_id,
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        },
        {
            "id": f"pix-probe-{seed}-1",
            "amount": 15000,
            "transaction_date": tx2_date.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": payer_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": payer_cpf},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": dest_old_acct,
                "opening_date": OLD_OPENING_DATE,
                "owner": {"document_number": dest_old_doc},
            },
            "source": {
                "device_id": device_id,
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        },
    ]


def generate_night_high_amount_persona(seed: str) -> List[dict]:
    seed_int = abs(hash(seed))
    payer_cpf = deterministic_cpf(seed_int + 999)
    payer_acct = f"{(seed_int % 800000000 + 600000000):010d}"
    dest_doc = deterministic_cpf(seed_int + 9991)
    dest_acct = f"{(seed_int + 77777) % 800000000 + 100000000:010d}"

    tx_date = datetime(2026, 10, 17, 22, 30, tzinfo=BRASILIA_TZ)

    return [{
        "id": f"pix-night-{seed}-0",
        "amount": 150000,
        "transaction_date": tx_date.isoformat(),
        "source_account": {
            "branch": "0001",
            "account_number": payer_acct,
            "opening_date": OLD_OPENING_DATE,
            "owner": {"document_number": payer_cpf},
        },
        "destination_account": {
            "participant": "60701190",
            "branch": "3675",
            "account_number": dest_acct,
            "opening_date": "2026-10-10T08:00:00-03:00",
            "owner": {"document_number": dest_doc},
        },
        "source": {
            "device_id": f"dvc-night-{seed}",
            "channel": "app",
            "ip": "198.51.100.23",
            "geolocation": {"latitude": -23.56, "longitude": -46.65},
        },
    }]


ALL_PERSONAS = [
    Persona(
        code="salaried_individual",
        name="Assalariada PF (horário comercial)",
        kind="legitimate",
        description="Paga contas e amigos em horário comercial com valores baixos e médios.",
        generator=generate_salaried_individual_persona,
    ),
    Persona(
        code="company_payroll",
        name="PJ Pagamento de Folha",
        kind="legitimate",
        description="Empresa pagando salários a múltiplos funcionários em horário comercial.",
        generator=generate_company_payroll_persona,
    ),
    Persona(
        code="mature_self_pix",
        name="Self-Pix Maduro",
        kind="legitimate",
        description="Transferências entre contas próprias abertas há mais de 30 dias.",
        generator=generate_mature_self_pix_persona,
    ),
    Persona(
        code="destination_fan_in",
        name="Campanha Fan-in (Conta Laranja)",
        kind="fraud",
        description="Múltiplos pagadores enviando para uma conta de destino recém-aberta em 24h.",
        generator=generate_destination_fan_in_persona,
    ),
    Persona(
        code="device_compromised",
        name="Dispositivo Compartilhado (Mula)",
        kind="fraud",
        description="Mesmo aparelho usado por 3 titulares distintos em sequência.",
        generator=generate_device_compromised_persona,
    ),
    Persona(
        code="probe_after_rejection",
        name="Sondagem pós-rejeição",
        kind="fraud",
        description="Tentativa de menor valor logo após rejeição em menos de 10 minutos.",
        generator=generate_probe_after_rejection_persona,
    ),
    Persona(
        code="night_high_amount",
        name="Noturno PF→PF de Alto Valor",
        kind="fraud",
        description="Pix de R$ 1.500 no período noturno para conta recém-aberta.",
        generator=generate_night_high_amount_persona,
    ),
]
