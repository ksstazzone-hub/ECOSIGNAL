import pytest
from ecosignal.geospatial import (
    bbox_to_geometry,
    geometry_to_query_bboxes,
    normalize_study_geometry,
    transform_point_to_wgs84,
)
from shapely.geometry import Point, shape


def test_dateline_polygon_is_split_without_covering_the_globe():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[170, -10], [-170, -10], [-170, 10], [170, 10], [170, -10]]],
    }

    normalized = normalize_study_geometry(polygon)
    geometry = shape(normalized)

    assert geometry.geom_type == "MultiPolygon"
    assert len(geometry.geoms) == 2
    assert geometry.covers(Point(179, 0))
    assert geometry.covers(Point(-179, 0))
    assert not geometry.covers(Point(0, 0))
    assert len(geometry_to_query_bboxes(normalized)) == 2


def test_bbox_search_can_cross_the_dateline():
    geometry = bbox_to_geometry([170, -5, -170, 5])

    assert geometry["type"] == "MultiPolygon"
    assert len(geometry_to_query_bboxes(geometry)) == 2


@pytest.mark.parametrize("latitude", [-91, 91])
def test_rejects_latitudes_outside_wgs84(latitude):
    polygon = {
        "type": "Polygon",
        "coordinates": [[[0, latitude], [1, latitude], [1, 0], [0, 0], [0, latitude]]],
    }
    with pytest.raises(ValueError, match="WGS84"):
        normalize_study_geometry(polygon)


def test_only_polygon_study_areas_are_accepted():
    with pytest.raises(ValueError, match="Polygon or MultiPolygon"):
        normalize_study_geometry({"type": "Point", "coordinates": [0, 0]})


def test_projected_coordinates_can_be_transformed_to_wgs84():
    longitude, latitude = transform_point_to_wgs84(111319.490793, 111325.142866, 3857)

    assert longitude == pytest.approx(1, abs=1e-5)
    assert latitude == pytest.approx(1, abs=1e-5)