# Skill inventory and privacy

AI Context Linker can publish a small capability index so ChatGPT knows which local Skills exist without receiving their instructions, scripts, or installation paths.

## Supported common locations

| Tool | User location | Workspace location |
|---|---|---|
| Codex / shared Agent Skills | `~/.agents/skills` | `.agents/skills` |
| Codex desktop compatibility | `~/.codex/skills` | Use the shared `.agents/skills` workspace location |
| Claude Code | `~/.claude/skills` | `.claude/skills` |
| Gemini CLI | `~/.gemini/skills` or `~/.agents/skills` | `.gemini/skills` or `.agents/skills` |

The location contract is based on the [Codex Skill documentation](https://developers.openai.com/codex/skills/), [Claude Code Skill documentation](https://code.claude.com/docs/en/skills), and [Gemini CLI Skill documentation](https://geminicli.com/docs/cli/skills/). Tool-specific plugin, extension, enterprise, managed, and bundled locations are intentionally excluded from automatic discovery because their ownership and layout differ.

Run discovery with explicit Skill opt-in:

```powershell
python -m ai_context_linker discover `
  --root "C:/Workspace" `
  --include-skills `
  --config-out "C:/Private/ai-context-linker/workspace.json"
```

The generated `skill_roots` entries remain private configuration. Users may remove roots or add another explicitly approved root with a safe `id`, `provider`, `scope`, and local `path`.

## Exactly what is read

For every direct child directory of an approved Skill root, the adapter checks for a real, non-linked `SKILL.md`. It reads at most 16 KiB and stops immediately at the closing YAML frontmatter delimiter.

Only these fields can enter the candidate manifest:

- root source identifier;
- provider and user/workspace/custom scope;
- declared `name`, falling back to the Skill directory name;
- declared `description`, falling back to an unknown-summary notice;
- a path-free frontmatter evidence label.

The Markdown instruction body, supporting files, scripts, references, assets, tool permissions, shell commands, and absolute Skill root are not read or published.

## Summary privacy checks

Skill summaries are untrusted metadata. Before entering the candidate manifest they are checked for:

- common secret and credential patterns;
- Windows, Unix, and UNC paths;
- URLs and network endpoints;
- email addresses;
- IPv4 addresses and optional ports.

A likely secret fails the whole scan closed. Other address-like content causes only that summary to be replaced with a safe omission notice, while the private scan report records the omission. The final manifest compiler repeats the same validation.

These checks reduce accidental disclosure but do not prove that arbitrary prose is anonymous. Human review remains required before publication.
