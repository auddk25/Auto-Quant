"""
AnchorFactor — RSI<40 anchor signal + v0.3.0 factor gates for bear protection

Paradigm: mean-reversion
Hypothesis: MeanRevADX's RSI<40 entry produces 97% win rate on 2023-2025 but
            loses 13% in 2022 bear market (no macro protection). By adding the
            v0.3.0 factor gates (funding_rate + stablecoin_7d) to the BTC path,
            we should keep the high-quality entry signal while preventing
            bear-market trap entries. ETH uses pure RSI<40 without gates (gates
            hurt ETH, as confirmed in R65/R69).
Parent: MeanRevADX (entry/exit logic), FactorMeanRevCandidate (factor gates)
Created: 2026-04-23
Status: active
"""

from pathlib import Path

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy

from autoq_data.strategy_bridge import merge_external_factors


class AnchorFactor(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.008}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200
    enriched_root: Path | None = None
    max_funding_rate = 0.001

    factor_columns = [
        "funding_rate",
        "stablecoin_mcap_growth",
    ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_external_factors(
            dataframe,
            metadata,
            columns=self.factor_columns,
            enriched_root=self.enriched_root,
        )

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=20)
        dataframe["stablecoin_mcap_growth_7d"] = dataframe["stablecoin_mcap_growth"].rolling(
            24 * 7
        ).sum()

        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_upper"] = bands["upperband"]
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        base_condition = dataframe["close"] > dataframe["ema200"]
        base_condition &= dataframe["adx"] > 19
        base_condition &= dataframe["close"] < dataframe["bb_lower"] * 0.997
        base_condition &= dataframe["rsi"] < 40

        if self._uses_factor_gate(metadata):
            condition = base_condition.copy()
            condition &= dataframe["funding_rate"].notna()
            condition &= dataframe["funding_rate"] < self.max_funding_rate
            condition &= dataframe["stablecoin_mcap_growth"].notna()
            stablecoin_growth_7d = dataframe.get(
                "stablecoin_mcap_growth_7d", dataframe["stablecoin_mcap_growth"]
            )
            condition &= stablecoin_growth_7d.notna()
            condition &= stablecoin_growth_7d > 0.0
        else:
            condition = base_condition

        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 58) & (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def _uses_factor_gate(self, metadata: dict) -> bool:
        return "BTC" in metadata.get("pair", "")
