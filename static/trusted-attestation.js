(function(root){"use strict";
const MAX_AGE=30*86400000,SKEW=300000;
function publicHttps(v){try{const u=new URL(String(v||"")),h=u.hostname.toLowerCase().replace(/\.$/,"");return u.protocol==="https:"&&!u.username&&!u.password&&(!u.port||u.port==="443")&&h!=="localhost"&&!h.startsWith("[")&&!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(h)&&![".local",".internal",".test",".invalid",".example"].some(s=>h.endsWith(s))&&h.split(".").length>=2}catch(_){return false}}
function canonical(v){if(Array.isArray(v))return"["+v.map(canonical).join(",")+"]";if(v&&typeof v==="object")return"{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+canonical(v[k])).join(",")+"}";return JSON.stringify(v)}
function decode(v){if(typeof v!=="string"||!/^[A-Za-z0-9_-]+$/.test(v))return null;try{const b=v.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-v.length%4)%4),s=root.atob(b);return Uint8Array.from(s,c=>c.charCodeAt(0))}catch(_){return null}}
const fail=reason=>Object.freeze({verified:false,reason});
function BufferlessBase64Url(bytes,encoded){try{const binary=Array.from(bytes,b=>String.fromCharCode(b)).join("");let base64=root.btoa(binary).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"");return base64===encoded}catch(_){return false}}
async function verifyTrustedAttestation(envelope,trustedKeys,now=Date.now()){try{
if(!root.crypto?.subtle)return fail("webcrypto_unavailable");
if(!envelope||typeof envelope!=="object"||Array.isArray(envelope))return fail("invalid_envelope");
const{key_id:keyId,payload,signature}=envelope;
if(typeof keyId!=="string"||!keyId||!payload||typeof payload!=="object"||Array.isArray(payload))return fail("invalid_envelope");
const trust=trustedKeys&&Object.hasOwn(trustedKeys,keyId)?trustedKeys[keyId]:null;
if(!trust||trust.status!=="active"||typeof trust.issuer!=="string"||!trust.issuer||typeof trust.public_key_spki!=="string")return fail("untrusted_signing_key");
if(trust.revoked===true)return fail("signing_key_revoked");
const keyStarts=trust.not_before?Date.parse(trust.not_before):NaN,keyEnds=trust.not_after?Date.parse(trust.not_after):NaN;
if((trust.not_before&&!Number.isFinite(keyStarts))||(trust.not_after&&!Number.isFinite(keyEnds)))return fail("invalid_trusted_key_dates");
if(Number.isFinite(keyStarts)&&now<keyStarts)return fail("signing_key_not_yet_valid");
if(Number.isFinite(keyEnds)&&now>=keyEnds)return fail("signing_key_expired");
if(payload.issuer!==trust.issuer)return fail("issuer_mismatch");
if(typeof payload.subject_origin!=="string"||!publicHttps(payload.subject_origin))return fail("invalid_subject_origin");
const subject=new URL(payload.subject_origin);if(subject.origin!==payload.subject_origin.replace(/\/$/,""))return fail("subject_origin_must_be_origin");
if(!publicHttps(payload.terms_url)||!Array.isArray(payload.evidence_urls)||payload.evidence_urls.length<1||payload.evidence_urls.length>10||!payload.evidence_urls.every(publicHttps)||new Set(payload.evidence_urls).size!==payload.evidence_urls.length)return fail("invalid_official_evidence");
const issued=Date.parse(payload.issued_at),expires=Date.parse(payload.expires_at);
if(!Number.isFinite(issued)||!Number.isFinite(expires))return fail("invalid_attestation_dates");
if(issued>now+SKEW)return fail("attestation_from_future");
if(expires<=now||expires<=issued||expires-issued>MAX_AGE)return fail("attestation_expired_or_too_long");
const required=["official_terms_verified","cash_payout_verified","country_eligibility_verified","no_purchase_required_verified","automation_permission_verified"];
if(required.some(k=>payload[k]!==true))return fail("required_claim_missing");
const spki=decode(trust.public_key_spki),sig=decode(signature);if(!spki||!sig||BufferlessBase64Url(spki,trust.public_key_spki)===false||BufferlessBase64Url(sig,signature)===false)return fail("invalid_signature_encoding");
const key=await root.crypto.subtle.importKey("spki",spki,{name:"Ed25519"},false,["verify"]);
if(!await root.crypto.subtle.verify({name:"Ed25519"},key,sig,new TextEncoder().encode(canonical(payload))))return fail("signature_invalid");
return Object.freeze({verified:true,issuer:payload.issuer,subject_origin:payload.subject_origin,terms_url:payload.terms_url,evidence_urls:Object.freeze([...payload.evidence_urls]),issued_at:payload.issued_at,expires_at:payload.expires_at,claims:Object.freeze(Object.fromEntries(required.map(k=>[k,true])))});
}catch(_){return fail("verification_error")}}
root.AutoEarnTrustedAttestation=Object.freeze({verifyTrustedAttestation});
})(globalThis);
