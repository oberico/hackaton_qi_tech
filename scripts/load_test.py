import argparse
import concurrent.futures
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
import requests


def generate_cpf(seed: int) -> str:
    base = [int(c) for c in f"{seed:09d}"]
    for n in (9, 10):
        total = sum(d * w for d, w in zip(base, range(n + 1, 1, -1)))
        base.append((total * 10 % 11) % 10)
    s = "".join(map(str, base))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def build_payload(index: int, scenario: str, run_id: str, run_seed: int) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    if scenario == "burst":
        payer_cpf = generate_cpf(100000000 + (run_seed % 100000) * 7919)
        dest_cpf = generate_cpf(300000000 + (run_seed % 100000) * 6007)
        payer_acct = f"{run_seed:06d}001"
        dest_acct = f"{run_seed:06d}999"
        amount = 3000
    elif scenario == "mixed" and index % 10 == 0:
        payer_cpf = generate_cpf(100000000 + (index % 100000) * 7919)
        dest_cpf = generate_cpf(300000000 + (index % 100000) * 6007)
        payer_acct = f"{run_seed:06d}{index:06d}"
        dest_acct = f"{run_seed + 1:06d}{index:06d}"
        amount = 25000
    else:
        payer_cpf = generate_cpf(100000000 + (index % 100000) * 7919)
        dest_cpf = generate_cpf(300000000 + (index % 100000) * 6007)
        payer_acct = f"{run_seed:06d}{index:06d}"
        dest_acct = f"{run_seed + 1:06d}{index:06d}"
        amount = 5000

    return {
        "id": f"load-{run_id}-{index}-{uuid.uuid4().hex[:8]}",
        "amount": amount,
        "transaction_date": now_iso,
        "source_account": {
            "branch": "0001",
            "account_number": payer_acct,
            "opening_date": "2024-01-01T08:00:00-03:00",
            "owner": {"document_number": payer_cpf},
        },
        "destination_account": {
            "participant": "60701190",
            "branch": "3675",
            "account_number": dest_acct,
            "opening_date": "2024-01-01T08:00:00-03:00",
            "owner": {"document_number": dest_cpf},
        },
        "source": {
            "device_id": f"dvc-{run_id}-{index if scenario != 'burst' else 1}",
            "channel": "app",
            "ip": "198.51.100.23",
            "geolocation": {"latitude": -23.56, "longitude": -46.65},
        },
    }


def send_transaction(session: requests.Session, url: str, token: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "INTERNAL-TOKEN": token,
    }
    start = time.perf_counter()
    try:
        response = session.post(f"{url}/pix/transaction", json=payload, headers=headers, timeout=10.0)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        internal_latency_ms = None
        status = response.status_code
        decision = "error"
        if status in (200, 201):
            data = response.json()
            decision = data.get("status", "unknown")
            internal_latency_ms = data.get("metadata", {}).get("latency_ms")

        return {
            "http_status": status,
            "decision": decision,
            "elapsed_ms": elapsed_ms,
            "internal_ms": internal_latency_ms,
            "success": status in (200, 201),
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "http_status": 0,
            "decision": "exception",
            "elapsed_ms": elapsed_ms,
            "internal_ms": None,
            "success": False,
            "error": str(exc),
        }


def run_load_test(base_url: str, token: str, total_requests: int, concurrency: int, scenario: str) -> dict:
    run_id = uuid.uuid4().hex[:6]
    run_seed = int(time.time() * 1000) % 800000 + 100000
    print("=" * 64)
    print("  MOTOR ANTIFRAUDE PIX — TESTE DE CARGA E LATÊNCIA")
    print("=" * 64)
    print(f"Target:       {base_url}")
    print(f"Cenário:      {scenario}")
    print(f"Requisições:  {total_requests}")
    print(f"Concorrência: {concurrency} threads")
    print("-" * 64)

    payloads = [build_payload(i, scenario, run_id, run_seed) for i in range(total_requests)]

    wall_start = time.perf_counter()
    results = []

    def worker(chunk):
        with requests.Session() as session:
            chunk_results = []
            for p in chunk:
                chunk_results.append(send_transaction(session, base_url, token, p))
            return chunk_results

    chunks = [payloads[i::concurrency] for i in range(concurrency)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker, chunk) for chunk in chunks if chunk]
        for f in concurrent.futures.as_completed(futures):
            results.extend(f.result())

    wall_elapsed = time.perf_counter() - wall_start
    throughput = len(results) / wall_elapsed if wall_elapsed > 0 else 0

    latencies = [r["elapsed_ms"] for r in results]
    internal_latencies = [r["internal_ms"] for r in results if r["internal_ms"] is not None]

    latencies.sort()
    count = len(latencies)

    def percentile(p, data):
        if not data:
            return 0.0
        k = (len(data) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(data) - 1)
        d = k - f
        return data[f] * (1.0 - d) + data[c] * d

    p50 = percentile(50, latencies)
    p90 = percentile(90, latencies)
    p95 = percentile(95, latencies)
    p99 = percentile(99, latencies)
    min_lat = latencies[0] if latencies else 0.0
    max_lat = latencies[-1] if latencies else 0.0
    mean_lat = statistics.mean(latencies) if latencies else 0.0
    stdev_lat = statistics.stdev(latencies) if len(latencies) > 1 else 0.0

    internal_p95 = percentile(95, sorted(internal_latencies)) if internal_latencies else 0.0
    internal_mean = statistics.mean(internal_latencies) if internal_latencies else 0.0

    status_counts = {}
    decision_counts = {}
    for r in results:
        status_counts[r["http_status"]] = status_counts.get(r["http_status"], 0) + 1
        decision_counts[r["decision"]] = decision_counts.get(r["decision"], 0) + 1

    print("\n" + "=" * 64)
    print("  RESULTADOS DO BENCHMARK")
    print("=" * 64)
    print(f"Tempo total:       {wall_elapsed:.2f} s")
    print(f"Throughput:        {throughput:.1f} req/s")
    print(f"Requisições:       {count} ({sum(1 for r in results if r['success'])} sucesso, {sum(1 for r in results if not r['success'])} erros)")
    print("-" * 64)
    print("Distribuição de Status HTTP:")
    for code, cnt in sorted(status_counts.items()):
        print(f"  HTTP {code}: {cnt} ({cnt / count * 100:.1f}%)")
    print("Decisões do Motor:")
    for dec, cnt in sorted(decision_counts.items()):
        print(f"  {dec}: {cnt} ({cnt / count * 100:.1f}%)")
    print("-" * 64)
    print("Latência HTTP de Ponta a Ponta (ms):")
    print(f"  Mínima:  {min_lat:6.2f} ms")
    print(f"  Média:   {mean_lat:6.2f} ms (± {stdev_lat:.2f} ms)")
    print(f"  p50:     {p50:6.2f} ms")
    print(f"  p90:     {p90:6.2f} ms")
    print(f"  p95:     {p95:6.2f} ms")
    print(f"  p99:     {p99:6.2f} ms")
    print(f"  Máxima:  {max_lat:6.2f} ms")

    if internal_latencies:
        print("-" * 64)
        print("Latência Interna do Motor / Banco (metadata.latency_ms):")
        print(f"  Média:   {internal_mean:6.2f} ms")
        print(f"  p95:     {internal_p95:6.2f} ms")

    print("=" * 64)
    sla_pass = p95 < 100.0
    if sla_pass:
        print(f" [PASS] Meta de latência (< 100 ms) ATENDIDA! (p95 = {p95:.2f} ms)")
    else:
        print(f" [WARN] Meta de latência (< 100 ms) estourada (p95 = {p95:.2f} ms)")
    print("=" * 64 + "\n")

    return {
        "total_requests": count,
        "throughput_rps": throughput,
        "elapsed_sec": wall_elapsed,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "mean_ms": mean_lat,
        "internal_mean_ms": internal_mean,
        "internal_p95_ms": internal_p95,
        "sla_pass": sla_pass,
    }


def main():
    parser = argparse.ArgumentParser(description="Teste de carga e latência do Motor Antifraude de Pix")
    parser.add_argument("--url", default="http://localhost:8001", help="URL base da API (padrão: http://localhost:8001)")
    parser.add_argument("--token", default="internal-token-dev", help="Token interno para autenticação")
    parser.add_argument("--requests", type=int, default=200, help="Total de requisições (padrão: 200)")
    parser.add_argument("--concurrency", type=int, default=10, help="Número de threads simultâneas (padrão: 10)")
    parser.add_argument("--scenario", choices=["happy_path", "burst", "mixed"], default="happy_path", help="Cenário de teste")
    parser.add_argument("--json", action="store_true", help="Imprime resultado final em formato JSON")

    args = parser.parse_args()
    summary = run_load_test(args.url, args.token, args.requests, args.concurrency, args.scenario)
    if args.json:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
