from pathlib import Path
from math import nan, isnan
import datetime as dt
import os
import asyncio
import json
from dataclasses import dataclass

import aiofiles
from aioconsole import ainput
import websockets
from dotenv import load_dotenv

_ = load_dotenv()

path = Path('data.json')
datetime_format = '%Y-%m-%d %H:%M:%S.%f'


@dataclass
class PriceStore:
    datetime: dt.datetime = dt.datetime.now()
    bid: float = nan
    ask: float = nan
    spread_max_bps: float = nan

    @property
    def mid(self):
        return 0.5 * (self.bid + self.ask)

    @property
    def spread_bps(self):
        spread_bps = (self.ask - self.bid) / self.mid * 1e4
        if not isnan(self.spread_max_bps):
            spread_bps = max(spread_bps, self.spread_max_bps)
        return spread_bps

    def to_dict(self):
        return dict(
            datetime=self.datetime.strftime(datetime_format),
            bid=self.bid,
            ask=self.ask,
            spread_max_bps=self.spread_max_bps,
            mid=self.mid,
            spread_bps=self.spread_bps,
        )


price_store = PriceStore()


def convert_datetime(unix_time_ns):
    datetime_str = dt.datetime.utcfromtimestamp(int(unix_time_ns) / 1e9)
    return datetime_str


# async def update_spread_max_bps():
#     global price_store
#     while True:
#         line = await ainput(">>> ")
#         try:
#             price_store.spread_max_bps = float(line)
#         except ValueError:
#             price_store.spread_max_bps = nan


async def serialize(ps: price_store):
    async with aiofiles.open(path, mode='w') as fp:
        await fp.write(json.dumps(ps.to_dict()))


async def crypto_compare():
    global price_store

    api_key = f'{os.environ["APIKEY"]}'
    url = "wss://streamer.cryptocompare.com/v2?api_key=" + api_key

    async with websockets.connect(url) as websocket:
        await websocket.send(json.dumps({
            "action": "SubAdd",
            "subs": ["30~Binance~BTC~USDT"],
        }))
        while True:
            try:
                data = await websocket.recv()
            except websockets.ConnectionClosed:
                break
            try:
                data = json.loads(data)
                if 'ASK' in data.keys():
                    price_store.ask = data['ASK'][0]['P']
                    price_store.datetime = convert_datetime(data['ASK'][0]['REPORTEDNS'])
                elif 'BID' in data.keys():
                    price_store.bid = data['BID'][0]['P']
                    price_store.datetime = convert_datetime(data['BID'][0]['REPORTEDNS'])

                print(price_store.to_dict())
                await serialize(price_store)
            except ValueError:
                print(data)


async def multiple_tasks():
    # input_coroutines = [update_spread_max_bps(), crypto_compare()]
    input_coroutines = [crypto_compare()]
    await asyncio.gather(*input_coroutines)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(multiple_tasks())
