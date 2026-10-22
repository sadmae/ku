/** Same formulas as calc.py. Runs in the browser and in Node. */

export function exampleProfile(nodeNames, optionNames) {
  const nodesSrc = [
    ["none", 12000, 30],
    ["none", 12000, 14],
    ["part", 8000, 7],
    ["yes", 3000, 2],
    ["none", 5000, 5],
  ];
  const optionsSrc = [
    [500, 12000, 50],
    [3500, 12000, 90],
    [0, 0, 0],
  ];
  const business = {
    revenue: 1800000,
    secondRevenue: null,
    marginPct: 40,
    salesPayroll: 80000,
    commissions: 40000,
    advertising: 30000,
    customers: 100,
    churnPct: 10,
    cac: 8000,
    elasticity: 0.3,
    nodeSpend: 15000,
  };
  const nodes = nodesSrc.map(([replacement, lossPerDay, days], i) => ({
    name: nodeNames[i],
    replacement,
    lossPerDay,
    days,
  }));
  const options = optionsSrc.map(([costPerDay, avoidedLossPerDay, successPct], i) => ({
    name: optionNames[i],
    costPerDay,
    avoidedLossPerDay,
    successPct,
  }));
  return { business, nodes, options };
}

export function totalRevenue(inp) {
  if (inp.secondRevenue == null) return num(inp.revenue);
  return num(inp.revenue) + num(inp.secondRevenue);
}

export function marketingSpend(inp) {
  return num(inp.salesPayroll) + num(inp.commissions) + num(inp.advertising);
}

export function demandMetrics(inp) {
  const revenue = totalRevenue(inp);
  const marketing = marketingSpend(inp);
  if (!(revenue > 0) || !Number.isFinite(revenue)) {
    return {
      revenue,
      marketingSpend: marketing,
      ku: null,
      kuMin: null,
      kuMax: null,
      minimumSpend: null,
      shortfall: null,
      level: "y",
      messageKey: "m_enterR",
      messageArgs: {},
    };
  }
  const margin = num(inp.marginPct) / 100;
  const churn = num(inp.churnPct) / 100;
  const ku = marketing / revenue;
  const minimumSpend = churn * num(inp.customers) * num(inp.cac);
  const kuMin = minimumSpend / revenue;
  const kuMax = margin * num(inp.elasticity);
  const shortfall = minimumSpend - marketing;
  let level;
  let messageKey;
  if (kuMin > kuMax) {
    level = "r";
    messageKey = "m_cost";
  } else if (ku < kuMin) {
    level = "r";
    messageKey = "m_melt";
  } else if (ku > kuMax) {
    level = "y";
    messageKey = "m_over";
  } else {
    level = "g";
    messageKey = "m_ok";
  }
  return {
    revenue,
    marketingSpend: marketing,
    ku,
    kuMin,
    kuMax,
    minimumSpend,
    shortfall,
    level,
    messageKey,
    messageArgs: messageKey === "m_melt" ? { x: shortfall } : {},
  };
}

export function assessNodes(nodes, revenue, nodeSpend) {
  const active = nodes.filter((node) => !isBlankNode(node));
  let uncovered = 0;
  let total = 0;
  let worstName = null;
  let worstExposure = null;
  let anyPartial = false;
  const rows = active.map((node) => {
    const exposure = num(node.lossPerDay) * num(node.days);
    let level;
    if (node.replacement === "none") {
      uncovered += 1;
      level = exposure > 0 ? "r" : "y";
    } else if (node.replacement === "part") {
      anyPartial = true;
      level = "y";
    } else {
      level = "g";
    }
    total += exposure;
    if (worstExposure == null || exposure > worstExposure) {
      worstExposure = exposure;
      worstName = (node.name || "").trim() || "—";
    }
    return { node, exposure, level };
  });
  const kuNodes = revenue > 0 && Number.isFinite(nodeSpend) ? nodeSpend / revenue : null;
  let level;
  let messageKey;
  let messageArgs = {};
  if (!active.length) {
    level = "y";
    messageKey = "m_addnodes";
  } else if (uncovered > 0) {
    level = (worstExposure || 0) > 0 ? "r" : "y";
    messageKey = "m_unc";
    messageArgs = { n: uncovered, name: worstName || "—", exp: worstExposure || 0 };
  } else {
    level = anyPartial ? "y" : "g";
    messageKey = "m_cov";
  }
  return { kuNodes, uncovered, totalExposure: total, worstName, worstExposure, level, messageKey, messageArgs, rows };
}

export function assessOptions(options) {
  const active = options.filter((option) => !isBlankOption(option));
  const scored = active.map((option) => {
    const cost = num(option.costPerDay);
    const loss = num(option.avoidedLossPerDay);
    const expected = loss * (num(option.successPct) / 100);
    let payback;
    if (cost > 0) payback = expected / cost;
    else if (expected > 0) payback = Infinity;
    else payback = 0;
    const level = payback > 2 ? "g" : payback >= 1 ? "y" : "r";
    return {
      option,
      expectedPerDay: expected,
      payback,
      limitPrice: expected,
      safePrice: expected / 2,
      level,
      isBest: false,
    };
  });
  scored.sort((a, b) => {
    const ai = Number.isFinite(a.payback) ? a.payback : Number.MAX_VALUE;
    const bi = Number.isFinite(b.payback) ? b.payback : Number.MAX_VALUE;
    return bi - ai;
  });
  if (scored.length) scored[0].isBest = true;
  if (!scored.length) {
    return { rows: [], doNothingMonth: null, level: "y", messageKey: "addopts", messageArgs: {} };
  }
  const best = scored[0];
  const level = best.payback > 2 ? "g" : best.payback >= 1 ? "y" : "r";
  const messageKey = best.payback > 2 ? "g_pay" : best.payback >= 1 ? "y_ok" : "r_no";
  const doNothingMonth = Math.max(...active.map((option) => num(option.avoidedLossPerDay))) * 30;
  return {
    rows: scored,
    doNothingMonth,
    level,
    messageKey,
    messageArgs: { name: (best.option.name || "").trim() || "—", pb: best.payback },
  };
}

export function estimateElasticity(r1, r2, m1, m2) {
  if (![r1, r2, m1, m2].every((value) => Number.isFinite(value) && value > 0)) return null;
  if (m1 === m2) return null;
  return Math.log(r2 / r1) / Math.log(m2 / m1);
}

export function optimalMarketingSpend(revenue, marginPct, marketing, elasticity) {
  if (!(revenue > 0) || !(marketing > 0) || !(marginPct > 0)) return null;
  if (!(elasticity > 0 && elasticity < 1)) return null;
  const margin = marginPct / 100;
  const base = (revenue * margin * elasticity) / marketing ** elasticity;
  if (!(base > 0)) return null;
  return base ** (1 / (1 - elasticity));
}

export function contributionProfit(revenue, marginPct, marketing, elasticity, spend) {
  if (!(revenue > 0) || !(marketing > 0) || spend < 0) return null;
  const predicted = revenue * (spend / marketing) ** elasticity;
  return (marginPct / 100) * predicted - spend;
}

export function profitCurve(revenue, marginPct, marketing, elasticity, points = 61) {
  const optimum = optimalMarketingSpend(revenue, marginPct, marketing, elasticity);
  const high = Math.max(marketing * 2.5, (optimum || 0) * 1.35, 1);
  const steps = Math.max(points, 2);
  const curve = [];
  for (let i = 0; i < steps; i += 1) {
    const spend = (high * i) / (steps - 1);
    const profit = contributionProfit(revenue, marginPct, marketing, elasticity, spend);
    if (profit != null) curve.push([spend, profit]);
  }
  return curve;
}

export function validateBusiness(inp) {
  const issues = [];
  const revenue = totalRevenue(inp);
  if (!(revenue > 0) || !Number.isFinite(revenue)) issues.push("err_revenue");
  if (!inRange(inp.marginPct, 0, 100) || !inRange(inp.churnPct, 0, 100)) issues.push("err_pct");
  if (!(num(inp.customers) >= 0)) issues.push("err_customers");
  if ([inp.salesPayroll, inp.commissions, inp.advertising, inp.cac, inp.nodeSpend].some((value) => !(num(value) >= 0))) {
    issues.push("err_nonneg");
  }
  if (!inRange(inp.elasticity, 0.1, 0.6)) issues.push("err_b");
  return [...new Set(issues)];
}

function num(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function inRange(value, min, max) {
  return Number.isFinite(Number(value)) && Number(value) >= min && Number(value) <= max;
}

function isBlankNode(node) {
  return !(node.name || "").trim() && num(node.lossPerDay) === 0 && num(node.days) === 0;
}

function isBlankOption(option) {
  return (
    !(option.name || "").trim() &&
    num(option.costPerDay) === 0 &&
    num(option.avoidedLossPerDay) === 0 &&
    num(option.successPct) === 0
  );
}
