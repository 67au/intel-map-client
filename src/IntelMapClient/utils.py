import math
from datetime import datetime


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


def datetime2timestamp_ms(datetime_: datetime) -> int:
    return int(datetime_.timestamp() * 1000)


def timestamp_ms2datetime(timestamp_ms: int) -> 'datetime':
    return datetime.fromtimestamp(timestamp_ms / 1000)
