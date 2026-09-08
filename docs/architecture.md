# 架构

```text
本地项目与私人事实
        |
        v
项目语义可见性门（默认 deny）-> 受审计的 allowlist 采集器
        |
        v
私有候选 manifest + changes + relationship review queue
        |
        v
人工复核 -> approve-snapshot -> 私有不可变批准历史
        |
        v
已批准事实 manifest  <-- 发布事实真源
        |
        +--> 安全策略门：字段白名单、密钥与路径检测、关系校验
        |
        +--> 小型 workspace/action 入口 + 项目分片
        |
        +--> 问题定向 Markdown（确定性裁剪）
        |
        +--> 派生项目/模块关系图 JSON
        |
        v
明确指定的发布目录 -> 专用 Google Drive 目录 -> ChatGPT Chat
```

## 层次

### 1. 证据层

项目先经过语义可见性门。新项目默认 `deny`，不进入候选或图谱；只有显式 `allow` 才读取用户列出的 README/AGENTS、Git 元数据和指定路径存在性，默认仍不读源码正文。显式 `summary-only` 只发布人工批准摘要。可选 code-path 关系适配器必须逐项目显式开启，只在本地受限扫描代码/配置中的其他批准项目根引用；本机路径与源码行不进入候选 manifest 或发布包。可选 Architecture Index 也必须逐项目把 `architecture_visibility` 从 `disabled` 改为 `modules-only` 或 `modules-symbols`，才会在本地读取有上限的 Python/JavaScript/TypeScript 语法。它只发布项目相对模块、结构名称、imports、外部包、测试模块、过滤后的内部 calls、hash、截断和失败计数，不发布源码正文、注释、docstring、字符串值、默认值或绝对根。可选 Skill 适配器只读 `SKILL.md` 的 bounded frontmatter 名称与原始摘要用于本地审计，在结束分隔符处停止，不读指令正文；原始摘要不发布，只有私有配置中人工批准的中性摘要可进入 Context。

项目状态适配器只读取人工从 `state_file_candidates` 移入 `state_files` 的固定根目录 Markdown，并按明确语义标题区块提取有上限的完整段落或列表；文件名、仅包含 `current` 的阶段标题、状态控制行和已完成 checklist 不得冒充当前目标或期限。自动提取记录进入候选事实但保持 `needs_review`。私有 review-state 适配器承载人工批准的 priority、activity、attention、why-now、goal、blocker、next action、done-when、owner、deadline 与有效期。`init-review-state` 只生成最多三个显式项目的无行动事实私有骨架，不执行批准。中立 session-summary 适配器只接受显式 JSON 文件，不发现或读取任何聊天工具的原始历史目录。

### 2. 事实层

核对入口 `preview-review-state` 复用同一 review-state 校验器，只在私有目录
生成中文核对单。它不接入扫描器、不产生批准事件、不改变任何事实，原文和
文件指纹用于人工确认准确版本；因此不是第二套编译器或 AI 总结流程。

保存已确认的项目目标、状态、信号、约束、风险、问题与证据引用。V0.2 状态统一为 `StateRecord`：稳定 `record_id`、`kind`、`status`、`source_kind`、`source_ref`、`observed_at`、可选 `expires_at` 与 `supersedes`。生命周期支持 `open`、`resolved`、`superseded`、`stale` 和 `needs_review`。来源消失只会触发待审，不会自动解释成解决；只有稳定 ID 或显式 supersedes 才能关闭旧状态。

批准状态在输出顺序和行动选择上高于自动抽取状态，但不会覆盖或删除原始事实。所有不确定内容显式保留为 `unknown`。

显示层在生成时间重新解析 lifecycle，入口与问题切片复用同一选择器。项目降级为 `summary-only` 或 `deny` 时，扫描器先为历史比较建立当前许可范围内的投影视图，再恢复状态或生成 diff；原始私有历史不被改写。未批准 blocker 不再自动成为事实性 `blocked-by`。

### 3. 图谱层

V0.2 正式关系分为三层：

- `observed`：`contains`、`scans-or-indexes`、`runtime-dependency`、`build-dependency`、`shared-data`、`blocked-by`、`document-reference`；
- `approved-semantic`：人工确认的 `separate-by-design`、`overlaps-with`、`alternative-to`、`replaces`、`complements` 或 `candidate-merge` 判断；
- `ai-candidate`：只存在于私有 review queue 的建议，不进入默认发布图、Markdown、切片或 semantic diff。

扫描器引用另一个项目根只能证明 `scans-or-indexes`，不能升级为运行依赖。普通词面同名不形成关系。启用 Architecture Index 时，派生图另外包含 project `contains` module、module `imports` module 和经过内部符号解析的 module `calls` module 边；每个模块及结构边都绑定项目相对证据。图谱是导航索引，可随时删除重建。

### 4. 生命周期与快照层

`scan` 先完成全部状态解析与 lifecycle resolution，再允许行动裁剪。它可读取上一份显式批准 snapshot，生成 `changes.json` 和 `changes.md`，覆盖项目、目标、next action、blocker、deadline 与关系变化；Git 数量只出现在附录。

`scan` 不自动批准。`approve-snapshot` 在非同步私有目录写入不可变历史和 `latest` 指针，并以独立 approval hash 绑定事实快照。

### 5. 安全策略层

执行白名单 schema、项目级 `allow/summary-only/deny`、secret、绝对路径、URL、邮箱、IP/端口、UNC 地址、Skill 提示注入、引用完整性和 fail-closed 输出检查。未经识别的内容不会“尽量上传”。

### 6. 行动裁剪层

V0.2 优先顺序固定为：批准的 `priority=P0/P1`、`attention=today`、当前 deadline、open blocker、active 且有批准 next action。最多输出三个主项目；超过三个 P0/P1 时失败关闭。每个主项目最多带一个解除当前 blocker 所需的最小依赖端点，未选项目输出具体或聚合原因。没有人工优先级时明确标记 `derived-recommendation`。Skill 清单默认不进入行动切片。

关系切片最多展开 12 条详细边和八个项目；`scans-or-indexes` 与 `document-reference` 默认只计数。架构切片在固定模块与字段上限内，先选择非测试模块，再按问题命中与结构连接量排序；模块内优先保留问题命中符号、内部调用目标和公有入口，避免按字母截断丢失真实修改链路。变化切片在没有上一份批准快照时直接返回不可比较，不把首次扫描中的全部项目当成变化项目展开。

### 7. 发布层

首次构建和重建都会在写入前检查输出目标、项目分片目录及已存在祖先的 symlink/reparse point；问题切片同样拒绝 SOL 保留目录。此为常规文件系统边界检查，不声称防御恶意并发进程替换路径的竞态。

只向用户明确指定的目录写入稳定文件。全景 `build` 生成小型 `ai_context.md` workspace/action 入口、`projects/<project-id>.md` 项目分片、`ai_context_linker.bundle.json` 生成物清单与派生图谱；重建时只会删除上一份清单明确记录且仍带 Linker 生成标记的过期项目卡，不碰同目录的用户文件。可选 `slice` 应只从已批准 manifest 生成更小的问题定向 Markdown。由于 candidate 与 approved manifest 共用事实 schema，生成物只声明输入事实与确定性编译，不自行声称已获批准；发布授权由独立 immutable approval snapshot 证明。核心编译器没有网络能力；Drive 同步由现有桌面客户端或用户操作承担。

## 0.2.1 maintenance decisions

- Discovery restores permissions only after a registry/path identity match;
  existing IDs are reserved before naming new candidates. Private source paths
  are rebased against the previous configuration without reading their contents.
- Entry, cards and slices share lifecycle resolution and optional `--as-of`.
  Only state records are copied; immutable architecture payloads are reused.
- JavaScript/Cargo development and build sections produce `build-dependency`;
  Python extras remain optional runtime dependencies rather than inferred dev groups.
- Python calls resolve through lexical scope or explicit internal imports, and
  JavaScript import matching ignores masked prose. This remains bounded static
  navigation, not complete runtime dispatch analysis.
- Stable state edits report changed field names even when record IDs/statuses
  remain the same. Missing source files reach `needs_review`; inspection errors
  and actual symlinks/reparse points remain rejected.
- The existing atomic writer is the single write implementation. Expected output
  types are checked before bundle writes; interrupted writes retain the previous
  file and remove their temporary file. This is per-file atomicity, not a
  transaction across an entire bundle under hardware failure.
