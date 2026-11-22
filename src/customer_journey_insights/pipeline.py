from __future__ import annotations

import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .analytics import build_daily_sales, build_funnel, build_purchase_cohorts, summarize

REQUIRED = ("event_id", "customer_id", "event_name", "event_at", "channel", "product_category", "order_value_eur")
EVENTS = {"product_view", "cart_created", "checkout_started", "order_completed"}


def read_events(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    accepted: list[dict[str, str]] = []
    findings: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = [name for name in REQUIRED if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        for row in reader:
            line = str(reader.line_num)
            errors = []
            if not row.get("event_id", "").strip(): errors.append("missing event_id")
            if not row.get("customer_id", "").strip(): errors.append("missing customer_id")
            if row.get("event_name") not in EVENTS: errors.append("unsupported event_name")
            if not row.get("channel", "").strip(): errors.append("missing channel")
            if not row.get("product_category", "").strip(): errors.append("missing product_category")
            try:
                timestamp = datetime.fromisoformat(row.get("event_at", "").replace("Z", "+00:00"))
                if timestamp.tzinfo is None: errors.append("event_at must include a timezone")
            except ValueError:
                errors.append("invalid ISO-8601 event_at")
            if row.get("event_name") == "order_completed":
                try:
                    if not row.get("order_value_eur", "").strip(): raise ValueError
                    amount = Decimal(row["order_value_eur"])
                    if not amount.is_finite(): raise ValueError
                    if amount < 0: errors.append("order_value_eur cannot be negative")
                except (ValueError, InvalidOperation):
                    errors.append("order_value_eur must be a non-negative number for completed orders")
            elif row.get("order_value_eur", "").strip():
                try:
                    amount = Decimal(row["order_value_eur"])
                    if not amount.is_finite(): raise ValueError
                    if amount < 0: errors.append("order_value_eur cannot be negative")
                except (ValueError, InvalidOperation):
                    errors.append("order_value_eur must be numeric when provided")
            event_id = row.get("event_id", "").strip()
            if event_id in seen: errors.append("duplicate event_id")
            if event_id: seen.add(event_id)
            if errors:
                findings.append({"source_row": line, "event_id": event_id, "reasons": "; ".join(errors)})
                continue
            accepted.append({key: (row.get(key) or "").strip() for key in REQUIRED})
    if not accepted:
        raise ValueError("No valid events remain after validation")
    return accepted, findings


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(input_path: Path, output_dir: Path) -> dict[str, object]:
    events, findings = read_events(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    as_of = max(datetime.fromisoformat(item["event_at"].replace("Z", "+00:00")) for item in events)
    metrics = summarize(events)
    funnel = build_funnel(events)
    cohorts = build_purchase_cohorts(events, as_of)
    daily = build_daily_sales(events)
    _write_csv(output_dir / "funnel.csv", funnel)
    _write_csv(output_dir / "purchase_cohorts.csv", cohorts)
    _write_csv(output_dir / "daily_sales.csv", daily)
    _write_csv(output_dir / "quality_findings.csv", findings)
    (output_dir / "summary.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Customer Journey Summary", "",
        f"- Valid events: {metrics['accepted_events']}",
        f"- Customers: {metrics['unique_customers']}",
        f"- Completed orders: {metrics['orders']}",
        f"- Buyers: {metrics['buyers']}",
        f"- Revenue: €{metrics['revenue_eur']}",
        f"- Rows with quality findings: {len(findings)}", "",
        "## Funnel", "", "| Stage | Customers | From viewers | From previous |", "|---|---:|---:|---:|",
    ]
    lines.extend(f"| {row['stage']} | {row['customers']} | {row['conversion_from_view']}% | {row['conversion_from_previous']}% |" for row in funnel)
    lines.extend(["", "## 30-day repeat-purchase cohorts", "", "| First order month | Customers | Mature | Repeat buyers | Repeat rate |", "|---|---:|---:|---:|---:|"])
    lines.extend(f"| {row['first_order_month']} | {row['customers']} | {row['mature_customers']} | {row['repeat_customers']} | {row['repeat_rate_30d_pct']}{'%' if row['repeat_rate_30d_pct'] != 'n.a.' else ''} |" for row in cohorts)
    lines.extend(["", "The funnel counts distinct customers across the full input period. Cohorts without 30 days of follow-up are excluded from the repeat-rate denominator. These descriptive metrics do not establish causality.", ""])
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return {"summary": metrics, "findings": len(findings), "output_dir": str(output_dir)}
