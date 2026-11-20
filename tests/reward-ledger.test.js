import test from "node:test";
import assert from "node:assert/strict";
import "../static/reward-ledger.js";
const {sumByCurrency,summarize,summarizeByMonth,validateReward,canTransition}=globalThis.AutoEarnRewardLedger;

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

test("groups reward totals by UTC month and currency without mixing statuses",()=>{
  const rows=[
    {amount:12,currency:"USD",status:"paid",reference:"TX-1",created_at:"2026-11-03T23:30:00-05:00"},
    {amount:8,currency:"USD",status:"pending",created_at:"2026-11-10T12:00:00Z"},
    {amount:4,currency:"EUR",status:"confirmed",created_at:"2026-10-02T08:00:00Z"},
    {amount:90,currency:"USD",status:"paid",reference:"",created_at:"2026-11-12T08:00:00Z"},
    {amount:50,currency:"USD",status:"rejected",created_at:"2026-11-12T08:00:00Z"},
    {amount:3,currency:"USD",status:"paid",reference:"TX-2",created_at:"not-a-date"}
  ];
  assert.deepEqual(summarizeByMonth(rows),[
    {month:"2026-11",currencies:{USD:{paid:12,pending:8,confirmed:0}}},
    {month:"2026-10",currencies:{EUR:{paid:0,pending:0,confirmed:4}}}
  ]);
});

test("allows only pending-to-confirmed/rejected and confirmed-to-paid/rejected transitions",()=>{
  assert.equal(canTransition("pending","confirmed"),true);
  assert.equal(canTransition("pending","rejected"),true);
  assert.equal(canTransition("confirmed","paid"),true);
  assert.equal(canTransition("confirmed","rejected"),true);
  for(const [from,to] of [["pending","paid"],["paid","confirmed"],["paid","rejected"],["rejected","pending"],["unknown","paid"]]){
    assert.equal(canTransition(from,to),false);
  }
});
