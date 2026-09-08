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

The generated `skill_roots` entries remain private configuration. Users may remove roots or add another explicitly approved root with a safe `id`, `provider`, `scope`, and local `path`. Optional human-authored summaries live in an `approved_summaries` map keyed by the declared Skill name.

## Exactly what is read

For every direct child directory of an approved Skill root, the adapter checks for a real, non-linked `SKILL.md`. It reads at most 16 KiB and stops immediately at the closing YAML frontmatter delimiter.

Only these fields can enter the candidate manifest automatically:

- root source identifier;
- provider and user/workspace/custom scope;
- declared `name`, falling back to the Skill directory name;
- a neutral summary-withheld notice;
- a path-free name-only evidence label.

The raw `description` is audited locally but is never copied into the Context. A summary enters only when the user writes or approves a neutral phrase in private configuration:

```json
{
  "id": "codex-user",
  "provider": "codex",
  "scope": "user",
  "path": "C:/Private/skills",
  "approved_summaries": {
    "project-review": "Reviews project direction from approved context."
  }
}
```

The Markdown instruction body, supporting files, scripts, references, assets, tool permissions, shell commands, and absolute Skill root are not read or published.

## Summary privacy checks

Skill descriptions are untrusted metadata. Raw descriptions are withheld and audited for:

- common secret and credential patterns;
- Windows, Unix, and UNC paths;
- URLs and network endpoints;
- email addresses;
- IPv4 addresses and optional ports.
- prompt-override language and commands to call, use, run, execute, upload, send, delete, write, read, trigger, or silently record.

A likely secret fails the whole scan closed. Other unsafe raw content is recorded only as a private finding. Human-approved summaries repeat all checks and fail closed if unsafe; edited manifests cannot bypass the compiler.

These checks reduce accidental disclosure but do not prove that arbitrary prose is anonymous. Human review remains required before publication.
