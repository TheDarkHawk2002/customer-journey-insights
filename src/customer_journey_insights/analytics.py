from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

EVENT_ORDER = ("product_view", "cart_created", "checkout_started", "order_completed")


def _date(event: dict[str, str]) -> datetime:
    return datetime.fromisoformat(event["event_at"].replace("Z", "+00:00"))


def build_funnel(events: list[dict[str, str]]) -> list[dict[str, str | int]]:
    reached: dict[str, set[str]] = {name: set() for name in EVENT_ORDER}
    for event in events:
        reached[event["event_name"]].add(event["customer_id"])
    viewers = len(reached["product_view"])
    previous = viewers
    rows = []
    for name in EVENT_ORDER:
        customers = len(reached[name])
        rows.append({
            "stage": name,
            "customers": customers,
            "conversion_from_view": f"{(customers / viewers * 100):.1f}" if viewers else "0.0",
            "conversion_from_previous": f"{(customers / previous * 100):.1f}" if previous else "0.0",
        })
        previous = customers
    return rows


def build_daily_sales(events: list[dict[str, str]]) -> list[dict[str, str | int]]:
    totals: dict[str, dict[str, object]] = defaultdict(lambda: {"orders": 0, "buyers": set(), "revenue": Decimal("0")})
    for event in events:
        if event["event_name"] != "order_completed":
            continue
        day = _date(event).date().isoformat()
        totals[day]["orders"] = int(totals[day]["orders"]) + 1
        totals[day]["buyers"].add(event["customer_id"])
        totals[day]["revenue"] = Decimal(totals[day]["revenue"]) + Decimal(event["order_value_eur"])
    return [
        {"date": day, "orders": int(values["orders"]), "buyers": len(values["buyers"]), "revenue_eur": f"{values['revenue']:.2f}"}
        for day, values in sorted(totals.items())
    ]


def build_purchase_cohorts(events: list[dict[str, str]], as_of: datetime) -> list[dict[str, str | int]]:
    purchases: dict[str, list[tuple[datetime, Decimal]]] = defaultdict(list)
    for event in events:
        if event["event_name"] == "order_completed":
            purchases[event["customer_id"]].append((_date(event), Decimal(event["order_value_eur"])))

    cohorts: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for customer, orders in purchases.items():
        first_order = min(orders, key=lambda item: item[0])[0]
        cohorts[first_order.strftime("%Y-%m")].append((first_order, customer))

    result = []
    for month, members in sorted(cohorts.items()):
        mature = [customer for first_order, customer in members if as_of >= first_order + timedelta(days=30)]
        repeaters = 0
        for customer in mature:
            first_order = min(purchases[customer], key=lambda item: item[0])[0]
            if any(first_order < order_at <= first_order + timedelta(days=30) for order_at, _ in purchases[customer]):
                repeaters += 1
        result.append({
            "first_order_month": month,
            "customers": len(members),
            "mature_customers": len(mature),
            "repeat_customers": repeaters,
            "repeat_rate_30d_pct": f"{(repeaters / len(mature) * 100):.1f}" if mature else "n.a.",
        })
    return result


def summarize(events: list[dict[str, str]]) -> dict[str, int | str]:
    orders = [event for event in events if event["event_name"] == "order_completed"]
    revenue = sum((Decimal(event["order_value_eur"]) for event in orders), Decimal("0"))
    channels = Counter(event["channel"] for event in events)
    return {
        "accepted_events": len(events),
        "unique_customers": len({event["customer_id"] for event in events}),
        "orders": len(orders),
        "buyers": len({event["customer_id"] for event in orders}),
        "revenue_eur": f"{revenue:.2f}",
        "top_channel": channels.most_common(1)[0][0] if channels else "n.a.",
    }
