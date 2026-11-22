# Customer Journey Insights

A small, reproducible Python analytics pipeline for understanding how customers move from product discovery to purchase and whether they return. It validates event exports, produces clear funnel and repeat-purchase metrics, and writes a concise report. The included dataset is deterministic and synthetic.

## Run

Python 3.11 or newer is required. The project uses only the Python standard library.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
journey-insights analyze --input data/demo_events.csv --output-dir output
```

The command writes `report.md`, `funnel.csv`, `purchase_cohorts.csv`, `daily_sales.csv`, and `quality_findings.csv` to the output directory.

## Metrics

- Funnel: distinct customers reaching product view, cart, checkout, and completed order; conversion is shown relative to product viewers and the preceding step.
- Repeat purchase: customers with a second completed order within 30 days of their first, grouped by first-order month.
- Daily sales: completed order count, revenue, and distinct buyers by calendar day.
- Data quality: rejected rows and their source line, with explicit reasons.

The funnel uses the full input period and does not claim session-level attribution. Cohorts with fewer than 30 days of follow-up are marked immature rather than reported as zero retention.

## Input contract

CSV columns: `event_id`, `customer_id`, `event_name`, `event_at`, `channel`, `product_category`, `order_value_eur`. Timestamps must be ISO 8601. Event names are `product_view`, `cart_created`, `checkout_started`, or `order_completed`. Order values are required and non-negative for completed orders; for other event types, they may be blank. Event IDs must be unique.

## Data flow

```text
CSV export -> schema and row validation -> accepted events
          -> funnel, sales, and cohort calculations -> CSV + Markdown report
```

The sample contains one intentionally invalid duplicate event with a negative amount so the quality report has a concrete example. The source CSV is read only. Metrics are descriptive and do not establish causality or predict individual behavior. All sample records are synthetic; this is a local portfolio case study, not a hosted analytics product or a claim of production deployment.
