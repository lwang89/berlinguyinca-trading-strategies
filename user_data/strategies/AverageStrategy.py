# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class AverageStrategy(IStrategy):
    """

    author@: Gert Wohlgemuth

    idea:

        defines a strategy whihc is based on the idea o
    """

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {
        "60": 0.01,
        "30": 0.03,
        "20": 0.04,
        "0": 0.05
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.45

    # Optimal ticker interval for the strategy
    ticker_interval = 1

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        macd = ta.MACD(dataframe)

        dataframe['cci'] = ta.CCI(dataframe)
        dataframe['sma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['sma50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma100'] = ta.SMA(dataframe, timeperiod=100)

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
                    (
                            (
                                    (dataframe['close'] > dataframe['sma25']) &
                                    (dataframe['sma25'] > dataframe['sma50']) &
                                    (dataframe['sma50'] > dataframe['sma100'])
                            ) &
                            (dataframe['macd'] > dataframe['macdsignal'])
                    ) |
                    (
                        # try ti catch oversold market conditions
                            (
                                    (dataframe['close'] < dataframe['sma25']) &
                                    (dataframe['sma25'] < dataframe['sma50']) &
                                    (dataframe['sma50'] < dataframe['sma100'])
                            ) &
                            (dataframe['macd'] > dataframe['macdsignal'])
                    )

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
                (dataframe['cci'] >= 100)
            ),
            'sell'] = 1
        return dataframe
