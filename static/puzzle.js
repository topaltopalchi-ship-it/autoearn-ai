(() => {
  const boardEl = document.getElementById("puzzle-board");
  if (!boardEl) return;
  const goal = "123456780";
  let state = goal.split("");
  let moves = 0;
  let busy = false;
  const $ = id => document.getElementById(id);
  const neighbors = i => [i-3,i+3,...(i%3 ? [i-1] : []),...(i%3!==2 ? [i+1] : [])].filter(n => n>=0 && n<9);
  const manhattan = s => s.reduce((sum,v,i) => {
    if (v === "0") return sum;
    const n = Number(v)-1;
    return sum + Math.abs(Math.floor(i/3)-Math.floor(n/3)) + Math.abs(i%3-n%3);
  },0);
  const solved = () => state.join("") === goal;
  function render(message) {
    boardEl.innerHTML = state.map((v,i) => v === "0"
      ? '<div class="puzzle-tile blank" aria-label="Empty"></div>'
      : '<button type="button" class="puzzle-tile" data-index="'+i+'" aria-label="Move tile '+v+'">'+v+'</button>').join("");
    boardEl.querySelectorAll("[data-index]").forEach(b => b.addEventListener("click", () => move(Number(b.dataset.index))));
    $("puzzle-moves").textContent = String(moves);
    $("puzzle-status").textContent = message || (solved() ? "Solved! Great work." : "Tap a tile next to the empty space.");
    $("puzzle-solve").disabled = busy || solved();
  }
  function move(i) {
    if (busy) return;
    const blank = state.indexOf("0");
    if (!neighbors(blank).includes(i)) return;
    [state[i],state[blank]] = [state[blank],state[i]];
    moves++;
    render();
  }
  function shuffle() {
    if (busy) return;
    state = goal.split("");
    let previous = -1;
    for (let k=0;k<24;k++) {
      const blank = state.indexOf("0");
      const choices = neighbors(blank).filter(n => n !== previous);
      const next = choices[Math.floor(Math.random()*choices.length)];
      [state[next],state[blank]] = [state[blank],state[next]];
      previous = blank;
    }
    moves = 0;
    render("New solvable puzzle ready. Auto-solve uses a local search algorithm.");
  }
  function findSolution() {
    const start = state.join("");
    const path = [];
    const opposite = {U:"D",D:"U",L:"R",R:"L"};
    const directions = [{d:"U",delta:-3},{d:"D",delta:3},{d:"L",delta:-1},{d:"R",delta:1}];
    let bound = manhattan(state);
    const maxBound = 45;
    function dfs(blank,g,previous,limit) {
      const h = manhattan(state);
      const f = g+h;
      if (f>limit) return f;
      if (h===0) return true;
      let min=Infinity;
      const options = directions.filter(x => x.d!==opposite[previous] && blank+x.delta>=0 && blank+x.delta<9 && !(x.d==="L"&&blank%3===0) && !(x.d==="R"&&blank%3===2))
        .map(x => ({...x,score: (()=>{const j=blank+x.delta;const v=state[j];const old=Math.abs(Math.floor(j/3)-(Number(v)-1)/3)+Math.abs(j%3-(Number(v)-1)%3);const ni=blank;const now=Math.abs(Math.floor(ni/3)-Math.floor((Number(v)-1)/3))+Math.abs(ni%3-(Number(v)-1)%3);return old-now;})()}))
        .sort((a,b)=>b.score-a.score);
      for (const option of options) {
        const j=blank+option.delta;
        [state[blank],state[j]]=[state[j],state[blank]];
        path.push(option.d);
        const result=dfs(j,g+1,option.d,limit);
        if(result===true)return true;
        path.pop();
        [state[blank],state[j]]=[state[j],state[blank]];
        if(result<min)min=result;
      }
      return min;
    }
    while(bound<=maxBound) {
      const result=dfs(state.indexOf("0"),0,"",bound);
      if(result===true){const answer=path.slice();state=start.split("");return answer;}
      if(!Number.isFinite(result))break;
      bound=result;
    }
    state=start.split("");
    return null;
  }
  async function autoSolve() {
    if (busy || solved()) return;
    busy=true;
    $("puzzle-shuffle").disabled=true;
    $("puzzle-solve").disabled=true;
    render("Finding a solution on this device…");
    const solution=findSolution();
    if(!solution){busy=false;$("puzzle-shuffle").disabled=false;render("Could not solve within the safe search limit. Shuffle and try again.");return;}
    const deltas={U:-3,D:3,L:-1,R:1};
    $("puzzle-status").textContent="Solution found: "+solution.length+" moves. Playing it now…";
    for(const direction of solution) {
      await new Promise(resolve=>setTimeout(resolve,170));
      const blank=state.indexOf("0"), next=blank+deltas[direction];
      [state[blank],state[next]]=[state[next],state[blank]];
      moves++;
      render("Auto-solver running…");
    }
    busy=false;
    $("puzzle-shuffle").disabled=false;
    render("Puzzle solved by AutoEarn's local demo solver. No external website or reward involved.");
  }
  $("puzzle-shuffle").addEventListener("click",shuffle);
  $("puzzle-solve").addEventListener("click",autoSolve);
  render("Local demo only — no account, payment, or external game is involved.");
})();
