---
name: shea-symphony-doctor
description: Use when diagnosing 3D-RAMS workflow blockers, local verification failures, stuck issues or PRs, missing evidence, install-health gaps, and safety-boundary risks, then giving one concrete repair path.
---

# Shea Symphony Doctor

Use this skill for read-first triage in this 3D-RAMS repository. Keep the
`shea-symphony` skill name; the migrated workflow targets 3D-RAMS.

## Repository

Default repository: `Capitano00/3D-RAMS`

Default local checkout: the current 3D-RAMS repo root.

Project anchors:

- `AGENTS.md`
- `CONTRIBUTING.md`
- `README.md`
- `docs/`
- `scripts/check-demo.sh`

## CLI Defaults

Default to the Shea CLI for workflow readiness and lane state. Run it from the
3D-RAMS repo root, never from the `shea-symphony` engine checkout:

```bash
GH_TOKEN="$(gh auth token --user Alive24)" \
cargo run --manifest-path ../shea-symphony/Cargo.toml -- \
autopilot plan .shea/workflows/shea-symphony.md
```

For one automated lane tick, use:

```bash
GH_TOKEN="$(gh auth token --user Alive24)" \
cargo run --manifest-path ../shea-symphony/Cargo.toml -- \
autopilot loop .shea/workflows/shea-symphony.md --once --write
```

Use `gh` reads, Git state, and local verification only for focused diagnosis or
when the CLI command fails. Record the exact CLI blocker before falling back.

## Operating Rule

Start with read-only diagnosis:

```bash
git status --short --branch
gh issue view <issue> --repo Capitano00/3D-RAMS --comments
gh pr view <pr> --repo Capitano00/3D-RAMS --json number,title,state,url,isDraft,baseRefName,headRefName,mergeStateStatus,reviewDecision,statusCheckRollup
bash scripts/check-demo.sh
```

Run only the commands that match the blocker. Do not run AWS, Bedrock, or hosted
smokes unless the task explicitly needs them and credentials are already safe.

Report:

- exact finding or failing check;
- blocker vs warning;
- affected issue, PR, worktree, file path, or local skill path;
- safest repair path;
- whether the repair can be executed in this session;
- any operator decision still needed before writing.

## Repair Shape

End with one concrete next action:

- route to `$shea-symphony-manual-main`, `$shea-symphony-manual-review`,
  `$shea-symphony-human-review`, or `$shea-symphony-manual-merge`;
- apply a bounded local repair and run focused verification;
- create or update a GitHub issue only after explicit confirmation;
- ask one operator question when evidence depends on a human decision.

## Boundaries

- Do not start implementation, review, or merge work from this skill.
- Do not mutate GitHub Project state directly when the CLI can perform the
  workflow action.
- Do not add secrets, client data, private planning notes, or live access codes.
- Preserve 3D-RAMS safety language: no certified RAMS, emergency guidance,
  legal/financial/medical advice, or approval-to-work claims.
- Keep Demo1 runnable without cloud credentials or live map keys.
