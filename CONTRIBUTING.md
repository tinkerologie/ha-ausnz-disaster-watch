# Contributing to Australia and New Zealand Disaster Watch for Home Assistant

Thank you for your interest in contributing to Australia and New Zealand Disaster Watch. This project welcomes contributions from human developers and autonomous AI coding agents alike.

Home Assistant integration for real-time disaster, hazard, and emergency incident monitoring across Australia and New Zealand.

To maintain code quality, protect maintainer capacity, and prevent maintainer burnout, all contributors must follow the standardized development and governance workflow outlined below.

---

## Code of Conduct and Standards

- Be respectful, constructive, and collaborative.
- Zero secrets policy: Never commit passwords, tokens, API keys, private certificates, or personal data.
- Anti-burnout principle: Perform full due diligence locally before opening pull requests or requesting review.

---

## Development Workflow

All contributions—whether submitted by humans or AI agents—must adhere to this step-by-step workflow:

### 1. Open a GitHub Issue First
- Every bug fix, feature, or enhancement must start with an issue.
- Use the appropriate GitHub Issue Form:
  - Bug Report (`01-bug-report.yml`)
  - Enhancement Request (`02-enhancement-request.yml`)
- Blank or unstructured issues are disabled. Pull requests without a corresponding issue will be closed.

### 2. CodeRabbit AI Plan Generation
- Once the issue is created, CodeRabbit AI is triggered to generate an implementation plan (either automatically via the `bug` or `enhancement` label, or by commenting `@coderabbitai plan` on the issue).
- CodeRabbit analyzes the codebase and posts a comprehensive Coding Plan containing:
  - Codebase research and affected components
  - Architectural design choices
  - Phased task breakdowns
  - Machine-readable agent prompts and verifiable acceptance criteria
- Contributors must review, refine, and confirm the plan before writing code. Do not start implementation without an approved plan.

### 3. Create a Dedicated Branch
- Create a feature or bugfix branch off `main`:
  - Features: `git checkout -b feat/<issue-number>-<short-description>`
  - Fixes: `git checkout -b fix/<issue-number>-<short-description>`
  - Documentation: `git checkout -b docs/<issue-number>-<short-description>`
- Never commit directly to the default branch (`main`).

### 4. Implementation and Local Validation
- Implement changes following project conventions and the approved plan.
- Update `CHANGELOG.md` under `## [Unreleased]` describing what changed and why.
- Run all required local validation checks (tests with coverage, linters, type checkers, and formatters). Ensure all checks pass with zero errors and zero warnings.

### 5. Follow the Pull Request Template
- Open a Pull Request using `.github/pull_request_template.md`.
- Complete all sections in the template:
  - Summary of changes
  - Linked issue keywords (`Fixes #<issue>`, `Closes #<issue>`, `Addresses #<issue>`)
  - Verification steps and pasted terminal output
  - Mandatory Pre-Submission Governance checklist (every box must be checked)

### 6. Open PR as DRAFT First
- Pull requests MUST be opened in Draft mode (`gh pr create --draft` or choose "Create draft pull request" in GitHub).
- Draft PRs allow CI workflows to run in isolation without triggering premature reviewer notifications or consuming unnecessary review capacity.
- Verify that all CI checks pass in draft mode and confirm that everything is working as expected from your end.

### 7. Mark Ready for Review
- Only after all local and draft CI checks have succeeded, convert the pull request to "Ready for Review".
- Pull requests marked ready for review with failing checks, incomplete templates, or unverified changes will be converted back to draft or closed.

### 8. Automated Quality Gates and Merge Criteria
Before a pull request can be merged, it must satisfy all automated quality gates:
- CodeRabbit AI Review: All review comments and suggestions must be resolved or addressed.
- GitHub Copilot Code Review: Must pass with no blocking feedback.
- Codecov Coverage Reports: Must pass with zero errors, zero warnings, and no coverage regressions below the repository target.
- Branch Ruleset Checks: All required status checks defined in the default branch ruleset must pass.

---

## Local Development and Verification

### Prerequisites and Setup

- Python 3.14.2 or later and Git.
- Run `script/setup/bootstrap` to install the project dependencies. The official
  `pytest-homeassistant` pin in `requirements_test.txt` selects the matching Core release.
- Bootstrap installs the project's Git hooks with `prek` in local checkouts.

### Validation Commands

```bash
script/test --cov
script/lint
script/type-check
script/check
script/hassfest
```

### Deprecations and Upcoming Home Assistant Releases

- **Current release (blocking):** `script/test` fails on deprecated use by the integration (#121).
  - `pyproject.toml` `filterwarnings` turns every warning into an error, and keeps `DeprecationWarning` and `PendingDeprecationWarning` raised from `custom_components.ausnz_disaster_watch` modules errors even if that rule is relaxed.
  - Home Assistant logs, rather than warns, when an integration uses a deprecated API (`report_usage`, deprecated constants, classes and functions) or when an entity class still defines a deprecated attribute (`custom_components.ausnz_disaster_watch.<module>::<Class> provides the deprecated <name>`). `tests/deprecations.py` collects those log lines when they name `ausnz_disaster_watch`, and the autouse `fail_on_ha_deprecation_reports` fixture in `tests/conftest.py` fails the test that logged one, including reports from `hass` setup and shutdown. Fix the call in the integration; do not silence the check.
  - `python -I script/import_smoke.py` imports every module in a clean interpreter against whichever Home Assistant is installed, and fails on a failed import or deprecated use. It needs no test harness, so it works against a beta.
- **Next release (early warning, non-blocking):** HA Next runs weekly, on demand and on pull requests that change test or compatibility tooling.
  - `release` tests the newest compatible Home Assistant release on PyPI, including beta releases.
  - `dev` tests Core at one commit from the `dev` branch.
  - Both channels run the full suite when the matching official plugin installs. The resolver checks PyPI and the matching Core tag or commit.
  - If the plugin is unavailable or fails to install, the job runs the import smoke test and Hassfest. The summary shows the check mode and fallback reason.
  - Scheduled and manual runs on `main` keep one issue per channel, labelled `ha-next` and `bug`. A fallback pass clears an issue opened by a fallback run. A full-suite pass can clear either issue.
- **Developer blog (early warning, non-blocking):** `.github/workflows/ha-dev-blog.yml` runs weekly and on demand (input `days`, default 22). `script/ha_dev_blog.py` reads the developer blog feed and searches `custom_components/ausnz_disaster_watch/` for the code identifiers named next to an announced deprecation, removal or breaking change. It opens one `ha-dev-blog` and `enhancement` issue per post that names something the integration uses (deduplicated by the post link across open and closed issues). Run it locally with `python3 script/ha_dev_blog.py --days 30`.
- **When ha-next fails:** open the run linked from the `ha-next` issue and read the job summary.
  - Release test failure: make a separate checkout and run `HA_VERSION=<version> script/setup/bootstrap`. Run the failing test with `script/test <path>`.
  - Dev test failure: use the pinned commit and requirements from the workflow's Resolve and Install steps in a scratch virtual environment. Activate it and run the failing test with `script/test <path>`.
  - Import smoke failure: use the same Core revision and declared requirements as the workflow. Run `python -I script/import_smoke.py` in that environment. Compatibility fixes must also work on the minimum Home Assistant version in `hacs.json`.
  - Hassfest failure: run the same command locally; a new validator rule or a changed Core layout may need a `script/hassfest` change.

---

## Commit Message Guidelines

We follow Conventional Commits:

- `feat(<scope>): <description>` — New feature
- `fix(<scope>): <description>` — Bug fix
- `docs(<scope>): <description>` — Documentation changes
- `test(<scope>): <description>` — Adding or updating tests
- `refactor(<scope>): <description>` — Code restructuring without functional change
- `chore(<scope>): <description>` — Tooling, dependencies, or repository maintenance

---

## Pull Request Governance Summary

- No spam or back-to-back PRs: Batch related changes into a single PR.
- AI-assisted PRs require human verification and local testing before submission.
- All template checkboxes must be confirmed.
- PRs must remain in Draft until verified.

## Issue and Pull Request Governance

These rules apply to every contributor, including AI coding agents. The full org-wide rules are in
[GOVERNANCE.md](https://github.com/tinkerologie/.github/blob/main/GOVERNANCE.md).

1. **Issue first.** Open an issue with the bug or enhancement template before opening a pull
   request. Keep the title prefix `[Bug]:` or `[Enhancement]:`, followed by a space and the title.
   Automation applies the `bug` or `enhancement` label when it can tell the type, and CodeRabbit
   then posts a Coding Plan on the issue. Implement from that plan. The labeler skips issues labeled
   `question`, `duplicate`, `invalid`, `wontfix`, or `no-type`, and never re-adds a type label that
   a maintainer removed.
2. **Link the issue.** In the PR's **Related Issues** section, write `Closes #<number>` (or `Fixes`
   or `Resolves`) when the PR completely resolves the issue; these keywords close it on merge. Use
   `Part of #<number>` or `Related to #<number>` for partial work. The linked issue must exist; an
   issue in another public repository (`owner/repo#123`) is fine. Only authors with write access or
   higher (maintainers) may write `None`, for housekeeping such as CI,
   documentation, or dependency updates; PR governance rejects `None` from everyone else.
3. **One change at a time.** Contributors without write access can have at most 2 open, non-draft
   pull requests here. GitHub enforces this limit, and draft pull requests do not count toward it.
   Do not open PRs that edit the same files as another open PR, such as `CHANGELOG.md`,
   translations, `README.md`, or generated bundles. Wait for the first to merge, rebase, then
   continue.
4. **Act on the Tinkerologie-Bot report.** When PR governance fails, Tinkerologie-Bot posts one comment
   listing every problem as a numbered item. Fix each item by editing the PR description or pushing
   the missing change; the check re-runs and the comment updates to passed.
5. **Rebase before review.** Rebase on `main` before marking a PR ready for review.
6. **Resolve conflicts first.** When a PR gets the `conflicts` label, rebase on `main`,
   resolve the conflicts (keep every `CHANGELOG.md` entry under `[Unreleased]`), re-run the tests,
   and force-push before doing any other work.
7. **Stale items.** Issues and PRs with no activity for 14 days are labeled `stale` and closed 30
   days later unless there is new activity. These labels are exempt:
   - Issues: `pinned`, `security`, `confirmed`, `work-in-progress`, `priority: critical`, `priority: high`.
   - Pull requests: `pinned`, `security`, `work-in-progress`.
