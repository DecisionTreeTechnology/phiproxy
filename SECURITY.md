# Security policy

phiveil sits between patient data and third-party AI providers. Two kinds of report matter:

1. **Vulnerabilities**: anything that lets PHI bypass masking (a request shape that is not masked, a way to switch the guardrail off from the client, a vault leak).
2. **Detection misses that leak PHI**: an identifier type or format phiveil does not catch.

## How to report

Use GitHub's private vulnerability reporting: **Security → Report a vulnerability** on this repository. Please do not open a public issue for either kind of report.

**Never include real patient data.** Reproduce the problem with invented values (phone numbers in the 555-01xx range, names that are not real people, `example.com` emails).

We aim to acknowledge reports within 3 business days and to share a fix timeline within 10.

## Supported versions

phiveil is pre-alpha. Only the latest commit on `main` receives fixes.

## Scope reminder

phiveil reduces how much PHI reaches an LLM provider. It is not a compliance guarantee and does not replace a BAA or equivalent agreement with the provider.
