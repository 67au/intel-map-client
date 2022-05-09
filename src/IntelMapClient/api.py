import asyncio
import heapq
import logging
import math
from datetime import datetime
from typing import Union

from .client import AsyncClient
from .errors import RequestError
from .types import MapTiles, Tile, TileSet, Portal, Plext
from .utils import datetime2timestamp_ms


class AsyncAPI:

    def __init__(self, client: AsyncClient):
        self.client = client
        self.logger = logging.getLogger(__name__)

    async def SearchPortalByLatLng(self,
                                   lat: float,
                                   lng: float,
                                   output_limit: int = 3,
                                   ) -> list[tuple[Portal, float]]:
        latE6, lngE6 = int(lat * 1e6), int(lng * 1e6)
        maptiles = MapTiles.from_square(lat, lng, 0, zoom=15)
        tileset = await self.GetEntitiesByMapTiles(maptiles)
        return heapq.nsmallest(
            output_limit,
            ((p, math.pow(p.latE6 - latE6, 2) + math.pow(p.lngE6 - lngE6, 2)) for p in tileset.portals()),
            key=lambda k: k[1]
        )

    async def GetEntitiesByMapTiles(self,
                                    map_tiles: MapTiles,
                                    chunk_size: int = 5,
                                    max_retries: int = 5,
                                    ) -> TileSet:
        wait_list = map_tiles.tileKeys().copy()
        tiles = {}
        retries = max_retries
        for _ in iter(lambda: any(wait_list) and retries > 0, False):
            tasks = [
                asyncio.create_task(
                    self.client.getEntities(wait_list[i: i+chunk_size])
                ) for i in range(0, len(wait_list), chunk_size)
            ]
            wait_list = []
            for task in asyncio.as_completed(tasks):
                resp = await task
                for name, ents in resp.data['map'].items():
                    if 'gameEntities' in ents:
                        tiles[name] = Tile.parse(name, ents)
                    else:
                        wait_list.append(name)
        return TileSet(map_tiles, list(tiles.values()), wait_list)

    async def SendMessageToComm(self,
                                lat: float,
                                lng: float,
                                message: str,
                                tab: str = None
                                ) -> bool:
        if tab not in {'all', 'faction'}:
            self.logger.error(f'{tab} not in [all, faction]')
            return False
        try:
            resp = await self.client.sendPlext(
                latE6=int(lat * 1e6),
                lngE6=int(lng * 1e6),
                message=message,
                tab=tab,
            )
        except RequestError as e:
            self.logger.error(e)
            return False
        else:
            return resp.data == 'success'

    async def GetPlextsByMapTiles(self,
                                  map_tiles: MapTiles,
                                  start: Union[datetime, int] = -1,
                                  end: Union[datetime, int] = -1,
                                  tab: str = None,
                                  reverse: bool = False,
                                  ):
        if tab not in {'all', 'faction', 'alerts'}:
            self.logger.error(f'{tab} not in [all, faction, alerts]')
            return
        minTimestampMs = datetime2timestamp_ms(start) if isinstance(start, datetime) else start
        maxTimestampMs = datetime2timestamp_ms(end) if isinstance(end, datetime) else end
        resp = await self.client.getPlexts(
            minLatE6=map_tiles.minLatE6,
            maxLatE6=map_tiles.maxLatE6,
            minLngE6=map_tiles.minLngE6,
            maxLngE6=map_tiles.maxLngE6,
            minTimestampMs=minTimestampMs,
            maxTimestampMs=maxTimestampMs,
            tab=tab,
            ascendingTimestampOrder=reverse,
        )
        plexts = resp.data
        while any(plexts):
            for plext in plexts:
                yield Plext.parse(plext)
            last_plext = Plext.parse(plexts[-1])
            if reverse:
                minTimestampMs = last_plext.timestampMs
            else:
                maxTimestampMs = last_plext.timestampMs
            resp = await self.client.getPlexts(
                minLatE6=map_tiles.minLatE6,
                maxLatE6=map_tiles.maxLatE6,
                minLngE6=map_tiles.minLngE6,
                maxLngE6=map_tiles.maxLngE6,
                minTimestampMs=minTimestampMs,
                maxTimestampMs=maxTimestampMs,
                tab=tab,
                ascendingTimestampOrder=reverse,
                plextContinuationGuid=last_plext.guid,
            )
            plexts = resp.data
