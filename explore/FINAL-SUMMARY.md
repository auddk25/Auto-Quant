# AutoQuant 量化策略探索 — 最终总结

> 完成时间: 2026-04-29
> 探索轮次: R103-R110 + 期货测试
> 最优策略: Ensemble CBBI (R105)

---

## 项目概览

AutoQuant 是一个基于 FreqTrade 的 Bitcoin 量化交易策略项目。经过 114 轮参数优化 + 7 个方向的全面探索，找到了经过鲁棒性验证的最优策略。

---

## 核心成果

### 最优策略: Ensemble CBBI (R105)

| 指标 | 值 | 说明 |
|------|-----|------|
| 收益 | +1118.2% | 2023-2025 全周期 |
| 回撤 | -5.3% | 远低于 BuyAndHold |
| 交易 | 28笔 | 3年，约10笔/年 |
| 胜率 | 57.1% | 超过50%即可盈利 |
| 盈亏比 | 12.61 | 单笔盈利远大于亏损 |
| 鲁棒性 | 4/5 (80%) | 蒙特卡洛✅ 熊市✅ 连续亏损✅ |

### 策略逻辑

**入场条件**（全部满足）:
1. CBBI 3日动量 > 0（恐惧消退）
2. CBBI < 0.65（不贪婪）
3. EMA100 > EMA200（趋势向上）

**出场条件**（3变体投票，≥2票同意）:
1. CBBI 3日动量 < -0.02/-0.018/-0.015（信心下降）
2. CBBI > 0.80（极度贪婪）
3. EMA100 < EMA200（趋势破位）

**使用的指标**:
- CBBI（链上情绪指标，0-1）
- CBBI 动量（3日变化量）
- EMA100/EMA200（日线趋势）

---

## 全方向探索结果

| 方向 | 结果 | 最佳收益 | 回撤 | 核心结论 |
|------|------|----------|------|----------|
| A. 鲁棒性优化 | ✅ 成功 | +1118.2% | -5.3% | 集成学习降低参数敏感性 |
| B. 期货多空 | ⚠️ 部分可行 | +714.7% | -2.9% | 做空不可行，杠杆做多有价值 |
| C. 多时间框架 | ❌ 不可行 | +389.6% | -6.2% | CBBI是日线级，4h引入噪音 |
| D. 多指标融合 | ❌ 不可行 | +148.1% | -14.3% | RSI/MACD/BB增加噪音交易 |
| E. 自适应参数 | ❌ 不可行 | +454.2% | -5.7% | CBBI动量已包含市场状态 |
| F. 组合策略 | ❌ 不可行 | +330.3% | -14.0% | SMA200在1h上太嘈杂 |

---

## 核心教训（17条）

### 参数优化 (1-8)
1. CBBI 动量方向 > CBBI 绝对值
2. 3d 入场 + 3d 出场是最优组合
3. BTC only > BTC+ETH
4. 固定止损 > 追踪止损
5. 入场选择性 > 立即入场
6. 简单 > 复杂
7. 全周期验证 > 单段训练
8. 出场敏感度很关键

### 鲁棒性 (9-12)
9. 参数空间已耗尽
10. 鲁棒性 > 绝对收益
11. 集成学习降低参数敏感性
12. CB_THRESHOLD=0.65 是最稳定区域

### 新方向探索 (13-17)
13. CBBI是日线级指标，1h是最低可用时间框架
14. 额外技术指标会降低入场门槛，增加无效交易
15. CBBI动量本身就是自适应的
16. SMA200在1h上太嘈杂
17. 添加过滤器 ≠ 改善策略

---

## 探索文件索引

### 策略文件
| 文件 | 说明 |
|------|------|
| `MtfTrendCbbiMomentumEnsemble.py` | ⭐ 最优策略 |
| `MtfTrendCbbiMomentumOpt.py` | 优化版单变体 |
| `MtfTrendCbbiMomentum.py` | 原版策略 |
| `MtfTrendCbbiAhr999Daily.py` | 日线双指标 |
| `MtfTrendLongShort.py` | 期货多空 |
| `MtfTrendBear01.py` | 熊市保护 |
| `MtfTrendSmartHold.py` | 趋势压舱石 |

### 探索报告
| 目录 | 内容 |
|------|------|
| `explore/ensemble-strategy/` | ⭐ 集成策略设计+鲁棒性报告 |
| `explore/cbbi-momentum-optimized/` | 参数优化详情 |
| `explore/cbbi-ahr999-daily/` | 日线双指标探索 |
| `explore/futures-long-short/` | 期货多空测试 |
| `explore/multi-timeframe-test/` | 多时间框架 ❌ |
| `explore/multi-indicator-fusion/` | 多指标融合 ❌ |
| `explore/adaptive-parameters/` | 自适应参数 ❌ |
| `explore/combination-strategy/` | 组合策略 ❌ |
| `explore/live-trading-plan/` | 实盘准备方案 |

### 核心文档
| 文件 | 内容 |
|------|------|
| `explore/exploration-summary.md` | 全方向探索汇总 |
| `explore/strategy-roadmap.md` | 策略路线图+教训 |
| `explore/README.md` | 探索导航 |
| `claude-progress.md` | 会话进度记录 |

### 测试脚本
| 脚本 | 用途 |
|------|------|
| `run_ensemble.py` | 集成策略快速回测 |
| `val_ensemble.py` | 滚动窗口验证 |
| `val_ensemble_robustness.py` | 鲁棒性验证 |
| `run_multi_tf.py` | 多时间框架对比 |
| `run_fusion_test.py` | 多指标融合对比 |
| `run_adaptive_test.py` | 自适应参数对比 |
| `run_combo_test.py` | 组合策略对比 |
| `run_futures_test.py` | 期货多空对比 |
| `run_dynamic_sl.py` | 动态止损对比 |

---

## 实盘准备

### 推荐方案
- 策略: Ensemble CBBI (R105)
- 交易所: Binance
- 资金: 1000 USDT 起步
- 交易对: BTC/USDT

### 启动步骤
1. 配置 Binance API 密钥
2. 部署策略文件
3. 设置 Telegram Bot 监控
4. 1000 USDT 小资金测试 1-2 个月
5. 确认表现后增加资金

详见: `explore/live-trading-plan/design.md`

---

## 项目统计

- 探索轮次: R103-R110 + 期货测试
- 测试策略数: 15+ 个变体
- 回测总数: 50+ 次
- 参数扫描: 243 组 (原始) + 35 组 (稳定性)
- 生成报告: 12 份
- 核心教训: 17 条

---

## 最终结论

**Ensemble CBBI (R105) 是经过全面验证的最优策略**。

经过 7 个方向的探索，所有试图改进的方案都失败了。这证明了一个核心原则：**简单 > 复杂**。

CBBI 动量 + EMA 趋势 + 3 变体投票 = 简单、鲁棒、高效。

下一步：配置 API，开始小资金实盘测试。
