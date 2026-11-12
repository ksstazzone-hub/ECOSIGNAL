from __future__ import annotations

from typing import Dict, List, Tuple


class GeographyService:
    """Global geospatial logic grounded in PostGIS-compatible coordinates."""

    @staticmethod
    def validate_coordinate(lat: float, lon: float) -> bool:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0

    @staticmethod
    def build_bbox(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> Dict[str, float]:
        return {
            "min_lat": float(min_lat),
            "min_lon": float(min_lon),
            "max_lat": float(max_lat),
            "max_lon": float(max_lon),
        }

    @staticmethod
    def normalize_polygon(points: List[Tuple[float, float]]) -> Dict[str, object]:
        return {
            "type": "Polygon",
            "coordinates": [list(points)],
        }

    @staticmethod
    def dateline_crossing_polygon(points: List[Tuple[float, float]]) -> bool:
        if len(points) < 2:
            return False
        longitudes = [lon for _, lon in points]
        return max(longitudes) - min(longitudes) > 180.0

    @staticmethod
    def coordinate_uncertainty(lat: float, lon: float, uncertainty_m: float = 0.0) -> Dict[str, float]:
        return {
            "latitude": float(lat),
            "longitude": float(lon),
            "uncertainty_m": float(uncertainty_m),
        }

    @staticmethod
    def privacy_mask(lat: float, lon: float, precision: int = 3) -> Dict[str, float]:
        scale = 10 ** precision
        return {
            "latitude": round(float(lat), precision),
            "longitude": round(float(lon), precision),
            "precision": precision,
            "masked": True,
            "scale": scale,
        }
