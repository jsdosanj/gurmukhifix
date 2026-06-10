# Publishing `gurmukhifix` to PyPI

This repository ships a ready-to-use release pipeline
(`.github/workflows/publish.yml`) that publishes the **`gurmukhifix`** package to
[PyPI](https://pypi.org/) using **Trusted Publishing (OIDC)** — so there are **no
API tokens to store** in the repo. You publish by cutting a GitHub Release; the
workflow builds, checks, and uploads automatically.

Follow these steps in order. Steps 1–2 are a **one-time setup**; after that,
releasing is just steps 4–6.

---

## 0. Prerequisites

- You can push to and create releases on `jsdosanj/gurmukhifix`.
- You have (or will create) an account on [pypi.org](https://pypi.org/account/register/)
  and, optionally, [test.pypi.org](https://test.pypi.org/account/register/) for dry runs.
- The package name `gurmukhifix` is available on PyPI (check
  <https://pypi.org/project/gurmukhifix/> — a 404 means it's free to claim).

---

## 1. Create the PyPI "pending publisher" (one-time)

Trusted Publishing lets GitHub Actions upload to PyPI without a password. Because
the project doesn't exist on PyPI yet, you register a **pending** publisher:

1. Log in to PyPI → **Account → Publishing**
   (<https://pypi.org/manage/account/publishing/>).
2. Under **Add a new pending publisher**, fill in:
   - **PyPI Project Name:** `gurmukhifix`
   - **Owner:** `jsdosanj`
   - **Repository name:** `gurmukhifix`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. Click **Add**.

> The **environment name must be exactly `pypi`** — it matches `environment: pypi`
> in the `publish-pypi` job. (For TestPyPI dry runs, repeat this on
> test.pypi.org with environment name `testpypi`.)

---

## 2. Create the GitHub environment (one-time)

1. In the repo: **Settings → Environments → New environment**.
2. Name it **`pypi`** (and optionally **`testpypi`**). No secrets are needed —
   OIDC handles authentication.
3. (Optional, recommended) Add yourself as a **required reviewer** so a release
   can't upload without your click.

---

## 3. (Optional) Dry-run on TestPyPI

Before the real thing, you can rehearse end-to-end:

1. Complete steps 1–2 again on **test.pypi.org** with environment `testpypi`.
2. In the repo: **Actions → Publish to PyPI → Run workflow**, choose
   **target = testpypi**.
3. Verify it appears at `https://test.pypi.org/project/gurmukhifix/` and installs:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ gurmukhifix
   ```

---

## 4. Bump the version

PyPI refuses to overwrite an existing version, so every release needs a new one.
Update **both** places to the same value (e.g. `0.1.0` → `0.2.0`):

- `pyproject.toml` → `version = "0.2.0"`
- `gurmukhifix/__init__.py` → `__version__ = "0.2.0"`

Use [semantic versioning](https://semver.org/): patch for fixes, minor for
features, major for breaking changes. Commit the bump:

```bash
git add pyproject.toml gurmukhifix/__init__.py
git commit -m "Release v0.2.0"
git push
```

### Sanity-check the build locally (optional but recommended)

```bash
pip install build twine
python -m build              # creates dist/gurmukhifix-0.2.0.tar.gz and .whl
python -m twine check dist/* # validates metadata/README rendering
```

---

## 5. Cut the GitHub Release

A published release is what triggers the pipeline.

**Via the UI:** Repo → **Releases → Draft a new release** → **Choose a tag** →
type `v0.2.0` (create it on publish) → set a title and notes → **Publish release**.

**Or via the CLI:**

```bash
git tag v0.2.0
git push origin v0.2.0
gh release create v0.2.0 --title "v0.2.0" --notes "What changed in this release."
```

> Tag convention is `vMAJOR.MINOR.PATCH`. The tag version should match the
> version you set in step 4.

---

## 6. Watch the workflow and verify

1. Repo → **Actions → Publish to PyPI** — watch the `build` then `publish-pypi`
   jobs. If you set a required reviewer in step 2, approve the deployment.
2. When it's green, confirm the package is live:
   <https://pypi.org/project/gurmukhifix/>
3. Install it fresh:
   ```bash
   pip install gurmukhifix
   gurmukhifix --version
   ```

That's it. For future releases you only repeat **steps 4–6**.

---

## Manual publish (fallback, without OIDC)

If you ever need to publish from your machine instead of CI:

```bash
python -m build
python -m twine upload dist/*      # prompts for a PyPI API token as the password
```

Create the token at **PyPI → Account → API tokens** and use `__token__` as the
username. Trusted Publishing (above) is preferred because it stores no secrets.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `non-existent or non-pending publisher` | The publisher in step 1 doesn't match the repo/workflow/environment exactly. Re-check owner `jsdosanj`, repo `gurmukhifix`, workflow `publish.yml`, environment `pypi`. |
| `File already exists` | That version is already on PyPI. Bump the version (step 4) and cut a new release. |
| `twine check` fails on the README | Long-description rendering issue — usually a Markdown problem in `README.md`. |
| Workflow didn't trigger | Make sure you **published** the release (not saved a draft), or use **Run workflow** for a manual run. |
| Deployment waiting | You added a required reviewer to the `pypi` environment — approve it in the Actions run. |
