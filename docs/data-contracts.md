# Data contracts

All records in this repository are synthetic. Amounts are represented as
base-10 decimal strings with two fractional digits.

## Source and silver entities

### customers

| Field | Type | Contract |
|---|---|---|
| customer_id | string | Required, unique, canonical uppercase key |
| first_name, last_name | string | Required, whitespace normalized |
| email | string | Required, lowercase, basic shape validation |
| segment | enum | `consumer`, `small_business`, or `enterprise` |
| joined_date | ISO date | Valid `YYYY-MM-DD` |
| country | string | Uppercase country code |
| is_active | boolean text | Canonical lowercase |

### products

| Field | Type | Contract |
|---|---|---|
| product_id | string | Required, unique |
| product_name | string | Required |
| category | string | Required |
| unit_price | decimal(18,2) | Greater than zero |
| unit_cost | decimal(18,2) | Non-negative |
| is_active | boolean text | Canonical lowercase |

### orders

| Field | Type | Contract |
|---|---|---|
| order_id | string | Required, unique |
| customer_id | string | Must exist in customers |
| order_date | ISO date | Valid `YYYY-MM-DD` |
| status | enum | `COMPLETED`, `RETURNED`, or `CANCELLED` |
| payment_method | string | Normalized lowercase |
| order_total | decimal(18,2) | Must equal the sum of its line totals |

### order_items

| Field | Type | Contract |
|---|---|---|
| order_item_id | string | Required, unique |
| order_id | string | Must exist in orders |
| product_id | string | Must exist in products |
| quantity | integer | Greater than zero |
| unit_price | decimal(18,2) | Greater than zero |
| discount_rate | decimal(4,2) | Synthetic generator uses 0%, 5%, or 10% |
| line_total | decimal(18,2) | Non-negative |

Silver entities carry `_pipeline_run_id` for run-level lineage. Bronze additionally
retains `_source_file`, `_ingested_at`, and a deterministic `_record_hash`.

## Gold products

### daily_sales

One row per sales date for completed orders. `net_revenue` is the sum of line
totals, `order_count` and `customer_count` are distinct counts, and
`average_order_value = net_revenue / order_count`.

### product_performance

One row per sold product for completed orders. Gross margin is calculated as
line revenue minus current unit cost multiplied by units. In a real slowly
changing catalog, the order-line cost snapshot would be used instead.

### customer_360

One row per purchasing customer, including completed lifetime order count,
revenue, average order value, and first/last order dates.

## Blocking checks

The silver publication gate contains 12 checks:

- unique customer, product, order, and order-line keys;
- order-to-customer, item-to-order, and item-to-product referential integrity;
- valid email shape and accepted order statuses;
- positive item quantity/price and non-negative line total;
- exact order-header to line-total reconciliation; and
- at least one line for every order.

Any failure writes a diagnostic quality report and prevents gold publication.

