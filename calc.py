"""Pure calculations for the business resilience calculator.

Formulas (monthly):
  KU demand      = marketing spend / revenue
  lower bound    = churn * customers * CAC / revenue
  upper bound    = contribution margin * elasticity b
  node exposure  = loss per day * days to replace
  KU nodes       = extra node spend / revenue
  payback        = (avoided loss per day * success probability) / cost per day
  safe price     = expected effect per day / 2
  contribution   = margin * revenue(M) - M, with revenue(M) = R0 * (M / M0) ** b
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Level(str, Enum):
    GREEN = "g"
    YELLOW = "y"
    RED = "r"
    NEUTRAL = "n"


REPLACEMENTS = ("none", "part", "yes")


@dataclass(frozen=True)
class BusinessInputs:
    revenue: float
    margin_pct: float
    sales_payroll: float
    commissions: float
    advertising: float
    customers: float
    churn_pct: float
    cac: float
    elasticity: float
    node_spend: float
    second_revenue: float | None = None

    @property
    def total_revenue(self) -> float:
        if self.second_revenue is None:
            return self.revenue
        return self.revenue + self.second_revenue

    @property
    def marketing_spend(self) -> float:
        return self.sales_payroll + self.commissions + self.advertising


@dataclass(frozen=True)
class Node:
    name: str
    replacement: str
    loss_per_day: float
    days: float


@dataclass(frozen=True)
class Option:
    name: str
    cost_per_day: float
    avoided_loss_per_day: float
    success_pct: float


@dataclass(frozen=True)
class Issue:
    key: str


@dataclass(frozen=True)
class DemandResult:
    revenue: float
    marketing_spend: float
    ku: float | None
    ku_min: float | None
    ku_max: float | None
    minimum_spend: float | None
    shortfall: float | None
    level: Level
    message_key: str
    message_args: dict[str, Any]


@dataclass(frozen=True)
class NodeRow:
    node: Node
    exposure: float
    level: Level


@dataclass(frozen=True)
class NodesResult:
    ku_nodes: float | None
    uncovered: int
    total_exposure: float
    worst_name: str | None
    worst_exposure: float | None
    level: Level
    message_key: str
    message_args: dict[str, Any]
    rows: tuple[NodeRow, ...]


@dataclass(frozen=True)
class PaybackRow:
    option: Option
    expected_per_day: float
    payback: float
    limit_price: float
    safe_price: float
    level: Level
    is_best: bool


@dataclass(frozen=True)
class PaybackResult:
    rows: tuple[PaybackRow, ...]
    do_nothing_month: float | None
    level: Level
    message_key: str | None
    message_args: dict[str, Any]


def example_profile(
    node_names: tuple[str, ...] | None = None,
    option_names: tuple[str, ...] | None = None,
) -> tuple[BusinessInputs, tuple[Node, ...], tuple[Option, ...]]:
    """Ainura's coffee-shop example. Marketing parts sum to 150 000 som."""
    nodes_src = (
        ("none", 12_000.0, 30.0),
        ("none", 12_000.0, 14.0),
        ("part", 8_000.0, 7.0),
        ("yes", 3_000.0, 2.0),
        ("none", 5_000.0, 5.0),
    )
    options_src = (
        (500.0, 12_000.0, 50.0),
        (3_500.0, 12_000.0, 90.0),
        (0.0, 0.0, 0.0),
    )
    node_names = node_names or (
        "Администратор кофейни",
        "Менеджер по продажам",
        "Шеф-повар",
        "Основной поставщик",
        "Печь",
    )
    option_names = option_names or (
        "Надбавка +500 сом/день",
        "Временный админ через агентство",
        "Вернуть менеджера, админа нет",
    )
    business = BusinessInputs(
        revenue=1_800_000,
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
    nodes = tuple(
        Node(node_names[i], repl, loss, days)
        for i, (repl, loss, days) in enumerate(nodes_src)
    )
    options = tuple(
        Option(option_names[i], cost, loss, prob)
        for i, (cost, loss, prob) in enumerate(options_src)
    )
    return business, nodes, options


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_business(inp: BusinessInputs) -> list[Issue]:
    issues: list[Issue] = []
    revenue = inp.total_revenue
    if not _finite(revenue) or revenue <= 0:
        issues.append(Issue("err_revenue"))
    if inp.second_revenue is not None and (
        not _finite(inp.revenue)
        or not _finite(inp.second_revenue)
        or inp.revenue < 0
        or inp.second_revenue < 0
    ):
        issues.append(Issue("err_revenue"))
    if not _finite(inp.margin_pct) or not 0 <= inp.margin_pct <= 100:
        issues.append(Issue("err_pct"))
    if not _finite(inp.churn_pct) or not 0 <= inp.churn_pct <= 100:
        issues.append(Issue("err_pct"))
    if not _finite(inp.customers) or inp.customers < 0:
        issues.append(Issue("err_customers"))
    for value in (
        inp.sales_payroll,
        inp.commissions,
        inp.advertising,
        inp.cac,
        inp.node_spend,
    ):
        if not _finite(value) or value < 0:
            issues.append(Issue("err_nonneg"))
            break
    if not _finite(inp.elasticity) or not 0.1 <= inp.elasticity <= 0.6:
        issues.append(Issue("err_b"))
    return _unique(issues)


def validate_nodes(nodes: list[Node] | tuple[Node, ...]) -> list[Issue]:
    for node in nodes:
        if _is_blank_node(node):
            continue
        if node.replacement not in REPLACEMENTS:
            return [Issue("err_node")]
        if not _finite(node.loss_per_day) or not _finite(node.days):
            return [Issue("err_node")]
        if node.loss_per_day < 0 or node.days < 0:
            return [Issue("err_node")]
    return []


def validate_options(options: list[Option] | tuple[Option, ...]) -> list[Issue]:
    for option in options:
        if _is_blank_option(option):
            continue
        if (
            not _finite(option.cost_per_day)
            or not _finite(option.avoided_loss_per_day)
            or not _finite(option.success_pct)
        ):
            return [Issue("err_opt")]
        if option.cost_per_day < 0 or option.avoided_loss_per_day < 0:
            return [Issue("err_opt")]
        if not 0 <= option.success_pct <= 100:
            return [Issue("err_opt")]
    return []


def demand_metrics(inp: BusinessInputs) -> DemandResult:
    revenue = inp.total_revenue if _finite(inp.total_revenue) else 0.0
    marketing = inp.marketing_spend if _finite(inp.marketing_spend) else 0.0
    empty = DemandResult(
        revenue=revenue,
        marketing_spend=marketing,
        ku=None,
        ku_min=None,
        ku_max=None,
        minimum_spend=None,
        shortfall=None,
        level=Level.YELLOW,
        message_key="m_enterR",
        message_args={},
    )
    if not _finite(revenue) or revenue <= 0:
        return empty
    margin = inp.margin_pct / 100.0 if _finite(inp.margin_pct) else 0.0
    churn = inp.churn_pct / 100.0 if _finite(inp.churn_pct) else 0.0
    customers = inp.customers if _finite(inp.customers) else 0.0
    cac = inp.cac if _finite(inp.cac) else 0.0
    elasticity = inp.elasticity if _finite(inp.elasticity) else 0.0
    ku = marketing / revenue
    minimum_spend = churn * customers * cac
    ku_min = minimum_spend / revenue
    ku_max = margin * elasticity
    shortfall = minimum_spend - marketing
    if ku_min > ku_max:
        level, key = Level.RED, "m_cost"
    elif ku < ku_min:
        level, key = Level.RED, "m_melt"
    elif ku > ku_max:
        level, key = Level.YELLOW, "m_over"
    else:
        level, key = Level.GREEN, "m_ok"
    return DemandResult(
        revenue=revenue,
        marketing_spend=marketing,
        ku=ku,
        ku_min=ku_min,
        ku_max=ku_max,
        minimum_spend=minimum_spend,
        shortfall=shortfall,
        level=level,
        message_key=key,
        message_args={"x": shortfall} if key == "m_melt" else {},
    )


def assess_nodes(
    nodes: list[Node] | tuple[Node, ...],
    revenue: float,
    node_spend: float,
) -> NodesResult:
    active = [node for node in nodes if not _is_blank_node(node)]
    rows: list[NodeRow] = []
    uncovered = 0
    total = 0.0
    worst_name: str | None = None
    worst_exposure: float | None = None
    any_partial = False
    for node in active:
        loss = node.loss_per_day if _finite(node.loss_per_day) else 0.0
        days = node.days if _finite(node.days) else 0.0
        exposure = loss * days
        if node.replacement == "none":
            uncovered += 1
            level = Level.RED if exposure > 0 else Level.YELLOW
        elif node.replacement == "part":
            any_partial = True
            level = Level.YELLOW
        else:
            level = Level.GREEN
        rows.append(NodeRow(node=node, exposure=exposure, level=level))
        total += exposure
        if worst_exposure is None or exposure > worst_exposure:
            worst_exposure = exposure
            worst_name = node.name.strip() or "—"
    ku_nodes = None
    if _finite(revenue) and revenue > 0 and _finite(node_spend):
        ku_nodes = node_spend / revenue
    if not active:
        level, key, args = Level.YELLOW, "m_addnodes", {}
    elif uncovered > 0:
        level = Level.RED if (worst_exposure or 0) > 0 else Level.YELLOW
        key = "m_unc"
        args = {
            "n": uncovered,
            "name": worst_name or "—",
            "exp": worst_exposure or 0,
        }
    else:
        level = Level.YELLOW if any_partial else Level.GREEN
        key, args = "m_cov", {}
    return NodesResult(
        ku_nodes=ku_nodes,
        uncovered=uncovered,
        total_exposure=total,
        worst_name=worst_name,
        worst_exposure=worst_exposure,
        level=level,
        message_key=key,
        message_args=args,
        rows=tuple(rows),
    )


def assess_options(options: list[Option] | tuple[Option, ...]) -> PaybackResult:
    active = [option for option in options if not _is_blank_option(option)]
    scored: list[PaybackRow] = []
    for option in active:
        cost = option.cost_per_day if _finite(option.cost_per_day) else 0.0
        loss = option.avoided_loss_per_day if _finite(option.avoided_loss_per_day) else 0.0
        probability = option.success_pct / 100.0 if _finite(option.success_pct) else 0.0
        expected = loss * probability
        if cost > 0:
            payback = expected / cost
        elif expected > 0:
            payback = math.inf
        else:
            payback = 0.0
        if payback > 2:
            level = Level.GREEN
        elif payback >= 1:
            level = Level.YELLOW
        else:
            level = Level.RED
        scored.append(
            PaybackRow(
                option=option,
                expected_per_day=expected,
                payback=payback,
                limit_price=expected,
                safe_price=expected / 2.0,
                level=level,
                is_best=False,
            )
        )
    scored.sort(key=lambda row: (math.isinf(row.payback), row.payback if math.isfinite(row.payback) else 0.0), reverse=True)
    if scored:
        best = scored[0]
        scored[0] = PaybackRow(
            option=best.option,
            expected_per_day=best.expected_per_day,
            payback=best.payback,
            limit_price=best.limit_price,
            safe_price=best.safe_price,
            level=best.level,
            is_best=True,
        )
        if best.payback > 2:
            level, key = Level.GREEN, "g_pay"
        elif best.payback >= 1:
            level, key = Level.YELLOW, "y_ok"
        else:
            level, key = Level.RED, "r_no"
        do_nothing = max(option.avoided_loss_per_day for option in active) * 30
        args = {"name": best.option.name.strip() or "—", "pb": best.payback}
    else:
        level, key, args, do_nothing = Level.YELLOW, "addopts", {}, None
    return PaybackResult(
        rows=tuple(scored),
        do_nothing_month=do_nothing,
        level=level,
        message_key=key,
        message_args=args,
    )


def estimate_elasticity(revenue_1: float, revenue_2: float, spend_1: float, spend_2: float) -> float | None:
    values = (revenue_1, revenue_2, spend_1, spend_2)
    if not all(_finite(value) and value > 0 for value in values):
        return None
    if spend_1 == spend_2:
        return None
    return math.log(revenue_2 / revenue_1) / math.log(spend_2 / spend_1)


def optimal_marketing_spend(
    revenue: float,
    margin_pct: float,
    marketing: float,
    elasticity: float,
) -> float | None:
    """Spend where marginal contribution equals 1, i.e. KU = margin * b."""
    if (
        not _finite(revenue)
        or not _finite(margin_pct)
        or not _finite(marketing)
        or not _finite(elasticity)
    ):
        return None
    if revenue <= 0 or marketing <= 0 or margin_pct <= 0:
        return None
    if not 0 < elasticity < 1:
        return None
    margin = margin_pct / 100.0
    base = revenue * margin * elasticity / (marketing**elasticity)
    if base <= 0:
        return None
    return base ** (1.0 / (1.0 - elasticity))


def contribution_profit(
    revenue: float,
    margin_pct: float,
    marketing: float,
    elasticity: float,
    spend: float,
) -> float | None:
    if (
        not _finite(revenue)
        or not _finite(marketing)
        or not _finite(elasticity)
        or not _finite(spend)
        or not _finite(margin_pct)
    ):
        return None
    if revenue <= 0 or marketing <= 0 or spend < 0:
        return None
    predicted = revenue * (spend / marketing) ** elasticity
    return (margin_pct / 100.0) * predicted - spend


def profit_curve(
    revenue: float,
    margin_pct: float,
    marketing: float,
    elasticity: float,
    points: int = 61,
) -> list[tuple[float, float]]:
    optimum = optimal_marketing_spend(revenue, margin_pct, marketing, elasticity)
    high = max(marketing * 2.5, (optimum or 0) * 1.35, 1.0)
    curve: list[tuple[float, float]] = []
    steps = max(points, 2)
    for index in range(steps):
        spend = high * index / (steps - 1)
        profit = contribution_profit(revenue, margin_pct, marketing, elasticity, spend)
        if profit is not None:
            curve.append((spend, profit))
    return curve


def _is_blank_node(node: Node) -> bool:
    return not node.name.strip() and node.loss_per_day == 0 and node.days == 0


def _is_blank_option(option: Option) -> bool:
    return (
        not option.name.strip()
        and option.cost_per_day == 0
        and option.avoided_loss_per_day == 0
        and option.success_pct == 0
    )


def _unique(issues: list[Issue]) -> list[Issue]:
    seen: set[str] = set()
    result: list[Issue] = []
    for issue in issues:
        if issue.key in seen:
            continue
        seen.add(issue.key)
        result.append(issue)
    return result
