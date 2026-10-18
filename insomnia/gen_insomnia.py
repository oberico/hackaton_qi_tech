import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('out')
parser.add_argument('--base-url', default='http://localhost:8001')
parser.add_argument('--token', default='internal-token-dev')
parser.add_argument('--run', default='1001')
args = parser.parse_args()
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
BASE_URL = args.base_url
TOKEN = args.token


def cpf(seed):
    base = [int(c) for c in f"{seed:09d}"]
    for n in (9, 10):
        total = sum(d * w for d, w in zip(base, range(n + 1, 1, -1)))
        base.append((total * 10 % 11) % 10)
    s = "".join(map(str, base))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def cnpj(seed):
    base = [int(c) for c in f"{seed:08d}"] + [0, 0, 0, 1]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        total = sum(d * w for d, w in zip(base, weights))
        rest = total % 11
        base.append(0 if rest < 2 else 11 - rest)
    s = "".join(map(str, base))
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


OLD_OPENING = "2025-03-02T10:00:00-03:00"
DEST_OLD_OPENING = "2024-01-10T09:00:00-03:00"
DEST_NEW_OPENING = "2026-10-10T09:00:00-03:00"
DAY = "2026-10-17T14:00:00-03:00"
NIGHT = "2026-10-17T22:15:00-03:00"
LISTED = "60701190"
UNLISTED = "12345678"
OWN = "99999999"
RUN = args.run

ws = "wrk_antifraud_pix"
resources = []
sort = [0]


def next_sort():
    sort[0] += 1
    return -1000000 + sort[0] * 100


def folder(fid, name, description=""):
    resources.append({"_id": fid, "_type": "request_group", "parentId": ws, "name": name,
                      "description": description, "environment": {}, "metaSortKey": next_sort()})


def request(rid, parent, name, method, path, body=None, token=True, description=""):
    headers = []
    if body is not None:
        headers.append({"name": "Content-Type", "value": "application/json"})
    if token:
        headers.append({"name": "INTERNAL-TOKEN", "value": TOKEN})
    item = {"_id": rid, "_type": "request", "parentId": parent, "name": name, "method": method,
            "url": BASE_URL + path, "headers": headers, "description": description,
            "metaSortKey": next_sort(), "parameters": [], "authentication": {}}
    if body is not None:
        text = body if isinstance(body, str) else json.dumps(body, indent=2, ensure_ascii=False)
        item["body"] = {"mimeType": "application/json", "text": text}
    resources.append(item)


def payload(tx_id, amount, date, src, dst, device, ip="198.51.100.23", channel="app", geo=True, src_opening=OLD_OPENING):
    source = {"device_id": device, "channel": channel, "ip": ip}
    if geo:
        source["geolocation"] = {"latitude": -23.56, "longitude": -46.65}
    return {
        "id": tx_id,
        "amount": amount,
        "transaction_date": date,
        "source_account": {"branch": "0001", "account_number": src[0], "opening_date": src_opening,
                           "owner": {"document_number": src[1]}},
        "destination_account": {"participant": dst[0], "branch": "3675", "account_number": dst[1],
                                "opening_date": dst[3], "owner": {"document_number": dst[2]}},
        "source": source,
    }


def payer(n):
    return (f"{RUN}{n:02d}", cpf(100000000 + n * 7919))


def dest(n, new=False, participant=LISTED, company=False):
    doc = cnpj(20000000 + n * 31) if company else cpf(300000000 + n * 6007)
    return (participant, f"{RUN}9{n:02d}", doc, DEST_NEW_OPENING if new else DEST_OLD_OPENING)


resources.append({"_id": ws, "_type": "workspace", "parentId": None, "name": "Antifraude Pix RNV", "scope": "collection",
                  "description": "Coleção de testes manuais e de carga do motor antifraude. Suba a API com `docker compose up -d`; "
                                 "para repetir um cenário sem colidir com o histórico anterior, regere a coleção com outro --run (veja o README)."})
resources.append({"_id": "env_base", "_type": "environment", "parentId": ws, "name": "Base Environment", "metaSortKey": 1,
                  "data": {"base_url": BASE_URL, "internal_token": TOKEN, "run": RUN}, "dataPropertyOrder": {"&": ["base_url", "internal_token", "run"]},
                  "color": None, "isPrivate": False, "created": 1760760000000, "modified": 1760760000000})

# 0 health
folder("fld_health", "0. Saúde")
request("req_root", "fld_health", "GET /", "GET", "/", token=False)
request("req_health", "fld_health", "GET /health_check", "GET", "/health_check", token=False,
        description="Esperado: 200 {\"status\":\"ok\"}")

# 1 challenge
folder("fld_challenge", "1. Payload do desafio")
challenge = payload("pix-000123", 150000, NIGHT, ("88213", "123.456.789-09"),
                    (LISTED, "10442", "987.654.321-00", DEST_NEW_OPENING), "dvc-9f2c71a8")
challenge["source_account"]["opening_date"] = "2025-03-02T10:00:00-03:00"
challenge["destination_account"]["branch"] = "3675"
request("req_challenge", "fld_challenge", "POST payload do desafio (id fixo pix-000123)", "POST", "/pix/transaction", challenge,
        description="Esperado: 201 rejected, decision_basis two_suspicious_axes (how: noturno PF→PF acima de R$ 1.000; where: destino aberto há 7 dias). "
                    "Repetir o mesmo envio devolve 200 com a mesma análise (idempotência).")
request("req_challenge_get", "fld_challenge", "GET pix-000123", "GET", "/pix/transaction/pix-000123",
        description="Esperado: 200 com o mesmo key/status/metadata do POST.")

# 2 idempotency
folder("fld_idem", "2. Idempotência")
idem_payload = payload(f"idem-{RUN}", 5000, DAY, payer(1), dest(1), f"dvc-idem-{RUN}")
idem_changed = json.loads(json.dumps(idem_payload))
idem_changed["amount"] = 5100
request(
    "req_idem_1", "fld_idem", "1. POST original", "POST", "/pix/transaction", idem_payload,
    description="Esperado: 201 (ou 200 se já rodou com este `run`).",
)
request("req_idem_2", "fld_idem", "2. POST repetido idêntico", "POST", "/pix/transaction", idem_payload, description="Esperado: 200, mesma key.")
request("req_idem_3", "fld_idem", "3. POST mesmo id, amount diferente", "POST", "/pix/transaction", idem_changed, description="Esperado: 422 RNV001024.")
request("req_idem_get", "fld_idem", "4. GET", "GET", f"/pix/transaction/idem-{RUN}", description="Esperado: 200.")

# 3 format errors
folder("fld_format", "3. Erros de formato e token (400/403)")
base = payload(f"fmt-{RUN}", 5000, DAY, payer(2), dest(2), f"dvc-fmt-{RUN}")


def mutate(fn):
    clone = json.loads(json.dumps(base))
    fn(clone)
    return clone


def drop_amount(d):
    del d["amount"]


def add_extra(d):
    d["extra"] = 1


def bad_cpf(d):
    d["source_account"]["owner"]["document_number"] = "12345678909"


def zero_amount(d):
    d["amount"] = 0


def bad_date(d):
    d["transaction_date"] = "2026-10-17T14:00:00"


def bad_ispb(d):
    d["destination_account"]["participant"] = "1234567"


def bad_geo(d):
    d["source"]["geolocation"]["latitude"] = 91


request("req_f1", "fld_format", "Corpo que não é objeto", "POST", "/pix/transaction", "[1,2,3]", description="Esperado: 400 RNV000001")
request("req_f2", "fld_format", "Sem amount", "POST", "/pix/transaction", mutate(drop_amount), description="Esperado: 400 RNV000007")
request("req_f3", "fld_format", "Campo extra", "POST", "/pix/transaction", mutate(add_extra), description="Esperado: 400 RNV000008")
request("req_f4", "fld_format", "CPF sem máscara", "POST", "/pix/transaction", mutate(bad_cpf), description="Esperado: 400 RNV000009")
request("req_f5", "fld_format", "Data sem fuso", "POST", "/pix/transaction", mutate(bad_date), description="Esperado: 400 RNV000009")
request("req_f6", "fld_format", "ISPB com 7 dígitos", "POST", "/pix/transaction", mutate(bad_ispb), description="Esperado: 400 RNV000009")
request("req_f7", "fld_format", "amount = 0", "POST", "/pix/transaction", mutate(zero_amount), description="Esperado: 400 RNV000010")
request("req_f8", "fld_format", "Latitude 91", "POST", "/pix/transaction", mutate(bad_geo), description="Esperado: 400 RNV000010")
request("req_f9", "fld_format", "POST sem token", "POST", "/pix/transaction", base, token=False, description="Esperado: 403 RNV000002")
request("req_f10", "fld_format", "GET sem token", "GET", "/pix/transaction/qualquer", token=False, description="Esperado: 403 RNV000002")
request("req_f11", "fld_format", "GET inexistente", "GET", "/pix/transaction/nao-existe-xyz", description="Esperado: 404 RNV001039")

# 4 semantic errors
folder("fld_semantic", "4. Erros de sentido (422/409)")
sem = payload(f"sem-{RUN}", 5000, DAY, payer(3), dest(3), f"dvc-sem-{RUN}")


def with_id(suffix, fn):
    clone = json.loads(json.dumps(sem))
    clone["id"] = f"sem-{suffix}-{RUN}"
    fn(clone)
    return clone


def invalid_cpf(d):
    d["source_account"]["owner"]["document_number"] = "123.456.789-00"


def invalid_cnpj(d):
    d["destination_account"]["owner"]["document_number"] = "11.111.111/1111-11"


def opening_after(d):
    d["source_account"]["opening_date"] = "2026-12-01T10:00:00-03:00"


def future(d):
    d["transaction_date"] = "2030-01-01T10:00:00-03:00"


def same_account(d):
    d["destination_account"].update({"participant": OWN, "branch": "0001", "account_number": d["source_account"]["account_number"]})


def bad_ip(d):
    d["source"]["ip"] = "999.1.1.1"


request("req_s1", "fld_semantic", "CPF com dígito inválido", "POST", "/pix/transaction", with_id("cpf", invalid_cpf), description="Esperado: 422 RNV001002")
request("req_s2", "fld_semantic", "CNPJ inválido", "POST", "/pix/transaction", with_id("cnpj", invalid_cnpj), description="Esperado: 422 RNV001020")
request(
    "req_s3", "fld_semantic", "opening_date depois do Pix", "POST", "/pix/transaction",
    with_id("open", opening_after), description="Esperado: 422 RNV001040",
)
request("req_s4", "fld_semantic", "Pix no futuro", "POST", "/pix/transaction", with_id("future", future), description="Esperado: 422 RNV001041")
request("req_s5", "fld_semantic", "Origem = destino", "POST", "/pix/transaction", with_id("same", same_account), description="Esperado: 422 RNV001042")
request("req_s6", "fld_semantic", "IP inválido", "POST", "/pix/transaction", with_id("ip", bad_ip), description="Esperado: 422 RNV001043")
first = payload(f"conf-a-{RUN}", 5000, DAY, payer(4), dest(4), f"dvc-conf-{RUN}")
second = payload(f"conf-b-{RUN}", 5000, DAY, payer(5), dest(4), f"dvc-conf-{RUN}")
second["destination_account"]["owner"]["document_number"] = cpf(999999)
request("req_s7", "fld_semantic", "409 passo 1: cria a conta de destino", "POST", "/pix/transaction", first, description="Esperado: 201.")
request("req_s8", "fld_semantic", "409 passo 2: mesma conta, outro titular", "POST", "/pix/transaction", second, description="Esperado: 409 RNV001044")

# 5 decisions
folder(
    "fld_decision", "5. Decisões do motor",
    "Cada pasta é um cenário. Rode as requisições em ordem (Runner, 1 iteração). "
    "Os resultados dependem das tarefas T03 (matriz), T08/T14/T16 (regras) e T10/T15 (histórico).",
)

folder("fld_dec_approved", "5.1 Approved: pagador novo, dia, valor baixo, destino antigo", "")
request("req_d1", "fld_dec_approved", "POST", "POST", "/pix/transaction",
        payload(f"appr-{RUN}", 5000, DAY, payer(10), dest(10), f"dvc-appr-{RUN}"),
        description="Esperado: 201 approved, decision_basis clean. Device novo com valor ≤ R$ 200 não ativa piso.")

folder("fld_dec_floor", "5.2 Piso de device novo: R$ 250 sem histórico → 2FA")
request("req_d2", "fld_dec_floor", "POST", "POST", "/pix/transaction",
        payload(f"floor-{RUN}", 25000, DAY, payer(11), dest(11), f"dvc-floor-{RUN}"),
        description="Esperado: 201 two_factor_required, decision_basis regulatory_floor, floors [FLOOR_UNREGISTERED_DEVICE].")

folder("fld_dec_2fa", "5.3 Um eixo suspeito: destino novo → 2FA")
request("req_d3", "fld_dec_2fa", "POST", "POST", "/pix/transaction",
        payload(f"2fa-{RUN}", 5000, DAY, payer(12), dest(12, new=True), f"dvc-2fa-{RUN}"),
        description="Esperado: 201 two_factor_required, single_suspicious_axis (WHERE_DESTINATION_NEW_ACCOUNT). Depende de T08.")

folder("fld_dec_unlisted", "5.4 ISPB fora da lista do STR")
request("req_d4", "fld_dec_unlisted", "POST", "POST", "/pix/transaction",
        payload(f"unl-{RUN}", 5000, DAY, payer(13), dest(13, participant=UNLISTED), f"dvc-unl-{RUN}"),
        description="Esperado: 201 (não é erro), where suspicious por WHERE_UNKNOWN_PARTICIPANT → two_factor_required. Depende de T08.")

folder("fld_dec_night", "5.5 Noturno PF→PF acima de R$ 1.000 e destino novo → rejected")
request("req_d5", "fld_dec_night", "POST", "POST", "/pix/transaction",
        payload(f"night-{RUN}", 150000, NIGHT, payer(14), dest(14, new=True), f"dvc-night-{RUN}"),
        description="Esperado: 201 rejected, two_suspicious_axes.")

folder("fld_dec_night_pj", "5.6 Mesmo valor noturno PF→PJ: piso noturno não se aplica")
request(
    "req_d6", "fld_dec_night_pj", "POST", "POST", "/pix/transaction",
    payload(f"nightpj-{RUN}", 150000, NIGHT, payer(15), dest(15, company=True), f"dvc-nightpj-{RUN}"),
    description=(
        "Esperado: sem FLOOR_NIGHT_LIMIT (comércio noturno é normal). "
        "Com device novo e valor > R$ 200, o piso de device ainda leva a 2FA."
    ),
)

folder(
    "fld_dec_velocity", "5.7 Velocity: 6 Pix do mesmo pagador em 10 min",
    "Mesmo pagador, mesmo device, mesmo destino antigo, de 2 em 2 minutos. "
    "Esperado: 3º em diante suspicious (2FA), 6º critical (rejected). Depende de T15 e T16.",
)
vel_payer = payer(16)
vel_dest = dest(16)
for k in range(6):
    minute = 10 + k * 2
    request(f"req_v{k + 1}", "fld_dec_velocity", f"Pix #{k + 1}", "POST", "/pix/transaction",
            payload(f"vel{k + 1}-{RUN}", 3000, f"2026-10-17T14:{minute:02d}:00-03:00", vel_payer, vel_dest, f"dvc-vel-{RUN}"),
            description=f"Pix {k + 1} de 6 (14:{minute:02d}).")

folder(
    "fld_dec_fanin", "5.8 Fan-in: 3 pagadores distintos para o mesmo destino novo",
    "Esperado: pagador novo é rejeitado por evidência do DESTINO (WHERE_DESTINATION_FAN_IN, critical). Depende de T14 e T15.",
)
fan_dest = dest(17, new=True)
for k in range(3):
    request(f"req_fi{k + 1}", "fld_dec_fanin", f"Pagador {k + 1}", "POST", "/pix/transaction",
            payload(f"fanin{k + 1}-{RUN}", 4000, f"2026-10-17T15:{k * 10:02d}:00-03:00", payer(20 + k), fan_dest, f"dvc-fanin{k + 1}-{RUN}"),
            description=f"Pagador {k + 1} de 3. Até o 2º: 2FA (destino novo). A partir do 3º: rejected.")

folder(
    "fld_dec_device", "5.9 Device compartilhado por 3 titulares",
    "Esperado: a partir do 3º titular, who critical (WHO_DEVICE_COMPROMISED) → rejected. Depende de T15 e T16.",
)
for k in range(3):
    request(f"req_dv{k + 1}", "fld_dec_device", f"Titular {k + 1}", "POST", "/pix/transaction",
            payload(f"dev{k + 1}-{RUN}", 4000, f"2026-10-17T16:{k * 10:02d}:00-03:00", payer(30 + k), dest(30 + k), f"dvc-shared-{RUN}"),
            description=f"Titular {k + 1} de 3 no mesmo device.")

# 6 load
folder(
    "fld_load", "6. Carga e latência (usar o Runner)",
    "No Runner: escolha a pasta, defina Iterations e Delay. A latência aparece em cada resposta (barra de tempo) "
    "e na tabela do Runner. Alvo: < 100 ms por Pix. "
    "Não usa arquivo de dados: cada iteração gera um id (uuid) e um número de conta (milissegundos) novos.",
)
ACCT = "{% now 'millis', '', 0 %}"
unique = payload(
    "ins-{% uuid 'v4' %}", 5000, DAY, (ACCT, cpf(111222333)),
    (LISTED, "7" + RUN, cpf(444555666), DEST_OLD_OPENING), "dvc-{% uuid 'v4' %}",
)
request(
    "req_load_unique", "fld_load", "A. Pagadores novos, destino antigo (caminho feliz)", "POST", "/pix/transaction", unique,
    description="Cada iteração é uma conta de origem nova (milissegundos) com id uuid. "
                "Esperado: 201 approved. Mede a latência do caminho feliz sem velocity nem fan-in.",
)
same = payload("ins-{% uuid 'v4' %}", 3000, DAY, payer(40), dest(40), f"dvc-burst-{RUN}")
request(
    "req_load_same", "fld_load", "B. Rajada de um só pagador (20 iterações, delay 0)", "POST", "/pix/transaction", same,
    description="Mesmo pagador e mesmo instante repetidos: a decisão deve escalar para 2FA e depois rejected (velocity). "
                "Mede a latência com histórico crescente. Para repetir, regere com outro --run.",
)
same_dest = payload("ins-{% uuid 'v4' %}", 3000, DAY, (ACCT, cpf(111222333)), dest(41, new=True), "dvc-{% uuid 'v4' %}")
request(
    "req_load_fanin", "fld_load", "C. Campanha: muitos pagadores novos para um destino novo", "POST", "/pix/transaction", same_dest,
    description="Fan-in: a partir do 3º pagador distinto, rejected por WHERE_DESTINATION_FAN_IN. Mede a latência da consulta de destino.",
)

export = {"_type": "export", "__export_format": 4, "__export_date": "2026-10-18T03:30:00.000Z",
          "__export_source": "insomnia.desktop.app:v10", "resources": resources}
(OUT / "antifraud-pix.insomnia.json").write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(len(resources), "resources")
