# Contributing

Thanks for helping. The most valuable contributions right now:

- **Benchmark data**: synthetic patient messages, call transcripts and referral notes with labelled identifiers, especially in languages other than English. All values must be invented.
- **Detection misses**: a realistic message where phiveil leaks an identifier. Report it privately if it is a leak in a common format (see SECURITY.md); otherwise open an issue with a synthetic example.
- **Adapters** for other gateways and SDKs.

## Ground rules

- **No real patient data anywhere**: not in code, tests, issues, PRs or benchmark files. Use 555-01xx phone numbers, `example.com` emails and made-up names.
- Detection changes must come with tests and must not lower benchmark recall: `python benchmark/score.py --config regex+known --min-recall 0.85`.
- Prefer recall over precision. Masking a non-identifier costs some answer quality; missing an identifier leaks PHI.
- Nothing in the detection path may call an external service.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,litellm]"
pytest -q
python benchmark/score.py
pip install "litellm[proxy]" && python examples/e2e/run_e2e.py   # optional, slower
```

## Sign-off (DCO)

Every commit must be signed off to certify the [Developer Certificate of Origin](https://developercertificate.org/):

```bash
git commit -s -m "your message"
```

This adds a `Signed-off-by: Your Name <email>` line. By signing off you confirm you have the right to submit the change under the project's Apache-2.0 license.
