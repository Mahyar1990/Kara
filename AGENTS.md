# Development instructions

- Read README.md and CONTRIBUTING.md before changing the platform.
- Follow docs/branches.md: master holds the Kara platform and all current reviews, requirements and planning documents. Keep clasor-agents aligned with master with no unique commits until dedicated Klassor implementation starts; only then commit its implementation and related assets there. Preserve existing agents and clasor-analysis-agents history separately.
- Use Kara (کارا) as this project and product name in introductions, user-facing copy and usage documentation. Reserve Dify for necessary technical references to the upstream code, versions and dependencies; describe the execution engine and team workflow features as parts of Kara.
- Follow docs/kara-platform-readiness-plan.md: prepare and accept the core team workflow on Kara before starting dedicated Klassor agents. Validate platform collaboration with synthetic deterministic steps first.
- Preserve the request, analysis-version and human-decision relationship.
- Use the sandbox branch as the baseline for all four Klassor source/test repositories. Record its exact ref and commit; do not substitute the current checkout. Local origin/sandbox may be read without switching branches or fetching.
- Build Klassor agent context from each source repository's AGENTS.md, relevant PROJECT_MAP.md sections, and selected doc/docs and repository skills. Keep repository rules separate from technical evidence, pin sources to the same snapshot, and refresh private context after path or baseline changes.
- Product-owner approval and TL manual merge must come from real human decisions.
- Keep local credentials, runtime data and customer documents outside Git.
- Keep the upstream Dify checkout at the commit in infra/dify.lock.json; use infra overrides rather than editing upstream.
- Run make check for shared-content changes. For runtime changes, also validate Compose configuration and run make doctor after startup.
- Record workflow exports and matching prompt revisions together; do not claim a model test without a real execution.
- Commit completed work incrementally in small, atomic commits. Each commit must implement exactly one coherent task; do not bundle independent features, fixes, refactors or documentation tasks at the end of a session.
- Apply the atomic-commit policy to code, infrastructure, integrations, prompts, workflow exports, fixtures, tests and documentation. Related implementation, necessary tests and documentation may share a commit when they all support that single task.
- Review the staged diff before each commit and stage only that task's files or hunks; do not include unrelated changes or another collaborator's work.
- Each commit message must explain what changed, why, how it was implemented and the checks actually performed, including any relevant checks not performed. Follow the format in CONTRIBUTING.md.
- Report each new commit's short hash and purpose when handing off completed work.
