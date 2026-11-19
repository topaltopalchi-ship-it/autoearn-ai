(function (root) {
  "use strict";

  function extractReviewFlags(notes) {
    const match = String(notes || "").match(/Due-diligence flags: ([^.]+)\./);
    return match ? match[1].trim() : "";
  }

  root.AutoEarnDueDiligence = Object.freeze({ extractReviewFlags });
})(globalThis);
