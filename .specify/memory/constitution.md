# Kara Constitution

## Core Principles

### I. Human authority and project isolation

Kara MUST derive actors from authenticated server sessions and scope every team record to the
project and its actual workspace. Active membership, business roles and explicit agent grants MUST
be checked afresh for each action. A business role MUST NOT silently confer native editor rights.
Only the active global administrator or the project's native owner manages grants. Management
MUST NOT imply PO approval, run or finalization authority. An actual PO approves intake for exact
request and flow revisions; the assigned authorized human finalizes each stage. Model output,
service identity and technical success MUST NOT fabricate human decisions. TL merge remains manual.

### II. Versioned evidence and explicit handoff

Request, flow, agent contract, published workflow, input and artifact revisions MUST be bound by
scope, stable identifiers and content digests. Published definitions and historical decisions MUST
remain immutable. Human feedback and edits create attributable revisions. A successful attempt
creates a draft; finalization selects one valid artifact. The next actor starts the ready stage
explicitly. Changed consumed inputs MUST invalidate affected downstream results without deleting
history or silently restoring approvals. Technical retries and human feedback rounds stay distinct.

### III. Compatible changes in the existing product

Reuse Kara's native accounts, workspaces, workflow engine, queue and frontend. Keep the upstream
checkout pinned by `infra/dify.lock.json` untouched; apply changes through `infra/` overlays/hooks.
Legacy apps MUST NOT become managed agents implicitly. Additive, checksum-verified transactional
migrations MUST preserve existing memberships, projects, runs, forms and decisions. Before a
runtime schema change, verify backup/restore in an isolated environment. Once managed execution is
used, rollback MUST retain enforcement or stop service for controlled recovery; old unprotected
code is not a safe rollback. Dispatch safety and idempotency MUST ship with the first dispatch,
not wait for a later roadmap step.

### IV. Proof proportional to the claim

Shared changes MUST pass `make check`. Runtime changes additionally require Compose validation,
startup and `make doctor`, focused backend/PostgreSQL and frontend checks, and real browser
acceptance for changed user journeys. Concurrency and migrations require PostgreSQL evidence;
SQLite or the pure reference state machine cannot prove them. Separate specification review,
structural tests, live orchestration and real model quality. Report actual commands, outcomes,
versions, omissions and recovery procedures. Never claim a model run, production behavior,
cacheless download or exactly-once delivery from weaker evidence.

### V. Specification before implementation

Every new bounded feature MUST have a reviewed `spec.md`, `plan.md`, design contracts and
`tasks.md` before implementation. Requirements, scenarios and tasks MUST be traceable. Amend the
specification and reconcile downstream artifacts when behavior changes. Unperformed implementation
tasks MUST remain unchecked. Review checklists concern requirement quality, not runtime acceptance.
Complete and accept KP-02 through KP-08 before dedicated Klassor agents. Manual intake can be
accepted before Jira; Jira mapping MUST use a real sanitized intermediary-service sample, never an
invented native schema. Kubernetes and a second workflow engine are outside this iteration.

## Additional Constraints

- Use Kara / کارا for the product. Dify denotes only the technical upstream and its attribution.
- Keep secrets, customer documents, credentials, runtime data and real connector samples outside Git.
  `sources/` is synced read-only reference material. Synthetic fixtures MUST be identified as such.
- All current platform planning and specifications belong to `master`. Keep `clasor-agents` at the
  same commit, with zero unique commits, until dedicated Klassor implementation starts. Preserve
  existing `agents` and `clasor-analysis-agents` history. Do not install Spec Kit's git extension
  or let spec creation change branches in this phase.
- External messages, issue creation, deployment and integrations require the relevant user scope;
  generating tasks MUST NOT publish issues, activate automation or send messages.

## Development Workflow and Quality Gates

Use the pinned local Specify CLI and installed Codex skills. Establish constitution, then execute
specify → clarify → plan → checklist → tasks → analyze. Resolve critical contradictions before
implementation. Select the feature explicitly using `SPECIFY_FEATURE_DIRECTORY`; branch names are
not the feature selector. Start implementation only for the requested step with satisfied gates.
Use implement → actual acceptance checks → converge, then review. Convergence cannot replace live
acceptance. Commit one coherent completed task at a time, inspect staged changes and use the
Persian what/why/how/check format in `CONTRIBUTING.md`. Record commit hashes and actual evidence.

## Governance

This constitution captures the user's existing decisions, `AGENTS.md`, the operating model and
team contract 1.0.0. Direct user instructions take precedence. Amendments MUST state the reason,
impact, affected specs and necessary migration/test updates; reconcile the documents before coding.
Use semantic versions: major for incompatible principle changes, minor for added obligations,
patch for wording only. Review every feature against these principles before and after design.
Keep completed specs as historical accepted records; proposed behavioral changes get a new spec
or explicit revision with a change log. Future drafts MUST be refreshed against accepted predecessor
contracts before implementation. This initial adoption adds no retrospective runtime guarantees.

**Version**: 1.0.0 | **Ratified**: 2026-10-22 | **Last Amended**: 2026-10-22
