import asyncio
import heapq
import math

from .client import AsyncClient
from .types import MapTiles, Tile, TileSet


class AsyncAPI:

    def __init__(self, client: AsyncClient):
        self.client = client

    async def SearchPortalByLatLng(self,
                                   lat: float,
                                   lng: float,
                                   output_limit: int = 3,
                                   ):
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