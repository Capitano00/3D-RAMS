# Impact Baseline Worksheet

Use this worksheet to measure a first-pass manual review task against the 3D-RAMS demo workflow.

Do not publish numeric speed-up claims until the worksheet has been completed and reviewed. A single timed run is demo evidence, not a production benchmark.

## Purpose

Measure whether 3D-RAMS can compress fragmented desk-review work into an inspectable pre-visit review pack while preserving evidence, uncertainty, trace, and human-review boundaries.

The comparison should measure the same task twice:

1. Manual baseline: reviewer uses the source list and prepares a first-pass review pack manually.
2. 3D-RAMS run: reviewer runs the app and inspects the generated review pack.

## Task Definition

Use the default cached public fixture:

| Field | Value |
| --- | --- |
| Site label | `8 Albert Embankment and land to the rear` |
| Coordinate | `51.492099, -0.118712` |
| Fixture pack | `public-lambeth-thames` |
| App mode | No-AWS deterministic mode unless the OpenAI-compatible gateway is explicitly being tested |

Manual source set to inspect:

- `fixtures/public-lambeth-thames/pack.json` for the fixture overview, hazards, evidence, and source metadata;
- `fixtures/public-lambeth-thames/sources.json` for source ids, attribution, freshness, and confidence notes;
- `fixtures/public-lambeth-thames/planning_data_brownfield.json` for Planning Data brownfield-land entity `1719372`, reference `BLR059`;
- `fixtures/public-lambeth-thames/flood_risk_zones.json` for Planning Data flood-risk-zone entities `65232137` and `65657427`;
- `fixtures/public-lambeth-thames/osm_context.geojson` for cached OSM-style access/public-realm context;
- `fixtures/public-lambeth-thames/planning_context.txt` for cached planning-style notes;
- safety boundary notes: human review only, not certified RAMS or work approval.

Key source ids to carry into the manual output:

- `public-planning-data-brownfield-lambeth`;
- `public-ea-flood-context`;
- `public-highway-access-context`;
- `public-lambeth-planning-context`;
- `public-lambeth-location`.

Expected output for both runs:

- first-pass pre-visit review pack;
- candidate hazards/checks;
- source list;
- confidence or uncertainty notes;
- human-review or escalation items.

## Manual Baseline Run

| Field | Value |
| --- | --- |
| Reviewer |  |
| Date/time |  |
| Start time |  |
| End time |  |
| Elapsed time |  |
| Sources opened |  |
| Output produced |  |
| Missing or uncertain items |  |
| Notes copied manually |  |
| Human-review/escalation items |  |

Manual timing starts when the reviewer opens the first source or note page. It ends when the reviewer has a first-pass briefing, source list, uncertainty notes, and review/escalation items.

## 3D-RAMS Run

| Field | Value |
| --- | --- |
| Reviewer |  |
| Date/time |  |
| Start time |  |
| End time |  |
| Elapsed time |  |
| Commit hash |  |
| App mode | `public-lambeth-thames`, live model disabled/fallback/real |
| Output inspected | scene, briefing, evidence, trace, visualizer |
| Missing or uncertain items |  |
| Human-review/escalation items |  |

App timing starts when the reviewer opens the app and begins the default scenario. It ends when the reviewer has inspected the scene, briefing, evidence register, trace, visualizer, and safety boundary.

## Evidence To Save

- screenshot of default run;
- screenshot of evidence register;
- screenshot of trace;
- screenshot of architecture visualizer;
- screenshot or clip of safety refusal;
- terminal output from `scripts/check-demo`;
- exact commit hash;
- notes on what felt unclear or slower than expected.

## Claim Rules

Allowed after one measured and reviewed run:

- "In one timed demo test, the MVP produced a first-pass review pack in X minutes versus Y minutes for the manual baseline."
- "This is demo evidence, not a production benchmark."
- "The result still requires human review and does not certify RAMS or approve work."

Not allowed:

- generalized percentage or time-saving claims across all projects;
- claims that the app automates certified RAMS;
- claims that a site is approved for work;
- claims that live official data was checked during the demo;
- claims that the system is production deployed.

## Review Checklist

Before using a timing result in a demo, README, submission, or pitch:

- both manual and app runs used the same task definition;
- the app run used fixture data unless a new source adapter was reviewed;
- screenshots or notes prove what was inspected;
- the claim says `timed demo test`, not production benchmark;
- safety boundary wording remains human-review only.
