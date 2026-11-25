# CI and Python release evidence

## Public contributor checks

`ci.yml` delegates repository policy and Python quality to the public
`alpininsight/.github` catalog introduced by its PR #52. Each reusable and its
runtime scripts are bound to the reviewed catalog revision
`7152544c2f591ed277e17894db9ad11f551b3069`; script digests match that revision.
The public catalog runbook requires immutable caller pins, replacing the earlier
proposal to use a moving `main` reference. No private reusable, repository secret
or self-hosted runner is needed for contributor CI.

The required checks remain **WebMCP Quality Gate** and
**repository-policy / Repository Policy**. Full CI covers Python 3.12/3.13/3.14,
minimum Django 6.0.4, optional Insight UI interoperability, installed Core assets,
wheel/sdist installation and Gitleaks. The interoperable profiles install
Insight UI 1.15.1 and the published 2.0.0rc1, with the RC also using
`ais-webmcp==0.2.1`. Every package profile provisions Node 24.
The public quality reusable owns these common steps; this repository owns its
package-specific commands and evidence contract.

Open pull requests against `develop`. Contributors can push their changes to
a feature branch in a public fork and open the pull request from that branch.
If GitHub queues a first-time contributor's workflow for approval, a maintainer
reviews the diff before starting CI.

PR opening, new commits, reopening and base retargeting run full CI. Main pushes
also run full CI. Develop pushes do not duplicate the tested PR matrix.
Title/body edits and Ready events use a separate concurrency group and revalidate
the latest full producer for the same repository, PR, head, base and attempt.
They never infer success from skipped tests or recursively reuse metadata runs.
The verifier is loaded from the trusted PR base. A newer failed/cancelled run,
missing contract, API error, changed source identity or timeout fails closed.
Policy and code checks are independent; both are required for merge.

## Source release

The source `release.yml` remains the documented GitHub tag/release entry point.
It accepts only the current protected Main source, including `release=false`.
`scripts/check_publication.py source` verifies the latest exact-SHA successful
Main-push CI and its unique Quality Gate. A release request also requires the
existing activation flag and the exact merged Develop-to-Main promotion.

GitVersion 6.8.x reads this repository's version configuration. The public
`create-release.yml` reusable receives that calculated version and immutable
source SHA. It verifies the pinned version/release scripts, requires current
Main, rejects conflicting tags or release identities, and creates a published
GitHub release only when `release=true`. Stable is the default;
`release_kind=rc` with `rc_number=1` creates `vX.Y.Z-rc.1` as a prerelease. The default false path validates
source/version identity and creates no tag or release. Reusable release creation
is the only job with `contents: write`; contributor checks remain read-only.
No activation variable or repository permission is changed by these definitions.

```bash
gh workflow run release.yml --repo alpininsight/insight-ui-webmcp --ref main -F release=false
```

After the normal release decision, DevOps can request the same source release
with `release=true`. This workflow never uploads to PyPI. The separately
maintained protected package publisher validates the matching GitHub release
and its exact source before uploading the reviewed distribution bundle. For RC1
the distribution version is `X.Y.Zrc1`. Build and smoke-test that bundle before
creating the matching GitHub prerelease.
Publisher credentials, environment setup and operational runbooks remain outside
this public package repository. GitHub release, PyPI upload, CDN distribution,
consumer deployment and native-browser acceptance are separate results.

## Dependencies and local development

Renovate extends the public `alpininsight/.github:pre-commit` preset to update
tracked hooks. Hook updates are reviewed against accepted versions; an unexplained
downgrade is not accepted merely because an automated PR has green tests.
The obsolete private scheduled hook workflow is removed.

```bash
uv sync --locked --all-groups
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked python -m django check --settings=tests.settings
uv lock --check
uv run --locked pytest
```

Package versions are independent of Core; the declared dependency range is the
contract. Passing contributor checks does not establish publication or runtime.
