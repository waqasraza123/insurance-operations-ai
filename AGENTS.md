# Codex Working Agreement

- Read `docs/project-state.md` before starting work.
- Read `docs/_local/current-session.md` when it exists.
- Treat project state as durable shared memory and current session as local working memory.
- Update durable memory only for verified architecture, decisions, milestones, risks, or commands.
- Update current-session after every meaningful task and whenever the active handoff changes.
- Never store secrets, credentials, tokens, personal data, or sensitive document contents in notes or code.
- Follow the existing architecture, naming, layout, and conventions.
- Keep notes concise, concrete, current, and non-speculative.
- Do not add unnecessary code comments.
- Use descriptive, consistent names and modular, reusable, strongly typed code.
- Validate inputs and configuration, and return clear errors.
- Do not guess requirements or introduce hardcoded hacks.
- Keep changes testable and maintainable; document the relevant checks for the owner.
- Do not run tests, builds, linters, type checks, migrations, seeds, readiness checks, smoke tests, live services, or other verification commands unless the owner explicitly asks for that specific execution.
- Do not start background terminals, development servers, watchers, or long-running processes.
- After each feature, clearly list the exact commands and manual checks the owner should run, and mark implementation as unverified until the owner reports the results.
- Keep commit messages under 140 characters.
