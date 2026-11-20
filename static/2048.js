(() => {
  "use strict";
  const boardEl = document.getElementById("game2048-board");
  if (!boardEl) return;
  const scoreEl = document.getElementById("game2048-score");
  const statusEl = document.getElementById("game2048-status");
  const SIZE = 4;
  let board = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
  let score = 0;
  let over = false;
  const copy = b => b.map(row => [...row]);
  function spawn(b) {
    const empty = [];
    b.forEach((row, y) => row.forEach((v, x) => { if (!v) empty.push([y, x]); }));
    if (!empty.length) return;
    const [y, x] = empty[Math.floor(Math.random() * empty.length)];
    b[y][x] = Math.random() < 0.9 ? 2 : 4;
  }
  function move(b, dir) {
    const out = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
    let gained = 0;
    for (let i = 0; i < SIZE; i++) {
      let line = dir === "left" || dir === "right" ? [...b[i]] : b.map(row => row[i]);
      if (dir === "right" || dir === "down") line.reverse();
      const vals = line.filter(Boolean), merged = [];
      for (let j = 0; j < vals.length; j++) {
        if (vals[j] === vals[j + 1]) { merged.push(vals[j] * 2); gained += vals[j] * 2; j++; }
        else merged.push(vals[j]);
      }
      while (merged.length < SIZE) merged.push(0);
      if (dir === "right" || dir === "down") merged.reverse();
      for (let j = 0; j < SIZE; j++) {
        if (dir === "left" || dir === "right") out[i][j] = merged[j];
        else out[j][i] = merged[j];
      }
    }
    return { board: out, gained, changed: out.some((r,y) => r.some((v,x) => v !== b[y][x])) };
  }
  function render() {
    boardEl.innerHTML = board.flat().map(v => '<div class="game2048-tile' + (v ? ' v' + Math.min(v,2048) : ' empty') + '" aria-label="' + (v || 'empty') + '">' + (v || '') + '</div>').join("");
    scoreEl.textContent = String(score);
    const won = board.flat().includes(2048);
    const stuck = !["left","right","up","down"].some(d => move(board,d).changed);
    over = stuck;
    statusEl.textContent = won ? "2048 reached! Keep going or start a new game." : stuck ? "No moves left. Start a new game." : "Use the arrow buttons or keyboard. This is a local practice game; no rewards.";
  }
  function play(dir) {
    if (over) return;
    const result = move(board, dir);
    if (!result.changed) return;
    board = result.board; score += result.gained; spawn(board); render();
  }
  function evaluate(b) {
    const vals = b.flat(), empty = vals.filter(v => !v).length;
    const logs = b.map(row => row.map(v => v ? Math.log2(v) : 0));
    let smooth = 0, mono = 0;
    for (let y=0;y<4;y++) for(let x=0;x<3;x++) smooth -= Math.abs(logs[y][x]-logs[y][x+1]);
    for (let x=0;x<4;x++) for(let y=0;y<3;y++) smooth -= Math.abs(logs[y][x]-logs[y+1][x]);
    for (let y=0;y<4;y++) { let inc=0,dec=0; for(let x=0;x<3;x++){const d=logs[y][x]-logs[y][x+1]; if(d>0)dec-=d; else inc+=d;} mono+=Math.max(inc,dec); }
    for (let x=0;x<4;x++) { let inc=0,dec=0; for(let y=0;y<3;y++){const d=logs[y][x]-logs[y+1][x]; if(d>0)dec-=d; else inc+=d;} mono+=Math.max(inc,dec); }
    const max=Math.max(...vals), corner=[b[0][0],b[0][3],b[3][0],b[3][3]].includes(max);
    return empty*270 + smooth*11 + mono*45 + (corner ? Math.log2(max)*18 : 0);
  }
  function suggest() {
    let best = null;
    for (const dir of ["left","up","right","down"]) {
      const first = move(board,dir);
      if (!first.changed) continue;
      const empty = [];
      first.board.forEach((r,y)=>r.forEach((v,x)=>{if(!v)empty.push([y,x]);}));
      let expected = 0;
      if (!empty.length) expected = evaluate(first.board);
      else {
        for (const [y,x] of empty) {
          for (const [tile,p] of [[2,0.9],[4,0.1]]) {
            const sample = copy(first.board); sample[y][x]=tile;
            expected += p * Math.max(...["left","up","right","down"].map(d=>evaluate(move(sample,d).board)));
          }
        }
        expected /= empty.length;
      }
      const value = expected + first.gained*0.08;
      if (!best || value > best.value) best={dir,value};
    }
    statusEl.textContent = best ? "AI suggestion: " + best.dir.toUpperCase() + " (advice only; tap the move yourself)." : "No legal moves.";
  }
  document.getElementById("game2048-new").addEventListener("click", () => { board=Array.from({length:4},()=>Array(4).fill(0)); score=0; over=false; spawn(board); spawn(board); render(); });
  document.querySelectorAll("[data-2048-move]").forEach(btn=>btn.addEventListener("click",()=>play(btn.dataset["2048Move"])));
  document.getElementById("game2048-hint").addEventListener("click",suggest);
  document.addEventListener("keydown", event => {
    if (!document.getElementById("game2048").getClientRects().length) return;
    const dirs={ArrowLeft:"left",ArrowRight:"right",ArrowUp:"up",ArrowDown:"down"};
    if (dirs[event.key]) { event.preventDefault(); play(dirs[event.key]); }
  });
  document.getElementById("game2048-new").click();
})();