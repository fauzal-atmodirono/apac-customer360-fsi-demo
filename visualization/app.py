"""Customer 360 & Hyper-Personalization — Streamlit dashboard.

Reads the live Gold mart (demo_gold_analytics.mart_customer_360) + Silver facts in
BigQuery. Run:  make dashboard   (pre-mints the masked-reader token), or
  streamlit run visualization/app.py
Auth: your ADC (fine-grained reader -> cleartext); the Governance page also
impersonates the c360-masked-reader SA to show masked PII side by side.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import queries as q

st.set_page_config(page_title="Customer 360 — Hyper-Personalization", page_icon="🏦", layout="wide")

# --- cached query wrappers (5 min) -------------------------------------------
cache = st.cache_data(ttl=300)
_fns = [
    "kpis", "segment_distribution", "age_distribution", "tier_vs_segment", "portfolio_totals",
    "region_summary", "income_band_summary", "tenure_summary",
    "churn_band_counts", "churn_scatter", "high_churn_customers", "churn_drivers",
    "churn_score_distribution", "churn_by_age_band",
    "top_spending_categories", "life_stage_bands", "propensity_distribution",
    "spend_by_category_segment", "cross_sell_opportunities", "hnw_no_mortgage",
    "daily_spend", "weekly_category_mix", "atm_trend",
    "pii_cleartext", "pii_masked",
]
Q = {name: cache(getattr(q, name)) for name in _fns}
target_list = cache(q.target_list)

# --- styling -----------------------------------------------------------------
SEGMENT_COLORS = {
    "HNW_INVESTOR": "#2E7D32", "DIGITAL_SHOPPER": "#1565C0",
    "LEVERAGED_BORROWER": "#C62828", "STANDARD_RETAIL": "#9E9E9E",
}
CHURN_COLORS = {"HIGH": "#C62828", "MEDIUM": "#F9A825", "LOW": "#2E7D32"}
CHANNEL_COLORS = {"Credit": "#1565C0", "Debit": "#26A69A"}
REGION_COORDS = {  # lat, lon for the generated regions (Indonesia)
    "JAKARTA": (-6.2088, 106.8456), "SURABAYA": (-7.2575, 112.7521),
    "BANDUNG": (-6.9175, 107.6191), "MEDAN": (3.5952, 98.6722),
    "SEMARANG": (-6.9667, 110.4167), "MAKASSAR": (-5.1477, 119.4327),
    "DENPASAR": (-8.6500, 115.2167), "BATAM": (1.0456, 104.0305),
}
SEQ = px.colors.qualitative.Safe
CHURN_ORDER = {"churn_risk_segment": ["HIGH", "MEDIUM", "LOW"]}


def money(x) -> str:
    x = float(x or 0)
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:,.0f}"


def nums(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def insight(text: str, kind: str = "info") -> None:
    {"info": st.info, "success": st.success, "warning": st.warning}[kind](text)


def style(fig, h: int = 360):
    fig.update_layout(height=h, margin=dict(t=40, b=10, l=10, r=10), legend_title_text="")
    return fig


# --- sidebar -----------------------------------------------------------------
st.sidebar.title("🏦 Customer 360")
st.sidebar.caption("Core Banking Hyper-Personalization")
PAGES = ["Executive overview", "Demographics", "Churn risk", "Marketing / NBA", "Spend & trends", "Governance"]
page = st.sidebar.radio("View", PAGES)
st.sidebar.divider()
st.sidebar.caption(f"Source: `{q.GOLD_DATASET}.mart_customer_360`")
st.sidebar.caption(f"Project: `{q.PROJECT}`")
st.sidebar.caption(f"Location: `{q.BQ_LOCATION}`")


# --- Executive ----------------------------------------------------------------
def page_executive():
    st.title("Executive overview")
    k = Q["kpis"]()
    aum = float(k["total_savings"]) + float(k["total_deposit_balance"]) if "total_deposit_balance" in k else float(k["total_savings"])
    c = st.columns(4)
    c[0].metric("Customers", f"{int(k['customers']):,}")
    c[1].metric("Total savings", money(k["total_savings"]))
    c[2].metric("Total loans", money(k["total_loans"]))
    c[3].metric("Avg invest. propensity", f"{float(k['avg_ips']):.0f}/100")
    c = st.columns(4)
    c[0].metric("Avg age", f"{float(k['avg_age']):.0f}")
    c[1].metric("Mortgage holders", f"{float(k['pct_mortgage']) * 100:.0f}%")
    c[2].metric("30-day card spend", money(k["total_card_spend"]))
    c[3].metric("Loan-to-savings ratio", f"{float(k['portfolio_ltv']):.2f}")

    seg = nums(Q["segment_distribution"](), ["customers", "avg_savings", "avg_card_spend"])
    top_seg = seg.sort_values("customers", ascending=False).iloc[0]
    insight(
        f"**{int(top_seg['customers'])} of {int(k['customers'])}** customers fall in "
        f"**{top_seg['segment']}**. Total relationship balances (savings + deposits) are "
        f"**{money(float(k['total_savings']) + float(k.get('total_deposit_balance', 0)))}**, "
        f"with **{float(k['pct_mortgage']) * 100:.0f}%** holding a mortgage."
    )
    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("Customers by propensity segment")
        fig = px.bar(seg, x="segment", y="customers", color="segment",
                     color_discrete_map=SEGMENT_COLORS, text="customers")
        st.plotly_chart(style(fig).update_layout(showlegend=False, xaxis_title=None), use_container_width=True)
        n_total = int(k["customers"])
        st.caption(f"💡 **{top_seg['segment']}** is {int(top_seg['customers']) / n_total * 100:.0f}% of the "
                   f"base — only **{n_total - int(top_seg['customers'])}** customers sit in high-value segments, "
                   f"so growth means *migrating* mass-retail clients upward.")
    with right:
        st.subheader("Age distribution")
        age = nums(Q["age_distribution"](), ["age"])
        fig = px.histogram(age, x="age", nbins=20, color_discrete_sequence=["#1565C0"])
        fig.add_vline(x=float(age["age"].mean()), line_dash="dash", line_color="#C62828",
                      annotation_text=f"avg {age['age'].mean():.0f}", annotation_position="top")
        st.plotly_chart(style(fig).update_layout(xaxis_title="age", yaxis_title="customers", bargap=0.05),
                        use_container_width=True)
        decades = (age["age"] // 10 * 10).astype(int).value_counts().head(2).index.tolist()
        st.caption(f"💡 Ages span **{int(age['age'].min())}–{int(age['age'].max())}** (avg "
                   f"**{age['age'].mean():.0f}**), busiest in the **{min(decades)}s** and **{max(decades)}s** — "
                   f"prime windows for life-stage offers (home, education, retirement).")

    left, right = st.columns(2)
    with left:
        st.subheader("Tier × propensity segment")
        tvs = nums(Q["tier_vs_segment"](), ["customers"])
        fig = px.bar(tvs, x="tier", y="customers", color="segment", barmode="group",
                     color_discrete_map=SEGMENT_COLORS)
        st.plotly_chart(style(fig).update_layout(xaxis_title=None), use_container_width=True)
        big_tier = tvs.groupby("tier")["customers"].sum().idxmax()
        st.caption(f"💡 The **{big_tier}** tier dominates the book; HNW/AFFLUENT tiers are where the "
                   f"investor & digital-shopper segments concentrate — focus wealth offers there.")
    with right:
        st.subheader("Portfolio composition")
        pt = nums(Q["portfolio_totals"](), ["amount"])
        fig = px.bar(pt, x="amount", y="pool", orientation="h", color="pool",
                     color_discrete_sequence=SEQ, text="amount")
        fig.update_traces(texttemplate="%{text:.2s}")
        st.plotly_chart(style(fig).update_layout(showlegend=False, yaxis_title=None, xaxis_title="$"), use_container_width=True)
        _sav = float(pt[pt["pool"] == "Savings"]["amount"].iloc[0])
        _loan = float(pt[pt["pool"] == "Loans outstanding"]["amount"].iloc[0])
        st.caption(f"💡 Savings **{money(_sav)}** vs loans **{money(_loan)}** — a deposit-rich "
                   f"**{_sav / _loan:.1f}:1** book with headroom to grow lending.")


# --- Demographics -------------------------------------------------------------
def page_demographics():
    st.title("Customer demographics")
    st.caption("Region, income tier, and tenure — for geographic targeting and lifecycle programs.")
    reg = nums(Q["region_summary"](), ["customers", "total_savings", "avg_ips"])
    inc = nums(Q["income_band_summary"](), ["customers", "avg_savings", "avg_income"])
    ten = nums(Q["tenure_summary"](), ["customers", "avg_savings", "avg_churn"])

    top_reg = reg.iloc[0]
    insight(
        f"**{top_reg['region'].title()}** is the largest market ({int(top_reg['customers'])} customers, "
        f"{money(top_reg['total_savings'])} savings). Customers span "
        f"**{len(reg)}** regions and **{len(inc)}** income tiers."
    )
    st.divider()

    st.subheader("Customer footprint across Indonesia")
    geo = reg.copy()
    geo["lat"] = geo["region"].map(lambda r: REGION_COORDS.get(r, (None, None))[0])
    geo["lon"] = geo["region"].map(lambda r: REGION_COORDS.get(r, (None, None))[1])
    geo = geo.dropna(subset=["lat", "lon"])
    fig = px.scatter_mapbox(
        geo, lat="lat", lon="lon", size="customers", color="total_savings",
        hover_name="region", hover_data={"customers": True, "total_savings": ":,.0f", "lat": False, "lon": False},
        color_continuous_scale="Blues", size_max=46, zoom=3.6,
        center={"lat": -2.5, "lon": 117}, mapbox_style="open-street-map",
    )
    fig.update_layout(height=420, margin=dict(t=10, b=10, l=10, r=10), coloraxis_colorbar_title="savings $")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"💡 Bubble size = customers, color = savings. The book is anchored in **Java** "
               f"(Jakarta, Surabaya, Bandung, Semarang); outer-island metros like "
               f"**{reg.sort_values('customers').iloc[0]['region'].title()}** are lighter-touch — "
               f"candidates for a digital-first acquisition play.")

    left, right = st.columns(2)
    with left:
        st.subheader("Customers by region")
        fig = px.bar(reg, x="customers", y="region", orientation="h", color="region",
                     color_discrete_sequence=SEQ)
        st.plotly_chart(style(fig).update_layout(showlegend=False,
                        yaxis={"categoryorder": "total ascending"}, yaxis_title=None), use_container_width=True)
        st.caption(f"💡 The book concentrates in **{top_reg['region'].title()}** and a few metros — "
                   f"focus branch staffing and field campaigns there, test digital in smaller regions.")
    with right:
        st.subheader("Savings by region")
        fig = px.bar(reg.sort_values("total_savings", ascending=False), x="region", y="total_savings",
                     color="region", color_discrete_sequence=SEQ)
        fig.update_traces(texttemplate="%{y:.2s}")
        st.plotly_chart(style(fig).update_layout(showlegend=False, xaxis_title=None, yaxis_title="$"),
                        use_container_width=True)
        rich_reg = reg.sort_values("total_savings", ascending=False).iloc[0]
        st.caption(f"💡 **{rich_reg['region'].title()}** holds the most savings ({money(rich_reg['total_savings'])}) "
                   f"— the priority region for wealth and deposit products.")

    left, right = st.columns(2)
    with left:
        st.subheader("Income-band distribution")
        order = ["LOW", "MID", "HIGH", "VERY_HIGH"]
        fig = px.bar(inc, x="income_band", y="customers", color="income_band",
                     category_orders={"income_band": order},
                     color_discrete_sequence=["#90CAF9", "#42A5F5", "#1565C0", "#0D47A1"])
        st.plotly_chart(style(fig).update_layout(showlegend=False, xaxis_title=None), use_container_width=True)
        hi = int(inc[inc["income_band"].isin(["HIGH", "VERY_HIGH"])]["customers"].sum())
        st.caption(f"💡 **{hi}** customers fall in HIGH / VERY_HIGH income tiers — the affluent base for "
                   f"premium cards, wealth advisory and investment offers.")
    with right:
        st.subheader("Tenure cohorts (avg churn score)")
        fig = px.bar(ten, x="tenure_band", y="customers", color="avg_churn",
                     color_continuous_scale="Reds")
        st.plotly_chart(style(fig).update_layout(xaxis_title=None, coloraxis_colorbar_title="churn"),
                        use_container_width=True)
        worst = ten.sort_values("avg_churn", ascending=False).iloc[0]
        st.caption(f"💡 The **{worst['tenure_band']}** cohort shows the highest avg churn score "
                   f"({worst['avg_churn']:.0f}) — prioritize onboarding/loyalty nudges for that tenure.")


# --- Churn --------------------------------------------------------------------
def page_churn():
    st.title("Churn risk")
    st.caption("Weighted on **ATM cash-flight intensity**, thin savings, and dormant card activity.")
    drivers = nums(Q["churn_drivers"](), ["customers", "avg_atm_withdrawals", "avg_savings", "pct_dormant_card", "savings_at_risk"])
    at_risk = drivers[drivers["band"].isin(["HIGH", "MEDIUM"])]
    n_risk = int(at_risk["customers"].sum())
    dollars = float(at_risk["savings_at_risk"].sum())
    total = int(drivers["customers"].sum())

    c = st.columns(3)
    c[0].metric("At-risk customers", f"{n_risk}", f"{n_risk / total * 100:.0f}% of base", delta_color="inverse")
    c[1].metric("Savings at risk", money(dollars))
    c[2].metric("Avg ATM (at-risk)", f"{at_risk['avg_atm_withdrawals'].mean():.1f}/mo")
    insight(
        f"**{n_risk}** customers ({n_risk / total * 100:.0f}%) are HIGH/MEDIUM churn risk, "
        f"holding **{money(dollars)}** in savings. At-risk customers average "
        f"**{at_risk['avg_atm_withdrawals'].mean():.1f}** ATM withdrawals/month vs "
        f"**{float(drivers[drivers.band=='LOW']['avg_atm_withdrawals'].iloc[0]):.1f}** for low-risk.",
        "warning",
    )
    st.divider()

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Risk bands")
        bands = nums(Q["churn_band_counts"](), ["customers"])
        fig = px.pie(bands, names="band", values="customers", hole=0.5,
                     color="band", color_discrete_map=CHURN_COLORS)
        st.plotly_chart(style(fig), use_container_width=True)
        st.caption(f"💡 **{(total - n_risk) / total * 100:.0f}%** are low-risk; **{n_risk}** "
                   f"({n_risk / total * 100:.0f}%) flag MEDIUM and **none HIGH yet** — a window to act "
                   f"before any defection.")
    with right:
        st.subheader("ATM cash-flight vs savings")
        sc = nums(Q["churn_scatter"](), ["churn_risk_score", "atm_withdrawals_last_30_days", "total_savings_balance", "cc_spend_last_30_days"])
        fig = px.scatter(sc, x="atm_withdrawals_last_30_days", y="total_savings_balance",
                         color="churn_risk_segment", size="churn_risk_score",
                         color_discrete_map=CHURN_COLORS, category_orders=CHURN_ORDER,
                         hover_data=["customer_id"])
        st.plotly_chart(style(fig).update_layout(xaxis_title="ATM withdrawals (30d)", yaxis_title="savings ($)"), use_container_width=True)
        st.caption("💡 At-risk customers (amber) sit **bottom-right** — thin savings being drained by "
                   "frequent ATM withdrawals. That cash-flight pattern is the strongest churn signal.")

    left, right = st.columns(2)
    with left:
        st.subheader("Churn-score distribution")
        dist = nums(Q["churn_score_distribution"](), ["churn_risk_score"])
        fig = px.histogram(dist, x="churn_risk_score", color="band", nbins=20,
                           color_discrete_map=CHURN_COLORS)
        st.plotly_chart(style(fig).update_layout(xaxis_title="churn score", yaxis_title="customers"), use_container_width=True)
        st.caption("💡 Scores cluster low (< 35); the **amber tail above 35** is the active watchlist — "
                   "small today, but the group to monitor as ATM/dormancy signals build.")
    with right:
        st.subheader("Risk band by age")
        cab = nums(Q["churn_by_age_band"](), ["customers"])
        fig = px.bar(cab, x="age_band", y="customers", color="band", barmode="group",
                     color_discrete_map=CHURN_COLORS)
        st.plotly_chart(style(fig).update_layout(xaxis_title=None), use_container_width=True)
        _risk_age = cab[cab["band"] != "LOW"].groupby("age_band")["customers"].sum()
        _top_age = _risk_age.idxmax() if len(_risk_age) else "—"
        st.caption(f"💡 Churn risk skews to the **{_top_age}** age band — tailor retention messaging "
                   f"(rates, fee waivers) to that cohort.")

    st.subheader("Retention target list (HIGH / MEDIUM)")
    st.dataframe(Q["high_churn_customers"](), use_container_width=True, hide_index=True)


# --- Marketing / NBA ----------------------------------------------------------
def page_marketing():
    st.title("Marketing / Next-Best-Action")
    hnw = Q["hnw_no_mortgage"]()
    cats = nums(Q["top_spending_categories"](), ["customers"])
    top_cat = cats.iloc[0]["category"] if len(cats) else "—"
    insight(
        f"**{len(hnw)}** affluent customers (savings > $100K) hold **no mortgage** — a prime "
        f"home-lending cross-sell. The most common spending category is **{top_cat}**.",
        "success",
    )
    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("Top spending categories")
        fig = px.bar(cats, x="customers", y="category", orientation="h",
                     color_discrete_sequence=["#1565C0"])
        st.plotly_chart(style(fig).update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title=None), use_container_width=True)
        _t3 = cats.head(3)["category"].tolist()
        st.caption(f"💡 **{', '.join(_t3)}** are the top spending categories — anchor merchant/cashback "
                   f"offers and next-best-action prompts to these.")
    with right:
        st.subheader("Investment-propensity distribution")
        ipsd = nums(Q["propensity_distribution"](), ["investment_propensity_score"])
        fig = px.histogram(ipsd, x="investment_propensity_score", color="segment", nbins=20,
                           color_discrete_map=SEGMENT_COLORS)
        st.plotly_chart(style(fig).update_layout(xaxis_title="IPS", yaxis_title="customers"), use_container_width=True)
        _n70 = int((ipsd["investment_propensity_score"] >= 70).sum())
        st.caption(f"💡 **{_n70}** customers score **70+** on investment propensity — the priority list "
                   f"for term-deposit and wealth-product campaigns.")

    left, right = st.columns(2)
    with left:
        st.subheader("Category mix by segment")
        scs = nums(Q["spend_by_category_segment"](), ["customers"])
        fig = px.bar(scs, x="category", y="customers", color="segment", barmode="stack",
                     color_discrete_map=SEGMENT_COLORS)
        st.plotly_chart(style(fig).update_layout(xaxis_title=None), use_container_width=True)
        st.caption("💡 Mass-retail spend is spread across all categories, while niche segments "
                   "concentrate in a few — letting you target offers by *segment × category*.")
    with right:
        st.subheader("Cross-sell map (savings vs card spend)")
        cs = nums(Q["cross_sell_opportunities"](), ["total_savings_balance", "cc_spend_last_30_days", "investment_propensity_score"])
        cs["mortgage"] = cs["has_active_mortgage"].map({True: "Has mortgage", False: "No mortgage"})
        fig = px.scatter(cs, x="total_savings_balance", y="cc_spend_last_30_days",
                         color="mortgage", size="investment_propensity_score",
                         color_discrete_map={"Has mortgage": "#9E9E9E", "No mortgage": "#2E7D32"},
                         hover_data=["customer_id"])
        st.plotly_chart(style(fig).update_layout(xaxis_title="savings ($)", yaxis_title="CC spend 30d ($)"), use_container_width=True)
        st.caption(f"💡 **Green** points to the right (high savings, **no mortgage**) are home-lending "
                   f"leads; **{len(hnw)}** hold $100K+ in savings without one. Larger dots = higher IPS.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("HNW investor targets")
        st.dataframe(target_list("HNW_INVESTOR"), use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Mortgage cross-sell (HNW, no mortgage)")
        st.dataframe(hnw, use_container_width=True, hide_index=True)


# --- Spend & trends -----------------------------------------------------------
def page_trends():
    st.title("Spend & transaction trends")
    st.caption("Card-transaction facts over the trailing 90 days (credit + debit purchases).")
    daily = nums(Q["daily_spend"](), ["spend"])
    by_channel = daily.groupby("channel")["spend"].sum()
    total = float(by_channel.sum())
    credit = float(by_channel.get("Credit", 0))
    wk = nums(Q["weekly_category_mix"](), ["spend"])
    top_cat = wk.groupby("category")["spend"].sum().idxmax() if len(wk) else "—"

    c = st.columns(3)
    c[0].metric("90-day spend", money(total))
    c[1].metric("Credit share", f"{credit / total * 100:.0f}%" if total else "—")
    c[2].metric("Top category (spend)", top_cat)
    insight(
        f"Customers spent **{money(total)}** on cards in 90 days — "
        f"**{credit / total * 100:.0f}%** credit / **{(total - credit) / total * 100:.0f}%** debit. "
        f"**{top_cat}** is the largest category by value.",
    )
    st.divider()

    st.subheader("Daily spend — credit vs debit")
    fig = px.line(daily, x="txn_date", y="spend", color="channel", color_discrete_map=CHANNEL_COLORS)
    st.plotly_chart(style(fig).update_layout(xaxis_title=None, yaxis_title="$/day"), use_container_width=True)
    st.caption(f"💡 **Credit** ({credit / total * 100:.0f}% of spend) consistently runs above debit, "
               f"peaking near **{money(daily['spend'].max())}/day** — credit is the primary payment rail "
               f"to build rewards/limit strategies around.")

    left, right = st.columns(2)
    with left:
        st.subheader("Weekly category mix")
        fig = px.area(wk, x="week", y="spend", color="category", color_discrete_sequence=SEQ)
        st.plotly_chart(style(fig).update_layout(xaxis_title=None, yaxis_title="$/week"), use_container_width=True)
        st.caption(f"💡 **{top_cat}** is the largest category by weekly value and the mix is stable "
                   f"week-to-week — a dependable base for category-linked offers.")
    with right:
        st.subheader("ATM withdrawals per week")
        atm = nums(Q["atm_trend"](), ["withdrawals", "amount"])
        fig = px.bar(atm, x="week", y="withdrawals", color_discrete_sequence=["#C62828"])
        st.plotly_chart(style(fig).update_layout(xaxis_title=None), use_container_width=True)
        st.caption(f"💡 ATM use peaks at **{int(atm['withdrawals'].max())} withdrawals** in a week — "
                   f"rising cash-out is an early churn cue (see the Churn page).")


# --- Governance ---------------------------------------------------------------
def page_governance():
    st.title("Governance: column-level security")
    st.caption("Same rows, two identities. PII columns carry BigQuery **policy tags** with "
               "**dynamic data masking** — enforced by the engine, not the app.")
    cols = ["customer_id", "full_name", "phone_number", "address", "card_number"]
    insight("**4 columns** across the medallion are policy-tag protected: name, phone, address, "
            "and card PAN. Access resolves per-identity at query time.", "success")
    left, right = st.columns(2)
    with left:
        st.subheader("🔓 Fine-grained reader (you)")
        st.caption("`categoryFineGrainedReader` → cleartext")
        st.dataframe(Q["pii_cleartext"]()[cols], use_container_width=True, hide_index=True)
        st.caption("💡 Authorized roles (e.g. marketing for outreach) see full PII — names, phones, "
                   "addresses, card numbers — to action campaigns.")
    with right:
        st.subheader("🔒 Masked reader (SA)")
        st.caption("`bigquerydatapolicy.maskedReader` → masked")
        st.dataframe(Q["pii_masked"]()[cols], use_container_width=True, hide_index=True)
        st.caption("💡 The **same query, same rows** returns SHA-256 names, redacted phones/cards and "
                   "NULL addresses for everyone else — masking is enforced by BigQuery, not the app.")
    st.markdown(
        "| Policy tag | Column | Masking rule |\n|---|---|---|\n"
        "| `PII_Name` | full_name | SHA-256 hash |\n"
        "| `PII_Phone` | phone_number | custom routine → `XXXX-XXXX-####` |\n"
        "| `PII_Address` | address | nullify → `NULL` |\n"
        "| `Card_PAN` | card_number | custom routine → `XXXXXXXXXXXX####` |"
    )


{
    "Executive overview": page_executive,
    "Demographics": page_demographics,
    "Churn risk": page_churn,
    "Marketing / NBA": page_marketing,
    "Spend & trends": page_trends,
    "Governance": page_governance,
}[page]()
