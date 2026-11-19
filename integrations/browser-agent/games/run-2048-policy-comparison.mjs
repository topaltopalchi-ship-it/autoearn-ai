import { compare2048Policies } from "./2048-policy-comparison.mjs";

const report = compare2048Policies();
console.log(JSON.stringify(report, null, 2));
