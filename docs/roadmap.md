# 路线图

`sol-context` 私有原型与当前开源内核的实测差距见
[`prototype-migration-baseline.md`](prototype-migration-baseline.md)。

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
- [ ] 为发现结果提供更清晰的逐项目批准体验；
- decision、capability、document、open_question 节点；
- 事实快照与变化摘要；
- 关系证据、置信度和冲突检测；
- 图谱仍可由事实层重建。

## V0.4 问题定向上下文

- 根据“聊哪个问题”生成更小的上下文切片；
- 衡量事实覆盖率、过期率和泄露拦截率；
- 用同一组真实问题对比普通 Chat、AI Context Linker 和 Codex/Work 的讨论质量。

## V1 可控刷新

- 本地定时构建；
- 有变化才更新稳定文件；
- 高风险变化必须人工确认；
- Drive 仍只接收发布层，不接触原始项目目录。
