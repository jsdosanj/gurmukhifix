# Security Policy

## Supported versions

Security fixes are released for the latest published version. Please upgrade to
the newest release before reporting.

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ |
| < 0.2   | ❌ |

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub, not in a public issue:

1. Go to the repository's **Security** tab:
   <https://github.com/jsdosanj/gurmukhifix/security>
2. Click **"Report a vulnerability"** to open a private advisory
   (GitHub private vulnerability reporting).

Include the affected version, a description, and — where relevant — the exact
input (OCR text and its script/language) that reproduces the issue, so we can turn
it into a regression test.

We aim to acknowledge a report within **5 business days** and to ship a fix or a
mitigation within **90 days** of confirmation, coordinating disclosure with you.
Please give us reasonable time to release a fix before any public disclosure.

## Sensitive surface specific to this project

gurmukhifix corrects sacred and heritage text, which creates two project-specific
concerns beyond ordinary software vulnerabilities:

- **Poisoned / adversarial corrections database.** The learner
  ([`gurmukhifix/learner.py`](gurmukhifix/learner.py)) stores confirmed
  corrections in a SQLite database and *promotes* a pair once it has been
  confirmed 10+ times (a frequency threshold). A crafted or tampered database
  could try to promote a pair that rewrites correct text. Treat a corrections
  database as **untrusted input** if it did not come from you — do not share or
  merge databases from sources you do not control.

- **PII in contributed manuscript snippets.** Bug reports and test fixtures may
  carry small excerpts of scanned manuscripts. Do not include personal data in
  issues, fixtures, or `tests/ground_truth/`; include only the minimal snippet
  needed to reproduce a correction bug.

### Why these are contained, not catastrophic

The [evidence gate](gurmukhifix/evidence.py) is the mitigation in both cases:
**promoted pairs still pass through the gate**, so even a poisoned pair cannot
increase a word's script-validity badness, cannot make an unsupported blind
substitution, and — most importantly — **can never override the scripture lock**
on verbatim Gurbani. A promoted pair applies only in the context it was confirmed
and never automatically alters locked scripture. This is enforced by the
property-based tests in
[`tests/test_zero_corruption.py`](tests/test_zero_corruption.py), which include
adversarial promotions.

If you find a way to make gurmukhifix silently corrupt valid or scripture text —
whether through a poisoned database, a config rule, or any other path — that is a
**high-severity** report and we want to hear about it.
