import { simulate2048Episodes } from "./2048-episode-simulator.mjs";

const report = simulate2048Episodes();
console.log(JSON.stringify(report, null, 2));
