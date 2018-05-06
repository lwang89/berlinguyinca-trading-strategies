# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from hyperopt import hp
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class BollingerRSIPingPong(IStrategy):
    """

    author@: Gert Wohlgemuth

    idea:
        this strategy is based around the idea of trading between the upper and lower bollinger band, while
        having a very low stoploss and avoiding false buys. It should not need a minimal roi
        since it should always sell on sell signals.

    """

    # Minimal ROI designed for the strategy.
    # we only sell after 100%, unless our sell points are found before
    minimal_roi = {
        "0": 0.1
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    # should be converted to a trailing stop loss
    stoploss = -0.05

    # Optimal ticker interval for the strategy
    ticker_interval = 5

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        ##################################################################################
        # required for entry and exit
        # CCI
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=11)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=11)


        ##################################################################################
        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']


        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        ##################################################################################
        # required for entry
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=1.6)
        dataframe['entry_bb_lowerband'] = bollinger['lower']
        dataframe['entry_bb_upperband'] = bollinger['upper']
        dataframe['entry_bb_middleband'] = bollinger['mid']

        # insurance for falling markets
        dataframe['sma_400'] = ta.SMA(dataframe, timeperiod=400)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['sma_100'] = ta.SMA(dataframe, timeperiod=100)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)

        # patterns for entry
        dataframe['CDLHAMMER'] = ta.CDLHAMMER(dataframe)
        dataframe['CDLINVERTEDHAMMER'] = ta.CDLINVERTEDHAMMER(dataframe)
        dataframe['CDLDRAGONFLYDOJI'] = ta.CDLDRAGONFLYDOJI(dataframe)
        dataframe['CDLSPINNINGTOP'] = ta.CDLSPINNINGTOP(dataframe) # values [0, -100, 100]

        ##################################################################################
        # required for exit

        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=1.5)
        dataframe['exit_bb_lowerband'] = bollinger['lower']
        dataframe['exit_bb_upperband'] = bollinger['upper']
        dataframe['exit_bb_middleband'] = bollinger['mid']

        # patterns
        # Harami: values [0, -100, 100]
        dataframe['CDLHARAMI'] = ta.CDLHARAMI(dataframe)  # values [0, -100, 100]

        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=5, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=5, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=5, price='low')
        stoch_fast = ta.STOCHF(dataframe, 5.0, 3.0, 0.0, 3.0, 0.0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        # volumne indicators
        dataframe['ad'] = ta.AD(dataframe)
        dataframe['mfi'] = ta.MFI(dataframe)

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame) -> DataFrame:
        dataframe.loc[
            (
                (
                    # # doesn't make to much sense this block
                    # # we should consider getting rid of it
                    # #
                    # # spike below entry band for 3 consecutive ticks
                    # # while highs are below the middle band and
                    # # over the lower band
                    # (
                    #     (dataframe['low'] < dataframe['entry_bb_lowerband'])
                    #     & (dataframe['low'].shift(1) < dataframe['entry_bb_lowerband'].shift(1))
                    #     & (dataframe['low'].shift(2) < dataframe['entry_bb_lowerband'].shift(2))
                    #     & (dataframe['high'].shift(1) < dataframe['entry_bb_middleband'].shift(1))
                    #     & (dataframe['high'].shift(2) < dataframe['entry_bb_middleband'].shift(2))
                    #     & (dataframe['high'].shift(1) > dataframe['entry_bb_lowerband'].shift(1))
                    #     & (dataframe['high'].shift(2) > dataframe['entry_bb_lowerband'].shift(2))
                    #     # pattern recognition
                    #     & (
                    #             (dataframe['close'] > dataframe['open'])
                    #             | (dataframe['CDLHAMMER'] == 100)
                    #             | (dataframe['CDLINVERTEDHAMMER'] == 100)
                    #             | (dataframe['CDLDRAGONFLYDOJI'] == 100)
                    #     )
                    #     # must be over bought
                    #     & (dataframe['cci'] < -100)
                    #
                    #     # sma for safe guarding, otherwise it buys in a falling market, which might
                    #     # cause unnecessary problems
                    #     # a bit extreme, see beging of block comment
                    #
                    # )
                    #
                    # |
                    # we have the four red one green pattern
                    # and the close is in the lower band
                    # and the low is outside the lower band
                    # and the lows must get higher
                    (
                        StrategyHelper.four_red_one_green_candle(dataframe)
                        & (dataframe['low'] < dataframe['entry_bb_lowerband'])
                        & (dataframe['close'] > dataframe['entry_bb_lowerband'])
                        & (dataframe['close'] < dataframe['entry_bb_middleband'])
                        & (dataframe['low'] >= dataframe['low'].shift(1))
                        # must be over bought
                        & (dataframe['cci'] < -100)
                    )
                    |
                    # we have 8 red candles in a row
                    # often a sign that the market will soon turn
                    # must be over bought
                    (
                        StrategyHelper.eight_red_candles(dataframe)
                        & (dataframe['cci'] < -100)
                    )

                    |
                    # 4 red candles with lower and lower lows
                    # while beeing outside the bollinger band
                    # and current is a hammer
                    # and a green candle
                    (
                        (
                            (dataframe['CDLHAMMER'] == 100)
                            & (dataframe['open'] < dataframe['close'])
                        )
                        & (dataframe['low'] < dataframe['low'].shift(1))
                        & (dataframe['low'].shift(1) < dataframe['low'].shift(2))
                        & (dataframe['low'].shift(2) < dataframe['low'].shift(3))
                        & (dataframe['low'].shift(3) < dataframe['low'].shift(4))

                        & (dataframe['low'] < dataframe['entry_bb_lowerband'])
                        & (dataframe['low'].shift(1) < dataframe['entry_bb_lowerband'].shift(1))
                        & (dataframe['low'].shift(2) < dataframe['entry_bb_lowerband'].shift(2))

                        & StrategyHelper.four_red_one_green_candle(dataframe)
                    )

                    |
                    # 3 lower and lower lows, followed by  2 higher lows
                    # while macd > macd signal
                    # while close below middle bollinger
                    (
                        (dataframe['low'] > dataframe['low'].shift(1))
                        & (dataframe['low'].shift(1) > dataframe['low'].shift(2))
                        & (dataframe['low'].shift(2) < dataframe['low'].shift(3))
                        & (dataframe['low'].shift(3) < dataframe['low'].shift(4))
                        & (dataframe['low'].shift(4) < dataframe['low'].shift(5))
                        & (dataframe['macdsignal'] < dataframe['macd'])
                        & (dataframe['close'] < dataframe['entry_bb_middleband'])

                    )
                )

            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame) -> DataFrame:
        # different strategy used for sell points, due to be able to duplicate it to 100%
        dataframe.loc[
            (
                (
                    # 8 green candles in a row
                    StrategyHelper.eight_green_candles(dataframe)
                    |
                    # 4 green followed by a red candle
                    # while being oversold
                    # open over middle band
                    # close outside the outer band
                    # for 3 candles
                    (
                        StrategyHelper.four_green_one_red_candle(dataframe)
                        & (dataframe['cci'] > 100)
                        & (dataframe['open'] > dataframe['exit_bb_middleband'])
                        & (dataframe['close'] > dataframe['exit_bb_upperband'])
                        & (dataframe['open'].shift(1) > dataframe['exit_bb_middleband']).shift(1)
                        & (dataframe['open'].shift(2) > dataframe['exit_bb_middleband']).shift(2)
                    )
                    |
                    # if it's a haramis
                    # which current clande is red
                    # and previous is green
                    # and it's over the exit bb upperband
                    (
                            (dataframe['CDLHARAMI'] == -100) &
                            (dataframe['open'] > dataframe['close']) &
                            (dataframe['open'].shift(1) < dataframe['close'].shift()) &
                            (dataframe['close'] > dataframe['exit_bb_upperband'])
                    )
                    # |
                    # # open has to be over ema
                    # (
                    #     (dataframe['open'] >= dataframe['ema_high'])
                    # )
                    # |
                    # #stoch has to be crossed
                    # (
                    #         (qtpylib.crossed_above(dataframe['fastk'], 70)) |
                    #         (qtpylib.crossed_above(dataframe['fastd'], 70))
                    # )
                )

            ),
            'sell'] = 1
        return dataframe


class StrategyHelper:
    """
        simple helper class to predefine a couple of patterns for our
        strategy
    """

    @staticmethod
    def seven_green_candles(dataframe):
        """
            evaluates if we are having 7 green candles in a row
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] < dataframe['close']) &
                (dataframe['open'].shift(1) < dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) < dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) < dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) < dataframe['close'].shift(4)) &
                (dataframe['open'].shift(5) < dataframe['close'].shift(5)) &
                (dataframe['open'].shift(6) < dataframe['close'].shift(6)) &
                (dataframe['open'].shift(7) < dataframe['close'].shift(7))
        )

    @staticmethod
    def eight_green_candles(dataframe):
        """
            evaluates if we are having 8 green candles in a row
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] < dataframe['close']) &
                (dataframe['open'].shift(1) < dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) < dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) < dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) < dataframe['close'].shift(4)) &
                (dataframe['open'].shift(5) < dataframe['close'].shift(5)) &
                (dataframe['open'].shift(6) < dataframe['close'].shift(6)) &
                (dataframe['open'].shift(7) < dataframe['close'].shift(7)) &
                (dataframe['open'].shift(8) < dataframe['close'].shift(8))
        )
    @staticmethod
    def eight_red_candles(dataframe):
        """
            evaluates if we are having 8 red candles in a row
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] > dataframe['close']) &
                (dataframe['open'].shift(1) > dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) > dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) > dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) > dataframe['close'].shift(4)) &
                (dataframe['open'].shift(5) > dataframe['close'].shift(5)) &
                (dataframe['open'].shift(6) > dataframe['close'].shift(6)) &
                (dataframe['open'].shift(7) > dataframe['close'].shift(7)) &
                (dataframe['open'].shift(8) > dataframe['close'].shift(8))
        )


    @staticmethod
    def four_green_one_red_candle(dataframe):
        """
            evaluates if we are having a red candle and 4 previous green
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] > dataframe['close']) &
                (dataframe['open'].shift(1) < dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) < dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) < dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) < dataframe['close'].shift(4))
        )


    @staticmethod
    def four_red_one_green_candle(dataframe):
        """
            evaluates if we are having a green candle and 4 previous red
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] < dataframe['close']) &
                (dataframe['open'].shift(1) > dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) > dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) > dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) > dataframe['close'].shift(4))
        )
