# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
from technical.util import resample_to_interval
from technical.util import resampled_merge
import talib.abstract as ta
from technical.indicators import cmf
from technical.indicators import osc
from technical.indicators import vfi


class MultiRsiVfi(IStrategy):
    """

    author@: Gert Wohlgemuth

    based on work from Creslin

    """
    minimal_roi = {
        "0": 0.01
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.05

    # Optimal ticker interval for the strategy
    ticker_interval = '15m'

    def get_ticker_indicator(self):
        return int(self.ticker_interval[:-1])

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        dataframe['sma5'] = ta.SMA(dataframe, timeperiod=5)
        dataframe['sma200'] = ta.SMA(dataframe, timeperiod=200)

        # resample our dataframes
        dataframe_short = resample_to_interval(dataframe, self.get_ticker_indicator() * 2)
        dataframe_long = resample_to_interval(dataframe, self.get_ticker_indicator() * 8)

        # compute our RSI's
        dataframe_short['rsi'] = ta.RSI(dataframe_short, timeperiod=14)
        dataframe_long['rsi'] = ta.RSI(dataframe_long, timeperiod=14)
        dataframe_short['cmf'] = cmf(dataframe_short, 14)
        dataframe_long['cmf'] = cmf(dataframe_long, 14)

        dataframe_short['osc'] = osc(dataframe_short, 14)
        dataframe_long['osc'] = osc(dataframe_long, 14)

        # merge dataframe back together
        dataframe = resampled_merge(dataframe, dataframe_short)
        dataframe = resampled_merge(dataframe, dataframe_long)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # fill NA values with previes
        dataframe.fillna(method='ffill', inplace=True)

        # Volume Flow Index: Add VFI, VFIMA, Histogram to DF
        dataframe['vfi'], dataframe['vfima'], dataframe['vfi_hist'] =  \
            vfi(dataframe, length=130, coef=0.2, vcoef=2.5, signalLength=5, smoothVFI=True)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        dataframe.loc[
            (
                # must be bearish
                    #(dataframe['sma5'] >= dataframe['sma200']) &
                    (dataframe['vfi'] >= dataframe['vfima']) &
                    (dataframe['rsi'] < (dataframe['resample_{}_rsi'.format(self.get_ticker_indicator() * 8)] - 20)) &
                    (dataframe['resample_{}_cmf'.format(self.get_ticker_indicator() * 8)] > 0)
            ),
            'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        dataframe.loc[
            (
                    (dataframe['vfi'] < dataframe['vfima']) &
                    (dataframe['rsi'] > dataframe['resample_{}_rsi'.format(self.get_ticker_indicator() * 2)]) &
                    (dataframe['rsi'] > dataframe['resample_{}_rsi'.format(self.get_ticker_indicator() * 8)])
            ),
            'sell'] = 1
        return dataframe
