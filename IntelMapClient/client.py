import asyncio
import json
import random
import re
import logging
import time
from typing import List, Dict, Optional

import httpx
from httpx_socks import AsyncProxyTransport

from .errors import ResponseError, CookieError, RequestError

logger = logging.getLogger(__name__)

MAX_WORKERS = 10


class AsyncClient:
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.8',
        'content-type': 'application/json; charset=UTF-8',
        'origin': 'https://intel.ingress.com',
        'referer': 'https://intel.ingress.com/intel',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/96.0.4664.45 Safari/537.36',
    }
    BASE_URL = 'https://intel.ingress.com'

    def __init__(self, cookies: str = None, proxy: str = None, max_workers: int = MAX_WORKERS):
        self._client: Optional['httpx.AsyncClient'] = None
        self._cookies: Optional[str] = cookies
        self._transport: Optional['AsyncProxyTransport'] = proxy
        self._sem: Optional['asyncio.Semaphore'] = asyncio.Semaphore(max_workers)
        self._data = {}
        self._login_event = asyncio.Event()
        self._login_lock = asyncio.Lock()

    @classmethod
    async def create_client(cls,
                            cookies: str,
                            proxy: str = None,
                            max_workers: int = 10
                            ) -> 'AsyncClient':
        self = AsyncClient()
        await cls.connect(self, cookies, proxy, max_workers)
        return self

    def is_login(self) -> bool:
        return self._client is not None

    def is_busy(self) -> bool:
        return self._sem.locked()

    def _update_client(self, cookies: str = None, proxy: str = None, max_workers: int = MAX_WORKERS):
        self._cookies = cookies or self._cookies
        if proxy:
            self._sem = asyncio.Semaphore(1)
            self._transport = AsyncProxyTransport.from_url(proxy, retries=10)
            logger.info('如果使用代理，则连接数限制为1，详情查看 https://github.com/encode/httpcore/issues/335')
        else:
            self._sem = asyncio.Semaphore(max_workers) if isinstance(max_workers, int) else self._sem
            self._transport = httpx.AsyncHTTPTransport(retries=10)
        self._client = httpx.AsyncClient(
            headers=self.headers,
            cookies=self.cookies2dict(self._cookies),
            transport=self._transport,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            timeout=httpx.Timeout(10.0, read=20.0)
        )

    async def connect(self, cookies: str, proxy: str = None, max_workers: int = None):
        self._update_client(cookies, proxy, max_workers)
        await self._login()

    @staticmethod
    def cookies2dict(cookies: str) -> Dict[str, str]:
        cookies_dict = {k.strip(): v for k, v in re.findall(r'(.*?)=(.*?);', f'{cookies};')}
        return cookies_dict

    async def _login(self):
        if self._login_lock.locked():
            return
        async with self._login_lock:
            if self._client is None:
                self._update_client()
            resp = await self._client.get(f'{self.BASE_URL}/intel')
            result = re.findall(r'/jsc/gen_dashboard_([\d\w]+)\.js"', resp.text)
            if len(result) == 1:
                logger.info('Intel Map 登录成功')
                self._data['v'] = result[0]
                self._client.headers.update({'x-csrftoken': resp.cookies['csrftoken']})
                self._login_event.set()
            else:
                logger.error('Cookies 验证失败')
                await self.close()
                raise CookieError('Login failed')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        self._login_event.clear()
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self,
                       url: str,
                       data: dict,
                       raw: bool = False,
                       max_retries: int = 5) -> list:
        if self._client is None:
            await asyncio.create_task(self._login())
        async with self._sem:
            await self._login_event.wait()
            content = json.dumps({**self._data, **data})
            for n in range(1, max_retries+1):
                try:
                    resp = await self._client.post(url=url, content=content)
                    resp.raise_for_status()
                    result = resp.json()
                    if raw:
                        return result
                    if 'result' in result:
                        return result['result']
                    if 'error' in result:
                        logger.error(f"{url} 返回错误结果：{result['error']}")
                        raise ResponseError(result['error'])
                    raise ResponseError('Bad Response')
                except httpx.HTTPStatusError:
                    if resp.status_code == 400:
                        raise RequestError('Bad request')
                except json.decoder.JSONDecodeError:
                    logger.error('cookies 可能已经过期.')
                    await self.close()
                    raise RequestError('Cookies may be expired')
                if n < max_retries:
                    delay_time = random.uniform(0.5, 2)
                    logger.debug(f'第 {n} 次请求 {url} 返回错误，{delay_time:.2}s 后进行重试.')
                    await asyncio.sleep(delay_time)
            logger.error(f'请求 {url} 的重试次数达到上限.')
            raise RequestError('Retries limit reached')

    async def getArtifactPortals(self):
        data = dict()
        url = f'{self.BASE_URL}/r/getArtifactPortals'
        return await self._request(url=url, data=data)

    async def getGameScore(self):
        data = dict()
        url = f'{self.BASE_URL}/r/getGameScore'
        return await self._request(url=url, data=data)

    async def getEntities(self, tileKeys: List[str]):
        data = dict(tileKeys=tileKeys)
        url = f'{self.BASE_URL}/r/getEntities'
        return await self._request(url=url, data=data)

    async def getPortalDetails(self, guid: str):
        data = dict(guid=guid)
        url = f'{self.BASE_URL}/r/getPortalDetails'
        return await self._request(url=url, data=data)

    async def getPlexts(self,
                        minLngE6: int,
                        maxLngE6: int,
                        minLatE6: int,
                        maxLatE6: int,
                        tab: str = 'all',
                        maxTimestampMs: int = -1,
                        minTimestampMs: int = -1,
                        plextContinuationGuid: Optional['str'] = None,
                        ascendingTimestampOrder: bool = False):
        # tab: 'all', 'faction', 'alerts'
        minTimestampMs = int(time.time() * 1000) if minTimestampMs == 0 else minTimestampMs
        data = dict(
            ascendingTimestampOrder=ascendingTimestampOrder,
            maxLatE6=maxLatE6,
            maxLngE6=maxLngE6,
            maxTimestampMs=maxTimestampMs,
            minLatE6=minLatE6,
            minLngE6=minLngE6,
            minTimestampMs=minTimestampMs,
            plextContinuationGuid=plextContinuationGuid,
            tab=tab,
        )
        url = f'{self.BASE_URL}/r/getPlexts'
        return await self._request(url=url, data=data)

    async def sendPlext(self,
                        lngE6: int,
                        latE6: int,
                        message: str,
                        tab: str = 'faction'):
        # tab: 'all', 'faction'
        data = dict(
            latE6=latE6,
            lngE6=lngE6,
            message=message,
            tab=tab
        )
        url = f'{self.BASE_URL}/r/sendPlext'
        return await self._request(url=url, data=data)

    async def getRegionScoreDetails(self,
                                    lngE6: int,
                                    latE6: int):
        data = dict(
            latE6=latE6,
            lngE6=lngE6
        )
        url = f'{self.BASE_URL}/r/getRegionScoreDetails'
        return await self._request(url=url, data=data)

    async def redeemReward(self, passcode: str):
        data = dict(
            passcode=passcode
        )
        url = f'{self.BASE_URL}/r/redeemReward'
        return await self._request(url=url, data=data, raw=True)

    async def getHasActiveSubscription(self):
        data = dict()
        url = f'{self.BASE_URL}/r/getHasActiveSubscription'
        return await self._request(url=url, data=data)

    async def getTopMissionsInBounds(self,
                                     eastE6: int,
                                     westE6: int,
                                     southE6: int,
                                     northE6: int):
        data = dict(
            eastE6=eastE6,
            westE6=westE6,
            southE6=southE6,
            northE6=northE6
        )
        url = f'{self.BASE_URL}/r/getTopMissionsInBounds'
        return await self._request(url=url, data=data)

    async def getMissionDetails(self, guid: str):
        data = dict(guid=guid)
        url = f'{self.BASE_URL}/r/getMissionDetails'
        return await self._request(url=url, data=data)

    async def getTopMissionsForPortal(self, guid: str):
        data = dict(guid=guid)
        url = f'{self.BASE_URL}/r/getTopMissionsForPortal'
        return await self._request(url=url, data=data)
