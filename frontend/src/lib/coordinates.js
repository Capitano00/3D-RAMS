function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function pickCoordinateSource(locationOrScene) {
  if (!locationOrScene || typeof locationOrScene !== "object") return null;
  if (locationOrScene.center && typeof locationOrScene.center === "object") return locationOrScene.center;
  return locationOrScene;
}

export function formatCoordinate(value) {
  if (!isFiniteNumber(value)) return "Unknown";
  return value.toFixed(5);
}

export function formatLatLon(latitude, longitude) {
  if (!isFiniteNumber(latitude) || !isFiniteNumber(longitude)) return "Unknown coordinates";
  return `${formatCoordinate(latitude)}, ${formatCoordinate(longitude)}`;
}

export function hasValidCoordinate(locationOrScene) {
  const source = pickCoordinateSource(locationOrScene);
  if (!source) return false;
  return (
    isFiniteNumber(source.latitude) &&
    isFiniteNumber(source.longitude) &&
    source.latitude >= -90 &&
    source.latitude <= 90 &&
    source.longitude >= -180 &&
    source.longitude <= 180
  );
}
