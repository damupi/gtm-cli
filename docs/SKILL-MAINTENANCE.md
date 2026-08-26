# Keeping the `gtm-cli` Claude skill in sync

The `gtm-cli` skill (`~/.claude/skills/gtm-cli/` — a symlinked directory whose real files
live on the `claude-memory` volume) teaches Claude Code agents how to use this CLI:
`SKILL.md` holds the rules and workflows, and `references/*.md` hold per-resource
command details (tags, triggers, variables, templates).

The skill is **hand-curated and lives outside this repo**, so nothing updates it
automatically. It drifts every time the CLI changes.

## Policy

**Every time there is a new version, release, update, or change to the CLI — any new
command, removed command, new/changed flag, or changed behavior — the `gtm-cli` skill
must be reviewed to see whether it needs updating with the new changes.**

The review happens when a feature branch is merged into `main` (see the
"Release / merge workflow" section in CLAUDE.md). Concretely, check whether the merged
changes make any of the following stale:

- `SKILL.md` **Rules** — absolute claims are the most fragile (e.g. "there is no
  `--json` flag", "`trigger update` only supports `--name`"). A new flag can silently
  falsify them.
- `SKILL.md` command sections and **Typical workflow** — new commands that belong in
  the standard flow (as `workspace quick-preview` did).
- `references/<resource>.md` — command tables, option tables, limitations, and
  examples for the resource that changed.
- Missing sections — a brand-new command group (as `built-in-variable` was) needs its
  own coverage.

## Past drift this policy exists to prevent

- The skill claimed "there is no `--json` flag anywhere in the CLI" after
  `--json-file` shipped on `tag update` / `trigger update` (issue #19).
- `references/triggers.md` said trigger filters "require the GTM UI or the Python
  client directly" after the CLI could do it.
