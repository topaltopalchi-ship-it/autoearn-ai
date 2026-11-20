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
