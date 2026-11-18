import test from "node:test";
import assert from "node:assert/strict";
import "../static/reward-ledger.js";
const {sumByCurrency,summarize,validateReward}=globalThis.AutoEarnRewardLedger;

test("sums currencies separately without mixing them",()=>{
  assert.deepEqual(sumByCurrency([{amount:10,currency:"USD"},{amount:5,currency:"EUR"},{amount:2,currency:"USD"}]),{USD:12,EUR:5});
});
test("only paid rows with a reference count as paid; pending and confirmed stay separate",()=>{
  const rows=[
    {amount:10,currency:"USD",status:"paid",reference:"TX-1"},
    {amount:99,currency:"USD",status:"paid",reference:""},
    {amount:7,currency:"EUR",status:"pending"},
    {amount:3,currency:"USD",status:"confirmed"},
    {amount:500,currency:"USD",status:"rejected"}
  ];
  const result=summarize(rows);
  assert.deepEqual(result.paid.map(r=>r.amount),[10]);
  assert.deepEqual(result.pending.map(r=>r.amount),[7]);
  assert.deepEqual(result.confirmed.map(r=>r.amount),[3]);
});
test("rejects invalid currency, status, nonpositive amount and paid without evidence",()=>{
  assert.match(validateReward({amount:1,currency:"US",status:"pending"}),/currency/i);
  assert.match(validateReward({amount:1,currency:"USD",status:"unknown"}),/status/i);
  assert.match(validateReward({amount:0,currency:"USD",status:"pending"}),/amount/i);
  assert.match(validateReward({amount:1,currency:"USD",status:"paid",reference:""}),/reference/i);
  assert.equal(validateReward({amount:1,currency:"USD",status:"paid",reference:"TX-2"}),"");
});
