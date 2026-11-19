import { benchmark2048Strategies } from "./2048-strategy-benchmark.mjs";

const report = benchmark2048Strategies();
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
