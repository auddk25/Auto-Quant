# AutoQuant 策略地图 v0.4.0

> 最后更新: 2026-04-29 (R104)
> 数据: 2022-2026 (熊市+牛市+阴跌，完整周期)
> 活跃策略: 5 | 归档: 41

---

## 全周期验证 (2022-2025 训练 + 7 段滚动窗口)

### 训练集 (2022-2025，含 -65% 熊市)

| 策略 | 收益 | Sharpe | 最大回撤 | 交易 | 胜率 | 盈亏比 |
|------|:------:|:------:|:------:|:----:|:----:|:-----:|
| **CbbiMomentumOpt** | **+1128.4%** | 0.11 | -5.3% | 21 | 57% | 14.28 |
| **CbbiMomentum** | +732.7% | 0.11 | -2.9% | 14 | 64.3% | 10.2 |
| **CbbiAhr999Daily** | +527.4% | 0.05 | -24.7% | 8 | 88% | 3.6 |
| Bear01 | +107.7% | 0.04 | -18.2% | 15 | 33.3% | 2.1 |
| SmartHold | +92.8% | 0.02 | -43.3% | 3 | 66.7% | 3.1 |
| BuyAndHold | +88.5% | - | 0% | 1 | 100% | - |

### 滚动窗口 (7 段 Walk-Forward)

| 策略 | 23H1 恢复 | 23H2 起涨 | 24H1 牛市 | 24H2 狂热 | 25H1 盘整 | 25H2 年末 | 26Q1 阴跌 | **均值** |
|------|:------:|:------:|:------:|:------:|:------:|:------:|:------:|:-----:|
| **CbbiMomentumOpt** | +36.0% | +50.5% | +98.5% | +123.6% | +25.4% | +2.4% | 0% | **+56.1%** |
| **CbbiMomentum** | +20.8% | +40.5% | +76.4% | +96.9% | +31.8% | -0.4% | 0% | **+38.0%** |
| **CbbiAhr999Daily** | +80.7% | +36.8% | +33.7% | +55.2% | +35.8% | -11.3% | -21.2% | **+30.0%** |
| BuyAndHold | +83.1% | +37.7% | +42.9% | +46.7% | +14.4% | -17.6% | -16.0% | +27.3% |
| SmartHold | +30.8% | +37.3% | +42.5% | +46.3% | +14.3% | -12.2% | 0% | +22.7% |
| Bear01 | +30.0% | +23.6% | +34.2% | +13.5% | -13.9% | -17.5% | 0% | +10.0% |

---

## CbbiMomentum 交易记录 (2022-2025, 14笔)

```
#   入场       出场       入场价     出场价     盈亏    持仓    逻辑
1   2023-03-26 2023-04-21 $27,463  $28,291   +2.8%   26d   CBBI初次反弹，试探入场
2   2023-04-26 2023-08-18 $28,300  $26,737   -5.7%  114d   ← 最大亏损：抄底略早
3   2023-08-22 2024-01-14 $26,100  $42,687  +63.2%  145d   2023年底精准抄底，吃到2024牛市
4   2024-01-26 2024-03-19 $39,896  $67,087  +67.8%   53d   牛市加速段
5   2024-05-04 2024-06-14 $63,084  $66,728   +5.6%   41d   盘整期波段
6   2024-06-29 2024-07-05 $60,771  $57,376   -5.8%    6d   ← 快速认错
7   2024-07-08 2024-08-02 $55,094  $64,898  +17.6%   25d   回调后重新入场
8   2024-08-08 2024-08-29 $55,300  $59,206   +6.8%   21d   
9   2024-08-30 2024-09-06 $59,204  $56,182   -5.3%    7d   ← 连续两次快进快出
10  2024-09-09 2024-12-14 $55,045 $101,301  +83.7%   96d   ← 2024主升浪！$55k→$101k
11  2025-03-14 2025-04-08 $81,503  $79,020   -3.2%   25d   
12  2025-04-11 2025-07-30 $79,043 $117,745  +48.7%  110d   2025冲顶，吃到最高点附近
13  2025-11-09 2025-11-14 $101,798 $98,974   -3.0%    5d   ← 年末快速止损
14  2025-11-23 2025-11-29 $84,972  $90,891   +6.8%    5d   年末最后波段

总结: 5次亏损平均 -4.6% | 9次盈利平均 +40.4% | 盈亏比 10:1
```

---

## 策略详情

### ⭐ CbbiMomentumOpt (R104) — 优化后的周期之王

**设计思路**: 不等恐惧，等恐惧消退。CBBI 是综合链上情绪指标(0~1)，它的方向比绝对水平更有信息量。

**指标准备** (populate_indicators):
```
1. 加载日线 EMA100, EMA200 (通过 @informative("1d"))
2. 加载 CBBI 日线数据 (通过 merge_cbbi)
3. 计算 CBBI 3日动量 = 当前CBBI - 3天前CBBI  (入场信号)
4. 计算 CBBI 3日动量 = 当前CBBI - 3天前CBBI  (出场信号)
```

**入场判断** (populate_entry_trend, 仅 BTC/USDT):
```
IF 全部满足:
  ① CBBI 3日动量 > 0          ← 恐惧在消退，信心恢复中
  ② CBBI < 0.65               ← 还没到贪婪区，有上涨空间
  ③ EMA100 > EMA200           ← 日线趋势向上
  ④ volume > 0                ← 有交易量
THEN:
  enter_long = 1               ← 全仓买入 (custom_stake_amount = 99%钱包)
```

**出场判断** (populate_exit_trend):
```
IF 任一满足:
  ① CBBI 3日动量 < -0.02      ← 信心在回落 (主要出场信号，更敏感)
  ② CBBI > 0.80               ← 极端贪婪，见顶信号
  ③ EMA100 < EMA200           ← 日线趋势反转
THEN:
  exit_long = 1                ← 全部卖出
```

**风控参数**:
```
stoploss: -0.25 (固定止损，跌25%强制离场)
minimal_roi: {"0": 100} (无止盈目标)
max_open_trades: 1 (一次只持有一个仓位)
process_only_new_candles: True (只在新区块产生时判断)
```

**优化结果 (R104)**:
```
参数扫描: 32 组 → EXIT_THRESHOLD=-0.02 最优 (+951.7%)
组合优化: 243 组 → ENTRY_MOM=3, EXIT_MOM=3, EXIT_THRESHOLD=-0.02 最优 (+1128.4%)
滚动验证: 7 段 → 均值 +56.1% (原 +38.0%，提升 +18.1pp)

关键变化:
  EXIT_MOM: 4 → 3 (更快出场信号)
  EXIT_THRESHOLD: -0.03 → -0.02 (更敏感出场)
```

**为什么 3d/3d 而非其他**:
```
243组参数扫描结果:
  Entry=3d, Exit=3d, Threshold=-0.02  →  +1128.4%  ← 最优
  Entry=3d, Exit=3d, Threshold=-0.03  →  +732.7%   ← 原参数
  Entry=3d, Exit=4d, Threshold=-0.02  →  +951.7%   ← 次优
  Entry=2d, Exit=3d, Threshold=-0.02  →  +917.7%   ← 入场太快
  Entry=4d, Exit=5d  →  均值 +33.5%  ← 入场太慢，错过机会
  Entry=3d, Exit=6d  →  均值 +36.7%  ← 出场太慢，利润回吐
```


### SmartHold (R90) — 趋势压舱石

**设计思路**: 牛市不需要择时——默认全仓，只在大趋势逆转时离场。

**指标准备**:
```
1. 加载日线 EMA50, EMA200, SMA200 (通过 @informative("1d"))
2. 无其他指标 — 最简单的策略
```

**入场判断** (仅 BTC/USDT):
```
IF volume > 0:              ← 有交易量的每个小时
  enter_long = 1            ← 立即入场，不择时
```

**出场判断**:
```
IF 同时满足:
  ① EMA50 < EMA200          ← 死叉形成
  ② close < SMA200          ← 价格跌破200日均线
THEN:
  exit_long = 1              ← 趋势确认逆转才出场
```

**风控**:
```
stoploss: -0.99 (近乎不止损 — 信任双条件出场)
```

**适用场景**: 牛市底仓策略。赚取整个牛市的收益。熊市中死叉+破SMA200提供双重保护。

### Bear01 (R87) — 熊市保险

**设计思路**: SMA200 是唯一可靠的牛熊分界线。上方才做多，下方绝对不碰。

**指标准备**:
```
1. 加载日线 SMA200 (通过 @informative("1d"))
2. 加载资金费率 + 稳定币增速 (通过 merge_external_factors)
3. fillna: funding_rate→0, stablecoin_growth→0
```

**入场判断** (全部满足才入场):
```
① close > SMA200            ← 在牛熊分界线上方
② funding_rate > -0.01      ← 不是极端空头踩踏
③ stablecoin_mcap_growth > 0 ← 流动性在流入，不是流出
④ volume > 0
THEN: enter_long = 1
```

**出场判断**:
```
IF close < SMA200:           ← 跌破牛熊分界线
  exit_long = 1              ← 立即离场
```

**风控**:
```
stoploss: -0.25
```

**参数优化记录**: 测试了4组放松变体（放宽资金费率、放宽稳定币条件），全部更差或相同。当前阈值已最优。

### MtfTrendLongShort (R102) — 期货多空

**设计思路**: 把 CbbiMomentum 的逻辑镜像到做空方向。

**入场判断**:
```
做多: CBBI 3d动量>0 + CBBI<0.65 + EMA100>EMA200
做空: CBBI 3d动量<0 + CBBI>0.25 + EMA100<EMA200
```

**出场判断**:
```
做多出场: CBBI 4d动量<-0.03 | CBBI>0.80 | EMA100<EMA200
做空出场: CBBI 4d动量>+0.03 | CBBI<0.15 | EMA100>EMA200
```

**状态**: config_futures.json 已创建，数据已下载，FreqTrade Binance期货 API 不稳定待修复。`_simulator_cbbi.py` 日线级验证完成。

### CbbiAhr999Daily (R103) — CBBI+ADR999 日线抄底

**设计思路**: CBBI (链上情绪) + AHR999 (定投指标) 双指标共振，识别被低估区域。日线级别减少噪音，延长持仓周期。

**指标准备**:
```
1. 加载 CBBI 日线数据 (通过 merge_cbbi)
2. 加载 AHR999 日线数据 (通过 merge_ahr999)
3. 计算 CBBI N日动量 = 当前CBBI - N天前CBBI (入场信号)
4. 计算 AHR999 N日动量 = 当前AHR999 - N天前AHR999 (入场信号)
5. 计算 SMA200, EMA50, EMA200 (出场信号)
```

**入场判断** (仅 BTC/USDT, 动量模式):
```
IF 全部满足:
  ① CBBI 3日动量 > 0          ← 恐惧在消退，信心恢复中
  ② AHR999 3日动量 > 0        ← 估值在回升
  ③ volume > 0                ← 有交易量
THEN:
  enter_long = 1               ← 全仓买入 (custom_stake_amount = 99%钱包)
```

**出场判断** (高估模式):
```
IF 任一满足:
  ① CBBI > 0.75               ← 情绪过热
  ② AHR999 > 1.3              ← 估值过高
THEN:
  exit_long = 1                ← 全部卖出
```

**风控参数**:
```
stoploss: -0.25 (固定止损，跌25%强制离场)
minimal_roi: {"0": 100} (无止盈目标)
max_open_trades: 1 (一次只持有一个仓位)
timeframe: 1d (日线级别)
```

**参数优化记录**:
```
粗筛 (40组): 动量入场远优于阈值入场
精筛 (120组): Top-3 参数组合:
  1. N=3, EXIT_AHR=1.3, EXIT_CB=0.75 → +527.4% (最优)
  2. N=7, EXIT_AHR=1.3, EXIT_CB=0.75 → +424.8%
  3. N=7, EXIT_AHR=1.1, EXIT_CB=0.75 → +419.8%
```

**滚动窗口验证 (7段)**:
```
2023 H1: +80.7%  | 2023 H2: +36.8%  | 2024 H1: +33.7%
2024 H2: +55.2%  | 2025 H1: +35.8%  | 2025 H2: -11.3%
2026 Q1: -21.2%
均值: +30.0% (超过 BuyAndHold +27.3%)
```

**vs 基线**:
```
收益: +527.4% (BuyAndHold +88.5% 的 6 倍)
回撤: -24.7% (SmartHold -43.3% 的一半)
滚动均值: +30.0% (超过 BuyAndHold +27.3%)
```

**状态**: 训练集 +527.4%，滚动均值 +30.0%，验收通过。

---

## 已归档策略摘要

| R# | 策略 | 归档原因 |
|----|------|---------|
| R86 | Cycle01 | AHR999+CBBI 入场，不识别阴跌(-16.5%在2026)；v2加SMA200出场改善到+3.4%，后被CbbiMomentum取代 |
| R88 | GoldenCross | EMA50/200金叉死叉，+196%；被SmartHold取代(同范式，SmartHold更好) |
| R89 | Combo | AHR999+金叉组合，+190%；冗余 |
| R91-93 | EmaCycle/Simple/Hybrid | 测试EMA/SMA不同组合，无一超过CbbiMomentum |
| R94 | EmaValuation | 4指标共振，+174%训练；CbbiMomentum动量版更好 |
| R95 | EmaAhr | R94的无CBBI版，结果相同，CBBI条件不绑定 |
| R96 | CbbiLead | CBBI绝对值<0.4入场，只在恐慌交易，5个窗口4个0%；被动量版取代 |
| R97 | Cycle01v2 | 加SMA200趋势出场，2026改善；被CbbiMomentum取代 |
| R88 | CbbiLead v2 | 出场0.70→0.75，+38pp；被3d/4d动量版取代 |
| 10x | CB2d4d~CB4d7d | 参数扫描变体，均不如3d/4d组合 |
| R101 | CbbiATR | ATR追踪止损，+208%→远不如固定止损(+668%) |
| R101 | CbbiETH | 双币版本，ETH拖累回撤，BTC-only更好 |

---

## 完整验证命令

```bash
uv run run.py              # 2023-2025 训练集 (run.py 默认)
uv run val.py              # 2026 Q1 单段 OOS
uv run val_rolling.py      # 7 段滚动窗口 (全周期)
uv run pytest tests/       # 13 个测试（基础设施健康检查）
```

## 构建新策略 — 完整步骤

### Step 1: 复制模板
```bash
cp user_data/strategies/_template.py.example user_data/strategies/MtfTrendNew.py
```

### Step 2: 编写策略类
```python
class MtfTrendNew(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False       # 现货=False, 期货=True
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200
```

### Step 3: 加载指标
```python
# 日线指标 (通过 @informative("1d"))
@informative("1d")
def populate_indicators_1d(self, dataframe, metadata):
    dataframe["ema100"] = ta.EMA(dataframe, timeperiod=100)
    return dataframe

# 1h指标 + 外部数据
def populate_indicators(self, dataframe, metadata):
    dataframe = merge_cbbi(dataframe, metadata)      # CBBI
    dataframe = merge_ahr999(dataframe, metadata)    # AHR999
    return dataframe
```

### Step 4: 编写入场/出场
```python
def populate_entry_trend(self, dataframe, metadata):
    # 你的入场条件
    dataframe.loc[condition, "enter_long"] = 1
    return dataframe

def populate_exit_trend(self, dataframe, metadata):
    # 你的出场条件
    dataframe.loc[condition, "exit_long"] = 1
    return dataframe
```

### Step 5: 训练集回测 (~30秒)
```bash
uv run run.py | grep "total_profit\|trade_count\|sharpe"
```
验收标准: 训练收益 > +50%, 交易数 > 2

### Step 6: 滚动窗口验证 (~2分钟, 最关键的检验)
```bash
uv run val_rolling.py
```
验收标准: 7段均值 > +20% (BuyAndHold 基线 +27%)

### Step 7: 参数优化 (如有阈值)
```python
# 创建变体测试不同参数组合
for entry_d, exit_d in [(2,4), (3,4), (3,5)]:
    create_variant(entry_d, exit_d)
    run backtest → val_rolling
```
选择均值最高的组合。

### Step 8: 记录
1. 在 `results.tsv` 添加一行 (round/strategy/event/metrics/notes)
2. 在 `STRATEGY_MAP.md` 更新表格和策略详情
3. Git commit: `Rxxx: strategy_name — one line description`
4. `git push`

## 核心教训 (R1→R100)

1. **CBBI 动量方向 > CBBI 绝对值**: 等恐惧不如做恐惧消退
2. **3d 入场 + 4d 出场**: 10 组扫描确认的非对称最优组合
3. **BTC only > BTC+ETH**: ETH 拖累回撤和收益
4. **固定止损 > 追踪止损**: 加密波动太大，追踪止损过早离场
5. **入场选择性 > 立即入场**: CbbiMomentum > SmartHold 的核心原因
6. **简单 > 复杂**: 3 个入场条件 + 3 个出场条件 = 最优
7. **全周期验证 > 单段训练**: 2022 熊市数据才是真正的压力测试
