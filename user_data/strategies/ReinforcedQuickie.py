# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame, DatetimeIndex, merge
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class ReinforcedQuickie(IStrategy):
    """

    author@: Gert Wohlgemuth

    idea:
        only buy on an upward tending market
    """

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {
        "0": 0.1
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.02

    # Optimal ticker interval for the strategy
    ticker_interval = 5

    # resample factor to establish our general trend. Basically don't buy if a trend is not given
    resample_factor = 12

    EMA_SHORT_TERM = 5
    EMA_MEDIUM_TERM = 12
    EMA_LONG_TERM = 21

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        # defines the reinforcement logic
        # resampled dataframe to establish if we are in an uptrend, downtrend or sideways trend
        df = dataframe.copy()
        df = df.set_index(DatetimeIndex(df['date']))

        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }

        df = df.resample(str(self.ticker_interval * self.resample_factor) + 'min', how=ohlc_dict).dropna(how='any')
        df['resample_sma'] = ta.SMA(df, timeperiod=25, price='close')
        df = df.drop(columns=['open', 'high', 'low', 'close'])
        df = df.resample(str(self.ticker_interval) + 'min')
        df = df.interpolate(method='time')

        df['date'] = df.index

        df.index = range(len(df))
        dataframe = merge(dataframe, df, on='date', how='left')

        ##################################################################################
        # buy and sell indicators

        dataframe['ema_{}'.format(self.EMA_SHORT_TERM)] = ta.EMA(
            dataframe, timeperiod=self.EMA_SHORT_TERM
        )
        dataframe['ema_{}'.format(self.EMA_MEDIUM_TERM)] = ta.EMA(
            dataframe, timeperiod=self.EMA_MEDIUM_TERM
        )
        dataframe['ema_{}'.format(self.EMA_LONG_TERM)] = ta.EMA(
            dataframe, timeperiod=self.EMA_LONG_TERM
        )

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        dataframe['min'] = ta.MIN(dataframe, timeperiod=self.EMA_MEDIUM_TERM)
        dataframe['max'] = ta.MAX(dataframe, timeperiod=self.EMA_MEDIUM_TERM)

        dataframe['mfi'] = ta.MFI(dataframe)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=7)

        ##################################################################################
        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe['volume'] < (dataframe['volume'].rolling(window=30).mean().shift(1) * 20)) &
                (dataframe['close'] < dataframe['ema_{}'.format(self.EMA_SHORT_TERM)]) &
                (dataframe['close'] < dataframe['ema_{}'.format(self.EMA_MEDIUM_TERM)]) &
                (dataframe['close'] == dataframe['min']) &
                (dataframe['close'] <= dataframe['bb_lowerband']) &
                (dataframe['resample_sma'] < dataframe['close']) &
                (dataframe['resample_sma'].shift(1) < dataframe['resample_sma']) &
                (dataframe['mfi'] < 20) &
                (dataframe['mfi'] < dataframe['rsi'])

            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_{}'.format(self.EMA_SHORT_TERM)]) &
                (dataframe['close'] > dataframe['ema_{}'.format(self.EMA_MEDIUM_TERM)]) &
                (dataframe['close'] >= dataframe['max']) &
                (dataframe['close'] >= dataframe['bb_upperband']) &
                (dataframe['mfi'] > 80)
            ) |
            (
                (dataframe['mfi'] > 80) &
                (dataframe['rsi'] > 80)
            )
            ,
            'sell'
        ] = 1
        return dataframe
