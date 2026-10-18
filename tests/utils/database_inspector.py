from os import environ
from typing import List

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
    def fetch(query: str, transaction_id: str) -> List[dict]:
        connection = DatabaseInspector.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, (transaction_id,))
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
