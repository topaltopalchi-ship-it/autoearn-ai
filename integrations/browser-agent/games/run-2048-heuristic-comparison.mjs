import { compare2048HeuristicWeights } from "./2048-episode-simulator.mjs";

function readBoundedInteger(name, fallback, min, max) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  if (!/^\d+$/.test(raw)) throw new RangeError(`${name} must be an integer from ${min} to ${max}.`);
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new RangeError(`${name} must be an integer from ${min} to ${max}.`);
  }
  return value;
}

const options = {
  seed: readBoundedInteger("AUTOEARN_2048_SEED", 2048, 0, 0xffffffff),
  episodes: readBoundedInteger("AUTOEARN_2048_EPISODES", 20, 2, 20),
  depth: readBoundedInteger("AUTOEARN_2048_DEPTH", 2, 1, 3),
  maxMoves: readBoundedInteger("AUTOEARN_2048_MAX_MOVES", 500, 1, 1000)
};
const report = compare2048HeuristicWeights(options);
process.stdout.write(`${JSON.stringify(report, null, 2)}\\n`);
