/**
 * Coordinates and spherical math utilities for Spiritus low-end disaster globe.
 * Pure math: lat/lon to 3D Cartesian vectors and distance calculations.
 */
const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

export function normalizeLongitude(lon) {
  return ((lon + 180) % 360 + 360) % 360 - 180;
}

export function latLonToXYZ(lat, lon, radius = 1) {
  const phi = lat * DEG2RAD;
  const theta = lon * DEG2RAD;
  return {
    x: radius * Math.cos(phi) * Math.cos(theta),
    y: radius * Math.sin(phi),
    z: -radius * Math.cos(phi) * Math.sin(theta)
  };
}

export function xyzToLatLon(x, y, z) {
  const r = Math.hypot(x, y, z);
  if (r === 0) return { lat: 0, lon: 0 };
  const lat = Math.asin(Math.max(-1, Math.min(1, y / r))) * RAD2DEG;
  const lon = normalizeLongitude(Math.atan2(-z, x) * RAD2DEG);
  return { lat, lon };
}

export function haversineDistanceKm(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * DEG2RAD;
  const dLon = (lon2 - lon1) * DEG2RAD;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * DEG2RAD) * Math.cos(lat2 * DEG2RAD) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return 6371.0 * c;
}
