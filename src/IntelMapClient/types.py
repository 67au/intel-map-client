from collections import defaultdict
from itertools import groupby, product, chain
from typing import Union, Iterator

from .utils import *


class GameEntity:
    __slots__ = ['guid', 'timestampMs']

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 ):
        self.guid = guid
        self.timestampMs = timestampMs

    @property
    def timestamp(self) -> datetime:
        return timestamp_ms2datetime(self.timestampMs)

    @classmethod
    def parse(cls, data: list) -> Union['Portal', 'Link', 'Field']:
        type_ = data[2][0]
        if type_ == 'p':
            return Portal.parse(data)
        elif type_ == 'e':
            return Link.parse(data)
        elif type_ == 'r':
            return Field.parse(data)


class PortalCore:

    def __init__(self,
                 guid: str,
                 latE6: int,
                 lngE6: int,
                 ):
        self.guid = guid
        self.latE6 = latE6
        self.lngE6 = lngE6

    @property
    def lat(self) -> float:
        return self.latE6 / 1e6

    @property
    def lng(self) -> float:
        return self.lngE6 / 1e6


class Portal(GameEntity, PortalCore):
    __slots__ = [
        'type',
        'team',
        'latE6',
        'lngE6',
        'level',
        'health',
        'resCount',
        'image',
        'title',
        'ornaments',
        'mission',
        'mission50plus',
        'artifactBrief',
        '_timestamp',
        'mods',
        'resonators',
        'owner',
        'artifactDetail',
        'history'
    ]

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 type_: str,
                 team: str,
                 latE6: int,
                 lngE6: int,
                 level: int,
                 health: int,
                 resCount: int,
                 image: str,
                 title: str,
                 ornaments: list,
                 mission: bool,
                 mission50plus: bool,
                 artifactBrief: Union[list, None],
                 timestamp: int,
                 mods: Union[list, None] = None,
                 resonators: Union[list, None] = None,
                 owner: Union[list, None] = None,
                 artifactDetail: Union[list, None] = None,
                 history: Union[int, None] = None,
                 ):
        super().__init__(guid, timestampMs)
        self.type = type_
        self.team = team
        self.latE6 = latE6
        self.lngE6 = lngE6
        self.level = level
        self.health = health
        self.resCount = resCount
        self.image = image
        self.title = title
        self.ornaments = ornaments
        self.mission = mission
        self.mission50plus = mission50plus
        self.artifactBrief = artifactBrief
        self._timestamp = timestamp
        self.mods = mods
        self.resonators = resonators
        self.owner = owner
        self.artifactDetail = artifactDetail
        self.history = history

    @classmethod
    def parse(cls, data: list):
        self = cls(data[0], data[1], *data[2])
        return self


class Link(GameEntity):
    __slots__ = ['type', 'team', 'portal1', 'portal2']

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 type_: str,
                 team: str,
                 po1_guid: str,
                 po1_latE6: int,
                 po1_lngE6: int,
                 po2_guid: str,
                 po2_latE6: int,
                 po2_lngE6: int,
                 ):
        super().__init__(guid, timestampMs)
        self.type = type_
        self.team = team
        self.portal1 = PortalCore(po1_guid, po1_latE6, po1_lngE6)
        self.portal2 = PortalCore(po2_guid, po2_latE6, po2_lngE6)

    @classmethod
    def parse(cls, data: list):
        self = cls(data[0], data[1], *data[2])
        return self


class Field(GameEntity):
    __slots__ = ['type', 'team', 'portal1', 'portal2', 'portal3']

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 type_: str,
                 team: str,
                 po1_guid: str,
                 po1_latE6: int,
                 po1_lngE6: int,
                 po2_guid: str,
                 po2_latE6: int,
                 po2_lngE6: int,
                 po3_guid: str,
                 po3_latE6: int,
                 po3_lngE6: int,
                 ):
        super().__init__(guid, timestampMs)
        self.type = type_
        self.team = team
        self.portal1 = PortalCore(po1_guid, po1_latE6, po1_lngE6)
        self.portal2 = PortalCore(po2_guid, po2_latE6, po2_lngE6)
        self.portal3 = PortalCore(po3_guid, po3_latE6, po3_lngE6)

    @classmethod
    def parse(cls, data: list):
        self = cls(data[0], data[1], data[2][0], data[2][1], *data[2][2][0], *data[2][2][1], *data[2][2][2])
        return self


class Plext(GameEntity):

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 plext: dict,
                 ):
        super().__init__(guid, timestampMs)
        self.text = plext['plext'].get('text')
        self.team = plext['plext'].get('team')
        self.markup = plext['plext'].get('markup')
        self.plextType = plext['plext'].get('plextType')
        self.categories = plext['plext'].get('categories')

    @classmethod
    def parse(cls, data: list):
        self = cls(data[0], data[1], data[2])
        return self


class Tile:

    def __init__(self,
                 name: str,
                 portals: Union[list, None] = None,
                 links: Union[list, None] = None,
                 fields: Union[list, None] = None,
                 ):
        self.name = name
        self.portals = portals or []
        self.links = links or []
        self.fields = fields or []

    @classmethod
    def parse(cls, name: str, game_entities: dict):
        portals, links, fields = [], [], []
        get_type = lambda x: x[2][0]
        groups = groupby(sorted(game_entities['gameEntities'], key=get_type), key=get_type)
        for t, ents in groups:
            if t == 'p':
                portals = list(map(Portal.parse, ents))
            elif t == 'e':
                links = list(map(Link.parse, ents))
            elif t == 'r':
                fields = list(map(Field.parse, ents))
        self = cls(name, portals, links, fields)
        return self


class MapTiles:

    def __init__(self,
                 min_lat: float,
                 max_lat: float,
                 min_lng: float,
                 max_lng: float,
                 zoom: int,
                 tiles: list[tuple]):
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lng = min_lng
        self.max_lng = max_lng
        self.zoom = zoom
        self.tiles = tiles

    def tileKeys(self) -> list[str]:
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
                   lat_range: tuple[float, float],
                   lng_range: tuple[float, float],
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


class TileSet:

    def __init__(self,
                 map_tiles: MapTiles,
                 tiles: list[Tile],
                 errors: Union[list, None] = None):
        self.map_tiles = map_tiles
        self._tiles = defaultdict(Tile)
        for t in tiles:
            self._tiles[t.name] = t
        self.errors = set([] or errors)

    def add(self, name: str, tile: Tile) -> bool:
        if name in self.errors:
            self._tiles[tile.name] = tile
            self.errors.remove(name)
            return True
        else:
            return False

    def portals(self) -> Iterator[Portal]:
        return chain.from_iterable(t.portals for t in self._tiles.values())

    def links(self) -> Iterator[Portal]:
        return chain.from_iterable(t.links for t in self._tiles.values())

    def fields(self) -> Iterator[Portal]:
        return chain.from_iterable(t.fields for t in self._tiles.values())

    @classmethod
    def parse(cls, map_tiles: MapTiles, data: dict):
        errors = []
        tiles = {}
        for name, t in data['map'].items():
            if 'gameEntities' in t:
                tiles[name] = Tile.parse(name, t)
            else:
                errors.append(name)
        self = cls(map_tiles, list(tiles.values()), errors)
        return self

    @property
    def tiles(self):
        return self._tiles
