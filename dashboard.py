import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Pickup Hub Dashboard", layout="wide", page_icon="📦")

CSV_PATH = "8a296c1ba2cacc19409c6fb7a2d79640.csv"

NUMERIC_COLS = [
    "fm_created", "fm_picked", "fm_created_unpicked",
    "ph_in_volume", "ph_in_picked", "ph_in_unpicked",
    "cron_present_rtd", "cron_pending_pickup",
    "cron_status_created", "cron_status_ofp", "cron_status_reattempt",
    "pick_thru_rate", "d0_pick_thru_rate", "d1_pick_thru_rate",
    "ph_in_pick_rate", "cron_present_pick_rate",
    "d0_attempt", "d1_attempt", "d1_plus_attempt", "d1_attempt_rate",
    "fm_d0_picked", "fm_d1_picked", "fm_d1_plus_picked", "zero_attempt_rto_num",
]

RATE_COLS = {
    "pick_thru_rate", "d0_pick_thru_rate", "d1_pick_thru_rate",
    "ph_in_pick_rate", "cron_present_pick_rate", "d1_attempt_rate",
}

@st.cache_data(show_spinner="Loading data...")
def load_data():
    df = pd.read_csv(CSV_PATH, dtype={"pickup_hub_name": str, "pickup_hub_city": str,
                                      "pickup_hub_zone": str, "seller_type": str,
                                      "payment_type": str, "reporting_date": str})
    df["reporting_date"] = pd.to_datetime(df["reporting_date"], errors="coerce")
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["pickup_hub_name"] = df["pickup_hub_name"].fillna("Unknown")
    df["pickup_hub_city"] = df["pickup_hub_city"].fillna("Unknown")
    df["pickup_hub_zone"] = df["pickup_hub_zone"].fillna("Unknown")
    return df

df = load_data()

# ── Sidebar Filters ──────────────────────────────────────────────
st.sidebar.title("📦 Filters")

dates = df["reporting_date"].dropna().dt.date
min_d, max_d = dates.min(), dates.max()
date_range = st.sidebar.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

zones = sorted(df["pickup_hub_zone"].dropna().unique())
zone_sel = st.sidebar.multiselect("Zone", zones, default=zones)

cities_pool = sorted(df[df["pickup_hub_zone"].isin(zone_sel)]["pickup_hub_city"].dropna().unique()) if zone_sel else sorted(df["pickup_hub_city"].dropna().unique())
city_sel = st.sidebar.multiselect("City", cities_pool)

seller_types = sorted(df["seller_type"].dropna().unique())
seller_sel = st.sidebar.multiselect("Seller Type", seller_types)

payment_sel = st.sidebar.radio("Payment Type", ["All", "prepaid", "cod"], horizontal=True)

# ── Apply Filters ────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)

if isinstance(date_range, tuple) and len(date_range) == 2:
    mask &= df["reporting_date"].dt.date.between(date_range[0], date_range[1])
elif isinstance(date_range, tuple) and len(date_range) == 1:
    mask &= df["reporting_date"].dt.date == date_range[0]

if zone_sel:
    mask &= df["pickup_hub_zone"].isin(zone_sel)
if city_sel:
    mask &= df["pickup_hub_city"].isin(city_sel)
if seller_sel:
    mask &= df["seller_type"].isin(seller_sel)
if payment_sel != "All":
    mask &= df["payment_type"] == payment_sel

fdf = df[mask]

st.sidebar.markdown(f"**Rows:** {len(fdf):,}")

# ── KPI Row ──────────────────────────────────────────────────────
st.title("📦 Pickup Hub Dashboard")

total_created = fdf["fm_created"].sum()
total_picked  = fdf["fm_picked"].sum()
total_unpicked = fdf["fm_created_unpicked"].sum()
pick_rate = (total_picked / total_created * 100) if total_created > 0 else 0
zero_rto  = fdf["zero_attempt_rto_num"].sum()
ph_in     = fdf["ph_in_volume"].sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("FM Created",   f"{total_created:,.0f}")
c2.metric("FM Picked",    f"{total_picked:,.0f}")
c3.metric("Unpicked",     f"{total_unpicked:,.0f}")
c4.metric("Pick-Thru %",  f"{pick_rate:.1f}%")
c5.metric("Zero-Att RTO", f"{zero_rto:,.0f}")
c6.metric("PH-In Volume", f"{ph_in:,.0f}")

st.divider()

# ── View Tabs ────────────────────────────────────────────────────
tabs = st.tabs(["🏙️ Hub Summary", "🗺️ Zone & City", "👤 Seller Type", "💳 Payment Split", "📋 Raw Data"])

# ── helper ──────────────────────────────────────────────────────
def pct_color(val):
    if pd.isna(val): return ""
    if val >= 80: return "background-color:#1a6b3a;color:white"
    if val >= 60: return "background-color:#856404;color:white"
    return "background-color:#842029;color:white"

def style_rates(df_in, rate_cols):
    def apply(val, col):
        if col in rate_cols: return pct_color(val)
        return ""
    return df_in.style.apply(
        lambda col: [apply(v, col.name) for v in col], axis=0
    ).format({c: "{:.1f}%" for c in rate_cols if c in df_in.columns},
             {c: "{:,.0f}" for c in df_in.columns if c not in rate_cols and df_in[c].dtype in [float, int]})

def show_table(agg_df, rate_cols=None, key=None):
    rate_cols = rate_cols or set()
    fmt = {}
    for c in agg_df.columns:
        if c in rate_cols:
            fmt[c] = "{:.1f}%"
        elif agg_df[c].dtype in [float, np.float64]:
            fmt[c] = "{:,.1f}"
        elif agg_df[c].dtype in [int, np.int64]:
            fmt[c] = "{:,}"
    st.dataframe(agg_df.style.format(fmt), width='stretch', hide_index=True, height=500)

# ── Tab 1: Hub Summary ───────────────────────────────────────────
with tabs[0]:
    st.subheader("Hub-Level Summary")
    col_sort, col_dir = st.columns([3, 1])
    sort_by = col_sort.selectbox("Sort by", ["fm_created", "fm_picked", "pick_thru_rate", "zero_attempt_rto_num", "ph_in_volume"], key="hub_sort")
    asc = col_dir.radio("Order", ["Desc", "Asc"], key="hub_dir", horizontal=True) == "Asc"

    hub_agg = fdf.groupby(["pickup_hub_name", "pickup_hub_city", "pickup_hub_zone"], as_index=False).agg(
        fm_created=("fm_created", "sum"),
        fm_picked=("fm_picked", "sum"),
        fm_unpicked=("fm_created_unpicked", "sum"),
        ph_in_volume=("ph_in_volume", "sum"),
        zero_attempt_rto_num=("zero_attempt_rto_num", "sum"),
        cron_pending_pickup=("cron_pending_pickup", "sum"),
        d0_attempt=("d0_attempt", "sum"),
        d1_attempt=("d1_attempt", "sum"),
    )
    hub_agg["pick_thru_rate"] = np.where(
        hub_agg["fm_created"] > 0,
        (hub_agg["fm_picked"] / hub_agg["fm_created"] * 100).round(1), 0
    )
    hub_agg = hub_agg.sort_values(sort_by, ascending=asc).reset_index(drop=True)

    st.caption(f"{len(hub_agg):,} hubs")
    show_table(hub_agg, rate_cols={"pick_thru_rate"}, key="hub_tbl")

# ── Tab 2: Zone & City ───────────────────────────────────────────
with tabs[1]:
    view = st.radio("Group by", ["Zone", "City"], horizontal=True, key="geo_view")
    grp_col = "pickup_hub_zone" if view == "Zone" else "pickup_hub_city"

    geo_agg = fdf.groupby(grp_col, as_index=False).agg(
        Hubs=("pickup_hub_name", "nunique"),
        FM_Created=("fm_created", "sum"),
        FM_Picked=("fm_picked", "sum"),
        Unpicked=("fm_created_unpicked", "sum"),
        PH_In=("ph_in_volume", "sum"),
        Zero_RTO=("zero_attempt_rto_num", "sum"),
        Cron_Pending=("cron_pending_pickup", "sum"),
        D0_Attempt=("d0_attempt", "sum"),
        D1_Attempt=("d1_attempt", "sum"),
    )
    geo_agg["Pick_Thru_%"] = np.where(
        geo_agg["FM_Created"] > 0,
        (geo_agg["FM_Picked"] / geo_agg["FM_Created"] * 100).round(1), 0
    )
    geo_agg = geo_agg.sort_values("FM_Created", ascending=False).reset_index(drop=True)
    show_table(geo_agg, rate_cols={"Pick_Thru_%"}, key="geo_tbl")

# ── Tab 3: Seller Type ───────────────────────────────────────────
with tabs[2]:
    st.subheader("Seller Type Breakdown")
    col_a, col_b = st.columns([2, 1])
    min_created = col_a.slider("Min FM Created", 0, int(fdf["fm_created"].sum() // 100), 0, key="seller_min")

    seller_agg = fdf.groupby("seller_type", as_index=False).agg(
        FM_Created=("fm_created", "sum"),
        FM_Picked=("fm_picked", "sum"),
        Unpicked=("fm_created_unpicked", "sum"),
        Zero_RTO=("zero_attempt_rto_num", "sum"),
        D0_Attempt=("d0_attempt", "sum"),
        D1_Attempt=("d1_attempt", "sum"),
        Hubs=("pickup_hub_name", "nunique"),
    )
    seller_agg["Pick_Thru_%"] = np.where(
        seller_agg["FM_Created"] > 0,
        (seller_agg["FM_Picked"] / seller_agg["FM_Created"] * 100).round(1), 0
    )
    seller_agg = seller_agg[seller_agg["FM_Created"] >= min_created]
    seller_agg = seller_agg.sort_values("FM_Created", ascending=False).reset_index(drop=True)
    st.caption(f"{len(seller_agg):,} seller types")
    show_table(seller_agg, rate_cols={"Pick_Thru_%"}, key="seller_tbl")

# ── Tab 4: Payment Split ─────────────────────────────────────────
with tabs[3]:
    st.subheader("Payment Type Breakdown")
    pay_grp = st.radio("Group by", ["payment_type", "pickup_hub_zone", "seller_type"], horizontal=True, key="pay_grp")

    pay_agg = fdf.groupby(["payment_type", pay_grp] if pay_grp != "payment_type" else ["payment_type"], as_index=False).agg(
        FM_Created=("fm_created", "sum"),
        FM_Picked=("fm_picked", "sum"),
        Unpicked=("fm_created_unpicked", "sum"),
        Zero_RTO=("zero_attempt_rto_num", "sum"),
        D0_Attempt=("d0_attempt", "sum"),
    )
    pay_agg["Pick_Thru_%"] = np.where(
        pay_agg["FM_Created"] > 0,
        (pay_agg["FM_Picked"] / pay_agg["FM_Created"] * 100).round(1), 0
    )
    pay_agg = pay_agg.sort_values(["payment_type", "FM_Created"], ascending=[True, False]).reset_index(drop=True)
    show_table(pay_agg, rate_cols={"Pick_Thru_%"}, key="pay_tbl")

# ── Tab 5: Raw Data ──────────────────────────────────────────────
with tabs[4]:
    st.subheader("Raw Filtered Data")
    cols_to_show = st.multiselect(
        "Columns",
        options=list(fdf.columns),
        default=["reporting_date", "pickup_hub_name", "pickup_hub_city", "pickup_hub_zone",
                 "seller_type", "payment_type", "fm_created", "fm_picked",
                 "pick_thru_rate", "zero_attempt_rto_num"],
        key="raw_cols"
    )
    if cols_to_show:
        st.caption(f"{len(fdf):,} rows")
        st.dataframe(fdf[cols_to_show].reset_index(drop=True), width='stretch', hide_index=True, height=500)
    else:
        st.info("Select at least one column.")
