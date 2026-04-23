"""
FactorMeanRevCandidate — v0.3.0 sidecar-factor mean-reversion strategy

Paradigm: mean-reversion with external factor gates
Hypothesis: BTC benefits from the v0.3.0 external-factor gate, while ETH is
            more robust with the StochMeanRev entry rule. Pair-adaptive logic
            should keep the main-window edge while reducing bear-market damage.
Parent: StochMeanRev, MeanRevADX, v0.3.0 factor sidecar pipeline
Created: 2026-04-23
Status: active

Validation: BTC factor + positive 7d stablecoin impulse and ETH stable Stoch
reached Sharpe 0.9628, 74 trades, PF 4.92 on 20230101-20251231 and 2022
stress Sharpe 0.5867.
"""

from pathlib import Path

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy

from autoq_data.strategy_bridge import merge_external_factors


class FactorMeanRevCandidate(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.010}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200
    enriched_root: Path | None = None
    max_funding_rate = 0.001
    min_stablecoin_mcap_growth = 0.0
    stoch_rsi_period = 25
    stable_stoch_rsi_period = 20
    stable_stoch_entry_threshold = 0.22

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

        rsi = ta.RSI(dataframe, timeperiod=20)
        stoch_factor = ta.STOCH(
            dataframe.assign(high=rsi, low=rsi, close=rsi),
            fastk_period=self.stoch_rsi_period,
            slowk_period=3,
            slowd_period=3,
        )
        stoch_stable = ta.STOCH(
            dataframe.assign(high=rsi, low=rsi, close=rsi),
            fastk_period=self.stable_stoch_rsi_period,
            slowk_period=3,
            slowd_period=3,
        )
        dataframe["stoch_factor_k"] = stoch_factor["slowk"] / 100.0
        dataframe["stoch_stable_k"] = stoch_stable["slowk"] / 100.0
        dataframe["stoch_k"] = dataframe["stoch_factor_k"]
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

        if self._uses_factor_gate(metadata):
            stoch_factor = dataframe.get("stoch_factor_k", dataframe["stoch_k"])
            condition = base_condition & (stoch_factor < 0.20)

            # Require positive stablecoin liquidity impulse and avoid extreme funding.
            condition &= dataframe["funding_rate"].notna()
            condition &= dataframe["funding_rate"] < self.max_funding_rate
            condition &= dataframe["stablecoin_mcap_growth"].notna()
            condition &= dataframe["stablecoin_mcap_growth"] > self.min_stablecoin_mcap_growth
            stablecoin_growth_7d = dataframe.get(
                "stablecoin_mcap_growth_7d", dataframe["stablecoin_mcap_growth"]
            )
            condition &= stablecoin_growth_7d.notna()
            condition &= stablecoin_growth_7d > 0.0
        else:
            stoch_stable = dataframe.get("stoch_stable_k", dataframe["stoch_k"])
            condition = base_condition & (
                stoch_stable < self.stable_stoch_entry_threshold
            )

        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        stoch_column = "stoch_factor_k" if self._uses_factor_gate(metadata) else "stoch_stable_k"
        if stoch_column not in dataframe.columns:
            stoch_column = "stoch_k"
        exit_cond = (dataframe[stoch_column] > 0.70) & (
            dataframe["close"] > dataframe["bb_upper"]
        )
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def _uses_factor_gate(self, metadata: dict) -> bool:
        return "BTC" in metadata.get("pair", "")
