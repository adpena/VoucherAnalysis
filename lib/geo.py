from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


Point = Tuple[float, float]
Ring = List[Point]
Polygon = List[Ring]


def _point_on_segment(point: Point, a: Point, b: Point, epsilon: float = 1e-9) -> bool:
    (x, y), (x1, y1), (x2, y2) = point, a, b
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > epsilon:
        return False
    dot = (x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)
    if dot < 0:
        return False
    squared_len = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if dot > squared_len:
        return False
    return True


def _point_in_ring(point: Point, ring: Ring) -> bool:
    if len(ring) < 3:
        return False
    x, y = point
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        if _point_on_segment(point, (x1, y1), (x2, y2)):
            return True
        intersects = (y1 > y) != (y2 > y)
        if intersects:
            x_at_y = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x < x_at_y:
                inside = not inside
    return inside


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    if not polygon:
        return False
    outer = polygon[0]
    if not _point_in_ring(point, outer):
        return False
    for hole in polygon[1:]:
        if _point_in_ring(point, hole):
            return False
    return True


def extract_polygons(geometry: dict) -> List[Polygon]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if not geom_type or coords is None:
        return []
    if geom_type == "Polygon":
        return [[[(float(x), float(y)) for x, y in ring] for ring in coords]]
    if geom_type == "MultiPolygon":
        polygons: List[Polygon] = []
        for polygon in coords:
            polygons.append([[(float(x), float(y)) for x, y in ring] for ring in polygon])
        return polygons
    return []


def polygon_bbox(polygons: Iterable[Polygon]) -> Tuple[float, float, float, float]:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for polygon in polygons:
        for ring in polygon:
            for x, y in ring:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    return min_x, min_y, max_x, max_y


@dataclass
class GeoFeature:
    bbox: Tuple[float, float, float, float]
    polygons: List[Polygon]
    properties: dict


class GeoFeatureIndex:
    def __init__(self, features: Iterable[dict]):
        self.features: List[GeoFeature] = []
        for feature in features:
            geometry = feature.get("geometry") or {}
            polygons = extract_polygons(geometry)
            if not polygons:
                continue
            bbox = polygon_bbox(polygons)
            self.features.append(
                GeoFeature(
                    bbox=bbox,
                    polygons=polygons,
                    properties=feature.get("properties", {}),
                )
            )

    def lookup(self, point: Point) -> dict | None:
        x, y = point
        for feature in self.features:
            min_x, min_y, max_x, max_y = feature.bbox
            if x < min_x or x > max_x or y < min_y or y > max_y:
                continue
            for polygon in feature.polygons:
                if point_in_polygon(point, polygon):
                    return feature.properties
        return None
