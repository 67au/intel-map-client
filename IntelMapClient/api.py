import asyncio
import heapq
import logging
import math
import random
from datetime import datetime
from typing import Union, AsyncIterator, Tuple, Iterator, Awaitable, Any

from .client import AsyncClient
from .errors import ParserError, RequestError, ResponseError, CommTabError
from .types import TileContainer, Tile, Portal, Link, Field, Plext, Reward, Player
from .utils import MapTiles, datetime2timestamp_ms

logger = logging.getLogger(__name__)


async def with_lock(coro: Awaitable, lock: asyncio.Lock) -> Any:
    async with lock:
        return await coro


class AsyncAPI:

    def __init__(self, client: 'AsyncClient'):
        self.client = client

    async def searchPortalByLatLng(self,
                                   lat: float,
                                   lng: float,
                                   output_limit: int = 3,
                                   ) -> list[tuple[Portal, float]]:
        latE6, lngE6 = int(lat * 1e6), int(lng * 1e6)
        map_tiles = MapTiles.from_square(lat, lng, 0, zoom=15)
        container = await self.getEntitiesByTiles(map_tiles)
        return heapq.nsmallest(
            output_limit,
            ((p, math.pow(p.latE6 - latE6, 2) + math.pow(p.lngE6 - lngE6, 2)) for p in container.portals()),
            key=lambda k: k[1]
        )

    async def PortalDetailsIterator(self,
                                    portals: Iterator[Union['Portal', str]],
                                    ordered: bool = False,
                                    ) -> AsyncIterator['Portal']:
        lock = asyncio.Lock()
        tasks = [
            asyncio.create_task(
                with_lock(self.getPortalByGUID(p.guid if isinstance(p, Portal) else p), lock)
            ) for p in portals
        ]
        if ordered:
            for task in tasks:
                yield await task
        else:
            for task in asyncio.as_completed(tasks):
                yield await task

    async def redeemReward(self,
                           passcode: 'str'
                           ) -> Tuple[bool, Union[Tuple['Reward', 'Player'], str]]:
        result = await self.client.redeemReward(passcode)
        if 'error' in result:
            logger.error(f"兑换物资失败: {result['error']}")
            return False, result['error']
        else:
            return True, (Reward(result['rewards']), Player(result['playerData']))

    async def sendMessageToComm(self,
                                lat: float,
                                lng: float,
                                message: str,
                                tab: 'str' = 'faction'
                                ) -> bool:
        if tab not in {'all', 'faction'}:
            raise CommTabError(f'"{tab}" not in ["all", "faction"]')
        result = await self.client.sendPlext(
            latE6=int(lat * 1e6),
            lngE6=int(lng * 1e6),
            message=message,
            tab=tab,
        )
        return result == 'success'

    async def getPortalByGUID(self,
                              guid: 'str',
                              ) -> 'Portal':
        max_retries = 5
        for _ in iter(lambda: max_retries > 0, False):
            try:
                result = await self.client.getPortalDetails(guid=guid)
                return self.parseGameEntities(guid, -1, result)
            except RequestError:
                max_retries -= 1
                t = random.randint(2, 4)
                logger.warning(f'Portal({guid}) 请求失败， {t}s 后重试')
                await asyncio.sleep(t)
        logger.error(f'无法获取 Portal({guid}) 数据')
        raise ResponseError('Retries limit reached')

    async def getEntitiesByTiles(self,
                                 map_tiles: 'MapTiles',
                                 max_retries: int = 10,
                                 ) -> TileContainer:
        container = TileContainer()
        todo = map_tiles.tileKeys()
        retries = max_retries
        for _ in iter(lambda: any(todo) and retries > 0, False):
            tasks = [asyncio.create_task(self.client.getEntities(todo[k:k + 5])) for k in range(0, len(todo), 5)]
            todo = []
            retries -= 1
            for task in asyncio.as_completed(tasks):
                for k, v in (await task)['map'].items():
                    if 'gameEntities' in v:
                        entities = [self.parseGameEntities(*i) for i in v['gameEntities']]
                        container.add(Tile(name=k, gameEntities=entities))
                    else:
                        todo.append(k)
        if any(todo):
            logger.error(f'无法获取 {map_tiles} 中全部 Tile 的数据')
            raise ResponseError('Get incomplete tile data')
        return container

    async def getPlextsByTiles(self,
                               map_tiles: 'MapTiles',
                               start: Union['datetime', int] = -1,
                               end: Union['datetime', int] = -1,
                               tab: str = 'all',
                               reverse: bool = False,
                               ) -> AsyncIterator['Plext']:
        if tab not in {'all', 'faction', 'alerts'}:
            raise ParserError(f'"{tab}" not in ["all", "faction", "alerts"]')
        minTimestampMs = datetime2timestamp_ms(start) if isinstance(start, datetime) else start
        maxTimestampMs = datetime2timestamp_ms(end) if isinstance(end, datetime) else end
        plext = await self.client.getPlexts(
            minLatE6=map_tiles.minLatE6,
            maxLatE6=map_tiles.maxLatE6,
            minLngE6=map_tiles.minLngE6,
            maxLngE6=map_tiles.maxLngE6,
            minTimestampMs=minTimestampMs,
            maxTimestampMs=maxTimestampMs,
            tab=tab,
            ascendingTimestampOrder=reverse,
        )
        while any(plext):
            for p in plext:
                yield Plext.parse(p)
            await asyncio.sleep(0)
            guid = plext[-1][0]
            if reverse:
                minTimestampMs = plext[-1][1]
            else:
                maxTimestampMs = plext[-1][1]
            plext = await self.client.getPlexts(
                minLatE6=map_tiles.minLatE6,
                maxLatE6=map_tiles.maxLatE6,
                minLngE6=map_tiles.minLngE6,
                maxLngE6=map_tiles.maxLngE6,
                minTimestampMs=minTimestampMs,
                maxTimestampMs=maxTimestampMs,
                plextContinuationGuid=guid,
                tab=tab,
                ascendingTimestampOrder=reverse,
            )

    def parseGameEntities(self, guid: str, timestampMs: int, a: list) -> Union['Portal', 'Link', 'Field']:
        parser = {
            'p': Portal,
            'e': Link,
            'r': Field,
        }
        try:
            return parser[a[0]].parse(guid, timestampMs, a)
        except KeyError:
            raise ParserError(f'Failed to parse: {a}')
