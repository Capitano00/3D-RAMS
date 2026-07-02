# ADR 0015: Case-Correlated Report And Evidence Persistence

## Status

Accepted direction from discussion.

## Context

`main` added hosted session persistence using:

- `DYNAMODB_SESSION_TABLE`;
- session ids;
- tester alias and access label;
- uploads list;
- run summaries;
- TTL-backed session retention.

That model fits a standalone hosted web MVP. It does not fit the accepted ASI/ASI:ONE entry direction.

`dev-chunteng` added a more relevant persistence boundary:

- `RAMS_REPORT_STORE_TABLE`;
- `caseId` as the report partition key;
- stored `run` and `structuredReport`;
- report lookup by `caseId`;
- no-AWS local behavior when the table is unset.

ADR 0012 makes ASI/ASI:ONE the real entry. ADR 0013 makes detailed report access ASI/ASI:ONE identity-bound. ADR 0014 makes material upload/storage ASI-owned, while allowing 3D-RAMS AgentCore to retrieve authorized material content under the case context.

Given those decisions, 3D-RAMS should not recreate a web session table. ASI/ASI:ONE owns user sessions. 3D-RAMS should persist case-correlated report, evidence, and workflow records needed to retrieve and audit a generated analysis.

This ADR is parallel to ADR 0012, ADR 0013, ADR 0014, and ADR 0016. It decides persistence boundaries only.

## Decision

Do not recreate Evan's `DYNAMODB_SESSION_TABLE` or web session/run/upload persistence model.

Use `caseId` as the central persistence key for 3D-RAMS-generated output. The supervisor/report persistence layer should store case-correlated report and evidence records, not standalone product sessions.

The persisted record may include:

- `caseId`;
- report id and status;
- non-sensitive ASI/ASI:ONE identity or session reference needed for authorization checks;
- entry-agent intake summary;
- material references and extracted evidence summaries;
- source ids and citation metadata;
- run trace and orchestration metadata;
- structured report payload;
- persistence timestamps and retention metadata.

The persisted record must not include:

- raw ASI/ASI:ONE identity tokens;
- raw private uploaded files;
- public signed URLs or long-lived material download links;
- shared access codes;
- AWS credentials or AgentCore secrets;
- private planning notes outside the confirmed case context;
- claims of certified RAMS, emergency guidance, legal approval, or approval to work.

ASI/ASI:ONE session continuity remains outside 3D-RAMS. 3D-RAMS stores only the minimum identity/session binding needed to verify that a report lookup requester is authorized for the requested `caseId`.

Pending ASI entry-agent intake remains process-local by design for Demo1. The in-memory `_PENDING_INTAKES` and bounded conversation state in `app/asi_one_entry_agent/main.py`, plus the hosted AgentVerse adapter's pending-intake hint cache, exist only to carry a confirmation-ready draft across adjacent chat turns in the same running process. They are not a 3D-RAMS-owned web session store and must not revive `/api/session/start`, `DYNAMODB_SESSION_TABLE`, upload/session lists, or standalone session ownership.

The recoverable boundary is narrow: a hosted runtime restart or cold start may lose a confirmation-ready intake before the user confirms and before supervisor launch. Future recovery should first live in ASI/ASI:ONE session continuity by re-sending or re-presenting the confirmation-ready intake context to the entry agent. 3D-RAMS should not use AgentCore Memory as durable pending-intake storage. If hosted dogfood proves process-local loss is a real user-facing problem and ASI/ASI:ONE cannot cover it alone, 3D-RAMS may add only a short-lived, report-access-bound pending-intake summary under a future case-correlated record or successor report-access record.

The smallest safe pending-intake recovery summary is metadata, not conversation history:

- `schemaVersion`, `pendingIntakeId`, `conversationRef` or ASI session reference, and optional future `caseId`;
- `entryAgentId`, `status: "awaiting_confirmation"`, `createdAt`, `updatedAt`, and `expiresAt`;
- redacted or normalized location summary, area-scope type/meters, and bounded user-goal summary;
- material count plus safe material reference ids/source ids only;
- non-secret report-access binding reference needed to verify the same ASI/ASI:ONE requester.

Pending-intake recovery records must expire quickly: minutes to hours, not report-retention timescales. They must be deleted or superseded once the user rejects the draft, starts over, confirms and launches the supervisor, or the expiry passes.

Pending-intake recovery must never persist or echo raw user messages, raw site/client details beyond the safe summary, private material contents, material retrieval artifacts, signed URLs, API handles, access codes, raw ASI identity tokens, credentials, AWS secrets, private planning notes, or any certified RAMS, emergency, legal, financial, medical, or approval-to-work claim.

Implementation remains parked until hosted dogfood evidence shows process-local pending-intake loss is a repeated user-facing problem. That evidence should dispatch a separate implementation issue with the exact ASI/ASI:ONE continuity gap and expiry requirement.

## Options Considered

1. Recreate Evan's web session table.
   - Pros: preserves the old hosted MVP session shape.
   - Cons: duplicates ASI/ASI:ONE session ownership and pulls 3D-RAMS back toward a standalone web product.

2. Store only `run` and `structuredReport` by `caseId`.
   - Pros: simple and close to current implementation.
   - Cons: insufficient once material ingestion and ASI-bound report access need evidence lineage and authorization binding.

3. Store case-correlated report, evidence, and authorization binding metadata.
   - Pros: keeps ASI sessions external while preserving enough information for report lookup, traceability, and material-derived evidence.
   - Cons: requires careful schema design and redaction discipline.

4. Persist pending ASI entry-agent drafts in AgentCore Memory or a 3D-RAMS session table.
   - Pros: could survive entry-runtime restarts.
   - Cons: duplicates ASI/ASI:ONE session ownership, risks storing raw chat/material context, and recreates the rejected web-session model.

5. Keep pending intake process-local unless hosted dogfood proves loss, then add only ASI-owned or report-access-bound summary recovery.
   - Pros: matches Demo1, avoids speculative persistence, and keeps recovery scoped to the pre-launch confirmation failure mode.
   - Cons: a restart can still require the user or ASI/ASI:ONE to re-present the intake until a later implementation is justified.

## Consequences

Positive:

- 3D-RAMS persistence aligns with AgentCore workflow output instead of web session state.
- ASI/ASI:ONE remains the source of truth for user sessions and material ownership.
- Report lookup can validate `caseId` against ASI/ASI:ONE authorization binding.
- Evidence lineage survives beyond a single runtime response.
- Pending-intake recovery has an explicit future boundary without committing Demo1 to a new store.

Tradeoffs:

- The report store schema must expand beyond the current minimal `run` and `structuredReport` item.
- Tests must cover authorization-binding metadata without using real private ASI identities.
- Retention rules must distinguish report/evidence summaries from raw material storage owned by ASI.
- Until hosted dogfood proves otherwise, a cold start may lose a draft intake that had not launched the supervisor.

## Acceptance Criteria

- The codebase does not reintroduce `DYNAMODB_SESSION_TABLE` as a 3D-RAMS web session store.
- `RAMS_REPORT_STORE_TABLE` or its successor stores case-correlated report/evidence records keyed by `caseId`.
- Stored records include enough ASI/ASI:ONE binding metadata to authorize report lookup without storing raw identity tokens.
- Material-derived evidence is persisted as bounded summaries, source ids, and citations, not raw private file content.
- Local no-AWS mode can skip persistence while still returning the same run/report envelope.
- Report lookup denies access when the ASI/ASI:ONE requester is not authorized for the requested `caseId`.
- Public docs disclose that persisted records are human-review evidence/report records and not certified RAMS, legal approval, emergency guidance, or approval to work.
- Pending entry-agent intake is documented as process-local for Demo1; any future durable recovery stores only short-lived, public-safe summary metadata and never old web-session state.

## Discussion Questions

- What is the minimum ASI/ASI:ONE binding field set: subject id hash, organization id, ASI session id, case owner id, or another handle?
- Should extracted material evidence snippets be stored directly, or should the store keep only citations plus extraction summaries?
- Should the report store remain one DynamoDB item per `caseId`, or split report metadata, evidence summaries, and trace into separate item types under the same partition key?
