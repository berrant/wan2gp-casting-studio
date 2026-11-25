# Publishing checklist

- Keep the repository private during initial inspection. Use this clean source tree, not the live installed plugin or WanGP directory.
- Do not upload private settings/prompt backups, runtime databases, generated media, logs, credentials, or RefMod model files. The `.gitignore` is a defense in depth, not a substitute for reviewing staged changes; already tracked files are not protected by ignore rules.
- Check that `plugin_info.json`, `plugin.py`, `README.md`, `app/` and `tests/` are at the repository root.
- Keep the original WanGP installation ZIP separate from the GitHub source archive. The installation ZIP has the required `wan2gp-casting-studio/` wrapper. GitHub's automatic source downloads are not the tested installation ZIP.
- Before public release, confirm copyright attribution, contributor rights and asset provenance. Both ZIPs require LICENSE, NOTICE.md and CONTRIBUTING.md. Do not imply official endorsement or complete compatibility testing.
- Do not package or deliver a candidate until the complete cumulative regression gate and all relevant new regression/adversarial tests pass against the final corrected source. Rerun the complete gate after any application or test correction.
- See `TEST_RESULTS.txt` for current measured results. The maintainer reported successful RC12.22 live generation, preview, conversion, Workshop, appearance analysis and Git update on WanGP v20.20. Verify RC12.23 inventory changes, appearance navigation and autosave, active-generation protection, clean live installation and public installation separately. Do not claim compatibility across every host/version.
- Run `python check_release_privacy.py --git-index` after staging. The checker also supports normalized source and installation ZIP files with the ZIP path as argument. This guard does not inspect prior Git history or author metadata.
- Before changing visibility, review the actual repository history, author/committer metadata, branches, tags, prior release assets, issues and settings for private data. The local staged-index guard cannot inspect these.
- Once ready, create tag `v1.0.0-rc.12.23` and mark the GitHub release as a pre-release. Upload the unchanged installation ZIP as the release asset.
