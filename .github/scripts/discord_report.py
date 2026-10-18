import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

EMBED_BUDGET = 5800
FIELD_LIMIT = 1024
MAX_FIELDS = 25
FAILURE_LINE_LIMIT = 160
SLOWEST_COUNT = 3
GREEN = 3066993
RED = 15158332
YELLOW = 16705372


def clip(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def embed_size(embed):
    size = len(embed.get("title", "")) + len(embed.get("description", ""))
    for field in embed.get("fields", []):
        size += len(field["name"]) + len(field["value"])
    return size


def parse_cases(paths):
    cases = []
    errors = []
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            errors.append(f"{os.path.basename(path)}: {clip(exc, 100)}")
            continue
        for case in root.iter("testcase"):
            cases.append(build_case(case))
    return cases, errors


def build_case(case):
    classname = case.get("classname", "")
    name = case.get("name", "?")
    segments = [part for part in classname.split(".") if part]
    group = segments[-1] if segments else "tests"
    display = f"{group}::{name}"
    status = "passed"
    message = ""
    for tag, label in (("failure", "failed"), ("error", "failed"), ("skipped", "skipped")):
        node = case.find(tag)
        if node is not None:
            status = label
            raw = node.get("message") or (node.text or "")
            lines = raw.strip().splitlines()
            message = lines[0] if lines else tag
            break
    try:
        duration = float(case.get("time", 0))
    except ValueError:
        duration = 0.0
    return {
        "group": group,
        "name": name,
        "display": display,
        "status": status,
        "message": message,
        "time": duration,
    }


def failed_step(steps_json):
    try:
        steps = json.loads(steps_json or "{}")
    except ValueError:
        return ""
    for step_id, data in steps.items():
        if data.get("outcome") == "failure":
            return step_id
    return ""


def chunk_lines(lines, wrapper, limit=FIELD_LIMIT):
    overhead = len(wrapper.format(""))
    chunks = []
    current = []
    size = overhead
    for line in lines:
        extra = len(line) + (1 if current else 0)
        if current and size + extra > limit:
            chunks.append(wrapper.format("\n".join(current)))
            current = []
            size = overhead
            extra = len(line)
        current.append(line)
        size += extra
    if current:
        chunks.append(wrapper.format("\n".join(current)))
    return chunks


def failure_fields(failures, budget):
    lines = [
        clip(f"{c['display']} — {c['message']}" if c["message"] else c["display"], FAILURE_LINE_LIMIT)
        for c in failures
    ]
    kept = list(lines)
    while True:
        shown = kept + ([f"… +{len(lines) - len(kept)} mais"] if len(kept) < len(lines) else [])
        chunks = chunk_lines(shown, "```\n{}\n```")
        cost = sum(len(c) for c in chunks) + len(chunks) * len("❌ Failed (999)")
        if cost <= budget or len(kept) <= 1:
            break
        kept.pop()
    fields = []
    for index, chunk in enumerate(chunks):
        name = f"❌ Failed ({len(failures)})" if index == 0 else "❌ Failed (cont.)"
        fields.append({"name": name, "value": chunk})
    return fields


def grouped(cases, status):
    groups = {}
    for c in cases:
        if c["status"] == status:
            groups.setdefault(c["group"], []).append(c["name"])
    return groups


def group_field(group, names, icon):
    header = f"{icon} {group} ({len(names)})"
    value = ""
    for index, name in enumerate(names):
        piece = ("" if index == 0 else ", ") + f"`{name}`"
        remaining = len(names) - index
        tail = f", … +{remaining} mais"
        if len(value) + len(piece) + len(tail) > FIELD_LIMIT and remaining > 1:
            return {"name": header, "value": value + f", … +{remaining} mais"}
        value += piece
    return {"name": header, "value": value[:FIELD_LIMIT]}


def listing_fields(groups, icon, embed, limit_fields):
    fields = []
    hidden_groups = 0
    hidden_tests = 0
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    for position, (group, names) in enumerate(ordered):
        field = group_field(group, names, icon)
        projected = embed_size(embed) + sum(len(f["name"]) + len(f["value"]) for f in fields)
        projected += len(field["name"]) + len(field["value"]) + 120
        if projected > EMBED_BUDGET or len(fields) >= limit_fields:
            rest = ordered[position:]
            hidden_groups = len(rest)
            hidden_tests = sum(len(n) for _, n in rest)
            break
        fields.append(field)
    if hidden_groups:
        fields.append(
            {
                "name": f"{icon} … +{hidden_groups} mais",
                "value": f"{hidden_tests} testes em {hidden_groups} grupos omitidos por limite de tamanho",
            }
        )
    return fields


def meta_fields(env, totals):
    sha = env.get("COMMIT_SHA", "")[:7]
    message = env.get("COMMIT_MESSAGE", "")
    first_line = clip(message.splitlines()[0], 200) if message.strip() else ""
    return [
        {"name": "Green", "value": str(totals["passed"]), "inline": True},
        {"name": "Red", "value": str(totals["failed"]), "inline": True},
        {"name": "Skipped", "value": str(totals["skipped"]), "inline": True},
        {"name": "Duration", "value": f"{totals['duration']:.1f}s", "inline": True},
        {"name": "Branch", "value": env.get("BRANCH", "?"), "inline": True},
        {"name": "Author", "value": env.get("ACTOR", "?"), "inline": True},
        {"name": "Commit", "value": f"[`{sha}`]({env.get('COMMIT_URL', '')}) {first_line}"[:FIELD_LIMIT]},
        {"name": "Run", "value": f"[Open GitHub Actions run]({env.get('RUN_URL', '')})"},
    ]


def slowest_field(cases):
    timed = sorted((c for c in cases if c["time"] > 0), key=lambda c: -c["time"])[:SLOWEST_COUNT]
    if not timed:
        return None
    lines = [f"`{clip(c['display'], 80)}` {c['time']:.2f}s" for c in timed]
    return {"name": "🐢 Slowest", "value": "\n".join(lines)[:FIELD_LIMIT]}


def build_payload(env):
    ok = env.get("JOB_STATUS") == "success"
    title = env.get("SERVICE_TITLE", "CI")
    paths = sorted(glob.glob("reports/*.xml"))
    cases, errors = parse_cases(paths)
    step = failed_step(env.get("STEPS_JSON", ""))

    embed = {
        "title": f"✅ {title} passed" if ok else f"❌ {title} failed",
        "url": env.get("RUN_URL", ""),
        "color": GREEN if ok else RED,
        "fields": [],
    }

    failures = [c for c in cases if c["status"] == "failed"]
    totals = {
        "passed": sum(1 for c in cases if c["status"] == "passed"),
        "failed": len(failures),
        "skipped": sum(1 for c in cases if c["status"] == "skipped"),
        "duration": sum(c["time"] for c in cases),
    }
    meta = meta_fields(env, totals)
    meta_cost = sum(len(f["name"]) + len(f["value"]) for f in meta) + len(embed["title"])

    notes = []
    if not paths:
        notes.append("Nenhum relatório JUnit encontrado (os testes não chegaram a rodar).")
    if errors:
        notes.append("XML inválido: " + "; ".join(errors))
    if step and not failures:
        notes.append(f"Step com falha: `{step}`")
    if not ok and step and failures:
        embed["title"] += f" — step `{step}`"
    if not ok and not cases and not step:
        notes.append("Job falhou antes de gerar o relatório.")
    if notes:
        embed["description"] = clip("\n".join(notes), 1500) if len(notes) == 1 else "\n".join(notes)[:1500]
        if not ok:
            embed["color"] = RED
    if ok and not cases:
        embed["color"] = YELLOW

    budget = EMBED_BUDGET - meta_cost - len(embed.get("description", "")) - 400
    fields = []
    if failures:
        fields.extend(failure_fields(failures, min(budget, 3200)))
    embed["fields"] = fields

    reserve = len(meta) + 1
    room = MAX_FIELDS - reserve - len(fields)
    slow = slowest_field(cases)
    skipped_groups = grouped(cases, "skipped")
    passed_groups = grouped(cases, "passed")

    if skipped_groups and room > 0:
        extra = listing_fields(skipped_groups, "⏭️", embed, min(2, room))
        embed["fields"].extend(extra)
        room -= len(extra)
    if passed_groups and room > 0:
        extra = listing_fields(passed_groups, "✅", embed, room)
        embed["fields"].extend(extra)
    if slow and embed_size(embed) + len(slow["name"]) + len(slow["value"]) + meta_cost < 6000:
        embed["fields"].append(slow)
    embed["fields"].extend(meta)

    while embed_size(embed) > 6000 or len(embed["fields"]) > MAX_FIELDS:
        removable = [i for i, f in enumerate(embed["fields"]) if f["name"].startswith(("✅", "⏭️", "🐢"))]
        if not removable:
            break
        embed["fields"].pop(removable[-1])
    return {"embeds": [embed]}


def fallback_payload(env, exc):
    return {
        "embeds": [
            {
                "title": f"{env.get('SERVICE_TITLE', 'CI')} — {env.get('JOB_STATUS', 'unknown')}",
                "url": env.get("RUN_URL", ""),
                "color": RED if env.get("JOB_STATUS") != "success" else GREEN,
                "description": f"Não foi possível montar o relatório detalhado: {clip(exc, 200)}",
            }
        ]
    }


def main():
    env = dict(os.environ)
    try:
        payload = build_payload(env)
    except Exception as exc:
        payload = fallback_payload(env, exc)
    json.dump(payload, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
