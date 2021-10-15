import asyncio
import logging
from datetime import datetime
import random
from typing import Union, List, AsyncIterator, Tuple, Iterator

from .client import AsyncClient
from .errors import IncompleteError, ParserError, RequestError
from .types import TileContainer, Tile, Portal, Link, Field, Plext, Reward, Player
from .utils import MapTiles, datetime2timestamp_ms


class AsyncAPI:

    logger = logging.getLogger(__name__)

    @classmethod
    async def updatePortals(cls,
                            client: 'AsyncClient',
                            portals: Iterator['Portal'],
                            ) -> AsyncIterator['Portal']:
        lock = asyncio.Lock()

        async def with_lock(coro):
            async with lock:
                await asyncio.sleep(0)
                return await coro

        tasks = [asyncio.create_task(with_lock(cls.getPortalByGUID(client, p.guid))) for p in portals]
        for task in asyncio.as_completed(tasks):
            yield await task


    @classmethod
    async def redeemReward(cls,
                           client: 'AsyncClient',
                           passcode: 'str') -> Tuple[bool, Union[Tuple['Reward', 'Player'], str]]:
        result = await client.redeemReward(passcode)
        if 'error' in result:
            cls.logger.error(f"兑换物资失败: {result['error']}")
            return False, result['error']
        else:
            return True, (Reward(result['rewards']), Player(result['playerData']))

    @classmethod
    async def sendMessageToComm(cls,
                                client: 'AsyncClient',
                                lat: float,
                                lng: float,
                                message: str,
                                tab: 'str' = 'faction') -> bool:
        if tab not in {'all', 'faction'}:
            raise ParserError(f'"{tab}" not in ["all", "faction"]')
        result = await client.sendPlext(
            latE6=int(lat * 1e6),
            lngE6=int(lng * 1e6),
            message=message,
            tab=tab,
        )
        return result == 'success'

    @classmethod
    async def getPortalByGUID(cls,
                              client: 'AsyncClient',
                              guid: 'str',
                              ) -> 'Portal':

        max_retries = 5
        for _ in iter(lambda: max_retries > 0, False):
            try:
                result = await client.getPortalDetails(guid=guid)
                return cls.parseGameEntities(guid, -1, result)
            except RequestError:
                max_retries -= 1
                t = random.randint(2, 4)
                cls.logger.warning(f'Portal({guid}) 请求失败，{t}秒后重试')
                await asyncio.sleep(t)
        cls.logger.error(f'无法获取 Portal({guid}) 数据')
        raise IncompleteError


    @classmethod
    async def getEntitiesByTiles(cls,
                                 client: 'AsyncClient',
                                 map_tiles: 'MapTiles',
                                 max_tries: int = 10,
                                 ) -> TileContainer:

        container = TileContainer()
        todo = map_tiles.tileKeys()
        tries = max_tries
        for _ in iter(lambda: any(todo) and tries > 0, False):
            tasks = [asyncio.create_task(client.getEntities(todo[k:k + 5])) for k in range(0, len(todo), 5)]
            todo = []
            tries -= 1
            for task in asyncio.as_completed(tasks):
                for k, v in (await task)['map'].items():
                    if 'gameEntities' in v:
                        entities = [cls.parseGameEntities(*i) for i in v['gameEntities']]
                        container.add(Tile(name=k, gameEntities=entities))
                    else:
                        todo.append(k)
        if any(todo):
            cls.logger.error(f'无法获取 {map_tiles} 中全部 Tile 的数据')
            raise IncompleteError
        return container

    @classmethod
    async def getPlextsByTiles(cls,
                               client: 'AsyncClient',
                               map_tiles: 'MapTiles',
                               start: Union['datetime', int] = -1,
                               end: Union['datetime', int] = -1,
                               tab: str = 'all',
                               ) -> AsyncIterator['Plext']:
        if tab not in {'all', 'faction', 'alerts'}:
            raise ParserError(f'"{tab}" not in ["all", "faction", "alerts"]')
        minTimestampMs = datetime2timestamp_ms(start) if isinstance(start, datetime) else start
        maxTimestampMs = datetime2timestamp_ms(end) if isinstance(end, datetime) else end
        plext = await client.getPlexts(
            minLatE6=map_tiles.minLatE6,
            maxLatE6=map_tiles.maxLatE6,
            minLngE6=map_tiles.minLngE6,
            maxLngE6=map_tiles.maxLngE6,
            minTimestampMs=minTimestampMs,
            maxTimestampMs=maxTimestampMs,
            tab=tab,
        )
        while any(plext):
            for p in plext:
                yield Plext.parse(p)
            await asyncio.sleep(0)
            guid = plext[-1][0]
            maxTimestampMs = plext[-1][1]
            plext = await client.getPlexts(
                minLatE6=map_tiles.minLatE6,
                maxLatE6=map_tiles.maxLatE6,
                minLngE6=map_tiles.minLngE6,
                maxLngE6=map_tiles.maxLngE6,
                minTimestampMs=minTimestampMs,
                maxTimestampMs=maxTimestampMs,
                plextContinuationGuid=guid,
                tab=tab,
            )

    parser = {
        'p': Portal,
        'e': Link,
        'r': Field,
    }

    @classmethod
    def parseGameEntities(cls, guid: str, timestampMs: int, a: list) -> Union['Portal', 'Link', 'Field']:
        try:
            return cls.parser[a[0]].parse(guid, timestampMs, a)
        except KeyError:
            raise ParserError(f'无法解析: {a}')
