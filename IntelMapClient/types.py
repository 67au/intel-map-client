from datetime import datetime
from itertools import groupby, compress
from typing import List, Union, Optional

from IntelMapClient.utils import datetime2timestamp_ms, timestamp_ms2datetime


class Entity:

    def __init__(self):
        self.guid: Optional[str] = None
        self._time: Optional[datetime] = None

    @property
    def timestampMs(self) -> int:
        return datetime2timestamp_ms(self._time)

    @property
    def time(self) -> datetime:
        return self._time

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.guid}, {self._time})'


class Tile:

    def __init__(self, name: str, gameEntities: List[Union['Portal', 'Link', 'Field']]):
        self.name = name
        self.gameEntities = gameEntities
        self._groups = {k: list(g) for k, g in groupby(self.gameEntities, key=lambda k: k.__class__)}

    @property
    def portals(self) -> List['Portal']:
        return self._groups.get(Portal, [])

    @property
    def links(self) -> List['Link']:
        return self._groups.get(Link, [])

    @property
    def fields(self) -> List['Field']:
        return self._groups.get(Field, [])


class Portal(Entity):

    def __init__(self, guid: str, type_: str, team: str, latE6: int, lngE6: int, level: int, health: int, resCount: int,
                 image: str, title: str, ornaments: list, mission: bool, mission50plus: bool, artifactBrief: list,
                 timestampMs: int, mods: list, resonators: list, owner: str, artifactDetail: list, *unknown):
        super().__init__()
        self.guid = guid
        self.type = type_
        self._time = timestamp_ms2datetime(timestampMs)
        self.team = team
        self.latE6 = latE6
        self.lngE6 = lngE6
        self.level = level
        self.health = health
        self.resCount = resCount
        self.image = image
        self.title = title
        self.ornaments = ornaments  # Ornaments
        self.mission = mission
        self.mission50plus = mission50plus
        self.artifactBrief = artifactBrief  #
        self.mods = mods  # Mods
        self.resonators = resonators  # Resonators
        self.owner = owner
        self.artifactDetail = artifactDetail  #
        self.unknown = unknown

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.guid}, {self._time}, \'{self.title}\')'


class Link(Entity):

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 type_: str,
                 team: str,
                 p1_guid: str,
                 p1_latE6: int,
                 p1_lngE6: int,
                 p2_guid: str,
                 p2_latE6: int,
                 p2_lngE6: int):
        super().__init__()
        self.guid = guid
        self._time = timestamp_ms2datetime(timestampMs)
        self.type = type_
        self.team = team
        self.p1_guid = p1_guid
        self.p1_latE6 = p1_latE6
        self.p1_lngE6 = p1_lngE6
        self.p2_guid = p2_guid
        self.p2_latE6 = p2_latE6
        self.p2_lngE6 = p2_lngE6


class Field(Entity):

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 type_: str,
                 team: str,
                 p1_guid: str,
                 p1_latE6: int,
                 p1_lngE6: int,
                 p2_guid: str,
                 p2_latE6: int,
                 p2_lngE6: int,
                 p3_guid: str,
                 p3_latE6: int,
                 p3_lngE6: int):
        super().__init__()
        self.guid = guid
        self._time = timestamp_ms2datetime(timestampMs)
        self.type = type_
        self.team = team
        self.p1_guid = p1_guid
        self.p1_latE6 = p1_latE6
        self.p1_lngE6 = p1_lngE6
        self.p2_guid = p2_guid
        self.p2_latE6 = p2_latE6
        self.p2_lngE6 = p2_lngE6
        self.p3_guid = p3_guid
        self.p3_latE6 = p3_latE6
        self.p3_lngE6 = p3_lngE6


class Plext(Entity):
    """
    用于储存消息
    """

    def __init__(self,
                 guid: str,
                 timestampMs: int,
                 plext: dict):
        super().__init__()
        self.guid = guid
        self._time = timestamp_ms2datetime(timestampMs)
        self.text = plext['plext'].get('text')
        self.team = plext['plext'].get('team')
        self.markup = plext['plext'].get('markup')
        self.plextType = plext['plext'].get('plextType')
        self.categories = plext['plext'].get('categories')

    def __repr__(self):
        return f'{self.__class__.__name__}({self.guid}, {self._time}, \'{self.text}\')'


class Reward:

    def __init__(self, reward: dict):
        self.ap = reward['ap']
        self.xm = reward['xm']
        self.other = reward['other']
        self.inventory = reward['inventory']

    def __str__(self) -> str:
        s = [f'{self.ap} AP', f'{self.xm} XM', f'{self.inventory_str}', f'{self.other_str}']
        t = [int(self.ap) > 0, int(self.xm) > 0, any(self.inventory), any(self.other)]
        return '\n'.join(compress(s, t))

    @property
    def inventory_str(self) -> str:
        return '\n'.join(
            f"L{j['level']} {i['name']} x{j['count']}" for i in self.inventory for j in i['awards']
        )

    @property
    def other_str(self) -> str:
        return '\n'.join(self.other)


class Player:

    def __init__(self, playerData: dict):
        self.ap = playerData.get('ap')
        self.energy = playerData.get('energy')
        self.team = playerData.get('team')
        self.available_invites = playerData.get('available_invites')
        self.xm_capacity = playerData.get('xm_capacity')
        self.min_ap_for_current_level = playerData.get('min_ap_for_current_level')
        self.min_ap_for_next_level = playerData.get('min_ap_for_next_level')
        self.guid = playerData.get('guid')
        self.recursion_count = playerData.get('recursion_count')
        self.nickname = playerData.get('nickname')
