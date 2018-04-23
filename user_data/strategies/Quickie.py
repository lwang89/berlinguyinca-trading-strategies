# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Quickie(IStrategy):
    """

    author@: Gert Wohlgemuth

    idea:
        momentum based strategie. The main idea is that it closes trades very quickly, while avoiding excessive losses. Hence a rather moderate stop loss in this case
    """

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {
        "0": 0.01
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.25

    # Optimal ticker interval for the strategy
    ticker_interval = 1

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        #our main deciding force
        dataframe['willr'] = ta.WILLR(dataframe)

        #some basic insurance
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
                (
                        dataframe['willr'] < -80  #
                ) &
                (
                        dataframe['macd'] > dataframe['macdsignal']
                )
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
            (
                    dataframe['willr'] > -20
            ),
            'sell'] = 1
        return dataframe
