(function (root) {
  "use strict";

  function estimateOpportunityEconomics(input = {}) {
    const reward = Number(input.rewardAmount);
    const probability = Number(input.successProbability);
    const hours = Number(input.timeHours);
    const costs = Number(input.directCosts ?? 0);
    const currency = String(input.currency || "").trim().toUpperCase();

    if (!Number.isFinite(reward) || reward <= 0) throw new TypeError("Reward amount must be greater than zero.");
    if (!/^[A-Z]{3}$/.test(currency)) throw new TypeError("Currency must be a three-letter code.");
    if (!Number.isFinite(probability) || probability < 0 || probability > 1) {
      throw new RangeError("Success probability must be between 0 and 1.");
    }
    if (!Number.isFinite(hours) || hours <= 0) throw new RangeError("Time estimate must be greater than zero.");
    if (!Number.isFinite(costs) || costs < 0) throw new RangeError("Direct costs cannot be negative.");

    const expectedGross = reward * probability;
    const expectedNet = expectedGross - costs;
    return Object.freeze({
      currency,
      expectedGross: Number(expectedGross.toFixed(2)),
      expectedNet: Number(expectedNet.toFixed(2)),
      expectedNetPerHour: Number((expectedNet / hours).toFixed(2)),
      breakEvenSuccessProbability: Number((costs / reward).toFixed(4)),
      profitableOnExpectedValue: expectedNet > 0,
      assumptions: Object.freeze([
        "Inputs are estimates supplied by the owner, not verified facts.",
        "Expected value is not a guarantee of success or payment.",
        "Only include opportunities with no required deposit, purchase, or investment.",
        "Automation is permitted only when the platform's official rules explicitly allow it."
      ])
    });
  }

  root.AutoEarnOpportunityEconomics = Object.freeze({ estimateOpportunityEconomics });
  if (typeof module !== "undefined" && module.exports) module.exports = root.AutoEarnOpportunityEconomics;
})(typeof globalThis !== "undefined" ? globalThis : this);
