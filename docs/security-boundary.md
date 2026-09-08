# 安全边界

## 显式文档附件

`slice --include-document PROJECT:PATH` 只选已验证 manifest 中、`cloud_visibility: allow` 项目的既有附件；不会读取本地同名文件或放宽扫描许可。默认切片仍不含正文。所有显式选择合计最多8份、正文256 KiB，超限或引用不存在时拒绝写出；正文保留完整行号和脱敏标记，不按问题截断失败条件。指定附件只影响证据包含，不产生人工批准或改变优先级。附文可能由开发代理整理，不能将其称为编译器自动分析结果。

`attach_files` 默认空，仅允许 `cloud_visibility: allow` 的项目选择 `allow_files` 中的元数据文档。附件进入候选 manifest，受严格 schema、全文安全校验、事实哈希和原有审核流程约束。不会自动附上任意源码、原始会话或全局记忆。

采集时替换包含已知秘密、绝对路径或敏感地址的整行，私钥块连同正文一起替换。保留原始行号和脱敏标记，不以删掉危险片段后的残句冒充原文。附件使用足够长的代码围栏并带有 UNTRUSTED_DATA 声明，AGENTS 内容只是待分析资料。这些措施不能保证模型永不受提示注入影响，也不能识别所有业务秘密；分享前仍应核对候选。

每项目最多 8 份，每份输入及脱敏文本不超过 64 KiB，合计不超过 256 KiB。文件缺失、越界、附件路径经过链接、格式错误或超过预算时拒绝生成，不静默截断。重新发现只为同一项目保留附件配置。旧配置不扩大导出范围；已授权的元数据读取不自动等于正文附带授权。

## 项目级语义门禁

- `discover` 产生的项目默认是 `sensitivity: private`、`cloud_visibility: deny`、`redaction_profile: standard`。默认状态不读取该项目元数据用于发布，项目及其关系都不进入候选。
- `cloud_visibility: allow` 必须同时显式填写 `sensitivity` 与 `redaction_profile`；此时才启用项目元数据、状态与派生关系采集。
- `cloud_visibility: summary-only` 必须同时填写人工批准的 `approved_summary`，只允许该摘要进入 Context，不发布 Git、状态、约束、风险、证据或自动关系。
- `cloud_visibility: deny` 完全排除该项目，并移除任何会暴露它的正式关系。review-state 与 session-summary 即使含有该项目，也不会进入候选包。
- `sensitivity` 取值为 `public`、`internal`、`private` 或 `highly-sensitive`。医学、法律、雇主内网与真实投资项目应由用户明确选择 `summary-only` 或 `deny`；系统不靠关键词猜测后放行。

## 显式允许后可发布

- 项目名称和非敏感简介；
- 用户明确确认的目标、状态、约束和决策；
- 脱敏后的进展信号、风险和开放问题；
- 不含本机路径的证据标签；
- 从上述事实派生的项目关系。

## 默认禁止发布

- 源码、补丁、完整 Git 历史和仓库压缩包；
- 密钥、令牌、密码、连接串和认证文件；
- 驱动器根目录、用户目录等本机绝对路径；
- 私人日志、投资账户、医疗材料和原始行为数据；
- 未经确认的模型推断；
- 整个工作区或 Drive 根目录。

## Google Drive 风险

ChatGPT 的 Google Drive 集成会访问或索引用户授权范围内的内容。因此发布目标必须是专用最小目录，里面只放生成后的认知包。不能把项目仓库、工作区根目录或私人数据目录作为同步源。

## V0.1 防线

- 严格字段白名单；
- 疑似 secret 检测；
- Windows 与 Unix 绝对路径检测；
- URL、邮箱、IP/端口和 UNC 地址检测；
- 关系端点完整性检查；
- 原子写入；
- 未通过校验时不产生新包。

这些检测降低意外泄露风险，但不能证明所有自然语言都已脱敏。真实发布前仍应保留一次人工预览。

每个 Markdown 输出面均声明项目文本为 `UNTRUSTED_DATA`，但警示本身不能保证任意模型抵御提示注入。盲评应限制工具和可读文件，且明确区分人工批准、模型判断与未知。

项目撤权同时约束历史：`summary-only` 不得包含详细状态、信号、证据、架构或关系；显式 `deny` 的别名不应经 generated diff 重新暴露。私有批准历史保留原件，不因新的公开范围被改写。首次/重复 bundle 与 slice 写入均检查已存在路径及祖先中的链接和 Windows reparse point；不承诺抵御恶意本机进程的并发路径替换。

## V0.2 本地采集边界

- workspace 配置是私有文件，可包含本机项目路径，但不得放入发布目录。
- 采集器只读每个项目明确列出的 `allow_files` 文本和 `observe_paths` 存在性；`allow_files` 还必须属于内置项目元数据文件名单，不接受源码文件；常见 secret、credential、SSH 和数据库路径即使只检查存在性也会被拒绝。
- 元数据文件限制为 64 KiB UTF-8 文本，禁止路径穿越和文件符号链接。
- Git 信号只记录分支、变更路径数和最新提交时间，不读 diff，不把活跃度当成价值。
- 候选 manifest 和扫描报告不包含项目根路径；发布仍是独立的第二步。
- `facts_sha256` 在 build 时会重新计算；审阅后内容被修改但哈希未更新时会失败关闭。
- `snapshot_changes.changes_sha256` 独立绑定比较视图；`facts_sha256` 不包含该视图，避免仅更换上一份基线就改变同一事实快照的身份。
- README、AGENTS 等自然语言仍属于不可信输入；工具不会声称自动识别所有隐私或提示词注入，真实候选 manifest 必须人工审阅。
- `review_dir` 显示命中常见 Google Drive、OneDrive、Dropbox 或 iCloud 目录名时会被拒绝，避免未审阅候选文件先行同步；这是防误操作护栏，不是通用云盘检测。
- `discover` 只枚举用户显式指定根目录的直属子目录和项目标志存在性；包含绝对路径的候选配置属于私有输入。目录链接、Windows reparse point、解析后越出根目录的候选以及常见生成目录会被排除。
- 自动从 README 提取的标题或摘要若包含绝对路径，会降级为待人工补充；疑似 secret 仍使整个扫描失败关闭。用户手填字段始终经过完整发布校验。
- 文件名清单适配器有目录剪枝、深度与条目上限；只发布固定入口文件名、测试数量和是否截断，不发布任意文件名。Git 变更只发布粗粒度分类数量，不发布具体路径。
- 手工 workspace 配置不能绕过目录边界：项目根与 `.git` 的 symlink 或 Windows reparse point 会被拒绝或跳过。
- 开放事项只来自已批准的根目录 README、AGENTS、CLAUDE、ROADMAP、TODO、STATUS、CHANGELOG 或 PROJECT_CHARTER 中的 Markdown 未完成复选项，最多 5 条并经过发布安全校验；源码 TODO、内部 `task_plan.md`/`progress.md`、任意任务数据库和私人运行记录不属于默认采集面。
- 项目约束只来自已批准的 AGENTS、CLAUDE 或 PROJECT_CHARTER 中标题明确为边界、合同、原则、安全、非目标或存储的小节，最多 8 条；其他工作流指令不进入约束字段，所有条目仍经过 secret 与绝对路径拦截。
- 依赖关系只解析经审阅的固定根目录依赖清单，且只在目标包身份唯一时成立；文档引用只认 Markdown 代码标记或链接，并过滤普通正文和重复模板。二者都不读取或发布源码正文，文档引用不会升级成依赖证明。
- 可选 `code_relationship_scan` 默认关闭，必须在每个私有项目配置中显式开启。它只扫描固定代码/配置扩展名，受深度、条目数、文件数和 256 KiB 文件大小上限约束，并跳过隐藏目录、测试、fixture、敏感文件名、依赖、生成目录、symlink 与 reparse point。输出只含项目 ID 和相对文件行号，不含源码行、secret 或绝对根路径；扫描报告必须披露读取文件数与截断状态。
- `slice` 只读取已通过上述校验的 manifest；问题文本限制为 500 字符并再次执行 secret 与绝对路径拦截。它不调用模型，不把问题或选择规则写回事实层。
- Skill 扫描必须由 `--include-skills` 或私有配置中的 `skill_roots` 显式开启。适配器只读取每个直属 Skill 目录中最多 16 KiB 的 YAML frontmatter，并在结束分隔符处停止；不读取指令正文、脚本、references 或 assets。
- 原始 Skill description 一律视作 `UNTRUSTED_DATA`，只在本地审计，不自动进入候选 manifest。默认发布名称与中性 withholding notice；能力摘要只能来自私有配置逐项填写的 `approved_summaries`。
- 原始和批准摘要除通用 secret 与绝对路径规则外，还检查 URL、邮箱、IP/端口、UNC 地址和命令式提示注入，包括覆盖上文、强制调用、上传、发送、删除、执行或静默记录。疑似 secret 使扫描失败；不安全原始摘要仅记入私有报告；不安全的人工批准摘要失败关闭。
- Skill 数据区在 Markdown 中显式标为 `UNTRUSTED_DATA`。本机 Skill 根路径只存在于私有配置；链接、reparse point、隐藏目录和非标准入口会跳过或失败关闭。
- `discover` 只把固定项目状态文件列入私有 `state_file_candidates`，不会自动加入读取白名单。人工移入 `state_files` 后，适配器才抽取明确行动标题下的列表项；每个文件、条目和项目都有上限。输出保留项目 ID、相对文件和行号，绝对路径或疑似 secret 使扫描失败。
- `session_summary_files` 只接受显式列出的中立 JSON 摘要。允许字段固定为完成项、决定、卡点、下一步和未决问题；`messages`、prompt、tool log 等原始会话形态字段不被接受。核心包不知道任何聊天工具的历史目录，扫描报告固定披露 `raw_transcripts_read: 0`。
- 会话摘要只能补充 `session-summary` 来源的陈述；项目自有状态文件优先于完全相同的会话条目。会话日期决定 freshness，未来日期或过期内容不能进入当前行动选择。

## V0.2 行动状态与关系审批边界

- `preview-review-state` 只读取明确的 manifest、草稿和一至三个项目 ID；不恢复 `summary-only` 或未明确允许详细信息的项目。核对单始终未批准，不导入草稿或自动延长有效期。使用同一状态 schema 和敏感文本检查，原文经 Markdown/HTML 转义，输出不带输入路径。
- 核对单拒绝写入 Git 仓库、已知云盘目录、SOL/Linker 保留目录及已有正式入口的目录；检查未解析路径及祖先的链接/reparse point，不覆盖不同内容。目录名称检查仍不能证明任意目录没有同步，提示注入警示与转义也不能证明所有模型安全。

- 私有 `review_state_files` 是 current action 的人工权威入口。允许字段固定为 priority、activity、attention、why-now、goal、next action、done-when、owner、deadline、blocker、更新时间与过期时间；输入大小、文件数和每项目条目数均有限制。
- approved-review 优先于自动抽取状态，但不覆盖、删除或改写原始项目事实。没有批准值时保持 unknown；Git 活跃度、文件数量、关系数量和项目名称不得填补状态或优先级。
- v0.2 状态使用稳定 record ID 和显式 lifecycle。文件消失只转为 `needs_review`；只有同一稳定 ID 的明确状态或显式 `supersedes` 能关闭旧记录。`resolved`、`superseded`、`stale`、`needs_review` 与未来日期不参与 open action 裁剪。
- `scan` 只生成候选和变化，不产生批准。`approve-snapshot` 必须单独调用，其历史目录若显式命中常见同步目录会失败；批准记录用独立 hash 绑定已验证 fact hash。
- 语义差异只发布项目 ID、状态种类、稳定 record ID、状态转换与关系键；不发布本机根路径。Git 数量只放附录，不参与变化语义或优先级。
- 关系层固定为 `observed`、`approved-semantic` 和 `ai-candidate`。AI candidate 输入必须来自显式私有 JSON，只能写入 `relationship-review-queue.json`，自动提升计数固定为 0。
- 默认 Markdown、图谱、问题切片与 semantic diff 全部排除 `ai-candidate`。人工批准需要把关系显式写入私有配置并选择 `approved-semantic` layer，不能直接把模型候选当作事实。
- 精确项目根引用只产生 `scans-or-indexes`，不证明 runtime dependency。普通正文同名不会形成关系；document reference 也不会升级为依赖。
- Priority Slice v2 在完整 lifecycle resolution 后运行，只读取 open 且未过期的批准行动状态。顺序从 P0/P1 开始；超过三个高优先级项目时失败关闭。最多三个主项目，每个最多一个最小 blocker endpoint，并输出未选原因；默认不输出 Skill 清单或端点的无关产品约束。

## Rediscovery identity and writes

An existing project ID is reserved across discovery. Prior policies apply only
to a matched registry/path identity, never to a new folder that happens to take
the same name. Rediscovery preserves explicit private source configuration;
subsequent scan validation still applies. Publication checks unresolved paths
before resolution and rejects links/reparse points and non-file output targets.
Atomic writes share one implementation; this is not an adversarial filesystem
sandbox or a multi-file transaction.
