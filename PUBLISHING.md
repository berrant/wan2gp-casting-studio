# Publishing checklist

- Keep the repository private during initial inspection. Use this clean source tree, not the live installed plugin or WanGP directory.
- Do not upload private settings/prompt backups, runtime databases, generated media, logs, credentials, or RefMod model files. The `.gitignore` is a defense in depth, not a substitute for reviewing staged changes; already tracked files are not protected by ignore rules.
- Check that `plugin_info.json`, `plugin.py`, `README.md`, `app/` and `tests/` are at the repository root.
- Keep the original WanGP installation ZIP separate from the GitHub source archive. The installation ZIP has the required `wan2gp-casting-studio/` wrapper. GitHub's automatic source downloads are not the tested installation ZIP.
- Before public release, settle licensing and review upstream provenance. Do not imply official endorsement or complete compatibility testing.
- The RC12.4 targeted test run passed 31 cases; the cumulative gate timed out. Live WanGP v20.20, GPU and Safari integration remain unverified. See `TEST_RESULTS.txt`.
- For a local release package, run `python check_release_privacy.py path/to/WanGP-release.zip` from this source tree. This guard checks the installation archive, not the GitHub source bundle or Git history.
- Once ready, create tag `v1.0.0-rc.12.4` and mark the GitHub release as a pre-release. Upload the unchanged installation ZIP as the release asset.
