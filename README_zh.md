[English](README.md) | [中文](README_zh.md)

# Auto-Quant / 自动量化

LLM 驱动的自主量化研究——将 Karpathy 的 autoresearch 模式应用于 FreqTrade 加密货币策略。

**当前推荐分支：`v0.4.0`**

## 研究成果 (v0.4.0)

经过 4 个大版本、96 轮实验，以下是核心发现。

### 策略表现

| 策略 | 指标 | 训练期 (2023-25) | 2026 Q1 样本外 |
|---|---|---|---|
| SmartHold (R90) | EMA50, EMA200, SMA200 | +427.1% | 0% ⭐ |
| CbbiLead (R96) | CBBI, EMA100, EMA200 | +251.4% | 0% ⭐ |
| EmaValuation (R94) | EMA100, EMA200, AHR999, CBBI | +173.7% | 0% ⭐ |
| Cycle01 (R86) | AHR999, CBBI | +93.4% | -16.5% |
| Bear01 (R87) | SMA200, 资金费率, 稳定币 | +58.8% | 0% ⭐ |
| BuyAndHold | (基准) | +429.6% | -16.0% |

> BTC 2023-2025: $16k → $100k | BTC 2026 Q1: $94k → $76k (-16%)

### 核心发现

1. **在牛市中，没有主动策略跑赢 BuyAndHold。** 2023-2025 是 6 倍涨幅，任何入场延迟都在损失收益。最好的策略通过几乎持续持仓捕获 >95% 的涨幅。

2. **熊市保护才是主动管理的价值所在。** 2026 Q1 阴跌 (-16%) 中，4/6 策略正确空仓，0 损失 vs 基准 -16%。SMA200 入场过滤和 EMA 死叉退出信号有效。

3. **CBBI 是最好的单一指标。** 纯 CBBI 择时（恐惧 <0.4 买入，贪婪 >0.7 卖出）实现 +251% 牛市收益 + 熊市零损失。它将多个链上指标聚合为一个信号。

4. **简单就是胜利。** 2-3 个指标优于 5+ 个——每个额外条件都是错过好交易的机会。

5. **SMA200 是最可靠的熊市过滤器。** 价格在 SMA200 下方一致识别了 2026 熊市。入场过滤比出场过滤更可靠。

## 工作原理

四个固定组件 + 一个代理工作区：

- `config.json` — FreqTrade 配置。交易对、时间框架、手续费。代理不修改。
- `prepare.py` — 数据下载。代理不修改。
- `run.py` — 批量回测工具。运行所有策略，输出指标。代理不修改。
- `program.md` — 代理指令。循环逻辑在这里。
- `user_data/strategies/` — 代理拥有的目录。在这里创建、进化、分叉、淘汰策略。

## 项目结构

```
Auto-Quant/
├── README.md                           # English version
├── README_zh.md                        # 本文件
├── STRATEGY_MAP.md                     # 策略演化与表现详情
├── pyproject.toml
├── config.json                         # FreqTrade 配置 (只读)
├── prepare.py                          # 数据下载 (只读)
├── run.py                              # 训练回测 (只读)
├── val.py                              # 样本外验证
├── program.md                          # 代理指令
├── user_data/
│   ├── strategies/
│   │   ├── _template.py.example
│   │   ├── MtfTrendSmartHold.py        # +427% 牛市, 0% 熊市
│   │   ├── MtfTrendCbbiLead.py         # CBBI 优先 +251%
│   │   ├── MtfTrendEmaValuation.py     # 4 指标组合
│   │   ├── MtfTrendCycle01.py          # AHR999+CBBI 周期
│   │   ├── MtfTrendBear01.py           # SMA200 熊市防护
│   │   ├── BuyAndHold.py               # 基准
│   │   └── .archive/                   # 38 个已归档实验
│   ├── data/                           # 训练数据 (2023-2025)
│   └── data_val/                       # 验证数据 (2026 Q1)
├── autoq_data/
│   ├── strategy_bridge.py              # 宏观因子 (资金费率, DVOL, 稳定币)
│   └── cycle_bridge.py                 # AHR999 + CBBI 指标
├── prepare_cbbi.py                     # 获取 CBBI 数据
├── prepare_ahr999.py                   # 预计算 AHR999
├── versions/                           # 历史版本快照
└── tests/                              # 13 个测试，全部通过
```

## 快速开始

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装 TA-Lib C 库
#    macOS: brew install ta-lib
#    Linux: 参见 https://github.com/mrjbq7/ta-lib#dependencies

# 3. 安装 Python 依赖
uv sync

# 4. 下载数据 (需要 Binance API)
uv run prepare.py

# 5. 预获取指标
uv run prepare_cbbi.py
uv run prepare_ahr999.py

# 6. 检查运行
uv run run.py > run.log 2>&1

# 7. 运行验证
uv run val.py
```

## 可用分支

| 分支 | 状态 | 内容 |
|---|---|---|
| `v0.4.0` | **推荐** | 6 策略 + 样本外验证 + CBBI/AHR999 指标 |
| `daily-trend` | 归档 | 日线策略 (DailyTrendEMA, R31-R81) |
| `autoresearch/apr22` | 归档 | 自动批量实验轮次 7-8 |
| `autoresearch/apr23` | 归档 | 自动批量实验轮次 (R125) |
| `master` | 归档 | v0.3.0 — 5 交易对 MTF 组合 |

## 版本历史

| 版本 | 轮次 | 峰值 Sharpe | 关键创新 |
|---|---|---|---|
| v0.1.0 | 99 | 1.44 (真实 0.19) | 单文件变异，发现 oracle 作弊 |
| v0.2.0 | 81 | 0.67 | 多策略 (3 槽位)，零 Goodhart |
| v0.3.0 | 39 | 1.07 | MTF + 5 交易对组合，逐对指标 |
| v0.4.0 | 96 | 0.16 (Sharpe) | 6 类替代数据 + CBBI/AHR999 + 2026 样本外验证 |

详见 `versions/` 目录。

## 许可证

MIT
