import { compare2048HeuristicWeights } from "./2048-episode-simulator.mjs";

const report = compare2048HeuristicWeights({ seed: 2048, episodes: 10, depth: 2, maxMoves: 500 });
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
