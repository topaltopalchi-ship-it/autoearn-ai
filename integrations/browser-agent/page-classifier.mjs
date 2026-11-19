const RULES = [
  { type: "verification", weight: 10, pattern: /captcha|verify you are human|robot check|security challenge|turnstile|hcaptcha|recaptcha|تأیید انسان|کد امنیتی/i },
  { type: "login", weight: 10, pattern: /sign in|log in|login|create account|register|password|ورود به حساب|ثبت.?نام|رمز عبور/i },
  { type: "folder", weight: 4, pattern: /folder|category|categories|collection|library|arcade|room|level select|پوشه|دسته.?بندی|مجموعه|اتاق|مرحله/i },
  { type: "game", weight: 3, pattern: /play now|start game|new game|game over|you win|you lost|score|level [0-9]|بازی کن|شروع بازی|امتیاز|برنده|بازنده/i },
  { type: "help", weight: 4, pattern: /help|how to play|instructions|rules|tutorial|راهنما|قوانین|آموزش/i }
];

export function classifySitePage(observation = {}) {
  const title = String(observation.title || "");
  const url = String(observation.url || "");
  const snapshot = String(observation.snapshot || "");
  const targets = Array.isArray(observation.navigationTargets) ? observation.navigationTargets : [];
  const text = (title + "\n" + url + "\n" + snapshot).slice(0, 30_000);
  const scores = { folder: 0, game: 0, help: 0, login: 0, verification: 0, unknown: 0 };
  const reasons = [];
  for (const rule of RULES) {
    if (rule.pattern.test(text)) {
      scores[rule.type] += rule.weight;
      reasons.push(rule.type + "_text_signal");
    }
  }

  const gameControls = targets.filter(target =>
    /play|start|move|left|right|up|down|restart|pause|شروع|بازی|حرکت|چپ|راست|بالا|پایین|شروع مجدد/i.test(target.name || "")
  ).length;
  const folderTargets = targets.filter(target =>
    /folder|category|collection|arcade|room|level|پوشه|دسته|مجموعه|اتاق|مرحله/i.test(target.name || "")
  ).length;
  const hasCanvas = /<canvas|canvas|application|game area|game board|صفحه بازی|زمین بازی/i.test(snapshot);
  const hasScore = /score|points|امتیاز/i.test(snapshot);
  if (gameControls) { scores.game += Math.min(4, gameControls); reasons.push("game_control_labels"); }
  if (hasCanvas) { scores.game += 3; reasons.push("canvas_or_game_area"); }
  if (hasScore) { scores.game += 2; reasons.push("score_indicator"); }
  if (folderTargets) { scores.folder += Math.min(5, folderTargets); reasons.push("folder_like_targets"); }

  const priority = ["verification", "login", "game", "folder", "help"];
  let type = "unknown";
  let best = 0;
  for (const candidate of priority) {
    if (scores[candidate] > best) {
      type = candidate;
      best = scores[candidate];
    }
  }
  const confidence = best === 0 ? 0 : Math.min(0.95, 0.45 + best * 0.05);
  return {
    type,
    confidence: Number(confidence.toFixed(2)),
    scores,
    reasons: [...new Set(reasons)],
    safeToExplore: type === "folder" || type === "game" || type === "help"
  };
}
