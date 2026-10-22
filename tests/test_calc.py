import math

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
    validate_business,
    validate_nodes,
    validate_options,
)
from texts import STRINGS


def test_languages_share_keys_and_placeholders():
    import re

    assert set(STRINGS["ru"]) == set(STRINGS["ky"])
    for key, value in STRINGS["ru"].items():
        other = STRINGS["ky"][key]
        assert type(value) is type(other)
        if isinstance(value, str):
            assert set(re.findall(r"\{(\w+)\}", value)) == set(re.findall(r"\{(\w+)\}", other))
        else:
            assert len(value) == len(other)


def test_ainura_demand_is_inside_the_corridor():
    business, _, _ = example_profile()
    result = demand_metrics(business)
    assert business.marketing_spend == 150_000
    assert result.ku == 150_000 / 1_800_000
    assert result.minimum_spend == 80_000
    assert result.ku_min == 80_000 / 1_800_000
    assert result.ku_max == 0.4 * 0.3
    assert result.level is Level.GREEN
    assert result.message_key == "m_ok"
    assert result.ku_min < result.ku < result.ku_max


def test_melting_base_reports_the_monthly_gap():
    business, _, _ = example_profile()
    thin = BusinessInputs(
        revenue=business.revenue,
        margin_pct=business.margin_pct,
        sales_payroll=10_000,
        commissions=0,
        advertising=0,
        customers=business.customers,
        churn_pct=business.churn_pct,
        cac=business.cac,
        elasticity=business.elasticity,
        node_spend=business.node_spend,
    )
    result = demand_metrics(thin)
    assert result.level is Level.RED
    assert result.message_key == "m_melt"
    assert result.shortfall == 70_000
    assert result.message_args["x"] == 70_000


def test_overspend_is_yellow():
    business, _, _ = example_profile()
    heavy = BusinessInputs(
        revenue=business.revenue,
        margin_pct=business.margin_pct,
        sales_payroll=300_000,
        commissions=0,
        advertising=0,
        customers=business.customers,
        churn_pct=business.churn_pct,
        cac=business.cac,
        elasticity=business.elasticity,
        node_spend=business.node_spend,
    )
    result = demand_metrics(heavy)
    assert result.ku == 300_000 / 1_800_000
    assert result.level is Level.YELLOW
    assert result.message_key == "m_over"


def test_acquisition_more_expensive_than_contribution():
    business, _, _ = example_profile()
    broken = BusinessInputs(
        revenue=business.revenue,
        margin_pct=business.margin_pct,
        sales_payroll=business.sales_payroll,
        commissions=business.commissions,
        advertising=business.advertising,
        customers=100,
        churn_pct=80,
        cac=50_000,
        elasticity=business.elasticity,
        node_spend=business.node_spend,
    )
    result = demand_metrics(broken)
    assert result.ku_min > result.ku_max
    assert result.level is Level.RED
    assert result.message_key == "m_cost"


def test_zero_revenue_does_not_divide():
    business, _, _ = example_profile()
    empty = BusinessInputs(
        revenue=0,
        margin_pct=business.margin_pct,
        sales_payroll=1,
        commissions=0,
        advertising=0,
        customers=business.customers,
        churn_pct=business.churn_pct,
        cac=business.cac,
        elasticity=business.elasticity,
        node_spend=business.node_spend,
    )
    result = demand_metrics(empty)
    assert result.ku is None
    assert result.message_key == "m_enterR"
    assert any(issue.key == "err_revenue" for issue in validate_business(empty))


def test_two_businesses_sum_revenue():
    business = BusinessInputs(
        revenue=1_000_000,
        second_revenue=800_000,
        margin_pct=40,
        sales_payroll=80_000,
        commissions=40_000,
        advertising=30_000,
        customers=100,
        churn_pct=10,
        cac=8_000,
        elasticity=0.3,
        node_spend=15_000,
    )
    result = demand_metrics(business)
    assert result.revenue == 1_800_000
    assert result.ku == 150_000 / 1_800_000


def test_validation_rejects_bad_percents_and_negative_spend():
    business, _, _ = example_profile()
    broken = BusinessInputs(
        revenue=business.revenue,
        margin_pct=140,
        sales_payroll=-1,
        commissions=0,
        advertising=0,
        customers=-5,
        churn_pct=10,
        cac=8_000,
        elasticity=0.9,
        node_spend=0,
    )
    keys = {issue.key for issue in validate_business(broken)}
    assert keys == {"err_pct", "err_nonneg", "err_customers", "err_b"}


def test_ainura_nodes_exposure():
    business, nodes, _ = example_profile()
    result = assess_nodes(nodes, business.total_revenue, business.node_spend)
    assert result.uncovered == 3
    assert result.total_exposure == 615_000
    assert result.worst_name == "Администратор кофейни"
    assert result.worst_exposure == 360_000
    assert result.ku_nodes == 15_000 / 1_800_000
    assert result.level is Level.RED
    assert result.message_key == "m_unc"
    assert [row.level for row in result.rows] == [
        Level.RED,
        Level.RED,
        Level.YELLOW,
        Level.GREEN,
        Level.RED,
    ]


def test_blank_nodes_are_ignored_and_covered_nodes_are_green():
    covered = assess_nodes(
        [Node("", "none", 0, 0), Node("Печь", "yes", 1000, 3)],
        1_800_000,
        0,
    )
    assert covered.uncovered == 0
    assert covered.total_exposure == 3_000
    assert covered.level is Level.GREEN
    assert covered.message_key == "m_cov"
    assert assess_nodes([], 1_800_000, 0).message_key == "m_addnodes"


def test_partial_replacement_stays_yellow_even_when_covered():
    result = assess_nodes([Node("Шеф", "part", 100, 2)], 1000, 0)
    assert result.uncovered == 0
    assert result.level is Level.YELLOW
    assert result.message_key == "m_cov"


def test_ainura_payback_ranks_the_bonus_first():
    _, _, options = example_profile()
    result = assess_options(options)
    assert [row.option.name for row in result.rows][0].startswith("Надбавка")
    assert result.rows[0].is_best
    assert result.rows[0].payback == 12
    assert result.rows[0].level is Level.GREEN
    assert result.rows[0].safe_price == 3_000
    assert result.rows[0].limit_price == 6_000
    assert math.isclose(result.rows[1].payback, 10_800 / 3_500)
    assert result.rows[1].level is Level.GREEN
    assert result.rows[2].payback == 0
    assert result.rows[2].level is Level.RED
    assert result.level is Level.GREEN
    assert result.message_key == "g_pay"
    assert result.do_nothing_month == 360_000


def test_payback_bands_and_free_option():
    yellow = assess_options([Option("Ровно 1", 100, 100, 100)])
    assert yellow.rows[0].payback == 1
    assert yellow.rows[0].level is Level.YELLOW
    assert yellow.message_key == "y_ok"

    edge = assess_options([Option("Ровно 2", 100, 200, 100)])
    assert edge.rows[0].payback == 2
    assert edge.rows[0].level is Level.YELLOW

    free = assess_options([Option("Бесплатно", 0, 100, 50)])
    assert math.isinf(free.rows[0].payback)
    assert free.rows[0].level is Level.GREEN

    losing = assess_options([Option("Дорого", 1_000, 100, 10)])
    assert losing.rows[0].level is Level.RED
    assert losing.message_key == "r_no"
    assert assess_options([]).message_key == "addopts"


def test_node_and_option_validation():
    assert validate_nodes([Node("А", "none", -1, 1)])[0].key == "err_node"
    assert validate_options([Option("Б", 1, 1, 140)])[0].key == "err_opt"
    assert validate_nodes([Node("", "none", 0, 0)]) == []


def test_elasticity_helper():
    value = estimate_elasticity(100, 130, 100, 200)
    assert value is not None
    assert math.isclose(value, math.log(1.3) / math.log(2))
    assert estimate_elasticity(100, 110, 50, 50) is None
    assert estimate_elasticity(0, 110, 50, 80) is None


def test_profit_curve_peaks_at_the_upper_bound():
    business, _, _ = example_profile()
    optimum = optimal_marketing_spend(
        business.total_revenue,
        business.margin_pct,
        business.marketing_spend,
        business.elasticity,
    )
    assert optimum is not None
    at_peak = contribution_profit(
        business.total_revenue,
        business.margin_pct,
        business.marketing_spend,
        business.elasticity,
        optimum,
    )
    nearby_low = contribution_profit(
        business.total_revenue,
        business.margin_pct,
        business.marketing_spend,
        business.elasticity,
        optimum * 0.85,
    )
    nearby_high = contribution_profit(
        business.total_revenue,
        business.margin_pct,
        business.marketing_spend,
        business.elasticity,
        optimum * 1.15,
    )
    assert at_peak > nearby_low
    assert at_peak > nearby_high
    predicted = business.total_revenue * (optimum / business.marketing_spend) ** business.elasticity
    assert math.isclose(optimum / predicted, business.margin_pct / 100 * business.elasticity, rel_tol=1e-6)
