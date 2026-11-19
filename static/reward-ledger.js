(function(root){
  "use strict";
  const VALID_STATUSES=new Set(["pending","confirmed","paid","rejected"]);
  function currencyCode(value){return /^[A-Z]{3}$/.test(String(value||"").trim().toUpperCase())?String(value).trim().toUpperCase():null}
  function sumByCurrency(rows){
    return (rows||[]).reduce((totals,row)=>{
      const currency=currencyCode(row.currency);
      const amount=Number(row.amount);
      if(!currency||!Number.isFinite(amount)||amount<0)return totals;
      totals[currency]=(totals[currency]||0)+amount;
      return totals;
    },{});
  }
  function summarize(rows){
    const valid=(rows||[]).filter(row=>VALID_STATUSES.has(row.status));
    return {
      paid:valid.filter(row=>row.status==="paid"&&String(row.reference||"").trim()).filter(row=>currencyCode(row.currency)&&Number.isFinite(Number(row.amount))&&Number(row.amount)>=0),
      pending:valid.filter(row=>row.status==="pending").filter(row=>currencyCode(row.currency)&&Number.isFinite(Number(row.amount))&&Number(row.amount)>=0),
      confirmed:valid.filter(row=>row.status==="confirmed").filter(row=>currencyCode(row.currency)&&Number.isFinite(Number(row.amount))&&Number(row.amount)>=0)
    };
  }
  function summarizeByMonth(rows){
    const groups=new Map();
    for(const row of rows||[]){
      const date=new Date(row.created_at||"");
      if(!Number.isFinite(date.getTime()))continue;
      const month=date.toISOString().slice(0,7);
      if(!groups.has(month))groups.set(month,[]);
      groups.get(month).push(row);
    }
    return [...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0])).map(([month,items])=>{
      const totals=summarize(items);
      const currencies=[...new Set([...totals.paid,...totals.pending,...totals.confirmed].map(row=>currencyCode(row.currency)).filter(Boolean))].sort();
      return {month,currencies:Object.fromEntries(currencies.map(currency=>[currency,{
        paid:sumByCurrency(totals.paid.filter(row=>currencyCode(row.currency)===currency))[currency]||0,
        pending:sumByCurrency(totals.pending.filter(row=>currencyCode(row.currency)===currency))[currency]||0,
        confirmed:sumByCurrency(totals.confirmed.filter(row=>currencyCode(row.currency)===currency))[currency]||0
      }]))};
    });
  }
  function validateReward(row){
    if(!Number.isFinite(row.amount)||row.amount<=0)return "Enter a valid reward amount greater than zero.";
    if(!currencyCode(row.currency))return "Enter a valid three-letter currency code, such as USD or EUR.";
    if(!VALID_STATUSES.has(row.status))return "Select a valid reward status.";
    if(row.status==="paid"&&!String(row.reference||"").trim())return "To record a reward as paid, enter a transaction reference or other payment evidence. Do not enter full card or account numbers.";
    return "";
  }
  const api={sumByCurrency,summarize,summarizeByMonth,validateReward};
  root.AutoEarnRewardLedger=api;
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
