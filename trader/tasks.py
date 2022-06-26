from trader.celery import app
from config import api_key, secret
import redis
import datetime
import ccxt


class Trader:
    LEVERAGE = 20
    MAX_LOSS_RATE = -0.05  # 전체 자산 대비 최대 손실 비율
    BUY_POSITION_NUM_STR = 'buy_position_number'
    SELL_POSITION_NUM_STR = 'sell_position_number'

    def __init__(self, symbol, is_buy, db_number, price):
        # 도중에 변경 안됨
        self.symbol = symbol
        self.is_buy = is_buy
        self.side = 'buy' if self.is_buy else 'sell'
        # 매매 시에 업데이트
        self.amount = 0  # buy면 +, sell이면 -
        self.is_earning = False
        self.margin_rate = 0
        self.offset_price = price
        # 항상 최신 유지
        self.last_price = price
        # 바이낸스 객체
        self.binance = ccxt.binance(config={
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'createMarketBuyOrderRequiresPrice': False
            }
        })
        balance = self.binance.fetch_balance()
        self.binance.set_leverage(Trader.LEVERAGE, symbol)
        self.total_balance = balance['USDT']['total']
        self.rd = redis.StrictRedis(host='localhost', port=6379, db=db_number, charset="utf-8", decode_responses=True)
        self.current_price = price
        self.update_current_price()
        self.set_position_number()

    def set_position_number(self):
        if self.side == 'buy':
            previous_position_num = int(self.rd.get(self.BUY_POSITION_NUM_STR))
            self.rd.set(self.BUY_POSITION_NUM_STR, previous_position_num + 1)
        if self.side == 'sell':
            previous_position_num = int(self.rd.get(self.SELL_POSITION_NUM_STR))
            self.rd.set(self.SELL_POSITION_NUM_STR, previous_position_num + 1)

    def reset_position_number(self):
        if self.side == 'sell':
            previous_position_num = int(self.rd.get(self.BUY_POSITION_NUM_STR))
            self.rd.set(self.BUY_POSITION_NUM_STR, previous_position_num + 1)
        if self.side == 'buy':
            previous_position_num = int(self.rd.get(self.SELL_POSITION_NUM_STR))
            self.rd.set(self.SELL_POSITION_NUM_STR, previous_position_num + 1)

    def print_order_result(self, order):
        last_price = float(order['price'])
        amount = float(order['amount'])
        order_result_str = f'[{self.symbol}] @@@ {last_price}에 {abs(amount)} USDT {"buy" if amount > 0 else "sell"}'
        print(order_result_str)

    def update_from_balance(self):
        '''
        update total_balance, margin, margin_rate, offset_price: balance로부터 얻을 수 있는 정보들
        '''
        balance = self.binance.fetch_balance()
        self.total_balance = balance['USDT']['total']
        positions = balance['info']['positions']
        for position in positions:
            if position["symbol"] == self.symbol:
                self.margin = float(position['positionInitialMargin'])  # USDT
                self.margin_rate = self.margin / self.total_balance
                self.offset_price = float(position['entryPrice'])
                self.amount = float(position['positionAmt'])
                break

    def update_last_price_from_order(self, order):
        self.last_price = float(order['price'])

    def update_current_price(self):
        now = datetime.datetime.now()
        time_string = datetime.datetime.strftime(now, '%Y-%m-%d %H:%M:%S')
        time_symbol = ' '.join([time_string, self.symbol])
        if not self.rd.get(time_symbol):
            return
        self.current_price = float(self.rd.get(time_symbol))

    def update_is_earning(self):
        prev_is_earning = self.is_earning
        self.is_earning = (self.current_price - self.offset_price) * self.is_buy > 0
        # if prev_is_earning != self.is_earning:
        #     print(f'is_earning : {self.is_earning}로 업데이트')
        did_change_to_black =  not prev_is_earning and self.is_earning
        return did_change_to_black

    def create_market_order(self, amount, reduce_only=False):
        if amount > 0:
            return self.binance.create_market_order(self.symbol, 'buy', abs(amount), params={"reduceOnly": reduce_only})
        else:
            return self.binance.create_market_order(self.symbol, 'sell', abs(amount), params={"reduceOnly": reduce_only})

    def increase_position(self, rate):
        self.update_from_balance()
        amount = self.is_buy * self.total_balance * self.LEVERAGE * rate / self.current_price
        order = self.create_market_order(amount)
        self.print_order_result(order)
        self.update_last_price_from_order(order)
        self.update_from_balance()

    def reduce_only(self, rate):
        self.update_from_balance()
        amount = -1 * self.amount * rate
        order = self.create_market_order(amount, reduce_only=True)
        self.print_order_result(order)
        self.update_last_price_from_order(order)
        self.update_from_balance()

    def close_all_positions(self):
        self.update_from_balance()
        self.create_market_order(-1 * self.amount, reduce_only=True)
        print(f'[{self.symbol}] 포지션 종료')
        self.rd.set(self.symbol, 'not trading')
        self.reset_position_number()

    def get_estimated_pnl_rate(self):
        return self.is_buy * self.margin_rate * (self.current_price - self.offset_price) / self.offset_price \
               * self.LEVERAGE

    def get_if_exceeds_max_loss(self):
        return self.get_estimated_pnl_rate() < self.MAX_LOSS_RATE

    def get_pnl_rate_from_last_price(self):
        return self.is_buy * (self.current_price - self.last_price) / self.last_price

    def get_pnl_rate_from_offset_price(self):
        return self.is_buy * (self.current_price - self.offset_price) / self.offset_price

    def get_previous_price(self, minutes):
        prev_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)  # (minutes=INTERVAL_MINUTES)
        prev_time_string = datetime.datetime.strftime(prev_time, '%Y-%m-%d %H:%M:%S')
        prev_time_symbol = ' '.join([prev_time_string, self.symbol])
        prev_price = self.rd.get(prev_time_symbol)
        return prev_price


@app.task
def trade(db_number, symbol, initial_fluctuation_rate, price):
    # 시작
    IS_BUY = 1 if initial_fluctuation_rate < 0 else -1

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(minutes=60)

    # 트레이딩
    trader = Trader(symbol=symbol, is_buy=IS_BUY, db_number=db_number, price=price)
    trader.increase_position(0.05)

    while datetime.datetime.now() < end_time:
        trader.update_current_price()
        did_change_to_black = trader.update_is_earning()

        if did_change_to_black and trader.margin_rate > 0.08:
                print(f'[{trader.symbol}] margin_rate : {trader.margin_rate} 본절 도달 후 포지션 줄이기 신호 발생')
                trader.reduce_only(0.50)

        # 급등락 포지션 정리
        INTERVAL_MINUTES = 1
        prev_price = trader.get_previous_price(INTERVAL_MINUTES)
        if prev_price:
            prev_price = float(prev_price)
            fluctuation_rate = (price - prev_price) / prev_price * 100
            if abs(fluctuation_rate) >= 1.5:
                if trader.get_pnl_rate_from_last_price() > 0.01:
                    print(f'[{symbol}] : 1분 동안 {fluctuation_rate}만큼 급등 및 마지막 매수가 기준 1프로 이상 변동')
                    if abs(trader.margin_rate) < 0.02:
                        print(f'[{symbol}] : 급등락 발생 & 포지션 0.02 이하로 인해 포지션 종료')
                        break
                    else:
                        print(f'[{symbol}] : 급등락 발생 & 포지션 0.02 이상 포지션 50% Reduce Only')
                        trader.reduce_only(0.50)

        # 5% 이상 손실 시 전체 포지션 종료
        if trader.get_if_exceeds_max_loss():
            print(f'[{symbol}] : 5% 이상 손실로 인해 포지션 종료')
            break

        # 물타기
        if trader.get_pnl_rate_from_last_price() < -0.02:
            print(f'[{symbol}] : 물타기 5% => 직전 거래가보다 2% 이상 손실')
            trader.increase_position(0.05)

        if trader.get_pnl_rate_from_offset_price() > 0.02 and trader.get_pnl_rate_from_last_price() > 0.02:
            if abs(trader.margin_rate) < 0.02:
                print(f'[{symbol}] : {abs(trader.margin_rate)} < 0.02 : 포지션 종료 => 2% 이익 및 직전 거래가보다 2% 이상 이익')
                break

            print(f'[{symbol}] : 익절 50% => 최초 변동폭 회복 및 직전 거래가보다 2% 이상 이익')
            trader.reduce_only(0.50)

    # 포지큼 종료
    trader.close_all_positions()
    return
