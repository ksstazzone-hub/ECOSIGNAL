from __future__ import annotations

import math
from typing import Any

from pyproj import CRS, Transformer
from shapely import make_valid
from shapely.affinity import translate
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping, shape
from shapely.ops import split, transform


def _unwrap_ring(ring: list[list[float]]) -> list[tuple[float, float]]:
    if len(ring) < 4:
        raise ValueError("Polygon rings must contain at least four coordinates")
    output: list[tuple[float, float]] = []
    previous_lon: float | None = None
    offset = 0.0
    for coordinate in ring:
        if len(coordinate) < 2:
            raise ValueError("Coordinates must contain longitude and latitude")
        lon, lat = float(coordinate[0]), float(coordinate[1])
        if not math.isfinite(lon) or not math.isfinite(lat) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Coordinates must use WGS84 longitude [-180, 180] and latitude [-90, 90]")
        adjusted_lon = lon + offset
        if previous_lon is not None:
            delta = adjusted_lon - previous_lon
            if delta > 180:
                offset -= 360
                adjusted_lon -= 360
            elif delta < -180:
                offset += 360
                adjusted_lon += 360
        output.append((adjusted_lon, lat))
        previous_lon = adjusted_lon
    if output[0] != output[-1]:
        raise ValueError("Polygon rings must be closed")
    return output


def _polygon_from_geojson_polygon(coordinates: list[list[list[float]]]) -> Polygon:
    shell = _unwrap_ring(coordinates[0])
    shell_polygon = Polygon(shell)
    holes: list[list[tuple[float, float]]] = []
    for ring in coordinates[1:]:
        unwrapped = _unwrap_ring(ring)
        hole_polygon = Polygon(unwrapped)
        shift = round((shell_polygon.centroid.x - hole_polygon.centroid.x) / 360) * 360
        holes.append([(x + shift, y) for x, y in unwrapped])
    polygon = Polygon(shell, holes)
    if not polygon.is_valid:
        polygon = make_valid(polygon)
    if polygon.is_empty:
        raise ValueError("Study area is empty or invalid")
    return polygon


def _wrap_polygon(polygon: Polygon) -> list[Polygon]:
    min_x, _, max_x, _ = polygon.bounds
    boundaries = [180 + 360 * turn for turn in range(math.floor((min_x - 180) / 360), math.ceil((max_x - 180) / 360) + 1)]
    pieces: list[Polygon] = [polygon]
    for longitude in boundaries:
        if min_x < longitude < max_x:
            meridian = LineString([(longitude, -90.000001), (longitude, 90.000001)])
            split_pieces: list[Polygon] = []
            for piece in pieces:
                split_result = split(piece, meridian)
                split_pieces.extend(item for item in split_result.geoms if isinstance(item, Polygon))
            pieces = split_pieces
    wrapped: list[Polygon] = []
    for piece in pieces:
        offset = 360 * math.floor((piece.representative_point().x + 180) / 360)
        normalized = translate(piece, xoff=-offset)
        if normalized.is_valid and not normalized.is_empty:
            wrapped.append(normalized)
    return wrapped


def normalize_study_geometry(geojson: dict[str, Any]) -> dict[str, Any]:
    """Validate WGS84 polygon input and split antimeridian-crossing rings."""
    geometry_type = geojson.get("type")
    coordinates = geojson.get("coordinates")
    if geometry_type == "Polygon":
        polygons = [_polygon_from_geojson_polygon(coordinates)]
    elif geometry_type == "MultiPolygon":
        polygons = [_polygon_from_geojson_polygon(item) for item in coordinates]
    else:
        raise ValueError("Study area must be a GeoJSON Polygon or MultiPolygon")
    parts = [piece for polygon in polygons for piece in _wrap_polygon(polygon)]
    if not parts:
        raise ValueError("Study area could not be normalized")
    return mapping(MultiPolygon(parts))


def bbox_to_geometry(bounds: list[float]) -> dict[str, Any]:
    if len(bounds) != 4:
        raise ValueError("Bounding box must be [west, south, east, north]")
    west, south, east, north = map(float, bounds)
    if not all(map(math.isfinite, (west, south, east, north))):
        raise ValueError("Bounding box coordinates must be finite numbers")
    if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Bounding box is outside WGS84 bounds")
    if west <= east:
        return mapping(shape({"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}))
    return mapping(MultiPolygon([
        shape({"type": "Polygon", "coordinates": [[ [west, south], [180, south], [180, north], [west, north], [west, south] ]]}),
        shape({"type": "Polygon", "coordinates": [[ [-180, south], [east, south], [east, north], [-180, north], [-180, south] ]]})
    ]))


def geometry_to_query_bboxes(geojson: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    geom = shape(geojson)
    if geom.geom_type == "Polygon":
        geometries = [geom]
    elif geom.geom_type == "MultiPolygon":
        geometries = list(geom.geoms)
    else:
        raise ValueError("Only polygon geometries can be searched")
    boxes = []
    for item in geometries:
        west, south, east, north = item.bounds
        boxes.append((west, south, east, north))
    return boxes


def transform_geometry_to_wgs84(geojson: dict[str, Any], source_epsg: int) -> dict[str, Any]:
    try:
        source_crs = CRS.from_epsg(source_epsg)
    except Exception as error:
        raise ValueError(f"Invalid source EPSG:{source_epsg}") from error
    if source_crs == CRS.from_epsg(4326):
        return geojson
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    transformed = transform(transformer.transform, shape(geojson))
    return mapping(transformed)


def transform_point_to_wgs84(longitude: float, latitude: float, source_epsg: int) -> tuple[float, float]:
    try:
        source_crs = CRS.from_epsg(source_epsg)
    except Exception as error:
        raise ValueError(f"Invalid source EPSG:{source_epsg}") from error
    if source_crs == CRS.from_epsg(4326):
        return longitude, latitude
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    transformed_longitude, transformed_latitude = transformer.transform(longitude, latitude)
    if not math.isfinite(transformed_longitude) or not math.isfinite(transformed_latitude):
        raise ValueError("Coordinate transformation did not produce finite WGS84 values")
    return transformed_longitude, transformed_latitude