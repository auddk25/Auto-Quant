# Multi-Timeframe CBBI Strategy Test

> Created: 2026-04-29
> Status: ❌ Completed — underperforms Ensemble
> Direction: C (多时间框架分析)

---

## 目标

测试不同时间框架组合是否能提升CBBI策略表现。

## 测试策略

### 1. MtfTrendCbbiMultiTF (1h入场 + 4h趋势确认)

**设计思路**:
- 1h: CBBI动量入场信号 (更灵敏)
- 4h: EMA趋势确认 (更稳定)
- 使用 `@informative("4h")` 装饰器

**参数**:
- ENTRY_MOM = 3 (1h CBBI 3日动量)
- CB_THRESHOLD = 0.65
- EXIT_MOM = 3
- EXIT_THRESHOLD = -0.02
- EXIT_CBBI = 0.80
- TREND_FAST = 100, TREND_SLOW = 200 (4h EMA)

**结果**:
- 收益: +383.2%
- 回撤: -5.3%
- 交易: 11笔
- 胜率: 54.5%
- 盈亏比: 9.95

**问题**: 交易次数过少 (11笔)，入场条件过于严格。

---

### 2. MtfTrendCbbiMultiTF2 (4h基准时间框架)

**设计思路**:
- 4h: 基准时间框架
- CBBI动量: `shift(6 * n)` (每天6根4h K线)
- 同样逻辑但在4h上执行

**参数**:
- ENTRY_MOM = 3 (4h CBBI 18根K线动量)
- CB_THRESHOLD = 0.65
- EXIT_MOM = 3
- EXIT_THRESHOLD = -0.02
- EXIT_CBBI = 0.80
- TREND_FAST = 100, TREND_SLOW = 200 (4h EMA)

**结果**:
- 收益: +389.6%
- 回撤: -6.2%
- 交易: 32笔
- 胜率: 43.8%
- 盈亏比: 4.01

**问题**: 胜率和盈亏比大幅下降，4h时间框架噪音更大。

---

## 对比总结

| 策略 | 收益 | 回撤 | 交易 | 胜率 | 盈亏比 | 评价 |
|------|------|------|------|------|--------|------|
| **Ensemble CBBI** ⭐ | +1118.2% | -5.3% | 28 | 57.1% | 12.61 | 最优 |
| Multi-TF (1h+4h) | +383.2% | -5.3% | 11 | 54.5% | 9.95 | ❌ 交易太少 |
| Multi-TF2 (4h base) | +389.6% | -6.2% | 32 | 43.8% | 4.01 | ❌ 盈亏比太低 |

---

## 结论

**多时间框架方案不可行**，原因:

1. **1h+4h组合**: 入场条件过严，3年只有11笔交易，统计不显著
2. **4h基准**: CBBI是日线指标，4h重采样后动量信号噪音增大，胜率从57%降到44%
3. **核心问题**: CBBI本身是日线级指标，在更细时间框架上计算动量会引入噪音

**教训**: CBBI适合在日线或1h级别使用，4h不是好的选择。1h+4h的多时间框架组合虽然理论合理，但实际上限制了交易机会。

---

## 文件

- `user_data/strategies/MtfTrendCbbiMultiTF.py` — 1h入场+4h趋势
- `user_data/strategies/MtfTrendCbbiMultiTF2.py` — 4h基准
- `run_multi_tf.py` — 对比脚本
