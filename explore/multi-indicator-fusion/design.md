# Multi-Indicator Fusion Strategy Test

> Created: 2026-04-29
> Status: ❌ Completed — all fusion variants underperform Ensemble
> Direction: D (多指标融合)

---

## 目标

测试将CBBI动量策略与RSI、MACD、布林带等技术指标融合是否能提升表现。

## 测试策略

### 1. CBBI + RSI Fusion

**设计思路**:
- 入场: CBBI动量 + RSI < 70 (避免超买入场)
- 出场: CBBI出场 + RSI > 75 (超买出场)
- RSI_PERIOD = 14

**结果**:
- 收益: +148.1%
- 回撤: -14.3%
- 交易: 94笔 (原28笔)
- 胜率: 71.3%
- 盈亏比: 1.86

**问题**: 交易次数增加3.4倍，收益下降87%。

---

### 2. CBBI + MACD Fusion

**设计思路**:
- 入场: CBBI动量 + MACD > Signal (动量确认)
- 出场: CBBI出场 + MACD < Signal (动量反转)
- MACD(12, 26, 9)

**结果**:
- 收益: +12.1%
- 回撤: -24.4%
- 交易: 253笔
- 胜率: 31.6%
- 盈亏比: 1.08

**问题**: MACD产生大量噪音信号，253笔交易几乎无效。

---

### 3. CBBI + Bollinger Bands Fusion

**设计思路**:
- 入场: CBBI动量 + Close < BB中轨 (逢低入场)
- 出场: CBBI出场 + Close > BB上轨 (超买出场)
- BB(20, 2)

**结果**:
- 收益: +43.7%
- 回撤: -13.9%
- 交易: 163笔
- 胜率: 67.5%
- 盈亏比: 1.35

**问题**: 交易次数增加5.8倍，收益下降96%。

---

## 对比总结

| 策略 | 收益 | 回撤 | 交易 | 胜率 | 盈亏比 | 评价 |
|------|------|------|------|------|--------|------|
| **Ensemble CBBI** ⭐ | +1118.2% | -5.3% | 28 | 57.1% | 12.61 | 最优 |
| CBBI + RSI | +148.1% | -14.3% | 94 | 71.3% | 1.86 | ❌ 噪音太多 |
| CBBI + MACD | +12.1% | -24.4% | 253 | 31.6% | 1.08 | ❌ 完全失败 |
| CBBI + Bollinger | +43.7% | -13.9% | 163 | 67.5% | 1.35 | ❌ 噪音太多 |

---

## 结论

**多指标融合方案不可行**，原因:

1. **RSI**: 虽然胜率提高到71.3%，但交易太频繁(94笔)，单笔利润太小
2. **MACD**: 产生大量噪音信号，253笔交易中68%亏损，回撤-24.4%
3. **布林带**: 类似RSI问题，163笔交易，单笔利润仅0.25%

**核心教训**:
- CBBI动量策略的优势在于**选择性入场**——只在高信心时交易
- 添加技术指标会降低入场门槛，增加噪音交易
- **简单 > 复杂**: 3个入场条件 + 3个出场条件 = 最优
- **入场选择性 > 更多信号**: CbbiMomentum > SmartHold 的核心原因在此再次验证

**教训编号**: #6 (简单 > 复杂) + #5 (入场选择性 > 立即入场)

---

## 文件

- `user_data/strategies/MtfTrendCbbiRsiFusion.py` — CBBI+RSI
- `user_data/strategies/MtfTrendCbbiMacdFusion.py` — CBBI+MACD
- `user_data/strategies/MtfTrendCbbiBbFusion.py` — CBBI+BB
- `run_fusion_test.py` — 对比脚本
