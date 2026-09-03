# F001 synthetic fixtures

This directory contains deterministic, unmistakably synthetic data for F001 tests only.
Values use labels such as `Synthetic` and reserved example domains; they are not copied from
any person's profile and must not be treated as usable application data.

When reviewing or extending a fixture, check that every value is synthetic, stable, and free of
personal information. Redact or replace anything that could identify a person before committing.
Real profiles, résumé exports, contact details, government identifiers, API keys, tokens, and
browser or keyring data must never enter Git. Keep generated reports, caches, and local exports
outside the repository (or in ignored paths).

The Python helpers under `apps/local-agent/tests/fixtures/f001_profiles.py` are pure builders:
they do not access services, the network, browser state, or an operating-system keyring.
