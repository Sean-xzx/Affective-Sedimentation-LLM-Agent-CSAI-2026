# Affective-Sedimentation-LLM-Agent-CSAI-2026

[English](README.md) · **[论文 PDF](paper/main.pdf)** · [架构](docs/ARCHITECTURE.md) · [验证记录](docs/VALIDATION.md)

**已被 CSAI 2026 接收，尚未发表。** PDF 链接指向仓库内稿件，不是出版平台页面。

**保留所有权利。** 仅公开供查看，其他使用须事先取得书面许可；既有法律、平台及此前许可产生的权利除外。详见 [RIGHTS.md](RIGHTS.md)。

## 项目价值

本项目将事件记忆与模型外计算的慢变情感状态分开，检验状态注入是否改变 LLM 智能体的选择。它解决的研究问题是：如何区分状态通道与记忆文本对行为的影响。明确的对照使这一接口可测量，无需改变模型权重。

## 我的贡献

**Zexian Xiong——第一作者。** 主要负责机制设计与验证，并全程参与研究推进。**Yan Li——导师、第二作者及通讯作者**，主要提供科研指导。代码实现、实验采集、统计分析及论文以合作研究成果呈现。

| 我已确认的贡献 | 具体工作 | 依据 |
|---|---|---|
| 机制设计 | 提出并设计“情感沉积”机制，用模型外的三层控制器维护慢变 P/A/D 状态 | [控制器](sprint/dynamics.py)、[论文](paper/main.pdf) |
| 机制验证 | 参与设计预注册实验、主动传感器对照及同记忆零状态消融，评估状态注入对选择的影响 | [冻结设计](configs/sprint_20260810.yaml)、[渲染器](sprint/renderer.py)、[结果](reports/final_results.json) |

## 关键方法

`交互事件 → 快/中/慢三层 P/A/D 状态 → 提示元数据 → A/B 选择 → 配对分析`

P/A/D 分别表示效价、激活与感知控制。状态在模型外计算，作为不指定动作的背景元数据写入提示。关键设计是把事件记忆与状态分开，用明确对照检查各通道：

- **E：标签对照**——比较情感标签和数字相同的传感器元数据，不加入事件记忆。
- **N：状态消融**——保持事件记忆相同，比较历史生成状态与归零状态。

AB/BA 选项顺序配对、固定 seed、冻结材料和预设门槛约束实验比较。实验检验提示接口，未单独识别三层递推机制的独特因果作用。合作实现包含 NumPy 数值计算、固定 seed 的确定性历史、六并发 Qwen 运行器、可恢复日志及 SHA-256 溯源，使实验执行可审查。细节见[架构说明](docs/ARCHITECTURE.md)。

## 成果与证据

**756 条正式观测**，另有 80 条开发及稳定性观测，共保存 **836 条日志记录**。冻结集合上的两组主门均通过。CS 表示选项顺序配对后的选择得分。

| 实验 | 正式观测 | 已记录效应 | 单侧符号翻转 p 值 |
|---|---:|---:|---:|
| E：情感减传感器斜率，CS / rendered-z | 180 | 0.2678 | 0.015625 |
| N：方向校正的完整状态减归零状态 CS | 576 | 0.1042 | 0.00390625 |

<details>
<summary>精确保存的效应值</summary>

E：`0.26775524691778746`；N：`0.10416666666666666`。

</details>

[原始日志](data/raw/sprint_raw.jsonl) · [锁定结果](reports/final_results.json) · [论文 PDF](paper/main.pdf)

**适用边界**：仅验证一个 Qwen 快照及自拟强制选择探针。E 的 15 个探针中有 9 个饱和，三个单轴检验均未通过 Holm 校正。N 的平均效应仅略高于固定的 0.10 工程门槛，8 个 seed 中有 3 个低于该门槛。结果支持有限的接口层面效应，不证明模型内部情绪、持续人格或跨模型通用性。

**工程证据**：已有验证记录显示，Python 3.11.9 在 Windows 与 Ubuntu 上均通过 **277 项测试**。无凭据演示检查数值控制器和两条模拟观测，证明功能可运行，不代表新增行为实验结果。详见[验证记录](docs/VALIDATION.md)。

## 快速开始

**仅供权利人及已事先取得书面许可的使用者执行。** 命令记录作者的验证流程，不授予运行、复用或修改权限。

Python **3.11.9** 已在本地 Windows、Ubuntu 24.04.5 和 Windows Server 2025 上验证；macOS 未测试。以下流程无需 GPU、API 密钥、模型权重或付费请求。安装依赖及下载四个 tokenizer 文件（约 15 MB）需要联网，环境需预留数百 MB。本地测试约需 1–3 分钟。

```sh
git clone https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026.git
cd Affective-Sedimentation-LLM-Agent-CSAI-2026
python -m venv .venv
```

Windows PowerShell 激活环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS 激活环境：

```sh
source .venv/bin/activate
```

如果 PowerShell 限制激活脚本，可用 `.\.venv\Scripts\python.exe` 代替 `python`。随后执行：

```sh
python -m pip install -r requirements-public.lock
python -m tools.reproduce demo
python -m tools.reproduce verify
python -m tools.prepare_resources
python -m tools.reproduce test
python -m tools.check_publication
```

成功标准：所有命令以状态码 0 结束；输出 `Demo PASS`、阶跃半时间 **1/8/69**、两条模拟观测及 `live_api_attempts=0`；`Verify PASS` 复现上表并核对 56 个受保护文件；资源准备验证四个 tokenizer 文件的哈希；测试报告 **277 passed**。测试会重建内容相同的结果文件并生成被忽略的辅助 SVG，若不能接受临时写入，请使用可丢弃的克隆副本。

## 配置、结构与深入阅读

[冻结配置](configs/sprint_20260810.yaml)固定 200-event 历史、seed `20260804`、探针、预算及已记录模型 `qwen3.7-flash-2026-07-15`。[资源元信息](docs/resources.json)固定代理 tokenizer `Qwen/Qwen3-0.6B`，它不是模型权重，也未证明与托管快照的 tokenizer 完全相同。缓存放在被忽略的 `.cache/` 中；发布依赖锁提供完整测试环境，历史依赖文件保持不变。

`sprint/` 实现状态、历史、渲染和采集；`tools/` 分析日志并提供安全入口；`tests/` 保护行为；`data/` 与 `reports/` 保存证据；`paper/` 保存稿件和图表。模块关系见[架构说明](docs/ARCHITECTURE.md)，seed、分析单位、离线资源、哈希及 TeX 要求见[复现说明](docs/REPRODUCIBILITY.md)。

发布整理没有重跑真实在线采集，该流程可能产生费用。`.env.example` 说明可选的 `DASHSCOPE_API_KEY`；接口读取环境变量，导入时不会加载 `.env`。保留冻结科学代码和数据，从根目录运行模块，测试前先准备 tokenizer。测试通过不代表已满足终稿投稿要求；历史 PDF 哈希锁和投稿说明可能对应较早版本。

提问、申请许可或报告已授权运行的问题，请使用 [Issues](https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026/issues)。不邀请未经许可的补丁或功能修改；问题报告应附脱敏输出、操作系统、Python 版本及提交 SHA。不承诺长期维护或托管服务可用性。

## 论文、来源与权利

Zexian Xiong 与 Yan Li，**Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in an LLM Agent**。引用[稿件](paper/main.pdf)时请注明仓库提交，不声明发表 DOI。非中性评价值归因于 Gebhard 和 Kipp（2006）Table 2，详见[参考文献](paper/refs.bib)、[文献证据](paper/LITERATURE_EVIDENCE.md)及[资源来源](docs/RESOURCE_PROVENANCE.md)。

本版本不提供开源许可证。[RIGHTS.md](RIGHTS.md)说明许可政策，以及旧 MIT 授权和 GitHub 平台权利带来的限制。第三方依赖与资源保留各自适用条款。
