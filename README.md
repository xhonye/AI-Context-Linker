# AI Context Linker

让 AI 持续看懂你的本地项目，无需上传源码。

> Link your local projects to AI without sharing the codebase.

AI Context Linker 在本地把人工确认的项目事实、关系、风险和待讨论问题编译成一个小型认知包。你只把这个认知包放进专用 Google Drive 目录，ChatGPT 读取的是项目地图，不是整个仓库。

## 它解决什么

- 想聊项目方向、优先级和产品判断时，不必启动 Codex 工程任务。
- ChatGPT 能先理解你正在做什么、项目之间怎样关联、哪些事实已经确认。
- 云端只出现经过允许的最小信息，不出现源码、密钥、本机路径和私人运行数据。
- 图谱帮助模型看到依赖、归属和约束，但图谱始终可从事实重建，不充当事实真源。

## V0.1 已有能力

- 从严格白名单 JSON manifest 生成稳定的 `ai_context_linker.md`。
- 同时生成派生关系图 `ai_context_linker.graph.json`。
- 拒绝未知字段、疑似密钥、本机绝对路径和悬空关系。
- 不扫描仓库、不联网、不上传、不自动读取私人数据。

## 快速体验

```powershell
git clone https://github.com/xhonye/AI-Context-Linker.git
Set-Location AI-Context-Linker
python -m pip install -e .
python -m ai_context_linker build `
  --manifest examples/synthetic-manifest.json `
  --output-dir output
```

然后将 `output/ai_context_linker.md` 放到一个只用于 AI Context Linker 的 Google Drive 目录。不要把源码目录、工作区根目录或私人数据目录加入同步范围。

## 产品边界

AI Context Linker 面向项目发展讨论，不替代 Codex 的代码读取、执行、测试和修改能力。“达到或优于 Work 的头脑风暴体验”是待验证目标，依赖上下文质量，不是当前已证明的事实。

更完整的边界见 `PROJECT_CHARTER.md` 和 `docs/security-boundary.md`。

## Open source

AI Context Linker is licensed under MIT. The standalone CLI and JSON Schema are the product core; `skills/ai-context-linker/` is an optional thin interface for compatible agents. See `CONTRIBUTING.md`, `SECURITY.md`, and `docs/oss-readiness.md` before publishing or contributing.
