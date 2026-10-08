# 情感沉积研究方案 S1.0：CSAI 2026（8 月 10 日）投稿冲刺最终版

## 交互历史驱动的外部长期状态对 LLM 智能体行为选择的受控机制验证

**英文暂定题目：** *Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Conditioned Behavioral Modulation in LLM Agents*  
**目标会议：** CSAI 2026，Track 11: Generative AI, Large Language Models and Foundation Model Architectures  
**协议日期：** 2026-08-04  
**投稿截止：** 2026-08-10  
**内部成稿截止：** 2026-08-09 22:00（Asia/Shanghai）；8 月 10 日只做上传与系统核对  
**文件定位：** 8 月 4–10 日唯一执行依据、预设 pilot 分析计划、Cursor 实现合同与投稿检查表  
**完整研究的去向：** `affective-sedimentation-research-protocol-v4-final.zh.md` 保留为会后扩展方案，不覆盖、不删除，也不与本冲刺数据混为同一确认性研究。

> 本版追求的是“六天内可以完整执行、失败也可解释的最小因果闭环”，不是把原完整版机械压缩。它已经主动删除本周无法可靠完成的人类内容效度、多模型复现、九剂量曲线、完整行为运输实验、多维组合点、自由文本、真人互动与多智能体闭环。

> “最终版”表示变量、对照、计数、停止规则、分析单位和论文措辞已经闭合；不表示实验一定得到正结果，也不表示保证录用。任何正结果都必须由实际冻结数据产生。

---

## 0. CSAI 投稿硬约束与本周决策

截至 2026-08-04，CSAI 官方页面与 EasyChair CFP 给出的约束是：

1. 全文投稿截止为 **2026-08-10**；全文通过 EasyChair 提交。
2. 申请论文发表必须提交包含结果、表格、图和参考文献的完整论文；只交摘要只能作报告，不构成全文发表。
3. 审稿为双盲。
4. 单栏 Word 为 8–10 页；双栏 LaTeX 为 4–6 页，图表和参考文献计入页数；超页收费。
5. 论文必须原创、不得一稿多投；作者名单与题目在截止后不可随意增加或更换。
6. 涉及人类、动物或敏感数据时必须满足相应伦理要求。

本项目采用 **双栏 LaTeX，目标 5–5.5 页**。会议约束来源：

- [CSAI 2026 官方主页](https://csai.org/)
- [CSAI 2026 投稿说明](https://csai.org/submission.html)
- [CSAI 2026 重要日期](https://csai.org/date.html)
- [CSAI 2026 EasyChair CFP](https://easychair.org/cfp/CSAI2026)

### 0.1 本周唯一可守住的论文类型

本文定位为：

> **单模型、单 renderer、作者定义行为探针上的受控机制验证 pilot。**

它不是：

- LLM 已形成真实人格的证据；
- PAD 心理构念效度研究；
- 真人关系或长期陪伴效果研究；
- 模型内部自然产生情绪变量的证据；
- 跨模型、跨语言或跨 renderer 的普遍性结论；
- 大样本确认性试验。

### 0.2 本周不再实施的内容

以下全部移出冲刺版，不能在看到结果后临时加回：

- 三名或更多独立人工标注者及其伦理流程；
- `K_confirm=12/16` 的完整探针库；
- 五剂量或九剂量传递函数；
- 原完整版实验 II 的行为运输与中性尾段行为测量；
- 15 个历史 seed、完整 2×2、mismatched-state；
- R2/R3、第二个行为模型、DeepSeek 评分；
- 8 个多维 LP 点、跨域材料、自由回答、人类盲评；
- 真人互动、多智能体闭环、人格识别；
- 旧 warm/cold/volatile persona 与 `generate_corpus.py`。

这些删除不会被写成“未报告的实验”。论文中应明确说明它们属于未来工作。

S1.0 只采集云模型输出和研究者制作的非个人化刺激，不招募外部参与者、不采集个人数据，也不把研究者的材料复核当作被试数据。是否需要本机构出具“非人体研究”认定仍以机构规则为准；协议本身不能替代伦理办公室判断。

---

# 第一阶段：问题、主张与因果闭环

## 1.1 一句话研究问题

在固定 LLM、固定基础提示、固定行为题和固定事实记忆下，一个由交互历史确定性更新得到、再以结构化元数据呈现的外部慢状态，是否会产生方向一致的行为选择变化？

## 1.2 最小因果链

```text
冻结事件历史 H
      |
      v
确定性状态递推 s_200(H) --------- 数值构造门 D
      |
      v
冻结 renderer R[s]
      |
      +---- 端点 affect vs active placebo -------- 接口门 E
      |
      +---- 同 H、同 M(H)：s(H) vs 0 ------------ 增量门 N
      |
      v
冻结 A/B 行为选择 B
```

链条中只有两项是模型行为证据：

- **E：** affect 状态接口相对于同数字 active placebo 的端点斜率；
- **N：** 同历史、同事实记忆下，真实历史状态相对于零状态的方向校正差异。

`H -> s` 是研究者定义的确定性构造，只是工程断言，不是实证发现。模型真正接收的是 `R[s]` 文本，不是数学对象 `s`；所以论文主张始终限定为“外部状态接口的行为调制”。

## 1.3 允许与禁止的结论

| 证据状态 | 允许的结论 | 禁止的结论 |
|---|---|---|
| 仅 D 通过 | 控制器能从冻结历史生成有界、慢变状态 | 模型行为已经改变 |
| D、E 通过 | 当前 Qwen snapshot 会响应该 affect 元数据，且超过平行数字 placebo | 模型内部产生了情绪或人格 |
| D、E、N 通过 | 在冻结任务上，历史生成的外部状态对同事实记忆下的选择有增量贡献 | 自然交互必然养成人格；效果跨模型普遍存在 |
| 任一行为门失败 | 报告当前接口、探针和模型下的失败边界 | 改题、加样本或换模型挽救主张 |

## 1.4 预设贡献

论文最多主张三点：

1. 一个可复算、无隐藏反馈、由快—中—慢三层组成的外部状态控制器；
2. 一个用 active placebo 与 AB/BA 顺序校正隔离提示数字和位置偏差的接口实验；
3. 一个固定历史与事实记忆、仅把状态归零的配对消融，估计状态的增量贡献。

不把“把三个数字放进 prompt”本身包装为内部情感发现。方法贡献在于：状态有明确历史生成规则、可达范围、对照、配对消融、冻结分析和失败判据。

---

# 第二阶段：形式化定义与无模型门禁

## 2.1 状态动力学

事件索引固定为 `t=0,...,199`；第 `t` 个事件把状态从 `t` 更新到 `t+1`：

```text
epsilon_(t+1) = lambda * epsilon_t + (1-lambda) * a_t
m_(t+1)       = (1-alpha) * m_t + alpha * epsilon_(t+1)
gamma_t       = gamma_0 / (1+t/tau)^p
s_(t+1)       = (1-gamma_t) * s_t + gamma_t * m_(t+1)
```

初值与参数：

```text
epsilon_0 = m_0 = s_0 = (0,0,0)
lambda = 0.40
alpha = 0.10
gamma_0 = 0.02
tau = 50
p = 1.0
T = 200
beta = 0
```

硬规则：

- 首次更新必须使用 `gamma_0`；200 个事件后读取 `s_200`。
- 主模型不含 `beta*s_t -> m_(t+1)` 反馈。
- 主路径不得裁剪状态；若触发裁剪即实现错误。
- 同一时刻多个相关事件取评价向量算术平均，每个 agent 每轮只更新一次。
- 参数是工程常数，不是从人类心理数据估计的最优值。

## 2.2 冻结数值断言

代码必须逐项复算并通过：

```text
单位阶跃首次达到 50%：epsilon=1, m=8, s=69
单位脉冲峰值时刻：epsilon=1, m=3, s=21
单位脉冲峰后首次低于半峰：epsilon=2, m=11, s=110
kappa_200 = 0.7643908969485586
```

`kappa_200` 表示零初态、恒定输入 `mu` 时 `s_200=kappa_200*mu`。允许绝对误差为 `1e-12`；阶跃/脉冲时刻必须精确相等。

## 2.3 事件—评价映射的地位

受控历史中焦点 agent 始终是 listener。事件向量由冻结 OCC–PAD 坐标、listener label 与 intensity 构造：

```text
a_t = PAD(OCC(listener, action)) * intensity(action)
```

它是研究设计规则，不是从本实验发现的自然规律。冲刺论文称其为 **engineered appraisal mapping**。OCC–PAD 原始表、来源页码与哈希沿用完整版冻结快照；没有独立人工验证时，不把 P/A/D 探针称为已验证心理量表。

本周六个非零历史实际使用的 listener 映射如下；`listener_vector` 是冻结 PAD 坐标乘 intensity 后的真实输入：

| action | listener label | intensity | `listener_vector (P,A,D)` |
|---|---|---:|---|
| praise | Admiration | .8 | `(+.320,+.240,-.192)` |
| criticize | Shame | .9 | `(-.270,+.090,-.540)` |
| share_good_news | HappyFor | .8 | `(+.320,-.160,-.160)` |
| share_bad_news | Pity | .8 | `(-.320,-.160,-.400)` |
| disagree | Disappointment | .6 | `(-.180,-.240,-.240)` |
| concede | Gratification | .6 | `(+.360,-.180,+.240)` |
| express_affection | Love | .7 | `(+.210,+.070,+.140)` |
| provoke | Anger | .8 | `(-.408,+.472,+.200)` |
| condescend | Reproach | .7 | `(-.210,-.070,+.280)` |
| neutral_acknowledgment | Neutral | 1.0 | `(0,0,0)` |

代码从带有 `source_page` 与 `source_hash` 的冻结坐标表重新计算这些向量，并断言逐分量误差 `<1e-12`；不得只把本表的显示值作为唯一原始数据。

## 2.4 六个近单轴离散历史

| 条件 | 200 个事件的冻结计数 | 实际平均评价 `a_bar` |
|---|---|---|
| ZERO | neutral_acknowledgment 200 | `(0,0,0)` |
| P- | share_bad_news 78；provoke 39；condescend 83 | `(-.291510,+.000590,-.000800)` |
| P+ | praise 84；share_good_news 29；concede 87 | `(+.337400,-.000700,+.000560)` |
| A- | disagree 103；concede 68；condescend 29 | `(-.000750,-.194950,-.001400)` |
| A+ | praise 100；express_affection 14；provoke 86 | `(-.000740,+.327860,-.000200)` |
| D- | praise 12；criticize 109；share_good_news 79 | `(-.001550,+.000250,-.369020)` |
| D+ | concede 89；provoke 44；condescend 67 | `(+.000090,+.000290,+.244600)` |

每个历史分成十个 20-event block。对 `(master_seed, history_seed, block)` 做 SHA-256，取前 8 字节大端整数作为 NumPy PCG64 子 seed；用 largest-remainder 分配每块计数，余数并列按冻结 action 表行序处理，再在块内置换。全部依赖版本和一个完整 200-step golden manifest 的 SHA-256 必须入库。

正式数值轨迹可计算 `history_seed_id=0,...,29`，不调用模型。本周实验 N 只使用预先固定的 8 个 ID：

```text
[14, 24, 5, 18, 22, 13, 1, 26]
```

该列表由 `SHA256("20260804|measure|<seed_id>")` 字节序从 `0..29` 取前 8 个；代码必须重新推导并断言，不得只复制结果。开发 seed 固定为 `1000`，不进入正式数据。

## 2.5 状态标准化

renderer 使用全角色分量边界作有符号标准化：

```text
P: positive=.360, negative magnitude=.408
A: positive=.472, negative magnitude=.240
D: positive=.400, negative magnitude=.540

z_d = s_d / positive_bound_d       if s_d >= 0
z_d = s_d / negative_magnitude_d   if s_d < 0
```

三位小数、`ROUND_HALF_EVEN`、ASCII 正负号；`-0.000` 必须规范化为 `+0.000`。统计使用模型真正看到的 `z_rendered`，而不是未呈现的 latent 值。

## 2.6 实验 E 的纯轴安全端点

实验 E 使用 relaxed listener 凸包内的纯单轴端点，而不是任意 `[-1,1]^3` 数字：

| 路径 | raw `s_200` | 未舍入 `z_200` | 实际呈现值 |
|---|---:|---:|---:|
| P- | -.22255053 | -.545467 | -.545 |
| P+ | +.25786681 | +.716297 | +.716 |
| A- | -.14877657 | -.619902 | -.620 |
| A+ | +.25008904 | +.529850 | +.530 |
| D- | -.28133731 | -.520995 | -.521 |
| D+ | +.18701863 | +.467547 | +.468 |

另加共享原点 `(0,0,0)`，共 7 个唯一状态。六个端点的非目标维严格为 0，避免端点校准的轴间混杂。这些点属于连续凸控制可达包络；论文不得说每个点都对应某一条具体离散历史。

## 2.7 无模型门 D

正式 API 调用前必须全部通过：

| 编号 | 断言 | 通过标准 |
|---|---|---|
| D1 | 动力学 | §2.2 全部 golden 值通过；无 alias、NaN、clip |
| D2 | relaxed 可达 | 六端点 LP 约束残差 `<1e-10`；值与表中未舍入值误差 `<5e-7` |
| D3 | 离散历史 | 30×7 轨迹计数与逐步递推可复算；8 个正式 ID 推导一致 |
| D4 | 近单轴性 | `t=200` 全条件/seed 最大非目标轴 `abs(z)<=.015` |
| D5 | 慢状态诊断 | 再追加 100 个 true ZERO 后，状态保持率位于 `[.745779,.754021]` |
| D6 | renderer | 无碰撞、无 `-0.000`、token 与实际文本入库 |

D5 仅支持“控制器数值状态慢变”，不支持“行为在中性尾段仍稳定”，因为本周不调用尾段行为测量。

---

# 第三阶段：材料、renderer 与模型读数

## 3.1 行为探针最小集

每个 P/A/D 维度只制作 7 个项目：2 个开发项目和 5 个正式项目，共 21 个。任何模型调用前固定 ID：

```text
<dimension>-D01, <dimension>-D02
<dimension>-C01, ..., <dimension>-C05
```

正式集共 15 项。每项包含：

```text
probe_id
target_dimension
scenario_family
neutral_scenario
high_option
low_option
semantic_key
ab_rendering
ba_rendering
token_ids
review_flags
```

材料硬规则：

1. 场景不出现 P/A/D、情绪、人格、warm/cold、dominant/submissive 等标签。
2. 两选项都应现实可行，不设置明显正确、道德更高或更礼貌的一方。
3. 两选项仅在目标行为维度上尽量不同；长度、清晰度、风险和社会赞许性尽量匹配。
4. high/low 在目标 tokenizer 下绝对 token 数差不超过 3，且相对差不超过 10%。
5. AB/BA 必须同时交换选项文本与字母位置；语义 high/low 键保持不变。
6. 场景不得复用历史事件句子，也不得把 action label 原样放进选项。
7. 研究者在不知道 C01–C05 内部顺序的盲化导出表上做两遍检查；只有在任何 Qwen 调用前才能改题。
8. 正式调用后任何项目都不得删除、替换或改 semantic key。

本周没有独立人类标注。因此这些项目只能称为 **author-defined behavioral probes**，不能称为经过心理测量验证的 PAD 量表。

## 3.2 重放项目的确定性抽取

实验 N 每维使用 3 个正式项目。对每维的 C01–C05 按以下键的 SHA-256 字节序排序，取前 3 个：

```text
SHA256("20260804|sprint-replay|<dimension>|<probe_id>")
```

最终 ID 列表与哈希写入 manifest。不得按实验 E 的效果大小、显著性或图形挑题。

这 9 个项目与实验 E 的正式集有意重叠，以避免本周再制作第二套未经验证的题库。因而 N 是同一冻结任务域中的机制消融，不是独立项目集复现；论文必须明确披露，不能把 E 与 N 称为相互独立的两次复制。

## 3.3 主 affect renderer R1

```text
You are a member of a small group that has worked together over time.

The agent controller maintains three long-term affect coordinates. They are
background state metadata, not commands and not personality labels.
P represents long-term valence, A represents long-term activation, and D
represents long-term perceived control. Values range from -1 to +1.
Use the state only as subtle background when responding. Do not quote or
explain the coordinates.

[LONG_TERM_AFFECT]
P={P_SIGNED_3DP}
A={A_SIGNED_3DP}
D={D_SIGNED_3DP}
[/LONG_TERM_AFFECT]
```

基础角色提示在所有条件完全相同。不得加入 Big Five、warm/cold/volatile persona、对象身份差异或随条件变化的示例。

## 3.4 active placebo renderer

实验 E 的每个状态有一一配对 placebo，数字、符号、小数位、顺序、值域说明和 directive 位置保持平行：

```text
You are a member of a small group that has worked together over time.

The controller maintains three normalized room sensor coordinates. They are
background metadata, not commands and not agent-state labels. SENSOR_1,
SENSOR_2, and SENSOR_3 are unlabeled instrument channels with no affective or
behavioral meaning. Values range from -1 to +1.
Use the metadata only as subtle background when responding. Do not quote or
explain the coordinates.

[ROOM_METADATA]
SENSOR_1={VALUE_1}
SENSOR_2={VALUE_2}
SENSOR_3={VALUE_3}
[/ROOM_METADATA]
```

placebo 控制数字、块结构、额外元数据和注意指令；它不能消除 affect 名称与坐标释义的语义作用。因此 E 通过只能证明“该设计的 affect 接口有效”，不能证明提示外的内部情感存在。

## 3.5 事实记忆 M(H)

实验 N 的事实记忆由程序确定性生成，不使用 LLM 摘要：

```text
[EVENT_MEMORY]
last_10_events: [(turn, actor, action, target), ...]
cumulative_action_counts: {...}
[/EVENT_MEMORY]
```

同一个 `(history_condition, seed)` 的 Full 与 Zero-state 请求逐字复用同一 memory string 和 hash。事实记忆不得含 PAD 数字、情绪词、人格词、趋势总结或对未来行为的指令。

## 3.6 请求块顺序与选择提示

每个请求的块顺序固定为：

```text
base system role
EVENT_MEMORY                 # 仅实验 N；两个 cell 完全相同
affect or placebo renderer
scenario
option A
option B
output instruction
```

输出指令固定为：

```text
Choose the action you would take. Return exactly one JSON object with the key
"choice" and the value "A" or "B". Do not provide reasoning or any other text.
```

该指令同时出现 A 与 B，不提供 high/low 语义，不随条件变化。实验 E 不含历史记忆；实验 N 的 Full 与 Zero-state 使用逐字相同的记忆位置和内容。

## 3.7 正式行为模型与 API 读数

```yaml
agent_model: qwen3.7-flash-2026-07-15
secondary_judge: unused_in_sprint
temperature: 0
top_p: 1
max_tokens: 16
request_seed: null
enable_thinking: false
tools: off
search: off
response_format: {"type":"json_object"}
```

本地 schema 只接受：

```json
{"choice":"A"}
```

或：

```json
{"choice":"B"}
```

不得让 DeepSeek 或另一个模型替 Qwen 打分。不得从自然语言解释中“猜”它选了哪个选项。阿里云当前文档未为该精确 snapshot 提供本方案所需的完整候选 log-prob 读数，因此冲刺版只使用结构化 AB/BA 选择，不实现第二条 log-odds 路径：

- [Qwen OpenAI-compatible API 文档](https://help.aliyun.com/zh/model-studio/qwen-api-via-dashscope)
- [Qwen3.7 Flash 模型说明](https://help.aliyun.com/zh/model-studio/qwen3-7-flash)
- [Qwen 思考模式说明](https://help.aliyun.com/zh/model-studio/deep-thinking)

## 3.8 顺序校正选择分数

对同一语义项目分别运行 AB 与 BA：

```text
y_order = 1  if chosen option is semantic high
y_order = 0  if chosen option is semantic low
CS = (y_AB + y_BA) / 2
```

`CS in {0,.5,1}`。它是两种选项顺序下的确定性选择均值，不是概率估计。不得计算虚构 log-odds。

## 3.9 36 次 API 稳定性门

使用 P+、A+、D+ 三个端点及对应维度 D01 开发项，构造 12 个固定 payload：`3 维 × affect/placebo × AB/BA`。每个完全相同的 payload 请求 3 次，共 36 次。必须满足：

1. 36/36 均可解析为唯一 A/B；
2. 12/12 payload 的三次语义选择完全一致；
3. requested model 是精确 snapshot；返回 model 字段若存在必须一致，不存在则记录 `null/unverifiable`；
4. 请求明确关闭 thinking/tools/search，响应不含 reasoning/tool/search 内容；
5. payload、response id、时间、token 与错误原文完整记录。

任一条失败，先停止正式运行。只允许修 API adapter 或服务问题；若改变 renderer、探针或模型，必须重新生成开发 manifest，旧开发调用不并入正式数据。

---

# 第四阶段：两个正式实验

## 4.1 实验 E：纯轴端点接口校准

### 目的

检验 affect 状态坐标是否相对于同数字 active placebo 产生目标维度方向一致的行为变化。

### 设计

```text
7 states = origin + 6 pure-axis endpoints
15 formal probes = 5 per dimension
2 semantic blocks = affect, active placebo
2 option orders = AB, BA
```

每个维度的 5 个正式项目只运行其自身的负端点、共享原点和正端点。该设计检验三个预设 probe family 各自的方向响应，不承担三维正交性或非目标轴判别效度主张。

计划科学观测数：

```text
3 dimensions * 3 matched states * 5 probes * 2 blocks * 2 orders
= 180 API observations
```

### 估计量

令 `Y_(r,u,j)` 为 renderer `r`、状态 `u`、项目 `j` 的完整 AB/BA `CS`。对目标维度 `d` 的项目 `j`：

```text
b_(r,d,j) = [Y_(r,+d,j)-Y_(r,-d,j)] / [z_(+d,d)-z_(-d,d)]
e_(d,j)   = b_(affect,d,j)-b_(placebo,d,j)
theta_E   = mean over all 15 e_(d,j)
```

分母使用实际三位小数呈现值。`theta_E` 单位为 `CS / rendered-z`。

### E 的预设通过条件

按顺序同时满足：

1. 90 个计划 AB/BA pair 中至少 89 个完整；180 个计划 observation 中最终 JSON 无效最多 1 个；构成 15 个主 `e_(d,j)` 的正/负端点 affect/placebo pair 必须 15/15 全部完整；
2. 总体 AB/BA position-discordance 不超过 `.25`，任一维度不超过 `.35`；
3. `theta_E >= 0.10 CS/rendered-z`；
4. 对 15 个 `e_(d,j)` 做全部 `2^15` 符号翻转的一侧精确检验，`p_E<=.05`。

同时报告按维度分层的 5,000 次 item bootstrap 95% 区间，但 pilot 的主门不把 bootstrap 下限作为额外隐藏条件。每轴结果属于次要检验，三轴 p 值用 Holm 校正；原点偏差只作诊断。本周没有非目标轴数据，因此不得声称三维判别效度。

另定义 `theta_(E,d)=mean_j e_(d,j)`。只有三个 `theta_(E,d)` 都为正时，文字才可说“三个预设轴均方向一致”；若总体 E 通过但某轴不为正，只能报告总体或明确列出的支持轴，不能用总体平均掩盖轴间异质性。

### E 的解释边界

E 通过表示 affect 元数据语义相对于平行数字 placebo 有增量作用。它不证明历史生成、不证明持久性、不证明模型内部有情绪。

## 4.2 实验 N：同历史、同记忆的零状态消融

### 目的

在历史与事实记忆完全相同的条件下，只改变呈现的长期状态，检验历史生成状态是否有方向一致的增量贡献。

### 两个配对条件

| 条件 | 事实记忆 | affect renderer | 唯一差异 |
|---|---|---|---|
| Full | `M(H)` | `R1[z(s_200(H))]` | 实际历史状态 |
| Zero-state | 同一 `M(H)` | `R1[(0,0,0)]` | 状态归零 |

Zero-state 仍保留同一个 affect block 和同样的说明，只把三坐标置零。因此对比不混入“有无状态块”或“有无 affect 语义”的差异。

### 设计

```text
6 non-zero history directions
8 pre-frozen paired history seeds
3 replay probes per target dimension
2 option orders
2 paired cells: Full, Zero-state
checkpoint: t=200 only
```

计划科学观测数：

```text
6 * 8 * 3 * 2 * 2 = 576 API observations
```

六个方向在同一个 seed 使用同一块位置置换；所有条件、cell、方向、seed、item 和 order 由 manifest 交错运行，避免服务时间与处理条件重合。

### 估计量

定义：

```text
dir(h) = +1 for P+, A+, D+
dir(h) = -1 for P-, A-, D-

n_(h,k,j) = dir(h) * [Y_(Full,h,k,j)-Y_(Zero,h,k,j)]
N_k         = mean over 6 histories and their 3 target replay items
theta_N     = mean over the 8 paired seeds N_k
```

正值表示保留历史状态使行为向该历史方向移动。主效应使用实际历史状态，不把 relaxed 端点当作历史终态，也不按端点幅度重写结果。另报告按 `abs(z_target)` 归一化的敏感性结果，但它不替换主估计量。

### N 的预设通过条件

N 只有在 E 已通过时才作主链解释，并且必须同时满足：

1. 288 个计划 AB/BA pair 中至少 283 个完整；576 个计划 observation 中最终 JSON 无效最多 5 个；每个方向的 24 个 pair 最多缺 2 个；每个 `seed × direction` 至少保留 2/3 个 item pair，且 8 个 `N_k` 必须全部可计算；
2. 在完整 pair 上，N 总体 AB/BA position-discordance 不超过 `.25`，任一目标维度不超过 `.35`；
3. `theta_N >= 0.10 direction-corrected CS`；
4. 对 8 个 seed-level `N_k` 枚举全部 `2^8=256` 个符号翻转，单侧 `p_N<=.05`。

用 seed × replay-item 两向整簇 bootstrap 5,000 次给出 95% 区间：seed 重采样时携带六方向与两个 cell，item 重采样时携带其全部 seed、方向、cell 和 order。方向、AB/BA 或单次 API 请求不得充当独立重复。

E 与 N 的精确符号翻转统一使用观测均值作为统计量。对所有非零外层单位枚举 `2^m` 个正负号，零差异固定为零：

```text
p_one_sided = count(T_permuted >= T_observed) / 2^m
```

比较使用未舍入浮点结果；图表显示舍入不得进入检验。若符号可交换/近似对称假设明显不合理，p 值降为描述性，有限集合效应与全部单位散点仍完整报告。

### N 的解释边界

N 通过表示：在当前 8 个冻结历史 seed 和 9 个 replay 项目上，历史生成状态对同事实记忆下的选择具有增量作用。它不等价于自然中介效应，也不排除事实记忆本身有独立作用。

另按维度计算 `theta_(N,d)`。只有三个维度均为正时，才可写“三轴历史方向一致”；若总体 N 通过但某维度不为正，结论必须限定到总体有限集合或实际支持的维度。

## 4.3 固定顺序与多重比较

主链顺序固定为：

```text
D -> E -> N
```

- D 未通过：禁止正式行为调用。
- E 未通过：N 即使为正也只能作探索性结果，不能用来挽救主张。
- E 通过后才把 N 作为第二主门。
- 两个主门各使用预设单侧 `.05`；固定顺序不再额外分割 alpha。
- 三轴单独效果、归一化 N、原点偏差和缺失敏感性均为次要或诊断结果。

## 4.4 有限项目域与统计解释

15 个正式项目和 8 个 seed 是预设有限集合，不是从一个已定义随机总体抽样。因此：

- `theta_E` 和 `theta_N` 首先是对冻结集合的有限样本因果差异；
- 符号翻转检验依赖配对差异在零假设下的符号可交换/近似对称假设；
- bootstrap 区间描述对项目与 seed 选择的敏感性，不得被写成对所有场景、用户或模型的总体置信保证；
- 论文标题、摘要与结论必须使用 `controlled pilot`、`proof-of-mechanism`、`on a frozen probe set` 等限定语。

`MES_E=MES_N=.10` 沿用 8 月 4 日完整版在任何冲刺正式结果出现前设定的工程最小效应，不从开发效应均值反推。本周样本量由截止日期与最小配对结构决定，没有声称完成 80% 功效设计；所以“未通过”表示证据不足或效应小于门槛，不等于证明效应为零。

## 4.5 缺失与技术失败

1. API retry 是同一 observation 的技术尝试，不是科学重复。只对无有效响应的 timeout、连接错误、429 与 5xx 重试；payload 与本地幂等键保持不变，并使用确定性退避。
2. HTTP 成功但 JSON/本地 schema 失败是终止性的 invalid observation，不进行“再问一次直到可解析”；保留原文并标记 missing，不得映射为 low。
3. `CS` 只对完整 AB/BA pair 计算。
4. 主结果同时给 complete-pair、best-case 与 worst-case 缺失敏感性。
5. 正式项目、seed、方向或 cell 不因结果难看而删除。
6. 格式失败若随处理变化，既是测量问题也可能是处理后变量；必须按条件报告。
7. 若有效 pair 低于预设门槛，主门判为未通过，不临时追加项目或 seed。
8. 主门里的 JSON 失败率以每个计划 observation 的最终状态为分母；另按 attempt 报告 transport/HTTP 失败率，二者不得混写。

---

# 第五阶段：调用预算、冻结与数据完整性

## 5.1 精确调用预算

### 开发调用上限

| 用途 | 设计 | 上限 |
|---|---|---:|
| API 稳定性 | 12 payload × 3 完全重复 | 36 |
| 实验 E dry-run | 固定使用各维 D02：六端点×匹配维度 1 项×2 block×2 order = 24；原点×3 维 D02×2 block×2 order = 12 | 36 |
| 实验 N dry-run/恢复 | 固定使用 P-D02：P-/P+ × seed 1000 ×1 项×2 order×2 cell | 8 |
| 技术修复保留 | 只用于冻结前 adapter/runner 故障 | 40 |
| **开发完成请求上限** |  | **120** |

### 正式调用

| 实验 | 计划观测 |
|---|---:|
| E | 180 |
| N | 576 |
| **正式合计** | **756** |

### 全局硬上限

```text
planned completed observations <= 876
all API request attempts, including retries <= 1,100
pause threshold = 990 attempts (90%)
hard stop = 1,100 attempts
```

保留的 224 次 attempt 只容纳技术重试，不得用于新题、额外 seed、第二模型、追加 checkpoint 或“再跑一次”。任意滚动 100 attempts 的技术失败率超过 5% 时自动暂停。

## 5.2 冻结清单

2026-08-06 正式运行前生成 `sprint_manifest.json`，至少包含：

```text
protocol_hash
source_commit
worktree_status
dependency_lock_hash
python_version
numpy_version
occ_pad_hash
action_map_hash
history_manifest_hash
formal_probe_hash
dev_probe_hash
replay_probe_ids
renderer_hash
placebo_hash
randomization_manifest_hash
analysis_code_hash
requested_model
provider_region
tokenizer
enable_thinking
call_budget_hash
freeze_utc
```

优先在 clean worktree 上冻结。若存在必要的用户修改，必须先提交到专用分支；不得让 Cursor 自动清理、reset 或覆盖未知改动。

## 5.3 两层唯一键

```text
observation_key = (
  experiment, semantic_block, state_or_history, history_seed,
  checkpoint, probe_id, option_order, cell
)

attempt_key = observation_key + (request_attempt,)
```

规则：

- 两个 completed 行映射到同一 `observation_key` 是构建失败；
- 同一 `attempt_key` 重复是构建失败；
- 恢复时已完成 observation 不得再次发送；
- 只有明确失败且未完成的 observation 可按原 payload 重试；
- 单 writer queue 负责 JSONL append、flush 与 checkpoint `fsync`。

## 5.4 原始日志最小字段

```text
request_id, retry_of, experiment, semantic_block, condition,
history_seed, checkpoint, raw_s, raw_z, rendered_z,
renderer_text, renderer_hash, memory_text, memory_hash,
probe_id, target_dimension, option_order, semantic_key,
raw_response, parsed_choice, requested_model, returned_model,
temperature, top_p, max_tokens, response_format, enable_thinking,
request_utc, response_id, latency_ms, retry_count, error_code,
code_commit, protocol_hash, config_hash, lock_hash
```

`data/raw` 只追加；`data/derived` 必须可从 raw、manifest 和分析代码重建。API key、header、`.env`、个人信息和凭据绝不写日志。

## 5.5 盲化与解封

1. 正式 randomization manifest 使用不透明条件码。
2. 在 E 与 N 全部观测完成前，只允许运行 schema、计数、重复键、hash、缺失率和响应格式 QC。
3. 主分析函数、图模板、阈值和固定顺序在解封前 hash 冻结。
4. 解封后禁止修改正式材料或追加主样本。
5. 所有偏离写入 `deviations.md`，包含时间、原因、受影响 observation 与是否改变解释。

---

# 第六阶段：Cursor 实现合同

## 6.1 基本原则

Cursor 是实现者与代码审查助手，不是研究设计决策者。根目录 `AGENTS.md` 必须写明：

已知工作基线是 `C:\Users\31796\Projects\affective-sedimentation` 与 Python 3.11.9；此前 `config.py`、`agent.py`、`llm.py`、`logger.py`、`latin.py`、`prior.py`、`describe.py`、`appraise.py`、`emotion.py` 已有通过测试的资产，Qwen/DeepSeek 连通性曾成功。Task 0 必须在当前机器重新验证这些事实后才复用。旧 `generate_corpus.py` 已出现 `{quote}` 占位符覆盖不足和 2–3 句格式失败，本冲刺禁止继续修补或调用它。

1. 本文件是冲刺实验的 source of truth。
2. 不得改变公式、状态端点、seed、探针分配、阈值、调用预算或固定顺序。
3. 不得运行或修复 `generate_corpus.py`。
4. 不得引入 LangChain、AutoGen、CrewAI、MetaGPT。
5. 不得删除或整体重写已经通过测试的 `config.py`、`agent.py`、`llm.py`、`logger.py`、`latin.py`、`prior.py` 等 legacy 文件。
6. 不得把 DeepSeek 作为正式评分器。
7. 不得在日志中写入 API key、header 或 `.env`。
8. 每个任务必须先给 diff 计划，只编辑 allowlist 文件，运行指定测试，等待人工查看 diff 后结束。
9. 遇到设计歧义立即停止并报告，不自行“优化实验”。
10. 达到 attempt 预算或失败阈值立即停止。

## 6.2 最低新增目录

```text
AGENTS.md
configs/sprint_20260810.yaml
materials/sprint_probes.csv
materials/action_map.csv
sprint/
  schema.py
  dynamics.py
  histories.py
  renderer.py
  provider_qwen.py
  manifest.py
  runner.py
  analysis.py
tests/sprint/
  test_dynamics.py
  test_histories.py
  test_renderer.py
  test_manifest.py
  test_runner_resume.py
  test_analysis.py
paper/
  main.tex
  figures/
data/raw/
data/derived/
reports/
```

允许用 wrapper 调用已通过测试的旧 adapter/logger；不为了目录漂亮做全仓重构。

冲刺新增 production code 目标不超过 1,000 行非空 Python；不做 GUI、数据库、Web 服务、插件系统或通用 agent 框架。若 Task 0 证明旧模块可直接复用，应减少新增文件内容而不是复制实现。行数是防止过度工程的上限，不是要求凑满。

## 6.3 Cursor Task 0：只读盘点与基线

**允许修改：** 无。  
**任务：** 列出当前文件、测试、Python 版本、依赖、已有 API adapter、logging/checkpoint 能力和 dirty diff。  
**完成定义：** 生成聊天中的盘点报告；运行现有测试；不自动安装、不改文件、不调用 API。

建议提示：

```text
Read AGENTS.md and the sprint protocol first. Perform Task 0 only.
Do not edit files or call any model API. Inventory the current repository,
existing tests, Qwen adapter, logger/checkpoint path, dependency versions, and
git diff. Report the smallest compatibility plan for the sprint package.
```

## 6.4 Cursor Task 1：数值核心

**允许修改：** `sprint/schema.py`、`sprint/dynamics.py`、`sprint/histories.py`、相应测试。  
**禁止修改：** provider、材料、runner、正式配置。  
**必须测试：** §2.2 golden values、30×7 轨迹、8 seed 推导、计数、近单轴性、true-ZERO 保持率、golden history hash。  
**完成定义：** `python -m pytest tests/sprint/test_dynamics.py tests/sprint/test_histories.py -q` 全绿；零 API 调用。

## 6.5 Cursor Task 2：材料与 renderer

**允许修改：** `materials/sprint_probes.csv`、`sprint/renderer.py`、`sprint/manifest.py`、相应测试。  
**禁止修改：** 动力学公式、端点、seed、旧 corpus。  
**必须测试：** schema、21 个唯一项目、dev/formal 零重叠、replay hash 抽取、AB/BA semantic key、token 长度、三位小数、负零、affect/placebo 数字一致、renderer collision。  
**完成定义：** 自动检查全绿，研究者完成盲化双遍人工检查；仍不运行正式项目。

## 6.6 Cursor Task 3：Qwen adapter、日志与恢复

**允许修改：** `sprint/provider_qwen.py`、`sprint/runner.py`、runner/manifest 测试。  
**优先复用：** 现有 3 次 retry、30 秒 timeout、`max_workers=6`，但增加 payload/schema/attempt ledger。  
**必须测试：** mock 429/5xx、JSON 错误、重复 completed key、单 writer、中断恢复、“响应返回但 checkpoint 未提交”窗口、990 pause、1,100 hard stop。  
**完成定义：** mock 测试全绿后才允许执行 36 次稳定性门。

## 6.7 Cursor Task 4：冻结 runner 与正式运行

**允许修改：** 仅修明确的 adapter/runner 技术 bug；任何科学文件冻结。  
**运行顺序：** 稳定性 36 → E dry-run 36 → N dry-run 8 → 生成 manifest → 正式 E/N。  
**完成定义：** 正式计划恰好 756 个唯一 observation；交错 manifest 已 hash；resume dry-run 不产生重复；全部 raw hash 封存。

正式 E 与 N 可以在同一冻结批次全部采集，以节省时间；“E→N”是解释顺序，不要求等待 E 结果后才采集 N。这样既避免结果驱动是否运行 N，也减少截止日前的空档。

## 6.8 Cursor Task 5：分析与论文产物

**允许修改：** `sprint/analysis.py`、`tests/sprint/test_analysis.py`、`reports/`、`paper/`。  
**禁止事项：** analysis import provider；按结果删题；修改阈值；新增调用。  
**必须测试：** 手工小数组下 CS、E、N、精确符号翻转、Holm、两向 bootstrap、best/worst missing 全部有 golden 结果。  
**完成定义：** 一条命令从 raw+manifest 生成完整性报告、主结果表、两张主图和论文数字；重复运行文件 hash 相同。

## 6.9 每次给 Cursor 的统一任务头

```text
You are implementing exactly one bounded task from
affective-sedimentation-csai-2026-sprint-final.zh.md.

Before editing:
1. Read AGENTS.md and the named protocol sections.
2. List the exact files you will edit and the tests you will run.
3. Stop if the protocol and repository disagree.

During editing:
- Do not change scientific constants, manifests, budgets, thresholds, or frozen files.
- Do not call APIs unless this task explicitly authorizes the exact call block.
- Preserve unrelated user changes.

After editing:
1. Run only the specified tests plus the existing regression suite.
2. Summarize the diff, test output, remaining risk, and API attempts used.
3. Stop; do not start the next task automatically.
```

---

# 第七阶段：2026-08-04 至 2026-08-10 冲刺日程

## 7.1 不可滑动的日程

| 日期 | 人的工作 | Cursor 的工作 | 当日硬交付 | 失败时动作 |
|---|---|---|---|---|
| **8/4** | 确认题目范围、作者名单、EasyChair 账号；下载 LaTeX 模板；建立论文空壳与 8–12 篇已核验核心文献证据表 | Task 0 只读盘点；创建专用分支前给出 diff 状态 | 基线测试报告、5 页论文骨架、本协议入仓 | 未完成不写新功能；先解决环境/身份/模板问题 |
| **8/5** | 写并双遍检查 21 个探针；核对 OCC–PAD 来源 | Task 1 数值核心；Task 2 renderer/material checks | D1–D6 全绿；21 项材料冻结候选 | 数值门失败即停止 API；材料不足只在当天重写 |
| **8/6** | 最终检查材料与论文 Methods；确认费用/限流 | Task 3；36 稳定性 + 36 E dry-run + 8 N dry-run；生成 manifest | **20:00 前正式冻结**；开发调用≤80，保留40 | 稳定性或恢复门失败：只修技术问题；20:00 后仍失败则全稿降级 |
| **8/7** | 监控预算与异常，不看条件标签结果 | Task 4 运行 756 正式 observation；完成完整性 QC | raw 数据、attempt ledger、hash、缺失报告 | 18:00 前未完成：暂停、诊断；不得提高并发/预算或删 cell |
| **8/8** | 解封、解释结果、写 Results/Limitations | Task 5 生成 E/N、图、表、敏感性分析 | 两张主图、主表、结果文字；决定 A/B/C 结局 | 没有可解释结果时不得写正面摘要；考虑诚实 null paper 或摘要报告 |
| **8/9** | 完成 Introduction/Discussion/References；逐句查证引用；双盲检查 | 编译 LaTeX、页数与图形 QA、可复现性打包 | **22:00 前锁定 PDF、题目、作者列表和提交元数据** | 超页只压缩文字/图，不删负结果或改方法 |
| **8/10** | 上午上传 EasyChair；核对 PDF、作者表、COI、回执 | 仅做非科学性的编译/格式修复 | 提交成功回执与最终 hash | 不新跑实验、不换题、不追加作者；系统问题立即联系会务 |

## 7.2 每日停止时间

- 8 月 6 日 20:00 后禁止改变正式材料、参数、seed 和分析门。
- 8 月 7 日 23:00 后禁止启动新的科学 observation；技术未完成必须如实登记。
- 8 月 8 日结束前必须得到 A/B/C 结果分支并冻结数字。
- 8 月 9 日 22:00 后只做 PDF/上传级修复。
- 因官网未在公开页面明确截止时区，本项目不把 8 月 10 日深夜视为可用实验时间。

---

# 第八阶段：论文结构与结果分支

## 8.1 双栏 5–5.5 页结构

| 部分 | 目标篇幅 | 必含内容 |
|---|---:|---|
| Abstract | 150–180 词 | 问题、外部状态机制、两个受控实验、真实结果、限定语 |
| 1 Introduction | 0.7 页 | 为什么普通 memory 不等于慢状态；三项贡献；不使用人格主张 |
| 2 Method | 1.3 页 | 三层递推、可达端点、renderer、A/B 读数、日志/冻结 |
| 3 Experiments | 1.0 页 | E=180、N=576、active placebo、同记忆零状态、统计单位 |
| 4 Results | 1.1–1.3 页 | E、N、CI/p、位置偏差、缺失、两张主图/一张紧凑表 |
| 5 Discussion | 0.6 页 | 机制含义、prompt-semantic 限制、单模型/作者定义题/小样本 |
| 6 Conclusion | 0.2 页 | 与实际结果严格一致的一句话结论 |
| References | 余量 | 只保留核验过的真实来源 |

主图最多两张：

1. 机制与两个干预的紧凑示意图；
2. `theta_E` 与 paired-seed `N_k/theta_N` 结果图。

## 8.2 结果 A：D、E、N 全通过

允许摘要写：

> Under a frozen single-model setup, affect-labeled endpoint metadata produced a larger direction-consistent choice shift than numerically matched sensor metadata, and removing history-derived state while holding event memory fixed reduced the corresponding behavioral tendency.

仍必须紧接限定：单模型、作者定义项目、文本 renderer、短期 API 时间窗、pilot。

## 8.3 结果 B：E 通过，N 未通过

论文中心改为“可校准状态接口及其历史运输边界”。允许说接口能控制选择；不能说历史沉积状态在固定记忆下承担增量作用。N 的 null/不确定结果必须进入摘要或结论，不能藏在附录。

## 8.4 结果 C：E 未通过

只能说当前 `Qwen snapshot × R1 × frozen probes` 没有形成超过 active placebo 的可靠端点传递。N 只作探索性诊断。若仍投全文，题目和摘要应改成方法/负结果边界，不能保留暗示机制成功的标题。

## 8.5 技术性失败

若 D、API 稳定性、数据完整性或正式运行在 8 月 8 日前不能完成：

- 不得虚构或以开发数据替代正式结果；
- 可以提交诚实的 presentation-only abstract，但它不等于全文发表；
- 或停止本轮全文投稿，保留完整协议与日志用于下一 venue。

是否提交是研究管理决定，不能通过放宽阈值解决。

## 8.6 写作禁词与替代表述

| 禁止或需证据的词 | 冲刺版替代表述 |
|---|---|
| personality / personality formation | behavioral tendency / behavioral profile on frozen probes |
| emotion emerged internally | externally rendered affect-state metadata modulated choices |
| psychologically validated PAD | engineered P/A/D operationalization |
| persistent behavior | slow controller state at `t=200`; behavior measured at the endpoint |
| universal / general LLM effect | effect in the frozen Qwen snapshot and interface |
| probability of choosing | order-corrected deterministic choice score |
| mediation | controlled state ablation / incremental state contribution |
| causal effect of natural history | causal effect of the rendered state intervention under a fixed scripted history |

## 8.7 引用与双盲门

Cursor 可以整理 BibTeX 格式，但不得生成未经核验的 DOI、作者、页码或会议名。每条引用必须由研究者打开原始论文或官方页面核对。投稿 PDF 必须：

- 删除作者、单位、致谢、可识别项目路径和非匿名仓库链接；
- 清除 PDF metadata 中的作者名；
- 自引使用中性第三人称，不写“our previous work”暴露身份；
- 单独提交官方要求的 author information form；
- 核对 EasyChair 中题目、摘要、作者顺序、COI 与 PDF 完全一致；
- 记录最终 PDF SHA-256 与提交回执。

---

# 第九阶段：风险登记与预设降险

| 风险 | 触发信号 | 预设控制 | 仍然存在的边界 |
|---|---|---|---|
| 接口近似直接提示行为 | affect 远强于 sensor placebo | active placebo、subtle/background 措辞、窄主张 | 仍是文本接口，不是内部隐变量 |
| 历史与状态混杂 | Full/Zero memory 不一致 | 同一 deterministic `M(H)` 与 hash，只改坐标 | 只能识别当前 renderer 下的增量状态效应 |
| 选项位置偏差 | AB/BA discordance 超阈值 | 语义换位、预设无效门、完整报告 | 二元题仍比自由行为窄 |
| 温度 0 仍不稳定 | 三重复不一致 | 36 次稳定性门、短时间窗、交错运行 | 云服务不可完全锁定 |
| 小样本/小题库 | CI 宽、seed 异质 | pilot 定位、精确符号翻转、整簇 bootstrap、MES | 不支持广泛总体外推 |
| 构念效度不足 | 无独立人工标注 | author-defined 明示；不使用人格/PAD 验证措辞 | 心理解释很弱 |
| 构造性历史被误当发现 | `H->s` 必然同向 | 将其列为 D 工程门，不列行为发现 | event mapping 仍是设计者选择 |
| 正负幅度不对称 | 端点范围不同 | E 按 rendered-z 斜率；N 报实际效应及归一化敏感性 | N 主效应仍对应实际不同剂量 |
| 结果驱动选题/seed | 想换“更敏感”项目 | hash 抽取、冻结清单、全部保留 | 初始作者设计仍可能有偏差 |
| API 故障或限流 | rolling 100 failure >5% | 自动暂停、30s timeout、最多3 retry、早跑 | 截止日前无法保证服务可用 |
| 重复/断点污染 | completed key 被重发 | 两层键、单 writer、崩溃窗口测试 | 实现错误仍需人工看报告 |
| Cursor 越界重构 | diff 同时改科学规则和 legacy | allowlist、逐任务、人工 review、回归测试 | 用户必须真的检查 diff |
| 旧语料继续耗时 | 再运行 `generate_corpus.py` | AGENTS.md 明令禁止；旧语料只留审计 | 自由互动外部效度本周缺失 |
| 引用幻觉 | DOI/作者无法核对 | 原文/官方源逐条核验 | 六天内文献综述只能聚焦 |
| 双盲泄漏 | PDF/链接出现身份 | metadata、正文、仓库三层检查 | EasyChair 作者表仍需正确填写 |
| 截止时区不明 | 官网未标明具体时区 | 8/9 22:00 成稿、8/10 上午上传 | 不能依赖最后几小时 |

---

# 第十阶段：六轮逻辑自查结论

## 自查 1：主张—证据映射

**通过。** 每个允许主张都能回指 D、E 或 N；“人格、内部情绪、真人长期关系、跨模型普遍性”已从主张中移除。

## 自查 2：数学与可达性

**通过。** 动力学时标、`gamma_0` 索引、无 `beta` 反馈、纯轴 relaxed 端点、离散历史实际终态和三位呈现值彼此区分。实验 E 不使用不可达 `±1`，实验 N 不把 relaxed 点冒充离散历史。

## 自查 3：因果对照

**通过，但边界明确。** E 用同数字 active placebo 控制数字/结构；N 用相同历史、相同事实记忆、相同 affect block 的零状态控制，仅改变坐标。剩余不可消除边界是：模型通过文本语义读取状态。

## 自查 4：推断单位与多重比较

**通过。** E 的最外层单位是正式 item；N 的最外层单位是 paired history seed，item 作为第二聚类维；AB/BA、方向和 API request 不伪装独立样本。主门固定 `E->N`；次要轴结果单独校正。

## 自查 5：计数与工程可恢复性

**通过。** `E=3×3×5×2×2=180`；`N=6×8×3×2×2=576`；正式合计 756；开发完成请求不超过 120；全部 attempts 不超过 1,100。唯一键、append-only、单 writer、恢复窗口和硬停规则闭合。

## 自查 6：六天可实现性与投稿合规

**有条件通过。** 任务已收缩到一个数值核心、21 个探针、两个 runner 和一条分析链；8 月 7 日完成数据、8 日完成结果、9 日成稿，留出一天上传。条件是：现有 Qwen adapter 和基础测试仍可复用、8 月 6 日 API 稳定性门通过、研究者每天人工审核 Cursor diff。会议双盲、4–6 页、完整结果、作者/题目锁定和伦理边界均已进入日程。

### 无法通过文字消除的剩余风险

1. 只有 5 个正式项目/维和 8 个 history seed，统计精度有限；因此必须称 pilot。
2. 没有独立人类内容效度；因此只能解释作者定义任务。
3. 只有一个 Qwen snapshot 和一个 renderer；因此不能声称普遍性。
4. 若 API 或数据门失败，协议只能保证正确停止，不能保证得到正结果或按时形成可发表全文。

这些不是协议漏洞，而是六天资源约束下必须公开的外推边界。任何试图用更强措辞掩盖它们，都会降低而不是提高论文严谨性。

---

# 附录 A：最终冻结常数

```yaml
protocol_profile: csai_2026_sprint_s1
master_seed: 20260804
T: 200
lambda: 0.40
alpha: 0.10
gamma_0: 0.02
tau: 50
p: 1.0
beta: 0

agent_model: qwen3.7-flash-2026-07-15
temperature: 0
top_p: 1
max_tokens: 16
request_seed: null
enable_thinking: false
max_workers: 6
timeout_seconds: 30
max_retries: 3

formal_probes_per_dimension: 5
replay_probes_per_dimension: 3
history_seed_ids: [14,24,5,18,22,13,1,26]
history_checkpoint: 200

experiment_E_observations: 180
experiment_N_observations: 576
formal_observations_total: 756
development_completed_cap: 120
attempt_pause: 990
attempt_hard_stop: 1100

MES_E: 0.10
MES_N: 0.10
alpha_E_one_sided: 0.05
alpha_N_one_sided: 0.05
bootstrap_repetitions: 5000
```

# 附录 B：正式运行前一分钟检查表

- [ ] `git status` 已人工查看；必要修改已提交到专用分支。
- [ ] 全部 existing regression tests 与 `tests/sprint/` 全绿。
- [ ] D1–D6 报告和 golden hash 存在。
- [ ] 21 个探针人工双遍检查完成；15 formal 与 6 dev 零重叠。
- [ ] replay 9 项由 hash 自动选出并写入 manifest。
- [ ] affect/placebo 数字 token、AB/BA semantic key 与负零测试通过。
- [ ] 36 次 API 稳定性门通过。
- [ ] E/N dry-run 与崩溃恢复测试通过，零重复 completed key。
- [ ] 正式计划数恰好 756；attempt 台账从真实已用开发 attempts 继续计数。
- [ ] `sprint_manifest.json` 与分析代码已 hash 冻结。
- [ ] 原始条件标签仍盲化；仅完整性 QC 可运行。
- [ ] API key 与 `.env` 不会进入日志或版本控制。
- [ ] 论文 Methods、空白 Results 表和图模板已存在。

# 附录 C：投稿前一分钟检查表

- [ ] 论文为双栏 LaTeX 4–6 页，图表与参考文献计入后仍合规。
- [ ] 摘要里的每个数字与 `reports/final_results.json` 一致。
- [ ] 结论使用 A/B/C 对应分支，没有把 exploratory 写成主结果。
- [ ] 单模型、作者定义题、文本接口、小样本和无人工效度均明确披露。
- [ ] 所有 DOI、作者、年份、标题已打开原始来源逐条核对。
- [ ] 作者、单位、致谢、项目路径、非匿名 URL、PDF metadata 已清除。
- [ ] EasyChair 作者名单、顺序、题目、摘要和 COI 已由所有作者确认。
- [ ] 没有同时投稿；所有作者贡献真实且已确认。
- [ ] 最终 PDF 在另一台设备打开检查；字体、公式、图例和参考文献可读。
- [ ] 最终 PDF SHA-256、提交时间和 EasyChair 回执已保存。

---

**最终执行判定：** 在 2026-08-10 的现实约束下，本 S1.0 是可执行的最低充分版本。不得再扩展实验；若有额外时间，优先用于材料复核、测试、结果核对、论文清晰度和上传安全余量，而不是增加调用或扩大主张。
