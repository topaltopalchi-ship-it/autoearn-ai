import test from "node:test";import assert from "node:assert/strict";import "../static/game-agent.js";const {createAgent}=globalThis.AutoEarnGameAgent;
test("agent reaches terminal state after verified moves",async()=>{let score=0;const a=createAgent({adapter:{observe:async()=>({score}),execute:async x=>{score+=x.amount;return{score};},isTerminal:s=>s.score>=3,verify:({after,result})=>after.score===result.score},decide:async()=>({type:"score",amount:1}),limits:{maxSteps:5,allowedActions:["score"]}});const r=await a.run();assert.equal(r.status,"completed");assert.equal(r.steps,3);});
test("agent blocks actions outside allowlist",async()=>{let ran=false;const a=createAgent({adapter:{observe:async()=>({}),execute:async()=>{ran=true;}},decide:async()=>({type:"purchase"}),limits:{allowedActions:["click"]}});const r=await a.run();assert.equal(r.status,"blocked");assert.equal(ran,false);});
test("agent enforces step budget",async()=>{let n=0;const a=createAgent({adapter:{observe:async()=>({n}),execute:async()=>({n:++n})},decide:async()=>({type:"move"}),limits:{maxSteps:2,allowedActions:["move"]}});const r=await a.run();assert.equal(r.reason,"step_limit");assert.equal(r.steps,2);});
test("agent stops on failed verification",async()=>{const a=createAgent({adapter:{observe:async()=>({}),execute:async()=>({}),verify:async()=>false},decide:async()=>({type:"move"}),limits:{allowedActions:["move"]}});const r=await a.run();assert.equal(r.reason,"action_not_verified");});
test("agent honours abort signal",async()=>{const c=new AbortController();c.abort();let ran=false;const a=createAgent({adapter:{observe:async()=>({}),execute:async()=>{ran=true;}},decide:async()=>({type:"move"}),limits:{allowedActions:["move"]}});const r=await a.run({signal:c.signal});assert.equal(r.status,"stopped");assert.equal(ran,false);});
test("agent stops a repeating board-state cycle before wasting its full step budget",async()=>{
  let state="A";
  const a=createAgent({
    adapter:{
      observe:async()=>({state}),
      getStateKey:observation=>observation.state,
      execute:async()=>{state=state==="A"?"B":"A";return{state};},
      verify:()=>true
    },
    decide:async()=>({type:"move"}),
    limits:{maxSteps:20,maxRepeatedStates:3,allowedActions:["move"]}
  });
  const r=await a.run();
  assert.equal(r.status,"stalled");
  assert.equal(r.reason,"repeated_state");
  assert.equal(r.steps,4);
});
test("agent ignores malformed or oversized semantic state keys",async()=>{
  let state=0;
  const a=createAgent({
    adapter:{
      observe:async()=>({state}),
      getStateKey:()=> "x".repeat(2001),
      execute:async()=>({state:++state}),
      verify:()=>true
    },
    decide:async()=>({type:"move"}),
    limits:{maxSteps:2,allowedActions:["move"]}
  });
  const r=await a.run();
  assert.equal(r.reason,"step_limit");
  assert.equal(r.steps,2);
});
