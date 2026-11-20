import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import "../static/trusted-attestation.js";
const {publicKey,privateKey}=generateKeyPairSync("ed25519");
const trusted={"review-key-1":{issuer:"independent-review-board",status:"active",not_before:"2026-11-01T00:00:00Z",not_after:"2026-12-01T00:00:00Z",public_key_spki:Buffer.from(publicKey.export({type:"spki",format:"der"})).toString("base64url")}};
const now=Date.parse("2026-11-20T12:00:00Z");
const payload={issuer:"independent-review-board",subject_origin:"https://rewards.example.org",terms_url:"https://rewards.example.org/rules",evidence_urls:["https://rewards.example.org/payout","https://rewards.example.org/automation"],issued_at:"2026-11-20T11:00:00Z",expires_at:"2026-11-25T11:00:00Z",official_terms_verified:true,cash_payout_verified:true,country_eligibility_verified:true,no_purchase_required_verified:true,automation_permission_verified:true};
function canonical(v){if(Array.isArray(v))return"["+v.map(canonical).join(",")+"]";if(v&&typeof v==="object")return"{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+canonical(v[k])).join(",")+"}";return JSON.stringify(v)}
function envelopeFor(p=payload){return{key_id:"review-key-1",payload:p,signature:sign(null,Buffer.from(canonical(p)),privateKey).toString("base64url")}}
test("accepts a correctly signed attestation from a configured trusted key",async()=>{const r=await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(),trusted,now);assert.equal(r.verified,true);assert.equal(r.claims.automation_permission_verified,true)});
test("fails closed for unknown signing keys",async()=>{assert.deepEqual(await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(),{},now),{verified:false,reason:"untrusted_signing_key"})});
test("rejects modified claims and issuer mismatch",async()=>{assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor({...payload,cash_payout_verified:false}),trusted,now)).reason,"required_claim_missing");assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor({...payload,issuer:"other"}),trusted,now)).reason,"issuer_mismatch")});
test("rejects expired, overlong and future attestations",async()=>{for(const p of [{...payload,expires_at:"2026-11-19T11:00:00Z"},{...payload,expires_at:"2027-01-01T00:00:00Z"},{...payload,issued_at:"2026-11-20T13:00:00Z"}])assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(p),trusted,now)).verified,false)});
test("rejects unsafe evidence URLs and non-origin subjects",async()=>{for(const p of [{...payload,subject_origin:"https://rewards.example.org/path"},{...payload,terms_url:"http://rewards.example.org/rules"},{...payload,evidence_urls:["https://localhost/private"]}])assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(p),trusted,now)).verified,false)});
test("rejects invalid signatures and malformed envelopes",async()=>{const e=envelopeFor();e.signature=(e.signature[0]==="A"?"B":"A")+e.signature.slice(1);assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(e,trusted,now)).verified,false);assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(null,trusted,now)).verified,false)});

test("requires active, non-revoked signing keys within their validity window",async()=>{
 const base=trusted["review-key-1"];
 for(const entry of [{...base,status:"pending"},{...base,revoked:true},{...base,not_before:"2026-12-01T00:00:00Z"},{...base,not_after:"2026-11-19T00:00:00Z"}]){
  const r=await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(),{"review-key-1":entry},now);
  assert.equal(r.verified,false);
 }
});
test("rejects duplicate official evidence URLs and non-canonical signature encoding",async()=>{
 const duplicate={...payload,evidence_urls:[payload.evidence_urls[0],payload.evidence_urls[0]]};
 assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(duplicate),trusted,now)).reason,"invalid_official_evidence");
 const e=envelopeFor();e.signature+="=";
 assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(e,trusted,now)).reason,"invalid_signature_encoding");
});

test("rejects ambiguous timestamps and non-JSON envelope objects",async()=>{
 const ambiguous={...payload,issued_at:"November 20, 2026 11:00 UTC"};
 assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(ambiguous),trusted,now)).reason,"invalid_attestation_dates");
 const cyclic={key_id:"review-key-1",payload:{...payload},signature:"x"};cyclic.payload.loop=cyclic.payload;
 assert.equal((await AutoEarnTrustedAttestation.verifyTrustedAttestation(cyclic,trusted,now)).reason,"invalid_envelope");
});

test("rejects ambiguous and inverted trusted-key validity windows",async()=>{
 const base=trusted["review-key-1"];
 for(const entry of [
  {...base,not_before:"November 1, 2026"},
  {...base,not_after:"2026-11-20"},
  {...base,not_before:"2026-11-25T00:00:00Z",not_after:"2026-11-24T00:00:00Z"}
 ]){
  const result=await AutoEarnTrustedAttestation.verifyTrustedAttestation(envelopeFor(),{"review-key-1":entry},now);
  assert.equal(result.verified,false);
  assert.equal(result.reason,"invalid_trusted_key_dates");
 }
});
