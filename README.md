# IntelMapClient

一个用于访问 intel.ingress.com 的客户端

## Key Features

- 支持异步
- 提供开箱即用的客户端
- 支持以实例对象形式返回客户端访问结果

## Requirements

- Python >= 3.7
- httpx >= 0.19.0
- httpx-socks[asyncio] >= 0.4.1

## Getting started

下面是下载指定区间内 Portal 的简单示例

```python
import asyncio
from itertools import chain

from IntelMapClient import AsyncClient, AsyncAPI
from IntelMapClient.utils import MapTiles

async def main():
    cookies = 'cookies'
    async with AsyncClient.create_client(cookies) as client:
        maptiles = MapTiles.from_box(23.11, 113.23, 23.13, 113.28, zoom=15)
        entities = await AsyncAPI.getEntitiesByTiles(client, maptiles)
        portals = list(chain.from_iterable(i.portals for i in entities))
        print(portals)

if __name__ == '__main__':
    asyncio.run(main())
```

其他 User API 可以参考 IntelMapClient.api 

## Todo List

### IntelMap API 
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

### User API

- [x] 获取指定坐标区域内所有 Tile 包含的 Portal、 Link、 Field 数据
  - [x] 请求头过大，分片
  - [x] 超时重试
- [x] 获取 comm 上指定坐标区域内与指定时间区间的数据，包括 all、 faction、 alerts
  - [x] 指定区域
  - [x] 指定时间
  - [ ] 处理 markup
  - [ ] ~~提供 filter~~ (通过迭代器代理方式实现)
- [x] 发送消息到 comm 
- [x] 获取指定 Portal 数据
  - [x] 批量下载
  - [ ] 处理部分属性，例如 Mods、Resonators
- [ ] 获取指定区域内 Mission 数据
- [x] 兑换游戏奖励
- [ ] 查看仓库 (C.O.R.E.)
- [ ] 游戏分数
- [ ] 获取用户数据 (非基于 API 实现)
