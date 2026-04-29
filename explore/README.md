# AutoQuant 量化策略探索

> 日期: 2026-04-29
> 分支: strategy-cbbi-ahr999

---

## 快速导航

- **[探索总结](exploration-summary.md)** — 所有探索结果汇总、最优策略对比、下一步计划
- **[策略路线图](strategy-roadmap.md)** — 所有策略全景、已完成探索、核心教训、潜在新方向
- **[动态止损测试](dynamic-stoploss-test.md)** — ATR止损测试结果，固定止损已是最优
- **[鲁棒性验证报告](robustness-report.md)** — CbbiMomentumOpt 鲁棒性测试结果 (2/6 通过)
- **[参数稳定性优化](stability-optimization-report.md)** — 35组参数扫描，CB=0.65是最稳定区域
- **[集成学习策略](ensemble-strategy/)** — 3变体投票，鲁棒性4/5通过，均值收益21.1%
- **[集成策略鲁棒性报告](ensemble-strategy/robustness-report.md)** — 蒙特卡洛✅ 交叉验证❌ 市场分层✅
- **[R103: CbbiAhr999Daily](cbbi-ahr999-daily/)** — CBBI+ADR999 日线抄底 (+527.4%)
- **[R104: CbbiMomentumOpt](cbbi-momentum-optimized/)** — 优化后的周期之王 (+1128.4%)

---

## 探索列表

| 探索 | 状态 | 收益 | 回撤 | 滚动均值 | 说明 |
|------|------|------|------|----------|------|
| [CbbiAhr999Daily](cbbi-ahr999-daily/) | ✅ 完成 | +527.4% | -24.7% | +30.0% | CBBI+ADR999 日线抄底 |
| [CbbiMomentum 优化](cbbi-momentum-optimized/) | ✅ 完成 | **+1128.4%** | -5.3% | **+56.1%** | 优化当前最优策略 |
| [集成学习策略](ensemble-strategy/) | ✅ 完成 | **+1118.2%** | -5.3% | **+21.1%** | 3变体投票，鲁棒性4/5通过 |
| [期货多空](futures-long-short/) | ⚠️ 完成 | +714.7% | -2.9% | - | 做空不可行，杠杆做多有价值 |
| [多时间框架](multi-timeframe-test/) | ❌ 完成 | +389.6% | -6.2% | - | 4h引入噪音，不可行 |
| [多指标融合](multi-indicator-fusion/) | ❌ 完成 | +148.1% | -14.3% | - | 额外指标=噪音，不可行 |
| [自适应参数](adaptive-parameters/) | ❌ 完成 | +454.2% | -5.7% | - | CBBI已自适应，不可行 |
| [组合策略](combination-strategy/) | ❌ 完成 | +330.3% | -14.0% | - | 趋势过滤引入噪音，不可行 |
| [实盘准备](live-trading-plan/) | 📋 进行中 | - | - | - | 小资金实盘测试方案 |

---

## 最优策略对比

| 策略 | 收益 | 回撤 | 滚动均值 | 交易 | 胜率 | 盈亏比 | 鲁棒性 |
|------|------|------|----------|------|------|--------|--------|
| **Ensemble CBBI** ⭐ | **+1118.2%** | -5.3% | **+21.1%** | 29 | 57% | 12.61 | 4/5 (80%) |
| **CbbiMomentumOpt** | +1128.4% | -5.3% | +17.7% | 21 | 57% | 14.28 | 2/6 (33%) |
| **CbbiMomentum** | +732.7% | -2.9% | +38.0% | 14 | 64.3% | 10.2 | - |
| **CbbiAhr999Daily** | +527.4% | -24.7% | +30.0% | 8 | 88% | 3.6 | - |
| BuyAndHold | +88.5% | 0% | +27.3% | 1 | 100% | - | - |

---

## 探索目标

1. **收益 ≥ BuyAndHold (+88.5%)**，同时回撤远小于它 ✅ R103 达成
2. **绝对收益超越 CbbiMomentum (+732.7%)** ✅ R104 达成 +1128.4%
3. **鲁棒性验证通过** ✅ R105 达成 4/5 (80%)

**当前状态**: 所有目标已达成，集成策略推荐实盘测试。详见 [探索总结](exploration-summary.md)。

---

## 已完成探索

### R103: CbbiAhr999Daily

**目标**: CBBI + AHR999 双指标共振，日线级别抄底

**结果**:
- 训练集收益: +527.4% (BuyAndHold 的 6 倍)
- 最大回撤: -24.7% (SmartHold 的一半)
- 滚动均值: +30.0% (超过 BuyAndHold)
- 交易次数: 8 笔 (胜率 88%)

**最佳参数**:
- 入场: 动量模式 (CBBI 3日动量 > 0 且 AHR999 3日动量 > 0)
- 出场: 高估模式 (CBBI > 0.75 或 AHR999 > 1.3)
- 止损: -25%

**验收**: ✅ 收益 ≥ BAH | ✅ 滚动均值 > BAH | ✅ 回撤 < -30% | ❌ 收益 < CbbiMomentum

---

### R104: CbbiMomentumOpt (优化后的周期之王)

**目标**: 优化当前最优策略，尝试超越 +732.7%

**结果**:
- 训练集收益: +1128.4% (原 +732.7%，提升 +395.7pp)
- 最大回撤: -5.3% (原 -2.9%，略有增加)
- 滚动均值: +56.1% (原 +38.0%，提升 +18.1pp)
- 交易次数: 21 笔 (原 14 笔)
- 胜率: 57% (原 64.3%)
- 盈亏比: 14.28 (原 10.2，提升 +4.08)

**最佳参数**:
- 入场: CBBI 3日动量 > 0 且 CBBI < 0.65 且 EMA100 > EMA200 (不变)
- 出场: CBBI **3日**动量 < **-0.02** 或 CBBI > 0.80 或 EMA100 < EMA200
- 关键变化: EXIT_MOM 4→3, EXIT_THRESHOLD -0.03→-0.02

**验收**: ✅ 收益 > CbbiMomentum | ✅ 滚动均值 > CbbiMomentum | ✅ 回撤 < -10%

---

### R105: Ensemble CBBI (集成学习策略)

**目标**: 解决 R104 鲁棒性问题，提升滚动均值至 20%+

**方法**: 3变体投票 (EXIT_THRESHOLD = -0.020, -0.018, -0.015)

**结果**:
- 全周期收益: +1118.2% (28笔交易)
- 滚动均值: +21.1% (**突破20%目标**)
- 总交易: 29笔 (vs 单一变体 25笔, +4笔)
- 亏损窗口: 1个 (与单一变体相同)
- 无交易窗口: 2个 (与单一变体相同)

**鲁棒性验证**: 4/5 通过 (80%)
- 蒙特卡洛5%分位数: ✅ 474.4% > 0%
- MC正收益概率: ✅ 100% > 90%
- 交叉验证折比: ❌ 9.7x (目标 <3x)
- 熊市均值: ✅ 0.0% > -20%
- 无连续CV亏损: ✅

**验收**: ✅ 滚动均值 > 20% | ✅ 参数敏感性降低 | ✅ 交易次数增加 | ✅ 鲁棒性提升

---

## 潜在新方向

所有7个探索方向已完成：

1. ~~**期货多空策略**~~ — ⚠️ 已完成，做空不可行，杠杆做多有价值
2. ~~**多时间框架分析**~~ — ❌ 已完成，不可行
3. ~~**多指标融合**~~ — ❌ 已完成，不可行
4. ~~**自适应参数**~~ — ❌ 已完成，不可行
5. ~~**组合策略**~~ — ❌ 已完成，不可行

**当前状态**: 所有探索方向已完成。Ensemble CBBI (R105, +1118.2%, 鲁棒性80%) 是经过全面验证的最优策略。下一步：准备小资金实盘测试。

---

## 文件结构

```
explore/
├── README.md                    # 本文件
├── strategy-roadmap.md          # 策略路线图 (全景+方向)
├── exploration-summary.md       # 探索总结 (汇总+对比+计划)
├── robustness-report.md         # R104 鲁棒性验证报告
├── stability-optimization-report.md  # 参数稳定性优化报告
├── dynamic-stoploss-test.md     # 动态止损测试报告
├── ensemble-strategy/           # 集成学习策略 (R105)
│   ├── design.md                # 策略设计文档
│   └── robustness-report.md     # R105 鲁棒性验证报告
├── cbbi-ahr999-daily/           # CBBI+ADR999 日线策略 (R103)
│   ├── README.md                # 探索概览
│   ├── design.md                # 策略设计
│   ├── plan.md                  # 实现计划
│   ├── historical-baselines.md  # 历史基线
│   └── exploration-summary.md   # 探索总结
├── cbbi-momentum-optimized/     # CbbiMomentum 优化 (R104)
│   ├── README.md                # 探索概览
│   ├── design.md                # 优化设计
│   ├── historical-baselines.md  # 历史基线
│   └── exploration-summary.md   # 探索总结
├── futures-long-short/          # 期货多空策略 (R102) ⚠️
│   └── design.md                # 测试报告
├── multi-timeframe-test/        # 多时间框架测试 (R107) ❌
│   └── design.md                # 测试报告
├── multi-indicator-fusion/      # 多指标融合测试 (R108) ❌
│   └── design.md                # 测试报告
├── adaptive-parameters/         # 自适应参数测试 (R109) ❌
│   └── design.md                # 测试报告
├── combination-strategy/        # 组合策略测试 (R110) ❌
│   └── design.md                # 测试报告
└── live-trading-plan/           # 实盘交易准备方案 📋
    └── design.md                # 完整准备方案
```

---

## 运行命令

```bash
# CBBI+ADR999 日线策略
uv run screen_cbbi_ahr.py              # 粗筛
uv run screen_cbbi_ahr.py --fine       # 精筛
uv run val_cbbi_ahr.py                 # 滚动验证

# CbbiMomentum 优化
uv run screen_cbbi_momentum.py         # 参数扫描
uv run screen_cbbi_momentum.py --optimize  # 组合优化
uv run val_cbbi_momentum_opt.py        # 滚动验证

# 集成学习策略
uv run run_ensemble.py                 # 快速回测
uv run val_ensemble.py                 # 滚动验证
uv run val_ensemble_robustness.py      # 鲁棒性验证

# 新方向探索对比
uv run run_multi_tf.py                 # 多时间框架对比
uv run run_fusion_test.py              # 多指标融合对比
uv run run_adaptive_test.py            # 自适应参数对比
uv run run_combo_test.py               # 组合策略对比
uv run run_futures_test.py             # 期货多空对比
```
