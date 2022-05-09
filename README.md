# IntelMapClient

![PyPI](https://img.shields.io/pypi/v/intel-map-client)
![GitHub](https://img.shields.io/github/license/67au/intel-map-client)

一个用于访问 intel.ingress.com 的 API 客户端

## Feature
- 使用`httpx`进行异步请求
- 支持使用代理

## Requirement
- Python >= 3.7
- httpx[socks] >= 0.22.0
- httpx-socks[asyncio] >= 0.7.3

## Installation

```shell
pip install intel-map-client
```

## Usage

下面是获取指定区间内全部 Portals 的简单示例

```python
import asyncio

from IntelMapClient import AsyncClient, AsyncAPI
from IntelMapClient.types import MapTiles

cookies = "<cookies>"  # Put your cookies here

client = AsyncClient()
api = AsyncAPI(client)
client.set_cookies(cookies)  # Set Cookies
client.set_proxy(proxy_url="socks5://127.0.0.1:7890")  # Set proxy if you need

async def main():
    lat, lng = 23.105252, 113.240577
    map_tiles = MapTiles.from_square(lat, lng, 7000, zoom=15)  # Build MapTiles
    async with client:
        await client.authorize()
        tile_set = await api.GetEntitiesByMapTiles(map_tiles)
        print(list(tile_set.portals()))  # Portals List
  
if __name__ == '__main__':
    asyncio.run(main())
```

更多用法详情可以等待 API 文档更新

## API List

### IntelMap Basic API 

- [x] getArtifactPortals
- [x] getGameScore
- [x] getEntities
- [x] getPortalDetails
- [x] getPlexts
- [x] sendPlext
- [x] getRegionScoreDetails
- [x] redeemReward
- [x] getHasActiveSubscription
- [x] getTopMissionsInBounds
- [x] getMissionDetails
- [x] getTopMissionsForPortal
- [ ] getInventory
- [ ] ~~sendInviteEmails~~
- [ ] ~~wipeAccount~~

### High-level API

- `SearchPortalByLatLng` - 通过经纬度搜索最近的 portal
- `GetEntitiesByMapTiles` - 下载 MapTiles 范围内的 GameEntities

## Roadmap

该版本是原来分支的重构，更多更新将在以后版本发布

## License

MIT License