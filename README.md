🌐 **简体中文** · [English](README.en.md)

<p align="center">
  <img src="docs/assets/brand-header.svg" width="860" alt="AI Context Linker：紫色星光字标与链条标识">
</p>

<h1 align="center">AI Context Linker · 让 ChatGPT 看懂你的本地项目</h1>

<p align="center">
  <a href="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml"><img src="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

**让 ChatGPT 看懂项目，把 Codex 留给开发执行。**

代码还没开始改，你已经和 Codex 聊了很久：现状是什么、先做哪个功能、几个项目能不能合并。想换到 ChatGPT 继续讨论，又得重新介绍背景、整理文件。

**AI Context Linker 帮你准备这份背景资料。** 把选定的本地项目说明和经核对的进展整理成一份 `ai_context.md`，交给 ChatGPT 分析、比较方案；选好方向后，再让 Codex 核验并实施。换个聊天，也不用从头介绍几个项目。

不用先搭 MCP 服务，也不用上传整个代码仓库。适合用 Codex 等本地 AI agent 做项目的人；目前通过 agent 或命令行安装。

[让 AI agent 帮你安装](#让-ai-agent-帮你安装) · [接入第一个项目](docs/quickstart-zh-CN.md)

## 让 AI agent 帮你安装

把下面这段复制给能在你电脑上执行命令的 AI agent：

```text
请安装 https://github.com/xhonye/AI-Context-Linker ，先阅读仓库的 INSTALL.md。
检查环境，采用隔离安装，再运行内置 demo，把生成的 ai_context.md 打开给我看。
安装和演示可以直接完成；演示不扫描我的真实项目，不上传。
然后帮我接入选定的真实项目：配置由你处理，我只核对分享范围和简报内容。
```

[安装说明（给 agent）](INSTALL.md)包含环境检查、安装、演示、失败处理和卸载。首次真实使用仍需你指定项目并核对内容。

**自己执行命令？** 需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Git；uv 可准备 Python 3.11 的隔离环境：

```sh
uv tool install --python 3.11 git+https://github.com/xhonye/AI-Context-Linker.git@v0.2.7
ai-context-linker demo --output-dir ./linker-demo
```

从仓库之外的本地目录运行演示，输出目录必须是新的。打开打印出的 `ai_context.md` 即可看到结果。演示使用虚构项目，不读取你的文件。

## 安装好后怎么用？

首次使用：告诉 agent 你想聊哪些项目，提供项目名称或大概位置。它会帮你确认范围，让 Linker 只整理选定项目，生成 `ai_context.md`。

项目有新进展时，跟 agent 说：

> 更新 ai_context

核对更新后的简报，再交给 ChatGPT 聊。

## 如何和网页版 ChatGPT 交互

打开网页版的普通 Chat，上传最新的 `ai_context.md`。也可以配置专用 Google Drive 目录自动同步，并连接到账号支持的 ChatGPT 功能，省去每次手动上传。

| 你现在想做什么 | 怎么配合 |
|---|---|
| “这几个项目，今天先推进哪个？” | Linker 整理已核对的目标、卡点和下一步，ChatGPT 帮你比较 |
| “先别写代码，帮我看看方案。” | 把简报交给 ChatGPT，讨论取舍和缺少的证据 |
| “方向定了，开始做。” | 把选定方案交给 Codex，核对实际代码后实施、验证 |

本地资料 → **Linker 简报** → **ChatGPT 讨论方案** → **Codex 开发执行**。

这里指普通 Chat；[ChatGPT Work 与 Codex 共享用量](https://learn.chatgpt.com/docs/pricing)。

## 从数字生命卡兹克的文章来？

卡神在[这篇文章](https://mp.weixin.qq.com/s/abqrwY1T1WieYW5xDFKRRg)里分享了“ChatGPT 分析规划、Codex 开发执行”的工作流。我也在留言区分享了自己用项目简报衔接上下文的小尝试，没想到收到了卡神的回复：**“也是个好思路！”**（第一次被卡神回复，感动！）

卡神文章中的 MCP 可以按需查询生产数据，Linker 则把选定的项目资料整理成简报。如果你主要想做日常项目规划和讨论，可以先从 Linker 上手，边用边探索适合自己的工作方式。

感谢卡神的分享和鼓励，让更多人看到了这个小项目！也推荐大家去看看他的开源项目 [Khazix Skills](https://github.com/KKKKhazix/khazix-skills)。

## 读取与分享范围

- 本地编译器不调用模型 API；零第三方 Python 运行时依赖。安装下载和 agent 自身运行另计。
- 新项目默认不导出；只收集明确允许的资料，默认不读取源码正文或原始聊天记录。
- 输出带敏感信息检查，但项目说明本身也可能敏感，分享前仍需核对。
- 没有记录的进展仍是未知；简报不会自动补齐生产数据，也不会让所有聊天自动更新。
- 首次接入时，agent 会检查简报是否包含完整项目说明和选定资料，确认单独上传即可阅读。需要你确认的资料不会自动扩大。

## 效果评估

我之前用 GPT-5.6 Sol，以纯 AI 的方式阅读、理解本地项目，再产出 Markdown 简报。随后反复迭代 AI Context Linker 的纯 Python 脚本，把两种方式产出的简报交给 ChatGPT 对照评估。

**在我的自用测试中，经 ChatGPT 对照评估，脚本产出的简报已能达到与前者基本相当的项目讨论效果。** 这个结论限于我的项目和所测问题，属于个人使用观察。详见[对照观察与评估范围](docs/question-test-observations.md)。

**对我来说，直接的收益是整理资料更省时、更省 token。** Python 编译器生成简报时不调用模型，省去了反复让 AI 阅读、归纳的生成开销。后续在 ChatGPT 网页版聊项目，走网页版单独用量，不占用 Codex 宝贵额度。

<details>
<summary>查看此前的匿名结果卡</summary>

以下为 AI 重新排版的匿名观察结果，不是原始聊天证据；完整条件与局限见上方说明。

![第一轮：缺失资料可能导致重复开发建议](docs/assets/round-1-anonymized.png)

![第二轮：补齐业务资料后，回答更有依据](docs/assets/round-2-anonymized.png)

</details>

## 交流与反馈

装不上、用不顺，或者想加什么功能？欢迎直接反馈，也欢迎分享你是怎么用 Linker 的。

- **QQ 交流群：** `1080546295`
- **GitHub Issues：** [使用求助、Bug 和功能建议](https://github.com/xhonye/AI-Context-Linker/issues)

可以直接在群里聊，需要持续跟进的问题，我会整理到 GitHub Issues。

## 更多资料

[详细命令与配置](docs/reference-zh-CN.md) · [安全边界](docs/security-boundary.md) · [架构](docs/architecture.md) · [贡献指南](CONTRIBUTING.md) · [MIT 许可](LICENSE)

如果它确实减少了你重复介绍项目的时间，欢迎点 Star。

## Star History

<a href="https://www.star-history.com/?repos=xhonye%2FAI-Context-Linker&amp;type=date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=xhonye/AI-Context-Linker&amp;type=date&amp;theme=dark&amp;legend=top-left" />
    <img alt="AI Context Linker Star History" src="https://api.star-history.com/chart?repos=xhonye/AI-Context-Linker&amp;type=date&amp;legend=top-left" />
  </picture>
</a>
