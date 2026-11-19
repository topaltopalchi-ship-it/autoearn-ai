/** Convert full-viewport visual boxes into clipped game-canvas-local boxes. */
export function mapViewportObjectsToCanvas(objects, canvasBox, viewport) {
  if (!Array.isArray(objects) || !canvasBox || !viewport ||
      ![canvasBox.x, canvasBox.y, canvasBox.width, canvasBox.height, viewport.width, viewport.height].every(Number.isFinite) ||
      canvasBox.width <= 0 || canvasBox.height <= 0 || viewport.width <= 0 || viewport.height <= 0) return [];
  return objects.slice(0, 30).flatMap(object => {
    if (!object || ![object.x, object.y, object.width, object.height, object.confidence].every(Number.isFinite) ||
        object.x < 0 || object.y < 0 || object.width <= 0 || object.height <= 0 ||
        object.x + object.width > 1 || object.y + object.height > 1 ||
        object.confidence < 0 || object.confidence > 1) return [];
    const left = object.x * viewport.width;
    const top = object.y * viewport.height;
    const right = left + object.width * viewport.width;
    const bottom = top + object.height * viewport.height;
    const clippedLeft = Math.max(left, canvasBox.x);
    const clippedTop = Math.max(top, canvasBox.y);
    const clippedRight = Math.min(right, canvasBox.x + canvasBox.width);
    const clippedBottom = Math.min(bottom, canvasBox.y + canvasBox.height);
    if (clippedRight <= clippedLeft || clippedBottom <= clippedTop) return [];
    return [{
      role: object.role,
      label: typeof object.label === "string" ? object.label.slice(0, 80) : "",
      x: (clippedLeft - canvasBox.x) / canvasBox.width,
      y: (clippedTop - canvasBox.y) / canvasBox.height,
      width: (clippedRight - clippedLeft) / canvasBox.width,
      height: (clippedBottom - clippedTop) / canvasBox.height,
      confidence: object.confidence
    }];
  });
}
