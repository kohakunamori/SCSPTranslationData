# SCSPTranslationData

[![License](https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-nc-sa.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)

《偶像大师 闪耀色彩 棱镜之歌》（SCSP）简体中文翻译数据仓库。

当前维护分支为 `TransData`。本仓库只保存公开的翻译数据与辅助文件，不包含游戏客户端、账号信息、运行日志、抓包、私有服务端或个人本地运行环境。

## 与 scsp-localify 的关系

公开插件仓库：[kohakunamori/scsp-localify](https://github.com/kohakunamori/scsp-localify)

`scsp-localify` 将本仓库作为 `resources/schinese` Git submodule 使用，因此插件仓库会固定到一个明确的翻译数据 commit。翻译内容本身保持 `scsp_localify/...` 目录结构，可以直接作为插件的本地化数据目录使用。

## 分支

- `TransData`：当前简体中文翻译数据，也是默认维护分支。
- `DumpData`：原始 Dump 数据参考。该分支可能落后于当前客户端，不应默认认为它就是最新原文。

提交译文前，推荐优先使用当前客户端实际 Dump 的文本与 `DumpData` 交叉确认。

## 当前数据内容

`scsp_localify/` 目前主要包含：

| 路径 | 用途 |
| --- | --- |
| `localify.json` | Localify 主文本表，按表/键组织 |
| `local2.json` | 不经过主 Localify 表的字符串映射 |
| `lyrics.json` | 歌词映射 |
| `scenario/` | 剧情/场景 JSON，本仓库当前包含 5,000+ 个 scenario JSON |
| `scsp-bundle` | 本地化使用的资源包 |
| `story-text-map.bin` | 剧情文本辅助映射数据 |
| `update_local_json.py` | 将旧 `localify.json` 译文迁移到新 Dump 的辅助脚本 |

当前 2.17 数据已经覆盖主文本、local2、歌词和大规模 scenario 数据。覆盖范围不等于每一行都需要被翻译：专有名词、占位符、资源键、程序标记以及本身就应保持原样的内容可能有意保留。

## 面向 Agent 与社区协作

本仓库现在提供一套公开、模型无关的翻译质量层，目标是让人工译者和不同 Agent 都能在同一套规则下协作，而不是依赖某个维护者的私有工作环境。

入口文档：

- [AGENTS.md](AGENTS.md)：Agent 在本仓库工作的首要说明，包含数据边界、修改规则、质量门和推荐流程；
- [CONTRIBUTING.md](CONTRIBUTING.md)：人工、小规模修订、批量 Agent 翻译和版本更新的贡献流程；
- [翻译风格指南](docs/translation-style-guide.md)；
- [Agent 翻译指南](docs/agent-translation-guide.md)；
- [翻译 QA 策略](docs/qa-policy.md)；
- [社区质量 Backlog](docs/community-quality-backlog.md)；
- [客户端版本更新流程](docs/version-update-workflow.md)。

GitHub 侧也提供了翻译质量 / source update Issue 表单与 Pull Request 模板。提交者需要明确 source provenance、QA/backlog 前后变化以及公开仓库隐私检查，方便社区 review 和 Agent 协作。

公开 QA/知识数据：

- `qa/glossary.json`：已审核的共享术语；
- `qa/names.json`：当前仓库沿用的人名映射；
- `qa/allowed-source-equal.json`：经审核可以保持原样的文本；
- `qa/rules.json`：结构、格式、隐私与各文本表面的 QA 策略；
- `qa/baseline-exceptions.json`：公开记录引入 QA 前已经存在的窄范围历史例外，新问题不会因此被放过；
- `qa/backlog-policy.json`：将 QA warning 映射为 P1/P2/P3 社区 review 任务；
- `qa/schemas/`：Agent batch/result 的公开 JSON Schema；
- `tools/qa.py`：统一质量检查入口；
- `tools/build_translation_memory.py`：从公开的 `TransData` 与 `DumpData` 对齐生成 Translation Memory。
- `tools/build_quality_backlog.py`：把 repository-wide warning 去重并整理成稳定、可筛选的社区质量任务；
- `tools/canonicalize_exact_source_conflicts.py`：检测严格可复现的 exact-source 双译分叉；默认只生成 proposal，`--apply` 才会修改 `local2.json`；
- `tools/prepare_agent_batch.py`：把未解决 source 去重后整理成模型无关的 Agent batch；
- `tools/validate_agent_result.py`：在应用 Agent 输出前验证 source identity、覆盖率和格式签名。

这些文件都应保持可公开复现，不依赖私人路径、账号、私有服务端或内部调试环境。

### 运行 QA

```bash
python tools/qa.py
```

QA 将结果区分为：

- **hard error**：JSON/结构错误、明确的占位符/格式破坏、隐私泄漏等，提交前必须处理；
- **review warning**：残留日文、原文未翻译、重复原文出现不同译法、术语差异、可能合理的换行/数字差异等，需要结合语境判断。

`DumpData` 默认只作为参考源，因此由旧 Dump 推导出的格式差异不会自动升级为 hard error。只有确认输入 Dump 与当前客户端一致时，才应使用：

```bash
python tools/qa.py --dump-ref <current-source-ref> --authoritative-dump
```

### 生成社区质量 Backlog

```bash
python tools/build_quality_backlog.py
```

默认输出到 `qa/generated/`，包括完整 JSONL task 列表和 JSON/Markdown summary。Backlog 会把 warning 去重并按 P1/P2/P3、术语、格式、数字、布局、一致性等维度分类。

例如只查看 P1：

```bash
python tools/build_quality_backlog.py --priority P1
```

或只准备适合 Agent review 的术语任务：

```bash
python tools/build_quality_backlog.py \
  --priority P2 \
  --category terminology \
  --agent-ready-only \
  --max-items 50
```

所有 backlog item 都明确带有 `auto_apply_allowed=false`。它们是 review 任务，不是自动修改指令。详见 [社区质量 Backlog](docs/community-quality-backlog.md)。

对于依赖历史 `DumpData` 的任务，backlog 还会标记 `source_authority=historical-reference` 与 `requires_source_verification=true`，提醒 Agent/贡献者先确认当前权威原文，再修复占位符、数字或源文敏感问题。

CI 对当前 source-key 数据还有两道额外质量门：

```bash
python tools/canonicalize_exact_source_conflicts.py --check
python tools/build_quality_backlog.py --check-current-key
```

第一条要求不存在可被严格规则机械闭合的 exact-source 分叉；第二条要求 `current-key` backlog 没有新增 blocker。历史 `DumpData` backlog 不会因此被误当成当前客户端事实。

数字 QA 会保留阿拉伯/全角数字作为锚点，同时识别目标中文中明确的等价表达，例如 `4 → 四名`、`2 → 两行`、`1 → 第一季`、`10 → 十次`、`2倍 → 翻倍`。确有语义等价但无法安全泛化的情况，只能以 `qa/rules.json` 中精确的 source+translation+surface exception 记录。

### 生成 Translation Memory

```bash
python tools/build_translation_memory.py
```

默认输出到 `qa/generated/`。该目录用于本地/CI 生成，不默认纳入版本控制。Translation Memory 会保留稳定 identity、日文 source、当前译文和公开 provenance；同一 source 存在多个译法时会单独生成 conflict 列表，避免 Agent 无脑复用。

### 准备与校验 Agent batch

```bash
python tools/prepare_agent_batch.py
```

默认只输出真正没有可复用译文的 source。需要把唯一 Translation Memory 候选也交给 reviewer/Agent 时：

```bash
python tools/prepare_agent_batch.py --include-tm-candidates
```

默认 batch 还会排除仅能从历史 `DumpData` 推导 source 的 unresolved localify/scenario 文本。只有已经独立确认某个 dump/ref 与当前客户端一致时，才应显式使用：

```bash
python tools/prepare_agent_batch.py \
  --dump-ref <current-source-ref> \
  --authoritative-dump
```

在当前公开 checkpoint 中，所有可由维护中的 source-key 直接确认的 unresolved 文本已经闭合，因此默认 batch 可以为空；被排除的历史 Dump-only source 仍需先完成当前客户端 source verification。

Agent 返回 JSONL 后，在写回翻译数据之前先运行：

```bash
python tools/validate_agent_result.py \
  qa/generated/agent-batch.jsonl \
  path/to/agent-result.jsonl
```

数据格式分别由 `qa/schemas/agent-batch-record.schema.json` 和 `qa/schemas/agent-result-record.schema.json` 公开定义。

## 使用方法

### 直接使用

如果你使用 [kohakunamori/scsp-localify](https://github.com/kohakunamori/scsp-localify)，推荐直接使用插件仓库中固定的 submodule 版本：

```bash
git clone --recursive https://github.com/kohakunamori/scsp-localify.git
```

已有仓库可执行：

```bash
git submodule update --init --recursive
```

插件默认的 `localifyBasePath` 是 `scsp_localify`。使用独立下载的本仓库时，将本仓库中的 `scsp_localify` 目录放到插件可读取的位置即可。

### 单独克隆翻译仓库

```bash
git clone -b TransData https://github.com/kohakunamori/SCSPTranslationData.git
```

只需要翻译数据时，不必下载或提交任何游戏文件。

## 更新 localify.json

当游戏更新后得到新的 `localify.json` Dump，可以用仓库自带脚本尽量保留已有译文：

```bash
cd scsp_localify
python update_local_json.py
```

脚本会依次询问：

1. 旧翻译文件路径，直接回车默认使用 `localify.json`；
2. 新 Dump 文件路径。

对于新 Dump 中仍存在、且旧翻译中已有的 `category/key`，脚本会保留旧译文，并输出 `new_localify.json`。

这个脚本只负责键级迁移，不会判断原文语义是否发生变化。游戏大版本更新后仍需要人工或工具复核变更项。

## 获取原文

推荐顺序：

1. 使用 [scsp-localify 的 Dump 功能](https://github.com/kohakunamori/scsp-localify#文本-dump-与翻译) 获取当前客户端实际文本；
2. 与本仓库 `DumpData` 分支进行对照；
3. 确认键、原文和上下文后再修改 `TransData`。

主文本、local2、歌词和 scenario 的加载路径不同，新增文本不一定只会出现在 `localify.json`。

## 贡献翻译

请从 `TransData` 创建修改，并保持文件路径和 JSON 结构不变。

提交前建议确认：

- 不修改 JSON key、scenario key 或资源标识，只修改确实属于用户可见文本的 value；
- 保留 `\n`、富文本标签、`<sprite>`、格式化占位符等控制内容；
- 人名、组合名、歌曲名和固定术语尽量保持全仓库一致；
- 不把调试日志、Dump 临时文件、游戏资源、账号信息或个人路径提交进仓库；
- 大批量翻译应进行术语一致性、占位符完整性、重复文本一致性和残留日文检查；
- 机器辅助翻译可以用于批处理，但提交前必须经过质量检查，不能把未经复核的原始机翻直接作为最终译文。

Pull Request 请说明修改范围，例如“歌词”“某一剧情系列”“某个主表”或“客户端更新后的键同步”。

## 翻译质量建议

批量处理时推荐至少做以下检查：

- JSON 能正常解析；
- key 数量没有意外减少；
- 占位符、富文本标签和换行结构未被破坏；
- 同一原文在同一语境下尽量使用一致译法；
- 人名与官方/既有译名一致；
- 对仍包含日文假名的结果做二次筛查；
- 对“原文 = 译文”的条目区分程序标记、专名、无需翻译内容和真正漏译，不要机械替换。

## 隐私与仓库边界

本仓库是公开翻译数据仓库。请勿提交：

- 游戏客户端或官方资源原文件；
- 账号、Cookie、Token、启动参数；
- 日志、抓包、崩溃 Dump；
- 私钥、证书；
- 个人用户名、绝对本地路径或私人项目结构；
- 与公开翻译数据无关的私有服务端/运行环境资料。

## 上游与贡献者

本 fork 基于社区 SCSP 翻译数据持续维护。上游项目与历史贡献可以参考：

- [ShinyGroup/SCSPTranslationData](https://github.com/ShinyGroup/SCSPTranslationData)
- [chinosk6/SCSPTranslationData](https://github.com/chinosk6/SCSPTranslationData)

当前 fork 的提交记录与贡献者：

<a href="https://github.com/kohakunamori/SCSPTranslationData/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=kohakunamori/SCSPTranslationData" />
</a>

## License

翻译数据沿用仓库现有许可，详见 [LICENSE](LICENSE)。
