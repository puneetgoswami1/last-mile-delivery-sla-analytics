# Last-Mile Delivery SLA & Carrier Delay Analytics

An operational logistics framework that splits order fulfillment into warehouse dwell time and carrier transit legs to pinpoint SLA breach root causes and weekend linehaul bottlenecks.

## Problem Context
Tracking overall On-Time Delivery (OTD) percentage alone does not tell operations teams how to fix late shipments. If an order arrives late, leadership needs to know whether internal warehouse picking stalled or the external courier missed transit windows.

## Files
- `fulfillment_sla_pipeline.sql`: Splits order timestamps into Click-to-Ship (`fc_dwell_hours`) and Ship-to-Deliver (`carrier_transit_hours`), flags active in-transit breaches via `COALESCE`, and attributes delay accountability.
- `delivery_bottleneck_engine.py`: Evaluates 30k+ shipments across regional hubs and carriers to compute OTD%, P90 transit tails, and Friday linehaul cutoff misses.
- `requirements.txt`: Python dependencies.

## Key Analytical Logic
1. **Stage Split Attribution:** Compares actual warehouse hours and transit hours against tier-specific SLAs (`EXPRESS` vs `STANDARD`) to separate warehouse bottlenecks from carrier delays.
2. **Active Breach Detection:** Uses `COALESCE(delivered_at, CURRENT_TIMESTAMP)` so un-delivered packages already past their promised date are flagged immediately rather than ignored.
3. **Cutoff Window Diagnostics:** Isolates Friday afternoon orders that miss weekend carrier pickups and sit idle in fulfillment hubs until Monday.

## How to Run

```bash
git clone [https://github.com/puneetgoswami1/last-mile-delivery-sla-analytics.git](https://github.com/puneetgoswami1/last-mile-delivery-sla-analytics.git)
cd last-mile-delivery-sla-analytics

pip install -r requirements.txt
python delivery_bottleneck_engine.py