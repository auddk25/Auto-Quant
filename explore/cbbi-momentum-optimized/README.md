# CbbiMomentum 优化探索

> 日期: 2026-04-29
> 状态: 设计完成，待执行
> 分支: strategy-cbbi-ahr999 (继续)

---

## 目标

优化 CbbiMomentum 策略，尝试超越当前最优 (+732.7%)

---

## 当前最优策略

**CbbiMomentum (R99v4)**:
- 收益: +732.7%
- 回撤: -2.9%
- 交易: 14 笔
- 胜率: 64.3%
- 盈亏比: 10.2

**参数**:
- 入场: CBBI 3日动量 > 0 且 CBBI < 0.65 且 EMA100 > EMA200
- 出场: CBBI 4日动量 < -0.03 或 CBBI > 0.80 或 EMA100 < EMA200
- 时间框架: 1h

---

## 探索方向

1. **动量周期优化**: 测试不同入场/出场周期组合
2. **CBBI 阈值优化**: 测试不同入场阈值
3. **出场信号优化**: 测试不同出场阈值
4. **趋势过滤优化**: 测试不同趋势过滤方式
5. **多指标组合**: 添加其他指标

---

## 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `design.md` | ✅ 已创建 | 探索设计文档 |
| `screen_cbbi_momentum.py` | ⏳ 待创建 | 筛选脚本 |
| `screen_results.log` | ⏳ 待运行 | 筛选结果 |
| `val_results.log` | ⏳ 待运行 | 验证结果 |

---

## 运行命令

```bash
# 参数扫描
uv run screen_cbbi_momentum.py

# 组合优化
uv run screen_cbbi_momentum.py --optimize

# 滚动验证
uv run val_rolling.py
```
