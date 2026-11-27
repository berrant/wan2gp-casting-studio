# Publishing checklist

- Keep the repository private during initial inspection. Use this clean source tree, not the live installed plugin or WanGP directory.
- Do not upload private settings/prompt backups, runtime databases, generated media, logs, credentials, or RefMod model files. The `.gitignore` is a defense in depth, not a substitute for reviewing staged changes; already tracked files are not protected by ignore rules.
- Check that `plugin_info.json`, `plugin.py`, `README.md`, `app/` and `tests/` are at the repository root.
- Keep the original WanGP installation ZIP separate from the GitHub source archive. The installation ZIP has the required `wan2gp-casting-studio/` wrapper. GitHub's automatic source downloads are not the tested installation ZIP.
- Before public release, confirm copyright attribution, contributor rights and asset provenance. Both ZIPs require LICENSE, NOTICE.md and CONTRIBUTING.md. Do not imply official endorsement or complete compatibility testing.
- Do not package or deliver a candidate until the complete cumulative regression gate and all relevant new regression/adversarial tests pass against the final corrected source. Rerun the complete gate after any application or test correction.
- See `TEST_RESULTS.txt` for current measured results. The maintainer reported successful RC12.22 live generation, preview, conversion, Workshop, appearance analysis and Git update on WanGP v20.20. The maintainer subsequently passed all 13 RC12.25 live acceptance checks, including appearance navigation, autosave, wardrobe separation and deferred scheduling. The maintainer subsequently reported all six RC12.26 focused live checks passed, including explicit inventory refresh. Public installation remains unverified. Do not claim compatibility across every host/version.
- Run `python check_release_privacy.py --git-index` after staging. The checker also supports normalized source and installation ZIP files with the ZIP path as argument. This guard does not inspect prior Git history or author metadata.
- Use a pseudonymous Git author name and the exact GitHub-provided private noreply address in repository-local Git configuration; enable private email and block pushes exposing private email in GitHub settings. Verify existing history independently.
- Before changing visibility, review the actual repository history, author/committer metadata, branches, tags, prior release assets, issues and settings for private data. The local staged-index guard cannot inspect these.
- After publisher clearance and explicit launch approval, create tag `v1.0.5` and publish a stable GitHub release. Upload the unchanged verified installation ZIP as the release asset. Verify native plugin-manager installation after publication.

- Wardrobe separation passed live on RC12.25; review existing saved profiles manually where needed.

- Before promoting v1.0.5, confirm private vulnerability reporting is enabled, review public-facing examples and screenshots for rights/consent clearance, and complete the outstanding v1.0.4 production-integrity checks and v1.0.5 compact-header live acceptance checks. Do not claim legal immunity or verified consent.

- v1.0.6 is a maintenance release. Complete its focused live acceptance in REGRESSION_CHECKLIST.md before promoting; do not imply that public launch or post-release verification has occurred merely because the source is packaged.
