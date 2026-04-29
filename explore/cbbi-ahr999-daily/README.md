# CBBI + AHR999 日线策略探索

> 分支: strategy-cbbi-ahr999
> 状态: ✅ 完成 (R103)
> 设计文档: docs/superpowers/specs/2026-04-29-cbbi-ahr999-daily-design.md
> 实现计划: docs/superpowers/plans/2026-04-29-cbbi-ahr999-daily.md

---

## 目标

1. **收益 ≥ BuyAndHold (+88.5%)**，同时回撤远小于它
2. **绝对收益超越 CbbiMomentum (+732.7%)**

## 策略设计

- **时间框架**: 日线 (`timeframe = "1d"`)
- **标的**: BTC/USDT only
- **指标**: CBBI (链上情绪 0~1) + AHR999 (定投指标, <1=便宜)
- **止损**: -25%

## 入场逻辑（3 种）

| 模式 | 逻辑 | 参数 |
|------|------|------|
| A. 阈值抄底 | CBBI < X AND AHR999 < Y | X∈{0.30,0.35,0.40}, Y∈{0.40,0.60,0.80} |
| B. 动量回升 | CBBI_N动量>0 AND AHR999_N动量>0 | N∈{3,5,7} |
| C. 混合 | CBBI<X AND AHR999<Y AND CBBI_N动量>0 | A+B组合 |

## 出场逻辑（3 种）

| 模式 | 逻辑 | 参数 |
|------|------|------|
| X. 高估出场 | CBBI>X OR AHR999>Y | X∈{0.75,0.80}, Y∈{1.0,1.2} |
| Y. 动量反转 | CBBI_N动量 < -阈值 | N∈{3,5}, 阈值∈{0.03,0.05} |
| Z. 趋势线 | close<SMA200 OR EMA50<EMA200 | 无参数 |

## 筛选流程

### 第 1 层: 粗筛（训练集 2022-2025）

组合矩阵: 8 入场 × 5 出场 = **40 组回测**

筛选标准:
- 总收益 > +88% (超过 BAH)
- 交易次数 >= 5
- 最大回撤 < -30%

输出: Top 3 策略类型 + 参数组合

### 第 2 层: 精筛（滚动窗口验证）

Top3 各展开 5-8 组参数变体 → val_rolling.py 7 段验证

筛选标准:
- 7 段均值 > +25%
- 任何单段回撤 < -25%

### 第 3 层: 最终验证

- run.py 训练集回测
- val_rolling.py 7 段滚动验证
- val.py 2026 Q1 OOS 验证

---

## 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `user_data/strategies/CbbiAhr999Daily.py` | ✅ 已创建 | 参数化策略类 |
| `screen_cbbi_ahr.py` | ✅ 已创建 | 筛选脚本 (支持粗筛/精筛) |
| `screen_coarse.log` | ✅ 完成 | 粗筛结果 (40组) |
| `screen_fine.log` | ✅ 完成 | 精筛结果 (120组) |
| `val_cbbi_ahr.py` | ✅ 已创建 | 滚动窗口验证脚本 |
| `val_cbbi_ahr.log` | ✅ 完成 | 滚动验证结果 |

---

## 已知约束

- CBBI API (colintalkscrypto.com) 返回 HTTP 406，缓存数据可用到 2026-04-24
- 日线数据点少（~1000 天），过拟合风险
- AHR999 仅对 BTC 有意义
- **FreqTrade 需要网络访问 Binance API 来验证交易所（即使在回测模式下）**

---

## 运行命令

```bash
# 粗筛（需网络）
uv run screen_cbbi_ahr.py 2>&1 | tee screen_coarse.log

# 精筛
uv run screen_cbbi_ahr.py --fine 2>&1 | tee screen_fine.log

# 滚动验证
uv run val_rolling.py 2>&1 | tee val_rolling_cbbiahr.log

# OOS 验证
uv run val.py 2>&1 | tee val_oos_cbbiahr.log

# 全策略对比
uv run run.py 2>&1 | tee run_compare.log
```
