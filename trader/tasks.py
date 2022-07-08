from trader.celery import app
from common import binance, get_last_max_loss_symbol, get_time_symbol, MAX_LOSS_TIME_FORMAT
import redis
import datetime
import time

class Trader:
    LEVERAGE = 15
    MAX_LOSS_RATE = -0.03  # 전체 자산 대비 최대 손실 비율
    BUY_POSITION_NUM_STR = 'buy_position_number'
    SELL_POSITION_NUM_STR = 'sell_position_number'

    def __init__(self, symbol, is_buy, db_number, price):
        # 도중에 변경 안됨
        self.symbol = symbol
        self.is_buy = is_buy
        self.side = 'buy' if self.is_buy == 1 else 'sell'
        # 매매 시에 업데이트
        self.amount = 0  # buy면 +, sell이면 -
        self.is_earning = False
        self.margin_rate = 0
        self.offset_price = price
        self.last_trade_time = datetime.datetime.now()
        # 항상 최신 유지
        self.last_price = price
        # 바이낸스 객체
        self.binance = binance
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
            print(f'[{self.symbol}] 매수 시작 : 총 매수 포지션 수 {previous_position_num + 1}로 업데이트')
        if self.side == 'sell':
            previous_position_num = int(self.rd.get(self.SELL_POSITION_NUM_STR))
            self.rd.set(self.SELL_POSITION_NUM_STR, previous_position_num + 1)
            print(f'[{self.symbol}] 매도 시작 : 총 매도 포지션 수 {previous_position_num + 1}로 업데이트')

    def reset_position_number(self):
        if self.side == 'buy':
            previous_position_num = int(self.rd.get(self.BUY_POSITION_NUM_STR))
            self.rd.set(self.BUY_POSITION_NUM_STR, previous_position_num - 1)
            print(f'[{self.symbol}] 매수 종료 : 총 매수 포지션 수 {previous_position_num - 1}로 업데이트')

        if self.side == 'sell':
            previous_position_num = int(self.rd.get(self.SELL_POSITION_NUM_STR))
            self.rd.set(self.SELL_POSITION_NUM_STR, previous_position_num - 1)
            print(f'[{self.symbol}] 매도 종료 : 총 매도 포지션 수 {previous_position_num - 1}로 업데이트')

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
        time_symbol = get_time_symbol(datetime.datetime.now(), self.symbol)
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
        self.last_trade_time = datetime.datetime.now()
        if amount > 0:
            return self.binance.create_market_order(self.symbol, 'buy', abs(amount), self.current_price, params={"reduceOnly": reduce_only})
        else:
            return self.binance.create_market_order(self.symbol, 'sell', abs(amount), self.current_price, params={"reduceOnly": reduce_only})

    def increase_position(self, rate):
        self.update_from_balance()
        prev_amount = self.amount
        amount = self.is_buy * self.total_balance * self.LEVERAGE * rate / self.current_price
        order = self.create_market_order(amount)
        self.print_order_result(order)
        self.update_last_price_from_order(order)
        self.update_from_balance()
        print(f'[{self.symbol}] 포지션 증가 후 {self.amount}(평균 단가 : {self.offset_price})로 업데이트')
        while self.amount == prev_amount:
            self.update_from_balance()
            print(f'[{self.symbol}] 포지션 증가 후 {self.amount}(평균 단가 : {self.offset_price})로 업데이트')

    def reduce_only(self, rate):
        self.update_from_balance()
        prev_amount = self.amount
        amount = -1 * prev_amount * rate
        order = self.create_market_order(amount, reduce_only=True)
        self.print_order_result(order)
        self.update_last_price_from_order(order)
        self.update_from_balance()
        print(f'[{self.symbol}] 포지션 감소 후 {self.amount}(평균 단가 : {self.offset_price})로 업데이트')
        while self.amount == prev_amount:
            self.update_from_balance()
            print(f'[{self.symbol}] 포지션 감소 후 {self.amount}(평균 단가 : {self.offset_price})로 업데이트')

    def close_all_positions(self):
        self.update_from_balance()
        self.create_market_order(-1 * self.amount, reduce_only=True)
        print(f'[{self.symbol}] 포지션 종료\n')
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
        while self.offset_price == 0:
            self.update_from_balance()
        return self.is_buy * (self.current_price - self.offset_price) / self.offset_price

    def get_previous_price(self, minutes):
        prev_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
        prev_time_symbol = get_time_symbol(prev_time, self.symbol)
        prev_price = self.rd.get(prev_time_symbol)
        return prev_price

    def record_max_loss(self):
        last_max_loss_symbol = get_last_max_loss_symbol(self.symbol)
        time_string = datetime.datetime.strftime(datetime.datetime.now(), MAX_LOSS_TIME_FORMAT)
        self.rd.set(last_max_loss_symbol, time_string)


@app.task
def trade(db_number, symbol, initial_fluctuation_rate, price):
    print('-------------------------------------')
    print(f'-------[{symbol}] 거래 시작-----------')

    # 시작
    IS_BUY = 1 if initial_fluctuation_rate < 0 else -1
    # 트레이딩
    trader = Trader(symbol=symbol, is_buy=IS_BUY, db_number=db_number, price=price)
    trader.increase_position(0.03)
    start_trading_time = datetime.datetime.now()
    while True:
        time.sleep(0.001)
        trader.update_current_price()
        did_change_to_black = trader.update_is_earning()

        if did_change_to_black and trader.margin_rate > 0.05 and trader.last_price < trader.offset_price:
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
            print(f'[{symbol}] : 3% 이상 손실로 인해 포지션 종료')
            trader.record_max_loss()
            break

        # 물타기
        if trader.get_pnl_rate_from_last_price() < -0.02:
            if datetime.datetime.now() - trader.last_trade_time > datetime.timedelta(minutes=1):
                print(f'[{symbol}] : 물타기 5% => 직전 거래가보다 2% 이상 손실')
                trader.increase_position(0.03)

        if trader.get_pnl_rate_from_offset_price() > abs(initial_fluctuation_rate)/100 * 0.5\
                and trader.get_pnl_rate_from_last_price() > 0.01:
            if abs(trader.margin_rate) < 0.02:
                print(f'[{symbol}] : {abs(trader.margin_rate)} < 0.02 : 포지션 종료 => 1% 이익 및 직전 거래가보다 1% 이상 이익')
                break

            print(f'[{symbol}] : 익절 50% => 최초 변동폭의 절반 회복 및 직전 거래가보다 1% 이상 이익')
            trader.reduce_only(0.50)

        if datetime.datetime.now() - start_trading_time > datetime.timedelta(hours=3) and trader.is_earning:
            print(f'[{symbol}] : 거래 시작 후 3시간 경과 및 이익 구간이므로 포지션 종료')
            break

        if datetime.datetime.now() - start_trading_time > datetime.timedelta(hours=6):
            print(f'[{symbol}] : 거래 시작 후 6시간 경과이므로 포지션 종료')
            break

    # 포지큼 종료
    trader.close_all_positions()
    print('-------------------------------------\n\n')
    return
