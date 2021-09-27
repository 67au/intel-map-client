import math
from datetime import datetime
from itertools import product
from typing import Tuple, List


def get_tiles_per_edge(zoom: int) -> int:
    tiles_list = [1, 1, 1, 40, 40, 80, 80, 320, 1000, 2000, 2000, 4000, 8000, 16000, 16000, 32000]
    zoom = 15 if zoom > 15 else 3 if zoom < 3 else zoom
    return tiles_list[zoom]


def lat2tile(lat: float, tpe: int) -> int:
    return int((1 - math.log(math.tan(lat * math.pi / 180) + 1 / math.cos(lat * math.pi / 180)) / math.pi) / 2 * tpe)


def lng2tile(lng: float, tpe: int) -> int:
    return int((lng / 360 + 0.5) * tpe)


def tile2lat(x: int, tpe: int) -> float:
    return x / tpe * 360 - 180


def tile2lng(y: int, tpe: int) -> float:
    n = (1 - 2 * y / tpe) * math.pi
    return 180 / math.pi * math.atan(0.5 * (math.exp(n) - math.exp(-n)))


class MapTiles:

    def __init__(self,
                 min_lat: float,
                 max_lat: float,
                 min_lng: float,
                 max_lng: float,
                 zoom: int,
                 tiles: List[tuple]):
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lng = min_lng
        self.max_lng = max_lng
        self.zoom = zoom
        self.tiles = tiles

    def tileKeys(self) -> List['str']:
        return [f'{self.zoom}_{x}_{y}_0_8_100' for x, y in self.tiles]

    @property
    def minLatE6(self) -> int:
        return int(self.min_lat * 1e6)

    @property
    def maxLatE6(self) -> int:
        return int(self.max_lat * 1e6)

    @property
    def minLngE6(self) -> int:
        return int(self.min_lng * 1e6)

    @property
    def maxLngE6(self) -> int:
        return int(self.max_lng * 1e6)

    @staticmethod
    def get_range(x, y):
        return range(*(y, x + 1) if x > y else (x, y + 1))

    @classmethod
    def from_box(cls,
                 minLat: float,
                 minLng: float,
                 maxLat: float,
                 maxLng: float,
                 zoom: int = 15
                 ) -> 'MapTiles':
        zpe = get_tiles_per_edge(zoom)
        x_range = cls.get_range(lng2tile(minLng, zpe), lng2tile(maxLng, zpe))
        y_range = cls.get_range(lat2tile(minLat, zpe), lat2tile(maxLat, zpe))
        return MapTiles(
            min_lat=minLat,
            max_lat=maxLat,
            min_lng=minLng,
            max_lng=maxLng,
            zoom=zoom,
            tiles=list(product(x_range, y_range))
        )

    @classmethod
    def from_range(cls,
                   lat_range: Tuple[float, float],
                   lng_range: Tuple[float, float],
                   zoom: int = 15
                   ) -> 'MapTiles':
        minLat, maxLat = lat_range
        minLng, maxLng = lng_range
        return cls.from_box(minLat, minLng, maxLat, maxLng, zoom)

    @classmethod
    def from_square(cls,
                    center_lat: float,
                    center_lng: float,
                    radian_meter: int,
                    zoom: int = 15
                    ) -> 'MapTiles':
        dpl = 111000  # distance per lat
        d_lat = 1.0 * radian_meter / dpl
        d_lng = 1.0 * radian_meter / (dpl * math.cos(center_lat / 180))
        return cls.from_box(center_lat - d_lat, center_lng - d_lng,
                            center_lat + d_lat, center_lng + d_lng, zoom)


def datetime2timestamp_ms(datetime_: datetime) -> int:
    return int(datetime_.timestamp() * 1000)


def timestamp_ms2datetime(timestamp_ms: int) -> 'datetime':
    return datetime.fromtimestamp(timestamp_ms / 1000)
