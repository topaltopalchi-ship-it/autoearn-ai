export function validateApprovedTarget(value, allowedOrigins) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error("AUTOEARN_GAME_URL must be a valid URL.");
  }
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    (url.port && url.port !== "443") ||
    !allowedOrigins.has(url.origin)
  ) {
    throw new Error("Target must use HTTPS and match an explicitly approved exact origin.");
  }
  return url;
}

export function isApprovedRequestUrl(value, approvedOrigin) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      url.origin === approvedOrigin &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === "443");
  } catch {
    return false;
  }
}
