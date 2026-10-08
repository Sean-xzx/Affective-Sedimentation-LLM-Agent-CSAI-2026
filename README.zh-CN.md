# LLM 智能体的情感沉积

[English](README.md) · [复现细节](docs/REPRODUCIBILITY.md) · [架构说明](docs/ARCHITECTURE.md)

一个受控研究试验：检验外部计算、由交互历史驱动的情感状态元数据，是否会改变 LLM 智能体的强制选择。

本仓库保存已完成的 CSAI 2026 实验，包括三层数值控制器、确定性事件历史、固定提示和行为探针、支持恢复日志的 Qwen 接口，以及已采集观测的可复现分析。适合了解基本开发流程、希望研究智能体状态接口和实验复现的开发者。

## 范围与已记录结果

控制器在模型外更新快、中、慢三层 P/A/D 状态。实验 E 比较带情感含义的端点和数字相同的传感器元数据；实验 N 保持事件记忆相同，比较历史生成状态与归零状态。解释顺序固定为 D（数值检查）、E、N。

| 已记录指标 | 数值 |
|---|---:|
| E 正式观测 | 180 |
| N 正式观测 | 576 |
| 开发及稳定性观测 | 80 |
| 日志总记录数 | 836 |
| E 效应，CS / rendered-z | 0.26775524691778746 |
| E 单侧符号翻转 p 值 | 0.015625 |
| N 效应，方向校正 CS | 0.10416666666666666 |
| N 单侧符号翻转 p 值 | 0.00390625 |

已记录的两组主门均通过；E 的三个单轴检验均未通过 Holm 校正。这些结果针对冻结的有限题目和 seed 集合，不构成总体保证。效应不对称且主要集中在激活维度；探针饱和、单一模型快照及较短采集窗口限制了解释范围。实验没有提供模型内部情绪或人格形成的证据。

## 环境要求

- Python **3.11.9** 已在本地 Windows，以及 GitHub Actions 的 Ubuntu 24.04.5 和 Windows Server 2025 上验证。macOS 未测试。
- 演示和已记录结果分析不需要 GPU、数据库、模型权重、API 密钥或付费服务。
- 克隆、安装依赖以及为完整测试下载四个代理 tokenizer 文件需要联网。资源准备完成后，测试套件离线运行。
- Python 环境需预留数百 MB，tokenizer 资源约 15 MB。本地回归测试耗时约 1-3 分钟，耗时随机器变化。
- 编译论文还需要包含 `acmart`、`pdflatex`、`bibtex` 的 TeX 环境；这是独立于统计复现的流程。

## 快速开始

克隆仓库并进入根目录：

```sh
git clone https://github.com/Sean-xzx/affective-sedimentation-llm-agent.git
cd affective-sedimentation-llm-agent
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

如果 PowerShell 限制激活脚本，可用 `.\.venv\Scripts\python.exe` 代替 `python`，无需修改系统执行策略。然后运行：

```sh
python -m pip install -r requirements-public.lock
python -m tools.reproduce demo
python -m tools.reproduce verify
python -m tools.prepare_resources
python -m tools.reproduce test
python -m tools.check_publication
```

演示使用模拟响应函数，仅在临时目录写入两条记录，不发送模型请求，也不改变科学实验日志。预期关键输出：

```text
Demo PASS: numerical controller, history, renderer and mock runner.
verify_paper_numbers: all locked fields match rebuild within tolerance
Verify PASS: ... protected files, locked statistics and secondary diagnostics.
Tokenizer ready: Qwen/Qwen3-0.6B @ c1899de289a04d12100db370d81485cdf75e47ca
```

演示报告阶跃半时间 `epsilon=1`、`m=8`、`s=69`、两条模拟观测及 `live_api_attempts=0`。验证应复现上表并以状态码 0 结束。测试命令运行原有科学回归套件及新增发布接口测试。[验证记录](docs/VALIDATION.md)说明实际通过数量和验证边界。

## 配置与资源

冻结的[配置](configs/sprint_20260810.yaml)规定 200-event 历史、主 seed `20260804`、模型标识、请求设置、门槛和预算。不要为修复结果或依赖问题而修改它。[动作映射](materials/action_map.csv)与 [21 个探针](materials/sprint_probes.csv)也已冻结。

已记录的模型标识为 `qwen3.7-flash-2026-07-15`。离线 tokenizer `Qwen/Qwen3-0.6B` 是**代理 tokenizer**，不是模型权重，也未被验证为与托管快照的 tokenizer 字节相同。[资源元信息](docs/resources.json)固定其 revision 和 SHA-256。准备工具将文件放入被忽略的 `.cache/huggingface/`；测试入口把默认 tokenizer 名称解析到已验证的本地快照，并关闭联网。

原有 `requirements.txt`、`requirements.lock` 按字节保留，因为其哈希属于实验溯源。`requirements-public.lock` 补齐发布与测试依赖，包括 `pypdf`、`pandas`、`seaborn`，不改写历史依赖锁。

`.env.example`说明可选的 `DASHSCOPE_API_KEY`。接口读取环境变量，导入包不会加载 `.env`。快速开始的所有命令都不需要凭据。在线采集可能产生费用，本次发布整理**没有重新运行或验证**在线采集，因此快速开始不提供真实采集命令。

## 结构与入口

```text
configs/                 冻结实验配置
materials/               动作表与开发/正式探针
sprint/                  控制器、历史、渲染器、接口与运行器
tools/                   分析、诊断、安全复现及检查工具
tests/sprint/            原有科学回归测试
tests/publication/       离线演示和发布完整性测试
data/raw/                已记录且不可变的 JSONL 日志
data/derived/            已记录分析汇总
reports/                 冻结清单、统计量与诊断
paper/                   论文源码、参考文献与图表资源
docs/                    架构、来源、资源与验证说明
.github/workflows/       离线复现 CI
```

动作映射生成确定性历史，`dynamics.py`计算慢状态，`renderer.py`把状态与记忆转成提示文本。`runner.py`组合探针、调度和模型接口，并追加请求日志。`tools/analysis_core.py`读取日志及随机化清单，计算 E/N 统计量；`sprint/analysis.py`导出这些函数。次级诊断和制图工具解释响应结构，论文引用选定图表。[架构说明](docs/ARCHITECTURE.md)进一步解释数据流和冻结主分析与次级诊断的区别。

## 复现与开发

- `python -m tools.reproduce demo`：数值和模拟运行器验证，无需 tokenizer 下载或凭据。
- `python -m tools.reproduce verify`：只读检查字节完整性，重现锁定统计与次级诊断。
- `python -m tools.prepare_resources`：仅联网下载固定 tokenizer 资源。
- `python -m tools.reproduce test`：使用离线 tokenizer 缓存运行原有回归与发布测试。
- `python -m tools.check_publication`：检查本地文档链接及中英文命令、结果的一致性。
- [详细复现说明](docs/REPRODUCIBILITY.md)：采样、seed、分析单位、哈希、论文编译与产物限制。

部分原有分析和制图命令会写入 `reports/`或 `paper/figures/`，请在可丢弃的克隆副本中试验。上述安全入口完成后，冻结科学文件的字节保持不变。原有回归测试会重建内容相同的结果文件，并生成两个被忽略的辅助 SVG；若要求原工作目录完全不发生写入，请使用可丢弃的克隆副本。Git 属性保留科学文件跨平台的字节，因为换行变化也可能使记录的哈希失效。

欢迎通过 [Issues](https://github.com/Sean-xzx/affective-sedimentation-llm-agent/issues) 和 Pull Request 提交复现问题或改进。请附操作系统、Python 版本、命令及脱敏后的错误输出；不要包含 API 密钥、私人 `.env`或个人日志。保留科学常数、核心代码和已记录数据；新的科学设计应成为明确分离的实验，不应悄悄改变本版本。不承诺长期维护或托管服务可用性。

## 已知限制与常见问题

- 从仓库根目录运行模块命令。模块缺失通常意味着目录不对或环境未启用。
- tokenizer 加载失败时先运行资源准备，不要更换代理或放宽材料门槛。离线复制方式见详细说明。
- 原始冻结清单保留两个空哈希字段及历史依赖哈希。[偏离记录](reports/deviations.md)说明后续分析哈希的锁定位置；不要改写清单。
- 历史投稿报告可能对应较早稿件。提交前需要独立核对当前 PDF、文献核验状态和图像分辨率；旧 PDF 哈希锁不对应当前 PDF。
- 回归测试通过不代表论文已满足投稿要求。文献核验和提交仍属于人工任务；论文 QA 门可能失败，同时科学复现通过。
- Windows 的 symlink 警告及未安装 PyTorch/TensorFlow 不影响只使用 tokenizer 的流程。已测试的 Windows/Linux 环境见上文，其他系统和语言版本需另行验证。

## 使用条件、来源与引用

项目代码采用 [MIT 许可证](LICENSE)。作者已允许公开实验日志及自有论文和图表；这些研究资源保留作者权利，不随代码自动更换许可证。具体范围和第三方条件见[资源来源说明](docs/RESOURCE_PROVENANCE.md)。

工程化评价映射将非中性 OCC-to-PAD 数值归因于 Gebhard 和 Kipp（2006）Table 2；方法与相关工作出处见 [refs.bib](paper/refs.bib)和[证据表](paper/LITERATURE_EVIDENCE.md)。仓库不分发第三方论文 PDF 或模型权重；附带参考文献样式在文件头声明为 public domain。

引用本实验时，请引用 Zexian Xiong 与 Yan Li 的论文 **Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in an LLM Agent**，并注明所用仓库提交。本说明不声称论文已被会议接收或拥有发表 DOI。
