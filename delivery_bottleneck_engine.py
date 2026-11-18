"""
Last-Mile Delivery SLA & Carrier Bottleneck Engine
Breaks down end-to-end delivery times into warehouse dwell vs carrier transit,
identifies weekend linehaul cutoff misses, and flags high-risk routes.
"""

import numpy as np
import pandas as pd


def generate_shipment_logs(n_orders: int = 30000) -> pd.DataFrame:
    """Simulates realistic multi-hub e-commerce order fulfillment logs."""
    rng = np.random.default_rng(42)

    hubs = rng.choice(["LAX-01", "DFW-02", "EWR-03", "ORD-04"], size=n_orders, p=[0.30, 0.25, 0.25, 0.20])
    carriers = rng.choice(["UPS", "FedEx", "RegionalExpress"], size=n_orders, p=[0.40, 0.35, 0.25])
    tiers = rng.choice(["STANDARD", "EXPRESS"], size=n_orders, p=[0.75, 0.25])
    
    # Day of week: 0=Mon ... 4=Fri, 5=Sat, 6=Sun
    order_dow = rng.integers(0, 7, size=n_orders)
    order_hour = rng.integers(0, 24, size=n_orders)

    # Base warehouse packing & dispatch time (hours)
    fc_dwell = np.where(tiers == "EXPRESS", rng.normal(8, 2.5, n_orders), rng.normal(18, 5.0, n_orders))
    
    # Realistic operational bottleneck: EWR-03 hub slows down on Friday afternoons (missed weekend pickup)
    friday_cutoff_miss = (hubs == "EWR-03") & (order_dow == 4) & (order_hour >= 15)
    fc_dwell = np.where(friday_cutoff_miss, fc_dwell + rng.uniform(18, 30, n_orders), fc_dwell).clip(2, 96)

    # Base carrier transit time (hours)
    transit_hrs = np.where(tiers == "EXPRESS", rng.normal(28, 6.0, n_orders), rng.normal(58, 14.0, n_orders))
    
    # RegionalExpress has higher transit tail delays
    transit_hrs = np.where(carriers == "RegionalExpress", transit_hrs * rng.uniform(1.05, 1.25, n_orders), transit_hrs).clip(8, 180)

    target_fc = np.where(tiers == "EXPRESS", 12.0, 24.0)
    target_transit = np.where(tiers == "EXPRESS", 36.0, 72.0)
    promised_total = target_fc + target_transit

    actual_total = fc_dwell + transit_hrs
    is_late = (actual_total > promised_total).astype(int)

    return pd.DataFrame({
        "order_id": [f"SHP-{500000 + i}" for i in range(n_orders)],
        "hub": hubs,
        "carrier": carriers,
        "tier": tiers,
        "day_of_week": order_dow,
        "order_hour": order_hour,
        "fc_dwell_hrs": np.round(fc_dwell, 1),
        "transit_hrs": np.round(transit_hrs, 1),
        "target_fc_hrs": target_fc,
        "target_transit_hrs": target_transit,
        "is_late": is_late
    })


def attribute_delay_cause(df: pd.DataFrame) -> pd.Series:
    """Assigns primary accountability for SLA breaches."""
    conditions = [
        df["is_late"] == 0,
        (df["fc_dwell_hrs"] > df["target_fc_hrs"]) & (df["transit_hrs"] > df["target_transit_hrs"]),
        df["fc_dwell_hrs"] > df["target_fc_hrs"],
    ]
    choices = ["ON_TIME", "BOTH_FC_AND_CARRIER", "WAREHOUSE_FC_DELAY"]
    return pd.Series(np.select(conditions, choices, default="CARRIER_TRANSIT_DELAY"), index=df.index)


def run_sla_diagnostics(df: pd.DataFrame):
    df["delay_cause"] = attribute_delay_cause(df)

    total = len(df)
    late_count = df["is_late"].sum()
    otd_pct = ((total - late_count) / total) * 100

    print("\n--- Fulfillment SLA & Carrier Performance Summary ---")
    print(f"Total Shipments Analyzed : {total:,}")
    print(f"Overall On-Time Delivery : {otd_pct:.2f}% ({late_count:,} SLA breaches)\n")

    # 1. Delay Accountability Breakdown
    late_df = df[df["is_late"] == 1]
    cause_dist = late_df["delay_cause"].value_counts(normalize=True) * 100
    print("Delay Root-Cause Breakdown (Share of Late Orders):")
    for cause, pct in cause_dist.items():
        print(f"  {cause:24s}: {pct:5.1f}%")

    # 2. Hub & Carrier SLA Matrix
    hub_carrier = (
        df.groupby(["hub", "carrier"])
        .agg(
            shipments=("order_id", "count"),
            otd_pct=("is_late", lambda x: round((1 - x.mean()) * 100, 1)),
            avg_fc_hrs=("fc_dwell_hrs", lambda x: round(x.mean(), 1)),
            p90_transit=("transit_hrs", lambda x: round(np.percentile(x, 90), 1))
        )
        .reset_index()
        .sort_values("otd_pct")
    )

    print("\nLowest Performing Hub-Carrier Corridors (Bottom 6):")
    print(hub_carrier.head(6).to_string(index=False))

    # 3. Weekend Cutoff Anomaly Check (Friday after 3 PM)
    fri_late = df[(df["day_of_week"] == 4) & (df["order_hour"] >= 15)]
    normal_days = df[~((df["day_of_week"] == 4) & (df["order_hour"] >= 15))]

    fri_fc_breach = (fri_late["fc_dwell_hrs"] > fri_late["target_fc_hrs"]).mean() * 100
    norm_fc_breach = (normal_days["fc_dwell_hrs"] > normal_days["target_fc_hrs"]).mean() * 100

    print("\nOperational Bottleneck Check (Friday Post-3PM Cutoff):")
    print(f"  Standard Window FC Breach Rate : {norm_fc_breach:.1f}%")
    print(f"  Friday Post-3PM FC Breach Rate : {fri_fc_breach:.1f}%")
    print("  Actionable Fix: Shift EWR-03 Friday carrier linehaul pickup from 4:00 PM to 7:30 PM.\n")


if __name__ == "__main__":
    shipments = generate_shipment_logs(30000)
    run_sla_diagnostics(shipments)