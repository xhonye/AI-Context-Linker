# 架构

```text
本地项目与私人事实
        |
        v
受审计的本地采集器（只读 allowlist 元数据）
        |
        v
人工批准的事实 manifest  <-- 事实真源
        |
        +--> 安全策略门：字段白名单、密钥与路径检测、关系校验
        |
        +--> Markdown 简报
        |
        +--> 派生关系图 JSON
        |
        v
明确指定的发布目录 -> 专用 Google Drive 目录 -> ChatGPT Chat
```

## 层次

### 1. 证据层

V0.2 可读取用户明确列出的 README/AGENTS、Git 元数据和指定路径存在性。它不读源码正文，本机路径只存在于私有配置，不进入候选 manifest 或发布包。

### 2. 事实层

保存已确认的项目目标、状态、信号、风险、问题与证据引用。事实、推断和未知分别表达，不能混写。

### 3. 图谱层

V0.1 支持 workspace、project 节点以及 contains 和用户明确记录的关系类型，例如 depends-on、supports、blocks、replaces、related-to。关系类型必须使用安全的短标识。后续可扩展 decision、capability、document、data_asset、open_question 节点。

每条未来的自动推导关系都应带来源、观察时间和置信度。图谱是导航索引，可随时删除重建。

### 4. 安全策略层

执行白名单 schema、危险文本检测、引用完整性检查和 fail-closed 输出。未经识别的内容不会“尽量上传”。

### 5. 发布层

只向用户明确指定的目录写入两个稳定文件。核心编译器没有网络能力；Drive 同步由现有桌面客户端或用户操作承担。
