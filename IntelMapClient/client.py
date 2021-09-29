import asyncio
import json
import re
import logging
import time
from typing import List, Dict, Optional

import httpcore
import httpx
from httpx_socks import AsyncProxyTransport

from IntelMapClient.errors import ResultError, LoginError, RequestError


def cookies2dict(cookies: str) -> Dict[str, str]:
    cookies_dict = {k.strip(): v for k, v in re.findall(r'(.*?)=(.*?);', f'{cookies};')}
    return cookies_dict


class AsyncClient:
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.8',
        'content-type': 'application/json; charset=UTF-8',
        'origin': 'https://intel.ingress.com',
        'referer': 'https://intel.ingress.com/intel',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/93.0.4577.82 Safari/537.36',
    }
    BASE_URL = 'https://intel.ingress.com'

    def __init__(self):
        self._client: Optional['httpx.AsyncClient'] = None
        self.cookies: Optional[Dict[str, str]] = None
        self._transport: Optional['AsyncProxyTransport'] = None
        self._sem: Optional['asyncio.Semaphore'] = None
        self._data = {}
        self.logger = logging.getLogger(__name__)


    @classmethod
    async def create_client(cls,
                            cookies: str,
                            proxy: str = None,
                            max_workers: int = 10
                            ) -> 'AsyncClient':
        self = AsyncClient()
        self.cookies = cookies2dict(cookies)
        if proxy:
            self._sem = asyncio.Semaphore(1)
            self._transport = AsyncProxyTransport.from_url(proxy, retries=10)
            self.logger.info('如果使用代理，则连接数限制为1，详情查看 https://github.com/encode/httpcore/issues/335')
        else:
            self._sem = asyncio.Semaphore(max_workers)
            self._transport = httpx.AsyncHTTPTransport(retries=10)
        self._client = httpx.AsyncClient(
            headers=self.headers,
            cookies=self.cookies,
            transport=self._transport,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        await self._login()
        return self

    @staticmethod
    def cookies2dict(cookies: str) -> Dict[str, str]:
        cookies_dict = {k.strip(): v for k, v in re.findall(r'(.*?)=(.*?);', f'{cookies};')}
        return cookies_dict

    async def _login(self):
        resp = await self._client.get(f'{self.BASE_URL}/intel')
        resp.raise_for_status()
        result = re.findall(r'/jsc/gen_dashboard_([\d\w]+)\.js"', resp.text)
        if len(result) == 1:
            self.logger.info('登录成功')
            self._data['v'] = result[0]
            self._client.headers.update({'x-csrftoken': resp.cookies['csrftoken']})
        else:
            self.logger.error('cookies验证失败')
            raise LoginError

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def close(self):
        await self._client.aclose()

    async def _request(self,
                       url: str,
                       data: dict,
                       raw: bool = False) -> list:
        if self._client is None:
            raise
        max_tries = 10
        async with self._sem:
            content = json.dumps(data)
            for n in range(1, max_tries+2):
                try:
                    resp = await self._client.post(url=url, content=content)
                    resp.raise_for_status()
                    result = resp.json()
                    if raw:
                        return result
                    if 'result' in result:
                        return result['result']
                    elif 'error' in result:
                        raise ResultError(result['error'])
                    raise RequestError
                except (httpx.HTTPStatusError, httpcore.ReadTimeout, httpx.ReadTimeout):
                    if n > max_tries:
                        self.logger.error(f'访问 {url} 返回错误，正在退出程序')
                        raise ResultError('Retries limit reached.')
                    else:
                        self.logger.warning(f'访问 {url} 返回错误，第{n}次进行重试')
                        await asyncio.sleep(0.2)
                except json.decoder.JSONDecodeError:
                    self.logger.error('cookies 可能已经过期')
                    raise LoginError

    async def getArtifactPortals(self):
        data = self._data
        url = f'{self.BASE_URL}/r/getArtifactPortals'
        return await self._request(url=url, data=data)

    async def getGameScore(self):
        data = self._data
        url = f'{self.BASE_URL}/r/getGameScore'
        return await self._request(url=url, data=data)

    async def getEntities(self, tileKeys: List[str]):
        data = dict(self._data, tileKeys=tileKeys)
        url = f'{self.BASE_URL}/r/getEntities'
        return await self._request(url=url, data=data)

    async def getPortalDetails(self, guid: str):
        data = dict(self._data, guid=guid)
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
            self._data,
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
            self._data,
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
            self._data,
            latE6=latE6,
            lngE6=lngE6
        )
        url = f'{self.BASE_URL}/r/getRegionScoreDetails'
        return await self._request(url=url, data=data)

    async def redeemReward(self, passcode: str):
        data = dict(
            self._data,
            passcode=passcode
        )
        url = f'{self.BASE_URL}/r/redeemReward'
        return await self._request(url=url, data=data, raw=True)

    async def getHasActiveSubscription(self):
        data = self._data
        url = f'{self.BASE_URL}/r/getHasActiveSubscription'
        return await self._request(url=url, data=data)

    async def getTopMissionsInBounds(self,
                                     eastE6: int,
                                     westE6: int,
                                     southE6: int,
                                     northE6: int):
        data = dict(
            self._data,
            eastE6=eastE6,
            westE6=westE6,
            southE6=southE6,
            northE6=northE6
        )
        url = f'{self.BASE_URL}/r/getTopMissionsInBounds'
        return await self._request(url=url, data=data)

    async def getMissionDetails(self, guid: str):
        data = dict(
            self._data,
            guid=guid
        )
        url = f'{self.BASE_URL}/r/getMissionDetails'
        return await self._request(url=url, data=data)

    async def getTopMissionsForPortal(self, guid: str):
        data = dict(
            self._data,
            guid=guid
        )
        url = f'{self.BASE_URL}/r/getTopMissionsForPortal'
        return await self._request(url=url, data=data)
