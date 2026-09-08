# 路线图

`sol-context` 私有原型与当前开源内核的实测差距见
[`prototype-migration-baseline.md`](prototype-migration-baseline.md)。

“今天推进什么、项目卡在哪里、下一步是什么”的能力追平计划见
[`sol-context-parity-plan.md`](sol-context-parity-plan.md)。该能力是当前最高优先级；
安全、体积和确定性指标不能替代行动建议质量。

## V0.1 安全认知包

- 人工批准 manifest；
- Markdown 项目简报；
- 派生关系图；
- secret、路径、schema 和关系校验；
- 显式本地发布目录。

## V0.2 确定性适配器

- [x] 从 `sol-context` 迁移经过收窄的 repo facts 读取逻辑；
- [x] 只读允许的元数据文件，不读源码正文，不导入 AI enrichment；
- [x] 为自动采集事实保留类型化证据标签和快照哈希；
- [x] 发布前展示新增、删除、变化项目和关系预览。

## V0.3 安全发现、变化与图谱

- [x] 从显式工作区根目录浅层发现项目候选；
- [x] 排除链接、reparse point、根目录逃逸、常见生成目录和云盘配置目标；
- [x] 增加限量文件名清单、Git 粗粒度变化和批准元数据开放事项；
- [x] 从固定结构化依赖清单和明确 Markdown 引用生成分级关系；
- [x] 提供默认关闭、逐项目批准的 code-path 关系适配器，不发布源码行或绝对根路径；
- [ ] 为发现结果提供更清晰的逐项目批准体验；
- decision、capability、document、open_question 节点；
- [x] 事实快照与变化摘要；
- [x] 关系证据与分级；
- [ ] 关系置信度和冲突检测；
- [x] 图谱仍可由事实层重建。

## V0.4 问题定向上下文

- [x] 根据“聊哪个问题”确定性生成更小的上下文切片；
- [x] 对优先级、下一步、关系、变化和指定项目问题保留事实、派生与未知边界；
- [x] 衡量事实覆盖率和泄露拦截率；
- [ ] 衡量事实过期率；
- [ ] 用固定真实问题持续对比 AI Context Linker 与 `sol-context`；2026-08-27 实测确认行动型问题尚未达到替代门槛。

## V0.5 行动上下文追平

- [x] 建立同模型、同问题、同项目集的可复现 A/B 评测框架；真实首轮尚待运行；
- [x] 通过上一份私有配置与 opaque Git-origin hash 复用稳定项目 ID；无唯一 origin 的移动项目仍需复核；
- [x] 增加 v0.2 私有 review-state，覆盖 priority、activity、attention、why-now、goal、next action、done-when、owner、deadline、blocker 与有效期；
- [x] 将状态统一为稳定 StateRecord，支持 open、resolved、superseded、stale、needs_review，且来源消失不自动视为 resolved；
- [x] 增加中立 JSON 脱敏会话摘要适配器，不扫描原始会话；
- [x] 增加独立 `approve-snapshot` 历史与目标、next action、blocker、deadline、关系的语义变化报告；
- [x] 生命周期解析后按固定顺序选择最多三个主项目及最小 blocker 依赖端点，输出未选原因，并对超过三个 P0/P1 的人工冲突失败关闭；
- [x] 图谱区分 observed、approved-semantic、ai-candidate，并将 AI 候选隔离到私有 review queue；
- [x] 建立 13 场景 synthetic gold suite，当前全部配置闸门通过；
- [x] 增加项目级 `allow/summary-only/deny` 语义门禁；未分类项目默认 `deny`，`deny` 项目及关系不进入候选；
- [x] 原始 Skill description 改为只审计不发布，只有私有配置逐项批准的中性摘要可进入 Context，并增加命令式注入检测；
- [ ] 连续两次真实更新达到 `sol-context` 同题能力后，才完成默认替代。

## V0.6 结构上下文超越

- [x] 增加默认关闭、逐项目 `architecture_visibility` 批准的 Python/JavaScript/TypeScript Architecture Index；
- [x] 只发布相对模块、class/function、imports、外部包、测试模块和内部 syntactic calls，不发布源码正文、注释、docstring、字符串值、默认值或绝对路径；
- [x] 过滤 `append/get/str/map` 等泛化调用，并只保留能解析到内部模块符号的 calls；
- [x] 将发布包拆为小型 `ai_context.md`、`projects/<project-id>.md` 和项目/模块 graph；
- [x] Architecture map hash 进入项目事实和 semantic diff；
- [x] 增加结构 synthetic gold evaluator 与百分比闸门；
- [ ] 用同一 Pro 模型完成 Linker 与 SOL 的固定代码导航问题盲测。

## V0.7 真实替代验证

- [x] 本地 Q1-Q6 双顺序盲评输入冻结与原始输出审计；缺状态时仅评拒答，不代替 Pro 验收；
- [ ] 为真实项目补齐人工批准且有 expires_at 的 current action review state；
- [ ] 用同一模型、同一问题、同一批准项目集完成首次私有 A/B；
- [ ] 完成第二次独立刷新，验证 lifecycle、semantic diff 与优先切片没有退化；
- [ ] 两次均达标后再讨论冻结 `sol-context`，否则继续保持 rollback benchmark。

## V1 可控刷新

- 本地定时构建；
- 有变化才更新稳定文件；
- 高风险变化必须人工确认；
- Drive 仍只接收发布层，不接触原始项目目录。

## 跨工具 Skill 能力索引

- [x] 扫描 Codex/Agent Skills、Claude Code 与 Gemini CLI 常见用户和项目位置；
- [x] 只读取 `SKILL.md` 的名称与摘要 frontmatter 作本地审计，不读取指令正文；原始摘要不自动发布；
- [x] 对原始及人工批准摘要执行 secret、路径、URL、邮箱、IP、UNC 与命令式提示注入检查；
- [x] 在全景和 Skill 定向问题切片中发布无路径能力索引；
- [ ] 支持插件与企业托管 Skill 的显式适配器。
