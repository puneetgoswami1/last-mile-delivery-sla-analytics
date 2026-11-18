-- Multi-stage fulfillment SLA tracking and delay root-cause attribution
-- Separates warehouse dwell time (Click-to-Ship) from carrier transit time (Ship-to-Deliver)

WITH shipment_milestones AS (
    SELECT 
        order_id,
        origin_hub_id,
        carrier_name,
        shipping_tier, -- 'STANDARD' or 'EXPRESS'
        order_placed_at,
        carrier_pickup_at,
        delivered_at,
        promised_delivery_at,
        
        -- Warehouse dwell time in hours (Order placed -> Handed to carrier)
        DATEDIFF('hour', order_placed_at, carrier_pickup_at) AS fc_dwell_hours,
        
        -- Carrier transit time in hours (Use current timestamp if still stuck in transit)
        DATEDIFF('hour', carrier_pickup_at, COALESCE(delivered_at, CURRENT_TIMESTAMP)) AS carrier_transit_hours,
        
        -- Expected SLA targets (in hours)
        CASE WHEN shipping_tier = 'EXPRESS' THEN 12 ELSE 24 END AS target_fc_hours,
        CASE WHEN shipping_tier = 'EXPRESS' THEN 36 ELSE 72 END AS target_transit_hours,
        
        -- Flag SLA breach (includes orders still in transit past promised date)
        CASE 
            WHEN COALESCE(delivered_at, CURRENT_TIMESTAMP) > promised_delivery_at THEN 1 
            ELSE 0 
        END AS is_sla_breached
    FROM logistics_dw.fct_shipments
    WHERE order_status NOT IN ('CANCELLED', 'RETURNED_TO_ORIGIN')
      AND order_placed_at >= CURRENT_DATE - INTERVAL '60 DAYS'
),

delay_attribution AS (
    SELECT 
        *,
        CASE 
            WHEN is_sla_breached = 0 THEN 'ON_TIME'
            WHEN fc_dwell_hours > target_fc_hours AND carrier_transit_hours > target_transit_hours THEN 'BOTH_FC_AND_CARRIER'
            WHEN fc_dwell_hours > target_fc_hours THEN 'WAREHOUSE_FC_DELAY'
            ELSE 'CARRIER_TRANSIT_DELAY'
        END AS delay_root_cause
    FROM shipment_milestones
)

SELECT 
    origin_hub_id,
    carrier_name,
    COUNT(order_id) AS total_shipments,
    SUM(is_sla_breached) AS total_late_orders,
    ROUND(((COUNT(order_id) - SUM(is_sla_breached)) * 100.0) / COUNT(order_id), 2) AS on_time_delivery_pct,
    ROUND(AVG(fc_dwell_hours), 1) AS avg_fc_dwell_hrs,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY carrier_transit_hours), 1) AS p90_transit_hrs,
    SUM(CASE WHEN delay_root_cause = 'WAREHOUSE_FC_DELAY' THEN 1 ELSE 0 END) AS fc_caused_delays,
    SUM(CASE WHEN delay_root_cause = 'CARRIER_TRANSIT_DELAY' THEN 1 ELSE 0 END) AS carrier_caused_delays
FROM delay_attribution
GROUP BY origin_hub_id, carrier_name
ORDER BY on_time_delivery_pct ASC;