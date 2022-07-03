import ccxt
import datetime
from config import api_key, secret


binance = ccxt.binance(config={
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'createMarketBuyOrderRequiresPrice': False
    }
})


FUTURE_SYMBOLS = ['APE/BUSD', 'BAKE/USDT', 'NKN/USDT', 'XEM/USDT', 'LRC/USDT', 'ZEC/USDT', 'LINA/USDT', 'YFI/USDT',
                  'RVN/USDT', 'QTUM/USDT', 'SXP/USDT', 'ETHUSDT_220624', 'CVC/USDT', 'CHZ/USDT', 'REEF/USDT',
                  'FIL/USDT', 'FTM/BUSD', 'OP/USDT', 'BNX/USDT', 'FTT/USDT', 'MTL/USDT', 'XRP/USDT', 'MATIC/USDT',
                  'APE/USDT', 'SOL/BUSD', 'COTI/USDT', 'NEO/USDT', 'ALGO/USDT', 'GAL/USDT', 'HBAR/USDT', 'BAT/USDT',
                  'REN/USDT', 'ADA/USDT', 'DODO/BUSD', 'AVAX/USDT', 'HOT/USDT', 'TRX/USDT', 'AXS/USDT', 'GAL/BUSD',
                  'IMX/USDT', 'SC/USDT', 'ALPHA/USDT', 'KNC/USDT', 'BTC/BUSD', 'CHR/USDT', 'AUDIO/USDT', 'API3/USDT',
                  'XTZ/USDT', 'KSM/USDT', 'BTS/USDT', 'HNT/USDT', 'DASH/USDT', 'ICP/USDT', 'DGB/USDT', 'DOGE/USDT',
                  'MASK/USDT', 'GMT/BUSD', 'WOO/USDT', 'ARPA/USDT', 'VET/USDT', 'AAVE/USDT', 'AVAX/BUSD', 'IOTX/USDT',
                  'SRM/USDT', 'ONE/USDT', 'RLC/USDT', 'NEAR/USDT', 'GTC/USDT', 'STORJ/USDT', 'EGLD/USDT', 'WAVES/USDT',
                  'AR/USDT', 'BTCUSDT_220624', 'ETH/USDT', '1INCH/USDT', 'EOS/USDT', 'PEOPLE/USDT', 'UNFI/USDT',
                  'SUSHI/USDT', 'RSR/USDT', 'OMG/USDT', 'IOTA/USDT', 'CRV/USDT', 'TRX/BUSD', 'ICX/USDT', 'ALICE/USDT',
                  'OGN/USDT', 'FTT/BUSD', 'RAY/USDT', 'LUNA2/BUSD', 'BCH/USDT', 'FTM/USDT', 'BLZ/USDT', 'BNB/USDT',
                  'KAVA/USDT', 'SKL/USDT', 'BNB/BUSD', 'JASMY/USDT', 'SOL/USDT', 'OCEAN/USDT', 'BTC/USDT',
                  'BTCDOM/USDT', 'DOGE/BUSD', 'LINK/USDT', 'SAND/USDT', 'ZRX/USDT', 'C98/USDT', 'XLM/USDT', 'GALA/USDT',
                  'ANKR/USDT', 'MANA/USDT', 'TRB/USDT', 'THETA/USDT', 'XRP/BUSD', 'ROSE/USDT', 'UNI/USDT', 'STMX/USDT',
                  'NEAR/BUSD', 'IOST/USDT', 'FLOW/USDT', 'BAND/USDT', 'KLAY/USDT', 'DAR/USDT', 'ETC/USDT', 'ETH/BUSD',
                  'ANC/BUSD', '1000LUNC/BUSD', 'ZIL/USDT', 'CTSI/USDT', 'ANT/USDT', 'ENJ/USDT', 'LTC/USDT', 'RUNE/USDT',
                  'DYDX/USDT', 'CTK/USDT', 'LIT/USDT', 'SFP/USDT', 'ATOM/USDT', 'ZEN/USDT', 'TOMO/USDT', 'GALA/BUSD',
                  'DEFI/USDT', 'FLM/USDT', '1000XEC/USDT', 'ADA/BUSD', 'CELO/USDT', 'ATA/USDT', 'BEL/USDT', 'COMP/USDT',
                  'ENS/USDT', 'ONT/USDT', 'DUSK/USDT', '1000SHIB/USDT', 'TLM/USDT', 'DOT/USDT', 'GRT/USDT', 'XMR/USDT',
                  'MKR/USDT', 'GMT/USDT', 'CELR/USDT', 'BAL/USDT', 'DENT/USDT', 'LPT/USDT', 'SNX/USDT']


USDT_FUTURE_SYMBOLS = [s for s in FUTURE_SYMBOLS if s.endswith('USDT')]


def get_last_max_loss_symbol(symbol):
    last_max_loss_symbol = 'Last Max Loss ' + symbol
    return last_max_loss_symbol


def get_time_symbol(datetime_obj, symbol):
    time_string = str(datetime.datetime.strftime(datetime_obj, '%Y-%m-%d %H:%M:%S'))
    time_symbol = ' '.join([time_string, symbol])
    return time_symbol
