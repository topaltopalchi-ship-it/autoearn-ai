import { compare2048Policies } from "./2048-policy-comparison.mjs";

function readBoundedInteger(name, fallback, minimum, maximum) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  if (!/^\d+$/.test(raw)) throw new Error(`${name} must be an integer from ${minimum} to ${maximum}.`);
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${name} must be an integer from ${minimum} to ${maximum}.`);
  }
  return value;
}

const report = compare2048Policies({
  seed: readBoundedInteger("AUTOEARN_2048_POLICY_SEED", 2048, 0, 0xffffffff),
  episodes: readBoundedInteger("AUTOEARN_2048_POLICY_EPISODES", 5, 1, 20),
  maxMoves: readBoundedInteger("AUTOEARN_2048_POLICY_MAX_MOVES", 500, 1, 1000)
});
console.log(JSON.stringify(report, null, 2));
