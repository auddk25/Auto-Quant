"""
MtfTrend02 -- Daily EMA trend + 4h EMA crossover + BTC cross-pair filter

Paradigm: pure trend-following with cross-pair confirmation
Hypothesis: ETH loses on false EMA crossovers in choppy markets. Adding a
            BTC strength gate (BTC close > BTC EMA50 on 1d) for ETH entries
            filters out bear-market whipsaws. BTC entries unchanged.
Parent: MtfTrend02 R3
Created: R3, evolved R4
Status: active
Uses MTF: yes (1d trend, 4h entry, cross-pair BTC filter for ETH)
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy, informative


class MtfTrend02(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    @informative("1d", "BTC/USDT")
    def populate_indicators_1d_btc(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["close_above_ema"] = (dataframe["close"] > dataframe["ema50"]).astype(int)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema12_prev"] = dataframe["ema12"].shift(1)
        dataframe["ema26_prev"] = dataframe["ema26"].shift(1)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_btc = metadata["pair"] == "BTC/USDT"

        base_cond = (
            (dataframe["close_1d"] > dataframe["ema50_1d"])
            & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
            & (dataframe["ema12_4h"] > dataframe["ema26_4h"])
            & (dataframe["ema12_prev_4h"] <= dataframe["ema26_prev_4h"])
            & (dataframe["rsi_4h"] > 40)
            & (dataframe["rsi_4h"] < 70)
            & (dataframe["volume"] > 0)
        )

        if is_btc:
            dataframe.loc[base_cond, "enter_long"] = 1
        else:
            eth_cond = base_cond & (dataframe["btc_usdt_close_above_ema_1d"] == 1)
            dataframe.loc[eth_cond, "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema50_1d"] < dataframe["ema150_1d"])
                | (dataframe["ema12_4h"] < dataframe["ema26_4h"])
            ),
            "exit_long",
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit, **kwargs) -> float:
        if current_profit >= 0.30:
            return -0.05
        return self.stoploss
