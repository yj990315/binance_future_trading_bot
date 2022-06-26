import asyncio
import datetime
import json
import pathlib
import signal
import ssl
import redis
import pytz
import websockets

from config import USDT_FUTURE_SYMBOLS
from functools import partial
from trader import tasks


class Ticker:

    def __init__(self, code, timestamp, open, high, low, close, volume):
        self.code = code
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    @staticmethod
    def from_json(json):
        return Ticker(
            code=json['s'],
            timestamp=datetime.fromtimestamp(json['k']['t'] / 1000, tz=pytz.timezone('Asia/Seoul')),
            open=json['k']['o'],
            high=json['k']['h'],
            low=json['k']['l'],
            close=json['k']['c'],
            volume=json['k']['v']
        )

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'Ticker <code: {self.code}, timestamp: {self.timestamp.strftime("%Y-%m-%d %H:%M:%S")}, ' \
               f'open: {self.open}, high: {self.high}, ' \
               f'low: {self.low}, close: {self.close}, volume: {self.volume}>'


async def recv_ticker():
    uri = 'wss://fstream.binance.com'
    markets = USDT_FUTURE_SYMBOLS
    stream = 'aggTrade'  # 'kline_1m'

    params = '/'.join([f'{market.replace("/","").lower()}@{stream}' for market in markets])
    uri = uri + f'/stream?streams={params}'

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    self_signed_cert = pathlib.Path(__file__).with_name("selfsigned.crt")
    ssl_context.load_verify_locations(self_signed_cert)

    redis_db_number = 0
    rd = redis.StrictRedis(host='localhost', port=6379, db=redis_db_number, charset="utf-8", decode_responses=True)
    # rd.execute_command('FLUSHDB ASYNC')

    BUY_POSITION_NUM_STR = 'buy_position_number'
    SELL_POSITION_NUM_STR = 'sell_position_number'

    rd.set(BUY_POSITION_NUM_STR, 0)
    rd.set(SELL_POSITION_NUM_STR, 0)
    for symbol in USDT_FUTURE_SYMBOLS:
        rd.set(symbol, 'not trading')

    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        var = asyncio.Event()

        def sigint_handler(var, signal, frame):
            print(f'< recv SIG_INT')
            var.set()

        signal.signal(signal.SIGINT, partial(sigint_handler, var))

        while not var.is_set():
            # 매일 오전 9시에 초기화
            if datetime.datetime.now().hour == 9 and datetime.datetime.now().minute == 0 and datetime.datetime.now().second == 0:
                rd.execute_command('FLUSHDB ASYNC')
                redis_db_number = 1 - redis_db_number
                rd = redis.StrictRedis(host='localhost', port=6379, db=redis_db_number, charset="utf-8", decode_responses=True)
                # TODO : flush하고 다시 쌓는 데 기다리는 시간 어떻게 할까?

            recv_data = await websocket.recv()
            recv_data_dict = json.loads(recv_data)['data']

            symbol = recv_data_dict['s']
            time_stamp = recv_data_dict['T']
            price = recv_data_dict['p']

            time = datetime.datetime.fromtimestamp(time_stamp / 1000, tz=pytz.timezone('Asia/Seoul')).replace(microsecond=0)
            time_string = datetime.datetime.strftime(time, '%Y-%m-%d %H:%M:%S')
            time_symbol = ' '.join([time_string, symbol])
            rd.set(time_symbol, price)
            # 특정 시간 전 데이터 조회
            INTERVAL_MINUTES = 3
            prev_time = time - datetime.timedelta(minutes=INTERVAL_MINUTES)  # (minutes=INTERVAL_MINUTES)
            prev_time_string = datetime.datetime.strftime(prev_time, '%Y-%m-%d %H:%M:%S')
            prev_time_symbol = ' '.join([prev_time_string, symbol])
            prev_price = rd.get(prev_time_symbol)
            if prev_price:
                price = float(price)
                prev_price = float(prev_price)
                fluctuation_rate = (price - prev_price) / prev_price * 100
                if abs(fluctuation_rate) >= 2 and (not rd.get(symbol) or rd.get(symbol) == 'not trading'):
                    # TODO : 거래량도 확인해서 신호를 낼까?
                    buy_position_num = int(rd.get(BUY_POSITION_NUM_STR))
                    sell_position_num = int(rd.get(SELL_POSITION_NUM_STR))
                    total_position_num = buy_position_num + sell_position_num
                    if total_position_num >= 4:
                        print(f'[{symbol}] {total_position_num}개의 코인이 이미 거래 중이므로, 신호 무시')
                    elif fluctuation_rate > 0 and buy_position_num > sell_position_num:
                        print(f'[{symbol}] {buy_position_num - sell_position_num}개 만큼의 순매수 포지션이므로, 신호 무시')
                    elif fluctuation_rate < 0 and sell_position_num > buy_position_num:
                        print(f'[{symbol}] {sell_position_num - buy_position_num}개 만큼의 순매도 포지션이므로, 신호 무시')
                    else:
                        print('*************')
                        print(datetime.datetime.now(), '신호 발생')
                        print(symbol, '등락율 : ', fluctuation_rate, '%')
                        print(f'[{symbol}] 거래 시작')
                        rd.set(symbol, 'trading')
                        tasks.trade.delay(redis_db_number, symbol, fluctuation_rate, price)


def main():
    asyncio.get_event_loop().run_until_complete(recv_ticker())


if __name__ == '__main__':
    main()