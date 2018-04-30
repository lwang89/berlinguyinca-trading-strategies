# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Counter(IStrategy):
    """

    author@: Gert Wohlgemuth

    idea:

        we count consecutive green bars, after 6 bars, we buy
    """

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {
        "0":  0.05
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.3

    # Optimal ticker interval for the strategy
    ticker_interval = 1

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:

        dataframe['open-6'] = dataframe.open.shift(6)
        dataframe['open-5'] = dataframe.open.shift(5)
        dataframe['open-4'] = dataframe.open.shift(4)
        dataframe['open-3'] = dataframe.open.shift(3)
        dataframe['open-2'] = dataframe.open.shift(2)
        dataframe['open-1'] = dataframe.open.shift(1)

        dataframe['close-6'] = dataframe.close.shift(6)
        dataframe['close-5'] = dataframe.close.shift(5)
        dataframe['close-4'] = dataframe.close.shift(4)
        dataframe['close-3'] = dataframe.close.shift(3)
        dataframe['close-2'] = dataframe.close.shift(2)
        dataframe['close-1'] = dataframe.close.shift(1)

        dataframe['cci'] = ta.CCI(dataframe)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """

        dataframe.loc[
            (
                  (dataframe['close'] > dataframe['open'])
                & (dataframe['close-1'] > dataframe['open-1'])
                & (dataframe['close-2'] > dataframe['open-2'])
                & (dataframe['close-3'] > dataframe['open-3'])
                & (dataframe['close-4'] > dataframe['open-4'])
            )
            ,
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (dataframe['cci'] >= 100)
            ,
            'sell'] = 1
        return dataframe
