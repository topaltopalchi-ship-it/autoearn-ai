import test from "node:test";
import assert from "node:assert/strict";
import "../static/opportunity-economics.js";

const estimate = globalThis.AutoEarnOpportunityEconomics.estimateOpportunityEconomics;

test("estimates risk-adjusted net reward and hourly value without promising income", () => {
  const result = estimate({
    rewardAmount: 20,
    currency: "usd",
    successProbability: 0.7,
    timeHours: 2,
    directCosts: 3
  });
  assert.deepEqual(
    {
      currency: result.currency,
      expectedGross: result.expectedGross,
      expectedNet: result.expectedNet,
      expectedNetPerHour: result.expectedNetPerHour,
      breakEvenSuccessProbability: result.breakEvenSuccessProbability,
      profitableOnExpectedValue: result.profitableOnExpectedValue
    },
    {
      currency: "USD",
      expectedGross: 14,
      expectedNet: 11,
      expectedNetPerHour: 5.5,
      breakEvenSuccessProbability: 0.15,
      profitableOnExpectedValue: true
    }
  );
  assert.match(result.assumptions[1], /not a guarantee/i);
});

test("reports negative expected value when estimated costs exceed expected reward", () => {
  const result = estimate({
    rewardAmount: 10,
    currency: "EUR",
    successProbability: 0.2,
    timeHours: 1,
    directCosts: 4
  });
  assert.equal(result.expectedNet, -2);
  assert.equal(result.profitableOnExpectedValue, false);
});

test("rejects invalid reward, currency, probability, time and costs", () => {
  assert.throws(() => estimate({ rewardAmount: 0, currency: "USD", successProbability: 1, timeHours: 1 }), /Reward/);
  assert.throws(() => estimate({ rewardAmount: 1, currency: "US", successProbability: 1, timeHours: 1 }), /Currency/);
  assert.throws(() => estimate({ rewardAmount: 1, currency: "USD", successProbability: 1.1, timeHours: 1 }), /probability/);
  assert.throws(() => estimate({ rewardAmount: 1, currency: "USD", successProbability: 1, timeHours: 0 }), /Time/);
  assert.throws(() => estimate({ rewardAmount: 1, currency: "USD", successProbability: 1, timeHours: 1, directCosts: -1 }), /costs/);
});

test("extracts only complete owner-entered estimates from the eligibility review marker", () => {
  const extract = globalThis.AutoEarnOpportunityEconomics.extractOwnerEstimate;
  const notes = "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + JSON.stringify({
    estimated_economics: {
      reward_amount: 20,
      currency: "USD",
      success_probability: 0.75,
      time_hours: 2,
      direct_costs: 1
    }
  });
  const result = extract(notes);
  assert.equal(result.expectedNet, 14);
  assert.equal(result.expectedNetPerHour, 7);
  assert.equal(result.currency, "USD");
  assert.equal(extract("Owner notes only"), null);
  assert.equal(extract("[OWNER OFFICIAL ELIGIBILITY REVIEW]\n{broken"), null);
});

test("ranks estimated hourly value first and keeps unestimated entries last without mutating input", () => {
  const sort = globalThis.AutoEarnOpportunityEconomics.sortByExpectedHourlyValue;
  const make = (id, hourly, created_at) => ({
    id,
    created_at,
    notes: "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + JSON.stringify({
      estimated_economics: {
        reward_amount: hourly * 2,
        currency: "USD",
        success_probability: 1,
        time_hours: 2,
        direct_costs: 0
      }
    })
  });
  const high = make("high", 8, "2026-01-01");
  const low = make("low", 2, "2026-01-03");
  const unknown = { id: "unknown", created_at: "2026-01-04", notes: "No estimate" };
  const input = [unknown, low, high];
  assert.deepEqual(sort(input).map(item => item.id), ["high", "low", "unknown"]);
  assert.deepEqual(input.map(item => item.id), ["unknown", "low", "high"]);
});

test("does not compare hourly estimates across different currencies", () => {
  const sort = globalThis.AutoEarnOpportunityEconomics.sortByExpectedHourlyValue;
  const make = (id, currency, created_at) => ({
    id, created_at,
    notes: "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + JSON.stringify({
      estimated_economics: {
        reward_amount: 100, currency, success_probability: 1,
        time_hours: 1, direct_costs: 0
      }
    })
  });
  const rows = [make("EUR", "EUR", "2026-01-01"), make("USD", "USD", "2026-01-02")];
  assert.deepEqual(sort(rows).map(item => item.id), ["USD", "EUR"]);
});
