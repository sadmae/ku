"""Streamlit interface for the business resilience calculator."""

from __future__ import annotations

import html
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calc import (
    BusinessInputs,
    Level,
    Node,
    Option,
    assess_nodes,
    assess_options,
    contribution_profit,
    demand_metrics,
    estimate_elasticity,
    example_profile,
    optimal_marketing_spend,
    profit_curve,
    validate_business,
    validate_nodes,
    validate_options,
)
from reports import csv_bytes, fmt_int, fmt_pb, fmt_pct, pdf_bytes, summary_rows
from texts import example_labels, t

NAVY = "#12263f"
GREEN = "#1a7f4b"
YELLOW = "#b7791f"
RED = "#c0392b"
LEVEL_COLOR = {
    Level.GREEN: GREEN,
    Level.YELLOW: YELLOW,
    Level.RED: RED,
    Level.NEUTRAL: "#9aa5b1",
}
LEVEL_BG = {
    Level.GREEN: "#e6f4ec",
    Level.YELLOW: "#fdf3dc",
    Level.RED: "#fbe7e4",
    Level.NEUTRAL: "#f8fafc",
}


def main() -> None:
    st.set_page_config(page_title="КУ — устойчивость бизнеса", layout="wide")
    st.markdown(_css(), unsafe_allow_html=True)
    _ensure_state()
    lang = _sidebar()
    business = _business_from_state()
    issues = validate_business(business)
    demand = demand_metrics(business)

    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">{esc(t(lang, "title"))}</div>
          <div class="hero-sub">{esc(t(lang, "sub"))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for issue in issues:
        _banner(Level.RED, t(lang, issue.key))

    kpi_slot = st.container()
    tab_demand, tab_nodes, tab_payback, tab_summary = st.tabs(
        [
            t(lang, "tab_demand"),
            t(lang, "tab_nodes"),
            t(lang, "tab_payback"),
            t(lang, "tab_summary"),
        ]
    )
    with tab_demand:
        _render_demand(lang, demand)
    with tab_nodes:
        nodes = _node_editor(lang)
        node_issues = validate_nodes(nodes)
        for issue in node_issues:
            _banner(Level.RED, t(lang, issue.key))
        node_result = assess_nodes(nodes, business.total_revenue, business.node_spend)
        _render_nodes(lang, node_result)
    with tab_payback:
        options = _option_editor(lang)
        option_issues = validate_options(options)
        for issue in option_issues:
            _banner(Level.RED, t(lang, issue.key))
        payback = assess_options(options)
        _render_payback(lang, payback)
    with tab_summary:
        _render_summary(lang, demand, node_result, payback)
    with kpi_slot:
        _render_strip(lang, demand, node_result, payback)


def _ensure_state() -> None:
    if "revenue" in st.session_state:
        return
    st.session_state.lang = "ru"
    st.session_state.two = False
    st.session_state.editor_nonce = 0
    st.session_state.b_note = None
    _load_example(bump=False)


def _load_example(bump: bool = True) -> None:
    lang = st.session_state.get("lang", "ru")
    node_names, option_names = example_labels(lang)
    business, nodes, options = example_profile(node_names, option_names)
    st.session_state.two = False
    st.session_state.revenue = float(business.revenue)
    st.session_state.revenue_2 = 0.0
    st.session_state.margin = float(business.margin_pct)
    st.session_state.payroll = float(business.sales_payroll)
    st.session_state.commissions = float(business.commissions)
    st.session_state.advertising = float(business.advertising)
    st.session_state.customers = float(business.customers)
    st.session_state.churn = float(business.churn_pct)
    st.session_state.cac = float(business.cac)
    st.session_state.elasticity = float(business.elasticity)
    st.session_state.node_spend = float(business.node_spend)
    st.session_state.node_rows = [_node_dict(node) for node in nodes]
    st.session_state.option_rows = [_option_dict(option) for option in options]
    st.session_state.b_note = None
    if bump:
        st.session_state.editor_nonce = int(st.session_state.get("editor_nonce", 0)) + 1


def _clear_inputs() -> None:
    st.session_state.two = False
    st.session_state.revenue = 0.0
    st.session_state.revenue_2 = 0.0
    st.session_state.margin = 0.0
    st.session_state.payroll = 0.0
    st.session_state.commissions = 0.0
    st.session_state.advertising = 0.0
    st.session_state.customers = 0.0
    st.session_state.churn = 0.0
    st.session_state.cac = 0.0
    st.session_state.elasticity = 0.3
    st.session_state.node_spend = 0.0
    st.session_state.node_rows = []
    st.session_state.option_rows = []
    st.session_state.b_note = None
    st.session_state.e_r1 = 0.0
    st.session_state.e_r2 = 0.0
    st.session_state.e_m1 = 0.0
    st.session_state.e_m2 = 0.0
    st.session_state.editor_nonce = int(st.session_state.get("editor_nonce", 0)) + 1


def _apply_elasticity() -> None:
    estimate = estimate_elasticity(
        float(st.session_state.get("e_r1") or 0),
        float(st.session_state.get("e_r2") or 0),
        float(st.session_state.get("e_m1") or 0),
        float(st.session_state.get("e_m2") or 0),
    )
    if estimate is None:
        st.session_state.b_note = ("b_need", None)
        return
    shown = f"{estimate:.2f}".replace(".", ",")
    if 0.1 <= estimate <= 0.6:
        st.session_state.elasticity = round(estimate, 2)
        st.session_state.b_note = ("b_applied", shown)
    else:
        st.session_state.b_note = ("b_bad", shown)


def _sidebar() -> str:
    with st.sidebar:
        st.radio(
            t(st.session_state.get("lang", "ru"), "lang_name"),
            options=["ru", "ky"],
            format_func=lambda code: "РУС" if code == "ru" else "КЫР",
            horizontal=True,
            key="lang",
            label_visibility="collapsed",
        )
        lang = st.session_state.lang
        left, right = st.columns(2)
        left.button(t(lang, "ex"), on_click=_load_example, width="stretch")
        right.button(t(lang, "clear"), on_click=_clear_inputs, width="stretch")
        st.checkbox(t(lang, "two"), key="two")
        if st.session_state.two:
            st.number_input(t(lang, "l_R1"), min_value=0.0, step=10_000.0, format="%.0f", key="revenue", help=t(lang, "h_R"))
            st.number_input(t(lang, "l_R2"), min_value=0.0, step=10_000.0, format="%.0f", key="revenue_2")
            total = float(st.session_state.revenue) + float(st.session_state.revenue_2)
            st.caption(t(lang, "l_R_total", x=fmt_int(total)))
        else:
            st.number_input(t(lang, "l_R"), min_value=0.0, step=10_000.0, format="%.0f", key="revenue", help=t(lang, "h_R"))
        st.number_input(t(lang, "l_m"), min_value=0.0, max_value=100.0, step=0.5, format="%.1f", key="margin", help=t(lang, "h_m"))
        st.caption(t(lang, "h_M"))
        st.number_input(t(lang, "l_payroll"), min_value=0.0, step=1_000.0, format="%.0f", key="payroll")
        st.number_input(t(lang, "l_comm"), min_value=0.0, step=1_000.0, format="%.0f", key="commissions")
        st.number_input(t(lang, "l_ads"), min_value=0.0, step=1_000.0, format="%.0f", key="advertising")
        marketing = (
            float(st.session_state.payroll)
            + float(st.session_state.commissions)
            + float(st.session_state.advertising)
        )
        st.caption(t(lang, "l_M_total", x=fmt_int(marketing)))
        st.number_input(t(lang, "l_N"), min_value=0.0, step=1.0, format="%.0f", key="customers", help=t(lang, "h_N"))
        st.number_input(t(lang, "l_c"), min_value=0.0, max_value=100.0, step=0.5, format="%.1f", key="churn", help=t(lang, "h_c"))
        st.number_input(t(lang, "l_cac"), min_value=0.0, step=100.0, format="%.0f", key="cac", help=t(lang, "h_cac"))
        st.slider(t(lang, "l_b"), min_value=0.1, max_value=0.6, step=0.01, key="elasticity", help=t(lang, "h_b"))
        with st.expander(t(lang, "helper_t")):
            st.number_input(t(lang, "e_R1"), min_value=0.0, step=1000.0, format="%.0f", key="e_r1")
            st.number_input(t(lang, "e_R2"), min_value=0.0, step=1000.0, format="%.0f", key="e_r2")
            st.number_input(t(lang, "e_M1"), min_value=0.0, step=1000.0, format="%.0f", key="e_m1")
            st.number_input(t(lang, "e_M2"), min_value=0.0, step=1000.0, format="%.0f", key="e_m2")
            st.button(t(lang, "calc_b"), on_click=_apply_elasticity)
            note = st.session_state.get("b_note")
            if note:
                key, shown = note
                st.caption(t(lang, key) if shown is None else t(lang, key, b=shown))
        st.number_input(t(lang, "l_ns"), min_value=0.0, step=1_000.0, format="%.0f", key="node_spend", help=t(lang, "h_ns"))
    return st.session_state.lang


def _business_from_state() -> BusinessInputs:
    second = float(st.session_state.revenue_2) if st.session_state.two else None
    return BusinessInputs(
        revenue=float(st.session_state.revenue),
        margin_pct=float(st.session_state.margin),
        sales_payroll=float(st.session_state.payroll),
        commissions=float(st.session_state.commissions),
        advertising=float(st.session_state.advertising),
        customers=float(st.session_state.customers),
        churn_pct=float(st.session_state.churn),
        cac=float(st.session_state.cac),
        elasticity=float(st.session_state.elasticity),
        node_spend=float(st.session_state.node_spend),
        second_revenue=second,
    )


def _render_strip(lang: str, demand, nodes, payback) -> None:
    columns = st.columns(3)
    with columns[0]:
        _card(
            t(lang, "c_ku2", a=fmt_pct(demand.ku_min), b=fmt_pct(demand.ku_max)),
            fmt_pct(demand.ku),
            demand.level,
        )
    with columns[1]:
        _card(t(lang, "c_unc"), fmt_int(nodes.uncovered), nodes.level)
    with columns[2]:
        best = payback.rows[0] if payback.rows else None
        _card(
            t(lang, "c_best"),
            fmt_pb(best.payback) if best else "—",
            best.level if best else Level.NEUTRAL,
        )


def _render_demand(lang: str, demand) -> None:
    st.subheader(t(lang, "s1t"))
    columns = st.columns(4)
    cards = (
        (t(lang, "c_ku"), fmt_pct(demand.ku), demand.level),
        (t(lang, "c_min"), fmt_pct(demand.ku_min), Level.NEUTRAL),
        (t(lang, "c_max"), fmt_pct(demand.ku_max), Level.NEUTRAL),
        (t(lang, "c_mmin"), fmt_int(demand.minimum_spend), Level.NEUTRAL),
    )
    for column, (label, value, level) in zip(columns, cards):
        with column:
            _card(label, value, level)
    if demand.ku is not None and demand.ku_min is not None and demand.ku_max is not None:
        st.plotly_chart(
            _corridor_figure(lang, demand.ku, demand.ku_min, demand.ku_max),
            config={"displayModeBar": False},
        )
        st.caption(t(lang, "note1"))
    _banner(demand.level, _message(lang, demand.message_key, demand.message_args))
    st.subheader(t(lang, "pi_title"))
    curve = profit_curve(
        demand.revenue,
        float(st.session_state.margin),
        demand.marketing_spend,
        float(st.session_state.elasticity),
    )
    if len(curve) < 2:
        st.caption(t(lang, "pi_need"))
        return
    optimum = optimal_marketing_spend(
        demand.revenue,
        float(st.session_state.margin),
        demand.marketing_spend,
        float(st.session_state.elasticity),
    )
    optimum_profit = None
    if optimum is not None:
        optimum_profit = contribution_profit(
            demand.revenue,
            float(st.session_state.margin),
            demand.marketing_spend,
            float(st.session_state.elasticity),
            optimum,
        )
    current_profit = contribution_profit(
        demand.revenue,
        float(st.session_state.margin),
        demand.marketing_spend,
        float(st.session_state.elasticity),
        demand.marketing_spend,
    )
    st.plotly_chart(
        _profit_figure(lang, curve, demand.marketing_spend, current_profit, optimum, optimum_profit),
        config={"displayModeBar": False},
    )
    st.caption(t(lang, "pi_note"))


def _render_nodes(lang: str, result) -> None:
    columns = st.columns(3)
    with columns[0]:
        _card(t(lang, "c_nodes"), fmt_pct(result.ku_nodes), result.level)
    with columns[1]:
        _card(t(lang, "c_unc"), fmt_int(result.uncovered), Level.RED if result.uncovered else Level.GREEN)
    with columns[2]:
        _card(t(lang, "c_tot"), fmt_int(result.total_exposure), Level.NEUTRAL)
    if result.rows:
        frame = pd.DataFrame(
            [
                {
                    t(lang, "th_node"): row.node.name.strip() or "—",
                    t(lang, "th_repl"): t(lang, _repl_key(row.node.replacement)),
                    t(lang, "th_exp"): fmt_int(row.exposure),
                }
                for row in result.rows
            ]
        )
        st.dataframe(frame, width="stretch", hide_index=True)
    _banner(result.level, _message(lang, result.message_key, result.message_args))


def _render_payback(lang: str, result) -> None:
    if not result.rows:
        _banner(Level.YELLOW, t(lang, "addopts"))
        return
    frame = pd.DataFrame(
        [
            {
                t(lang, "th_opt"): ("★ " if row.is_best else "") + (row.option.name.strip() or "—"),
                t(lang, "th_cost"): fmt_int(row.option.cost_per_day),
                t(lang, "th_eff"): fmt_int(row.expected_per_day),
                t(lang, "th_pb"): fmt_pb(row.payback),
                t(lang, "th_limit"): fmt_int(row.limit_price),
                t(lang, "th_safe"): fmt_int(row.safe_price),
                "_level": row.level.value,
            }
            for row in result.rows
        ]
    )
    visible = frame.drop(columns="_level")
    styles = frame["_level"].map(lambda level: f"background-color: {LEVEL_BG[Level(level)]}")
    styled = visible.style.apply(lambda _: styles, axis=0)
    st.dataframe(styled, width="stretch", hide_index=True)
    st.plotly_chart(
        _payback_figure(lang, result),
        config={"displayModeBar": False},
    )
    _banner(result.level, _message(lang, "best", result.message_args))
    if result.message_key:
        _banner(result.level, t(lang, result.message_key))
    if result.do_nothing_month is not None:
        _banner(Level.YELLOW, t(lang, "nothing", x=fmt_int(result.do_nothing_month)))


def _render_summary(lang: str, demand, nodes, payback) -> None:
    st.subheader(t(lang, "s4t"))
    _banner(demand.level, _message(lang, demand.message_key, demand.message_args))
    if not nodes.rows:
        _banner(nodes.level, t(lang, "m_nodesempty"))
    elif nodes.uncovered:
        _banner(
            nodes.level,
            t(lang, "m_unc4", n=nodes.uncovered, tot=fmt_int(nodes.total_exposure)),
        )
    else:
        _banner(nodes.level, t(lang, "m_cov4"))
    if payback.rows:
        _banner(payback.level, _message(lang, "rec", payback.message_args))
    st.caption(t(lang, "rule"))
    st.caption(t(lang, "disc"))
    narrative = [_message(lang, demand.message_key, demand.message_args)]
    if nodes.rows and nodes.uncovered:
        narrative.append(t(lang, "m_unc4", n=nodes.uncovered, tot=fmt_int(nodes.total_exposure)))
    elif nodes.rows:
        narrative.append(t(lang, "m_cov4"))
    else:
        narrative.append(t(lang, "m_nodesempty"))
    if payback.rows:
        narrative.append(_message(lang, "rec", payback.message_args))
        narrative.append(t(lang, "rule"))
    rows = summary_rows(lang, demand, nodes)
    csv_col, pdf_col = st.columns(2)
    csv_col.download_button(
        t(lang, "csv"),
        data=csv_bytes(rows),
        file_name="ustoychivost.csv",
        mime="text/csv",
        width="stretch",
    )
    pdf = pdf_bytes(lang, demand, nodes, payback, narrative)
    if pdf is None:
        pdf_col.caption(t(lang, "pdf_missing"))
    else:
        pdf_col.download_button(
            t(lang, "pdf"),
            data=pdf,
            file_name="ustoychivost.pdf",
            mime="application/pdf",
            width="stretch",
        )


def _node_editor(lang: str) -> list[Node]:
    st.subheader(t(lang, "s2t"))
    frame = _nodes_frame(lang)
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"nodes_{lang}_{st.session_state.editor_nonce}",
        column_config={
            "name": st.column_config.TextColumn(t(lang, "th_node"), required=False),
            "replacement": st.column_config.SelectboxColumn(
                t(lang, "th_repl"),
                options=[t(lang, "repl_none"), t(lang, "repl_part"), t(lang, "repl_yes")],
                required=True,
            ),
            "loss": st.column_config.NumberColumn(t(lang, "th_loss"), min_value=0, step=100),
            "days": st.column_config.NumberColumn(t(lang, "th_days"), min_value=0, step=1),
        },
    )
    nodes = _nodes_from_frame(edited, lang)
    st.session_state.node_rows = [_node_dict(node) for node in nodes]
    return nodes


def _option_editor(lang: str) -> list[Option]:
    st.subheader(t(lang, "s3t"))
    frame = _options_frame(lang)
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"options_{lang}_{st.session_state.editor_nonce}",
        column_config={
            "name": st.column_config.TextColumn(t(lang, "th_opt")),
            "cost": st.column_config.NumberColumn(t(lang, "th_cost"), min_value=0, step=100),
            "loss": st.column_config.NumberColumn(t(lang, "th_avoid"), min_value=0, step=100),
            "probability": st.column_config.NumberColumn(t(lang, "th_p"), min_value=0, max_value=100, step=1),
        },
    )
    options = _options_from_frame(edited)
    st.session_state.option_rows = [_option_dict(option) for option in options]
    return options


def _nodes_frame(lang: str) -> pd.DataFrame:
    rows = st.session_state.node_rows
    frame = pd.DataFrame(
        [
            {
                "name": row["name"],
                "replacement": t(lang, _repl_key(row["replacement"])),
                "loss": float(row["loss"]),
                "days": float(row["days"]),
            }
            for row in rows
        ]
    )
    if frame.empty:
        frame = pd.DataFrame(
            {
                "name": pd.Series(dtype="object"),
                "replacement": pd.Series(dtype="object"),
                "loss": pd.Series(dtype="float64"),
                "days": pd.Series(dtype="float64"),
            }
        )
    return frame


def _options_frame(lang: str) -> pd.DataFrame:
    del lang
    rows = st.session_state.option_rows
    frame = pd.DataFrame(
        [
            {
                "name": row["name"],
                "cost": float(row["cost"]),
                "loss": float(row["loss"]),
                "probability": float(row["probability"]),
            }
            for row in rows
        ]
    )
    if frame.empty:
        frame = pd.DataFrame(
            {
                "name": pd.Series(dtype="object"),
                "cost": pd.Series(dtype="float64"),
                "loss": pd.Series(dtype="float64"),
                "probability": pd.Series(dtype="float64"),
            }
        )
    return frame


def _nodes_from_frame(frame: pd.DataFrame, lang: str) -> list[Node]:
    labels = {
        t(lang, "repl_none"): "none",
        t(lang, "repl_part"): "part",
        t(lang, "repl_yes"): "yes",
    }
    nodes: list[Node] = []
    for record in frame.to_dict("records"):
        name = _text(record.get("name"))
        replacement = labels.get(_text(record.get("replacement")), "none")
        loss = _num(record.get("loss"))
        days = _num(record.get("days"))
        node = Node(name, replacement, loss, days)
        if name or loss or days:
            nodes.append(node)
    return nodes


def _options_from_frame(frame: pd.DataFrame) -> list[Option]:
    options: list[Option] = []
    for record in frame.to_dict("records"):
        name = _text(record.get("name"))
        cost = _num(record.get("cost"))
        loss = _num(record.get("loss"))
        probability = _num(record.get("probability"))
        option = Option(name, cost, loss, probability)
        if name or cost or loss or probability:
            options.append(option)
    return options


def _corridor_figure(lang: str, ku: float, ku_min: float, ku_max: float) -> go.Figure:
    values = [ku * 100, ku_min * 100, ku_max * 100, 1]
    high = max(values) * 1.25
    figure = go.Figure()
    left, right = sorted((ku_min * 100, ku_max * 100))
    if right > left:
        figure.add_shape(
            type="rect",
            x0=left,
            x1=right,
            y0=0,
            y1=1,
            fillcolor="rgba(26,127,75,0.28)",
            line_width=0,
        )
    figure.add_trace(
        go.Scatter(
            x=[ku * 100],
            y=[0.5],
            mode="markers",
            marker={"size": 18, "color": NAVY, "symbol": "diamond"},
            hovertemplate="%{x:.1f}%<extra></extra>",
            showlegend=False,
        )
    )
    figure.update_xaxes(range=[0, high], title=t(lang, "chart_axis"), ticksuffix="%")
    figure.update_yaxes(visible=False, range=[0, 1])
    figure.update_layout(
        height=170,
        margin={"l": 8, "r": 8, "t": 10, "b": 40},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return figure


def _profit_figure(lang, curve, current, current_profit, optimum, optimum_profit) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[point[0] for point in curve],
            y=[point[1] for point in curve],
            mode="lines",
            line={"color": NAVY, "width": 3},
            name="π(M)",
            hovertemplate="%{x:,.0f} → %{y:,.0f}<extra></extra>",
        )
    )
    if current_profit is not None:
        figure.add_trace(
            go.Scatter(
                x=[current],
                y=[current_profit],
                mode="markers",
                marker={"size": 12, "color": NAVY},
                name=t(lang, "pi_now"),
            )
        )
    if optimum is not None and optimum_profit is not None:
        figure.add_trace(
            go.Scatter(
                x=[optimum],
                y=[optimum_profit],
                mode="markers",
                marker={"size": 14, "color": GREEN, "symbol": "diamond"},
                name=t(lang, "pi_opt"),
            )
        )
    figure.update_layout(
        height=360,
        margin={"l": 8, "r": 8, "t": 10, "b": 40},
        legend={"orientation": "h"},
        xaxis_title=t(lang, "pi_x"),
        yaxis_title=t(lang, "pi_y"),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return figure


def _payback_figure(lang: str, result) -> go.Figure:
    names = [(row.option.name.strip() or "—") for row in result.rows]
    values = [20 if math.isinf(row.payback) else row.payback for row in result.rows]
    colors = [LEVEL_COLOR[row.level] for row in result.rows]
    figure = go.Figure(
        go.Bar(
            y=names,
            x=values,
            orientation="h",
            marker_color=colors,
            text=[fmt_pb(row.payback) for row in result.rows],
            textposition="outside",
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title=t(lang, "pb_chart"),
        height=max(220, 56 * len(names)),
        margin={"l": 8, "r": 24, "t": 40, "b": 24},
        xaxis_title=t(lang, "th_pb"),
        yaxis={"autorange": "reversed"},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return figure


def _card(label: str, value: str, level: Level) -> None:
    st.markdown(
        f"""
        <div class="card" style="border-left-color:{LEVEL_COLOR[level]}">
          <div class="card-value">{esc(value)}</div>
          <div class="card-label">{esc(label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _banner(level: Level, text: str) -> None:
    st.markdown(
        f'<div class="banner" style="background:{LEVEL_BG[level]}">{esc(text)}</div>',
        unsafe_allow_html=True,
    )


def _message(lang: str, key: str, args: dict) -> str:
    prepared = {}
    for name, value in args.items():
        if name in {"x", "exp", "tot"} and isinstance(value, (int, float)):
            prepared[name] = fmt_int(value)
        elif name == "pb" and isinstance(value, (int, float)):
            prepared[name] = fmt_pb(value)
        else:
            prepared[name] = value
    return t(lang, key, **prepared)


def _css() -> str:
    return """
    <style>
      .stApp { background: #f5f6f8; }
      .hero { background:#12263f; color:#fff; padding:16px 18px; border-radius:12px; margin-bottom:8px; }
      .hero-title { font-size:22px; font-weight:700; }
      .hero-sub { color:#b8c4d6; font-size:14px; margin-top:4px; }
      .card { background:#f8fafc; border-left:5px solid #9aa5b1; border-radius:10px; padding:12px 14px; min-height:86px; margin-bottom:8px; }
      .card-value { font-size:22px; font-weight:700; color:#1f2933; }
      .card-label { font-size:12px; color:#6b7785; margin-top:4px; }
      .banner { padding:10px 12px; border-radius:8px; margin:8px 0; line-height:1.45; color:#1f2933; }
      div[data-testid="stSidebar"] { background:#ffffff; }
    </style>
    """


def _node_dict(node: Node) -> dict:
    return {
        "name": node.name,
        "replacement": node.replacement,
        "loss": node.loss_per_day,
        "days": node.days,
    }


def _option_dict(option: Option) -> dict:
    return {
        "name": option.name,
        "cost": option.cost_per_day,
        "loss": option.avoided_loss_per_day,
        "probability": option.success_pct,
    }


def _repl_key(code: str) -> str:
    return {"none": "repl_none", "part": "repl_part", "yes": "repl_yes"}.get(code, "repl_none")


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _num(value) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
