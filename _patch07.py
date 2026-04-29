import pathlib

p = pathlib.Path("user_data/strategies/MtfTrend07.py")
txt = p.read_text()

# 1. Replace ema12_prev/ema26_prev with rsi_prev in 4h indicators
old_4h = '''        dataframe"ema12_prev" = dataframe"ema12".shift(1)
        dataframe"ema26_prev" = dataframe"ema26".shift(1)'''
new_4h = '''        dataframe"rsi_prev" = dataframe"rsi".shift(1)'''
txt = txt.replace(old_4h, new_4h)

# 2. Replace entry logic: remove ETH branch, change BTC to pullback recovery
old_entry = '''    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_btc = metadata"pair" == "BTC/USDT"

        trend_cond = (
            (dataframe"close_1d" > dataframe"ema50_1d")
            & (dataframe"ema50_1d" > dataframe"ema150_1d")
        )
        momentum_cond = (
            (dataframe"ema12_4h" > dataframe"ema26_4h")
        )
        macro_cond = (
            (dataframe"funding_rate" > 0)
            & (dataframe"stablecoin_mcap_growth" > 0)
            & (dataframe"btc_dvol" < 65)
            & (dataframe"oi_rising" == 1)
        )
        volume_cond = dataframe"volume" > 0

        if is_btc:
            rsi_cond = (dataframe"rsi_4h" > 40) & (dataframe"rsi_4h" < 70)
            crossover = dataframe"ema12_prev_4h" <= dataframe"ema26_prev_4h"
            cvd_cond = dataframe"cvd_24h" > 0
            entry = trend_cond & momentum_cond & crossover & macro_cond & rsi_cond & cvd_cond & volume_cond
            dataframe.locentry, "enter_long" = 1
        else:
            rsi_cond = (dataframe"rsi_4h" > 30) & (dataframe"rsi_4h" < 60)
            btc_gate = dataframe"btc_usdt_close_above_ema_1d" == 1
            entry = trend_cond & momentum_cond & macro_cond & rsi_cond & btc_gate & volume_cond
            dataframe.locentry, "enter_long" = 1

        return dataframe'''

new_entry = '''    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_cond = (
            (dataframe"close_1d" > dataframe"ema50_1d")
            & (dataframe"ema50_1d" > dataframe"ema150_1d")
        )
        momentum_cond = (
            (dataframe"ema12_4h" > dataframe"ema26_4h")
        )
        macro_cond = (
            (dataframe"funding_rate" > 0)
            & (dataframe"stablecoin_mcap_growth" > 0)
            & (dataframe"btc_dvol" < 65)
            & (dataframe"oi_rising" == 1)
        )
        volume_cond = dataframe"volume" > 0
        pullback_recovery = (
            (dataframe"rsi_prev_4h" < 50)
            & (dataframe"rsi_4h" >= 50)
        )
        cvd_cond = dataframe"cvd_24h" > 0
        entry = trend_cond & momentum_cond & pullback_recovery & macro_cond & cvd_cond & volume_cond
        dataframe.locentry, "enter_long" = 1

        return dataframe'''
txt = txt.replace(old_entry, new_entry)

# 3. Remove ETH special stoploss
old_sl = '''        if pair == "ETH/USDT":
            return -0.06
'''
txt = txt.replace(old_sl, '')

# 4. Add timedelta import
txt = txt.replace('from datetime import datetime', 'from datetime import datetime, timedelta')

# 5. Add confirm_trade_entry before custom_exit
confirm_method = '''    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        trades = Trade.get_trades_proxy(pair=pair, is_open=False)
        trades += Trade.get_trades_proxy(pair=pair, is_open=True)
        if trades:
            last_entry = max(t.open_date_utc for t in trades)
            if (current_time
