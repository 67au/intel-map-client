import asyncio
import json
import logging
import random
import re
import time
from http.cookies import SimpleCookie
from typing import Union

import httpx
from httpx_socks import AsyncProxyTransport

from .errors import CookiesError, RequestError, ResponseError


DEFAULT_HEADERS = {
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'en-US,en;q=0.8',
    'content-type': 'application/json; charset=UTF-8',
    'origin': 'https://intel.ingress.com',
    'referer': 'https://intel.ingress.com/intel',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/96.0.4664.45 Safari/537.36',
}

DEFAULT_MAX_WORKERS = 10
DEFAULT_MAX_RETRIES = 5


class Session:

    def __init__(self):
        self.cookies = None
        self.vcode = ''
        self.transport = httpx.AsyncHTTPTransport(retries=1)
        self.proxy = None

    def set_cookies(self, cookies: Union[dict, str]):
        if isinstance(cookies, str):
            cookie = SimpleCookie()
            cookie.load(rawdata=cookies)
            self.cookies = {k: v.value for k, v in cookie.items()}
        else:
            self.cookies = cookies

    def set_vcode(self, vcode: str):
        self.vcode = vcode

    def set_proxy(self, proxy_url: str):
        self.transport = AsyncProxyTransport.from_url(proxy_url, retries=1)


class Response:

    def __init__(self,
                 method: str,
                 data: Union[list, dict],
                 client: 'AsyncClient',
                 is_raw: bool = False):
        self.method = method
        self.data = data
        self.client = client
        self.is_raw = is_raw


class AsyncClient:

    BASE_URL = 'https://intel.ingress.com'

    def __init__(self,
                 cookies: Union[dict, str, None] = None,
                 proxy_url: Union[str, None] = None,
                 ):
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(10.0)
        )
        self.session = Session()
        if cookies is not None:
            self.set_cookies(cookies)
        self._sem = asyncio.Semaphore(DEFAULT_MAX_WORKERS)
        if proxy_url is not None:
            self.set_proxy(proxy_url=proxy_url)
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._client.aclose()

    def set_cookies(self, cookies: Union[dict, str]):
        self.session.set_cookies(cookies)

    def set_proxy(self, proxy_url: str):
        self.session.set_proxy(proxy_url=proxy_url)

    def set_workers(self, workers: int):
        self._sem = asyncio.Semaphore(workers)

    def set_headers(self, headers: dict):
        self._client.headers = headers

    async def authorize(self) -> bool:
        self._client.cookies = self.session.cookies
        self._client._transport = self.session.transport
        resp = await self._client.get(f'{self.BASE_URL}/intel')
        match = re.search(r'/jsc/gen_dashboard_(?P<V>[\d\w]+)\.js"', resp.text)
        if match:
            self.session.set_vcode(match.group('V'))
            self._client.headers.update({'x-csrftoken': resp.cookies['csrftoken']})
            return True
        else:
            return False

    async def request(self,
                      method: str,
                      data: dict,
                      return_raw: bool = False):
        data.update({'v': self.session.vcode})
        content = json.dumps(data)
        url = f'{self.BASE_URL}/r/{method}'
        result = await self._request(url=url, content=content)
        if return_raw:
            return Response(method=method, data=result, client=self, is_raw=True)
        if 'result' in result:
            return Response(method=method, data=result['result'], client=self)
        if 'error' in result:
            raise ResponseError(result['error'])
        self.logger.error(f'Unknown Response:\n{result}')
        raise ResponseError("Unknown Response")

    async def _request(self, url: str, content: str):
        async with self._sem:
            for _ in range(DEFAULT_MAX_WORKERS):
                try:
                    resp = await self._client.post(url=url, content=content)
                    resp.raise_for_status()
                    result = resp.json()
                    return result
                except httpx.HTTPStatusError:
                    if resp.status_code == 400:
                        raise RequestError('Bad Request')
                except json.decoder.JSONDecodeError:
                    raise CookiesError('Cookies may be expired')
                finally:
                    await asyncio.sleep(random.random() * 3)
            raise RequestError('Retries limit reached')

    async def getArtifactPortals(self):
        data = {}
        return await self.request(method='getArtifactPortals', data=data)

    async def getGameScore(self):
        data = {}
        return await self.request(method='getGameScore', data=data)

    async def getEntities(self, tileKeys: list[str]):
        data = {'tileKeys': tileKeys}
        return await self.request(method='getEntities', data=data)

    async def getPortalDetails(self, guid: str):
        data = {'guid': guid}
        return await self.request(method='getPortalDetails', data=data)

    async def getPlexts(self,
                        minLngE6: int,
                        maxLngE6: int,
                        minLatE6: int,
                        maxLatE6: int,
                        tab: str = 'all',
                        maxTimestampMs: int = -1,
                        minTimestampMs: int = -1,
                        plextContinuationGuid: Union[str, None] = None,
                        ascendingTimestampOrder: bool = False):
        # tab: 'all', 'faction', 'alerts'
        data = {
            'ascendingTimestampOrder': ascendingTimestampOrder,
            'maxLatE6': maxLatE6,
            'maxLngE6': maxLngE6,
            'maxTimestampMs': maxTimestampMs,
            'minLatE6': minLatE6,
            'minLngE6': minLngE6,
            'minTimestampMs': int(time.time() * 1000) if minTimestampMs == 0 else minTimestampMs,
            'plextContinuationGuid': plextContinuationGuid,
            'tab': tab,
        }
        return await self.request(method='getPlexts', data=data)

    async def sendPlext(self,
                        lngE6: int,
                        latE6: int,
                        message: str,
                        tab: str = 'faction'):
        # tab: 'all', 'faction'
        data = {
            'latE6': latE6,
            'lngE6': lngE6,
            'message': message,
            'tab': tab
        }
        return await self.request(method='sendPlext', data=data)

    async def getRegionScoreDetails(self,
                                    lngE6: int,
                                    latE6: int):
        data = {'latE6': latE6, 'lngE6': lngE6}
        return await self.request(method='getRegionScoreDetails', data=data)

    async def redeemReward(self, passcode: str):
        data = {'passcode': passcode}
        return await self.request(method='redeemReward', data=data, return_raw=True)

    async def getHasActiveSubscription(self):
        data = {}
        return await self.request(method='getHasActiveSubscription', data=data)

    async def getTopMissionsInBounds(self,
                                     eastE6: int,
                                     westE6: int,
                                     southE6: int,
                                     northE6: int):
        data = {
            'eastE6': eastE6,
            'westE6': westE6,
            'southE6': southE6,
            'northE6': northE6
        }
        return await self.request(method='getTopMissionsInBounds', data=data)

    async def getMissionDetails(self, guid: str):
        data = {'guid': guid}
        return await self.request(method='getMissionDetails', data=data)

    async def getTopMissionsForPortal(self, guid: str):
        data = {'guid': guid}
        return await self.request(method='getTopMissionsForPortal', data=data)
