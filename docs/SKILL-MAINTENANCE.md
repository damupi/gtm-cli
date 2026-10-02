# Keeping the repository AI assets in sync

The repository owns two portable AI capability assets:

- `skills/gtm-cli/` teaches an agent how to operate this CLI safely and correctly.
- `agents/google-tag-manager-admin.md` defines the planning, approval, validation, and reporting workflow for GTM administration.

These files are canonical. Copies installed in a particular AI coding tool are consumers, not sources of truth.

## Policy

Every CLI release or behavior change must include a review of the affected AI assets in the same pull request. This includes any new, removed, or renamed command; changed option; changed output shape; changed confirmation behavior; credential-handling rule; or mutation workflow.

Review:

- `skills/gtm-cli/SKILL.md` – cross-command rules, safety gates, auth, validation, and standard workflow.
- `skills/gtm-cli/references/*.md` – command tables, options, limitations, and examples for the changed resource.
- `agents/google-tag-manager-admin.md` – planning, scope, approval, validation, and publishing assumptions.
- `docs/AI-USAGE.md`, `README.md`, and the command table in `AGENTS.md` when the public command surface changes.

Validate documented commands against the current nested `--help` output. Avoid copying every help option into the skill or agent: `--help` owns exact syntax, the skill owns non-obvious tool behavior, and the agent owns operational workflow and safety.

## Portability

Do not hard-code installation paths or metadata for one AI product in the repository assets. An AI environment may adapt unsupported frontmatter when installing the files, but it must preserve the prompt body and safety gates.

Keep company-specific account IDs, naming standards, Jira workflows, and implementation conventions outside these portable assets.

## Past drift this policy exists to prevent

- The skill claimed there was no `--json` support after `--json-file` shipped for tag and trigger updates.
- Trigger documentation said nested filters required the GTM UI after the CLI could update them.
- A locally installed administration agent still claimed Custom Templates and custom-event trigger creation were unsupported after both issues had been fixed.
