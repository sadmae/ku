import assert from "node:assert/strict";
import test from "node:test";
import {
  assessNodes,
  assessOptions,
  demandMetrics,
  estimateElasticity,
  exampleProfile,
  optimalMarketingSpend,
  contributionProfit,
} from "../public/calc.js";

const names = ["Администратор кофейни", "Менеджер по продажам", "Шеф-повар", "Основной поставщик", "Печь"];
const optNames = ["Надбавка +500 сом/день", "Временный админ через агентство", "Вернуть менеджера, админа нет"];

test("ainura corridor, nodes and payback match the python model", () => {
  const { business, nodes, options } = exampleProfile(names, optNames);
  const demand = demandMetrics(business);
  assert.equal(demand.marketingSpend, 150000);
  assert.equal(demand.ku, 150000 / 1800000);
  assert.equal(demand.minimumSpend, 80000);
  assert.equal(demand.kuMax, 0.12);
  assert.equal(demand.level, "g");
  assert.equal(demand.messageKey, "m_ok");

  const nodeResult = assessNodes(nodes, 1800000, 15000);
  assert.equal(nodeResult.uncovered, 3);
  assert.equal(nodeResult.totalExposure, 615000);
  assert.equal(nodeResult.worstName, "Администратор кофейни");
  assert.equal(nodeResult.worstExposure, 360000);

  const payback = assessOptions(options);
  assert.equal(payback.rows[0].payback, 12);
  assert.equal(payback.rows[0].safePrice, 3000);
  assert.ok(Math.abs(payback.rows[1].payback - 10800 / 3500) < 1e-9);
  assert.equal(payback.doNothingMonth, 360000);
  assert.equal(payback.messageKey, "g_pay");
});

test("melting base and impossible acquisition", () => {
  const { business } = exampleProfile(names, optNames);
  const thin = { ...business, salesPayroll: 10000, commissions: 0, advertising: 0 };
  const melt = demandMetrics(thin);
  assert.equal(melt.messageKey, "m_melt");
  assert.equal(melt.shortfall, 70000);
  const broken = { ...business, churnPct: 80, cac: 50000 };
  assert.equal(demandMetrics(broken).messageKey, "m_cost");
});

test("elasticity and profit peak", () => {
  const value = estimateElasticity(100, 130, 100, 200);
  assert.ok(Math.abs(value - Math.log(1.3) / Math.log(2)) < 1e-12);
  assert.equal(estimateElasticity(100, 110, 50, 50), null);
  const optimum = optimalMarketingSpend(1800000, 40, 150000, 0.3);
  const peak = contributionProfit(1800000, 40, 150000, 0.3, optimum);
  const low = contributionProfit(1800000, 40, 150000, 0.3, optimum * 0.85);
  const high = contributionProfit(1800000, 40, 150000, 0.3, optimum * 1.15);
  assert.ok(peak > low && peak > high);
});
