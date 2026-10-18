from os import environ
from typing import List, Optional

import psycopg2
import psycopg2.extras

DATABASE_DSN = "host={host} port={port} user={user} password={password} dbname={name}"

RULE_ROWS_QUERY = """
SELECT rule.rule_code, axis.enumerator AS axis, outcome.enumerator AS outcome, level.enumerator AS level,
       rule.observed, rule.threshold, rule.reason
FROM pix_analysis_rule rule
JOIN pix_analysis analysis ON analysis.id = rule.pix_analysis_id
JOIN pix_transaction pix ON pix.id = analysis.pix_transaction_id
JOIN rule_axis axis ON axis.id = rule.rule_axis_id
JOIN rule_outcome outcome ON outcome.id = rule.rule_outcome_id
LEFT JOIN risk_level level ON level.id = rule.risk_level_id
WHERE pix.transaction_id = %s
ORDER BY rule.rule_code
"""

AXIS_ROWS_QUERY = """
SELECT axis.enumerator AS axis, level.enumerator AS level
FROM pix_analysis_axis analysis_axis
JOIN pix_analysis analysis ON analysis.id = analysis_axis.pix_analysis_id
JOIN pix_transaction pix ON pix.id = analysis.pix_transaction_id
JOIN rule_axis axis ON axis.id = analysis_axis.rule_axis_id
JOIN risk_level level ON level.id = analysis_axis.risk_level_id
WHERE pix.transaction_id = %s
ORDER BY axis.enumerator
"""

LATENCY_QUERY = """
SELECT analysis.latency_ms
FROM pix_analysis analysis
JOIN pix_transaction pix ON pix.id = analysis.pix_transaction_id
WHERE pix.transaction_id = %s
"""

TRANSACTION_COUNT_QUERY = """
SELECT count(*) AS total FROM pix_transaction WHERE transaction_id = %s
"""

ANALYSIS_KEYS_QUERY = """
SELECT analysis.analysis_key
FROM pix_analysis analysis
JOIN pix_transaction pix ON pix.id = analysis.pix_transaction_id
WHERE pix.transaction_id = %s
"""

ACCOUNT_DEVICE_QUERY = """
SELECT device.approved_count, device.first_approved_at, device.last_approved_at
FROM account_device device
JOIN account ON account.id = device.account_id
JOIN account_holder holder ON holder.id = account.account_holder_id
WHERE holder.document_number = %s AND account.account_number = %s AND device.device_id = %s
"""

ACCOUNT_COUNTERPARTY_QUERY = """
SELECT counterparty.approved_count, counterparty.approved_amount_minor,
       counterparty.first_approved_at, counterparty.last_approved_at
FROM account_counterparty counterparty
JOIN account source ON source.id = counterparty.source_account_id
JOIN account_holder payer ON payer.id = source.account_holder_id
JOIN account destination ON destination.id = counterparty.destination_account_id
JOIN account_holder beneficiary ON beneficiary.id = destination.account_holder_id
WHERE payer.document_number = %s AND source.account_number = %s
  AND beneficiary.document_number = %s AND destination.account_number = %s
"""


class DatabaseInspector:
    @staticmethod
    def connect():
        dsn = DATABASE_DSN.format(
            host=environ.get("DB_HOST", "localhost"),
            port=environ.get("DB_PORT", "5434"),
            user=environ.get("DB_USER", "rnv"),
            password=environ.get("DB_PASSWORD", "rnv"),
            name=environ.get("DB_NAME", "antifraud"),
        )
        return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    @staticmethod
    def fetch(query: str, *parameters: str) -> List[dict]:
        connection = DatabaseInspector.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    @staticmethod
    def rule_rows(transaction_id: str) -> List[dict]:
        return DatabaseInspector.fetch(RULE_ROWS_QUERY, transaction_id)

    @staticmethod
    def axis_rows(transaction_id: str) -> List[dict]:
        return DatabaseInspector.fetch(AXIS_ROWS_QUERY, transaction_id)

    @staticmethod
    def latency_ms(transaction_id: str) -> int:
        return DatabaseInspector.fetch(LATENCY_QUERY, transaction_id)[0]["latency_ms"]

    @staticmethod
    def transaction_count(transaction_id: str) -> int:
        return DatabaseInspector.fetch(TRANSACTION_COUNT_QUERY, transaction_id)[0]["total"]

    @staticmethod
    def analysis_keys(transaction_id: str) -> List[str]:
        return [row["analysis_key"] for row in DatabaseInspector.fetch(ANALYSIS_KEYS_QUERY, transaction_id)]

    @staticmethod
    def account_device(payload: dict) -> Optional[dict]:
        source = payload["source_account"]
        rows = DatabaseInspector.fetch(
            ACCOUNT_DEVICE_QUERY, source["owner"]["document_number"], source["account_number"], payload["source"]["device_id"]
        )
        return rows[0] if rows else None

    @staticmethod
    def account_counterparty(payload: dict) -> Optional[dict]:
        source, destination = payload["source_account"], payload["destination_account"]
        rows = DatabaseInspector.fetch(
            ACCOUNT_COUNTERPARTY_QUERY,
            source["owner"]["document_number"],
            source["account_number"],
            destination["owner"]["document_number"],
            destination["account_number"],
        )
        return rows[0] if rows else None
