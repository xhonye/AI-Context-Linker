🌐 [简体中文](README.md) · **English**

<p align="center">
  <img src="docs/assets/brand-header.svg" width="860" alt="AI Context Linker — purple starlight wordmark and connected-link logo">
</p>

<h1 align="center">AI Context Linker · Local project context for ChatGPT</h1>

<p align="center">
  <a href="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml"><img src="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

**Give ChatGPT the project context. Bring the chosen plan back to Codex.**

Before changing any code, you may spend a long conversation in Codex understanding the project, comparing features, or deciding what to tackle first. Switching to ChatGPT means explaining the background and gathering files again.

**AI Context Linker prepares that context.** It turns selected local documents and reviewed project state into `ai_context.md`. Share it with ChatGPT to compare options, then bring the chosen plan to Codex for code-level verification and implementation. Reuse the briefing across project discussions.

No MCP server or whole-repository upload is needed for this file-based workflow. For people building local projects with a coding agent; installation currently uses an agent or CLI.

[Ask your agent to install](#ask-your-agent-to-install) · [Connect a real project](INSTALL.md#4-connect-selected-projects-when-requested)

## Ask your agent to install

Copy this to an agent that can execute commands on your computer:

```text
Install https://github.com/xhonye/AI-Context-Linker after reading its INSTALL.md.
Check prerequisites, use an isolated installation, run the built-in demo,
and open the generated ai_context.md for me.
Proceed with installation and the synthetic demo; do not scan my real projects or upload.
Then help me connect my selected projects: handle the configuration and let me review
which information will be shared and the resulting briefing.
```

The [agent installation guide](INSTALL.md) covers prerequisites, installation, verification, failures, and removal. Real project use still requires your selection and content review.

**Prefer commands?** With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git available, uv can provision an isolated Python 3.11 environment:

```sh
uv tool install --python 3.11 git+https://github.com/xhonye/AI-Context-Linker.git@v0.2.6
ai-context-linker demo --output-dir ./linker-demo
```

Run the demo from a local directory outside repositories. The output directory must be new. Open the printed `ai_context.md` path. The fictional demo reads no real projects. The current demo and generated headings are in Chinese.

## After installation: everyday use

First time: tell your agent which projects you want to discuss, using their names or approximate folder locations. It confirms your selection and has Linker generate `ai_context.md` for those projects.

When projects change, tell your agent:

> Update ai_context

Review the refreshed briefing, then bring it to ChatGPT.

## How to work with ChatGPT on the web

Open ordinary Chat on the ChatGPT website and upload the latest `ai_context.md`. Alternatively, configure a dedicated Google Drive sync folder and connect it to ChatGPT if supported by your account, avoiding repeated manual uploads.

| What you want to do | How the tools work together |
|---|---|
| “Which project should I advance today?” | Linker supplies reviewed goals, blockers, and next actions; ChatGPT helps compare them |
| “Help me evaluate the plan before coding.” | Share the briefing and discuss trade-offs and missing evidence |
| “The direction is clear. Let's build.” | Give the chosen plan to Codex to check against the code, implement, and validate |

Local documents → **Linker briefing** → **ChatGPT discussion** → **Codex development**.

Use ordinary Chat here; [ChatGPT Work shares usage with Codex](https://learn.chatgpt.com/docs/pricing).

## Community conversation

In [his Chinese-language article](https://mp.weixin.qq.com/s/abqrwY1T1WieYW5xDFKRRg), Khazix described planning in ChatGPT and implementing with Codex. I shared my small experiment with file-based project context in the comments and was delighted when he replied “也是个好思路！” (“That's a good approach too!”).

The MCP setup in Khazix's article queries production data on demand, while Linker turns selected project information into a briefing. If your main goal is everyday project planning and discussion, you can start with Linker and explore the workflow that suits you as you go.

Thank you, Khazix, for the encouragement and for helping people discover this small project! I also recommend checking out his open-source [Khazix Skills](https://github.com/KKKKhazix/khazix-skills).

## Scope and privacy

- The local compiler makes no model API calls and has no third-party Python runtime dependencies. Installation downloads and your agent's own operation are separate.
- New projects are excluded by default. Only explicitly permitted information is collected; source-code bodies and raw conversations are outside the default scan.
- Sensitive-data checks help, but project descriptions can themselves be sensitive. Review before sharing.
- Missing progress remains unknown. A briefing does not fill gaps in production data or automatically update every conversation.
- During first-project setup, the agent must verify that the briefing contains the project details and selected documents needed for a single-file upload, within your approved scope.

## Effectiveness evaluation

I previously used GPT-5.6 Sol to read and understand my local projects and produce Markdown briefings through an AI-driven workflow. I then iterated on AI Context Linker's pure Python approach and used ChatGPT to compare the resulting briefings for project discussions.

**In my own tests, ChatGPT's comparison found the script-generated briefings supported broadly comparable project discussions.** This is my experience with the projects and questions tested, not an independent benchmark or a guarantee for every task. See the [observations and evaluation limits](docs/question-test-observations.md).

**The practical benefit is less time and fewer tokens spent preparing context.** The Python compiler generates the briefing without model calls, avoiding repeated AI reading and synthesis during generation. Continue discussing your projects in ChatGPT on the web, using its separate chat allowance without consuming your valuable Codex quota.

<details>
<summary>Earlier anonymized result cards (Chinese)</summary>

These AI-redrawn cards summarize anonymized observations, not original chat evidence. See the conditions and limitations linked above.

![Round one: missing evidence can lead to redundant development advice](docs/assets/round-1-anonymized.png)

![Round two: reviewed business evidence supports more grounded answers](docs/assets/round-2-anonymized.png)

</details>

## Community & Feedback

Need help getting started, ran into a bug, or have a feature idea?
[Open an issue](https://github.com/xhonye/AI-Context-Linker/issues)—and feel free to tell me how you're using Linker.

## More

[Commands and configuration](docs/reference.md) · [Security boundary](docs/security-boundary.md) · [Architecture](docs/architecture.md) · [Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)

If it saves you repeated project introductions, a Star helps others find it.

## Star History

<a href="https://www.star-history.com/?repos=xhonye%2FAI-Context-Linker&amp;type=date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=xhonye/AI-Context-Linker&amp;type=date&amp;theme=dark&amp;legend=top-left" />
    <img alt="AI Context Linker Star History" src="https://api.star-history.com/chart?repos=xhonye/AI-Context-Linker&amp;type=date&amp;legend=top-left" />
  </picture>
</a>
