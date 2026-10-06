# Development instructions

- Read README.md and CONTRIBUTING.md before changing the platform.
- Keep local credentials, runtime data and customer documents outside Git.
- Keep the upstream Dify checkout at the commit in infra/dify.lock.json; use infra overrides rather than editing upstream.
- Run make check for shared-content changes. For runtime changes, also validate Compose configuration and run make doctor after startup.
