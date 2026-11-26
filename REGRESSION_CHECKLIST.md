# v1.0.4 — Production integrity follow-up
- [x] Five new permanent regression tests: reproduction and correction of TV remake collision, wrong-year cast writes and qualified film poster, repeated and ambiguous TV lookups, atomic mixed-year rejection and exact private-name exclusions. Complete final gate: 482 passed, 2 approved skips, 0 failures, 484 collected across 100 test modules.
- [x] Exact v1.0.3 synthetic upgrade and separate fresh startup; final fingerprints and syntax checks; distribution privacy gate before delivery.
- [ ] Live acceptance: finish generation and back up external data before update. Verify separate original/remake TV records, repeat import, matching TV credits and artwork; check film remake poster and correct cast credits. Continue earlier outstanding functional checks. Do not modify real user records to test an invalid import. Publisher clearance and explicit launch authorization remain separate.

# v1.0.3 — Queue-pass, remake isolation and cast coverage
- [x] Six permanent focused regressions cover 100-task manifests, unique subset validation, last-selection protection and tab-session persistence, Queue All with 99 remaining and failed preflight, separate remake records including an unknown legacy year, multi-format film credits including partial-provider recovery/private-name exclusion, and acknowledged dialog controls. Existing 13 film regressions passed with these six in the final focused run.
- [x] Complete cumulative gate: 477 passed, 2 approved retired Docker skips, 0 failures, 479 collected, 99 modules; final fingerprints and syntax checks passed. Synthetic exact v1.0.2 Git fast-forward and separate fresh startup passed. Distribution privacy audit required before delivery.
- [ ] Live host: back up external data, complete active generations before upgrading, verify About v1.0.3, existing library/consent, select 3 or more roles and test Queue & Next to completion, start a fresh queue pass, test Queue All excluding previously staged roles, review native jobs and prompts, repeat The Thing (1982)/(2011) without merging cast, inspect additional cast entries in a film and TVMaze coverage, verify acknowledged dialog has only Close. Finish earlier live checks and publisher clearance before launch.

# v1.0.2 — Film title discovery repair
- [x] 13 permanent focused tests: exact reported search, alias/redirect handling, year and episode checks, ambiguity, retry after failure, local metadata preservation, private-name isolation and browser picker reuse. Full cumulative gate: 471 passed, zero failures, 2 approved skips, 473 collected, 98 modules. See TEST_RESULTS.txt.
- [x] Exact v1.0.1 synthetic Git fast-forward and separate fresh local startup passed; database integrity and runtime data preservation verified. Final syntax and fingerprints passed.
- [ ] Live native plugin-manager update; retry the reported lowercase film search and verify the 1977 article, actor/role names, release year, source link and selected cast import. Test another film and a TV series; finish remaining v1.0.1 privacy/consent and provider live checks. Publisher clearance and launch approval remain separate.

# v1.0.1 — Unreleased phase 2
- [x] Four new focused cases: legacy marker and multiple categories, private-profile rejection, browser category editor/legacy navigation, provider links. Three existing license tests plus 17 related navigation, icon, long-video and identity checks passed (24 total).
- [x] Three new phase 2 tests cover direct API rejection, strict explicit acknowledgment, stale policy, persistence across initialization, backup isolation, consent scope edits, and actual browser checkbox/save-failure retry. Focused suite: 57 passed, 2 approved skips, 94 FastAPI deprecation warnings across two disjoint focused groups (includes phase 1, native, portrait, conversion, deferred analysis, navigation, layout, backup and branding).
- [ ] Review remaining identifiable-person safeguards and external provider/image-download behavior. Verify source-level attribution, terms and privacy boundaries. Confirm private reporting configuration.
- [ ] Complete cumulative gate on final application/test code, syntax, exact Git upgrade, fresh installation, source/archive/index privacy and live acceptance. No release ZIP from this intermediate phase.

# v1.0.0 — Initial stable release preparation
- [x] RC12.26 focused live acceptance: 6/6 maintainer-reported passes.
- [x] MIT selected with generic attribution; maintainer reports GitHub email privacy settings configured.
- [x] Final cumulative gate: 440 passed, zero failed, two approved skips, 442 collected, 94 modules. See TEST_RESULTS.txt.
- [x] Synthetic upgrade, fresh installation and staged-source audit passed. Final archive audits required before delivery.
- [ ] Repository historical privacy, applicable rights, explicit public launch approval and public installation verification.

# RC12.26 — Reference integrity and failure reporting
- Six permanent tests: truncated portrait, corrupt approved reference, replacement recovery, exact selected-byte validation, disappearing file, complete and partial failure (some tests cover multiple checks).
- [x] Final complete cumulative gate: 442 collected, 440 passed, zero failures, two approved skips; 94 test modules; three zero exit codes. See TEST_RESULTS.txt.
- [x] Maintainer confirmed artwork was created by ChatGPT during development; historical creation records not independently examined.
- [x] Maintainer reports all six RC12.26 focused live checks passed.
- [ ] Final rights and publisher review remain pending.

# RC12.25 — Deferred appearance analysis
- Waiting batch visible independently of native generation queue; one batch only; cancel while waiting and running; reject permanent errors; stale reference/model checks; no retry of completed inference; release lock if generation joins before model load; reopen review from server status.
- [x] Eight permanent deferred-analysis cases, native lock acquisition race, 23 related focused checks, synthetic exact Git upgrade and fresh installation. Full gate: 434 passed, 0 failed, two approved skips, 436 collected, 93 modules. Final fingerprints and syntax checks passed.
- [x] Maintainer reported 13/13 RC12.25 live acceptance checks, including deferred scheduling, cancellation, Safari refresh, autosave/navigation and wardrobe separation.

# v1.0.0-rc.12.24 — Physical identity review

- [x] Complete cumulative regression gate on final code: 426 passed, zero failed, two approved skips, 428 collected, 92 modules. Final fingerprints, syntax, synthetic exact Git upgrade and fresh installation passed.
- [x] Maintainer verified RC12.24 wardrobe separation on RC12.25.

# v1.0.0-rc.12.23 — Final stabilization

- [x] Reproduce duplicate cold scans and concurrent Personal-registration disclosure on unchanged RC12.22.
- [x] Three focused tests: shared scan, invalidation and Personal exclusion, cache and scan-failure recovery.
- [x] Initial inventory-only candidate: 412 passed, zero failed, two approved retired Docker skips, 414 collected, 89 modules. Superseded by navigation changes; not the final gate.
- [x] Focused browser tests for exact appearance navigation, approved/unapproved reviews and manual character identity autosave (debounce, flush on close/switch, failure recovery, empty draft, concurrent edits).
- [x] Final complete cumulative regression gate: 423 passed, zero failed, two approved retired Docker skips, 425 collected, 91 modules. Final fingerprints, Python/JS syntax, synthetic exact Git upgrade and fresh native mount passed. See TEST_RESULTS.txt.
- [x] Maintainer verified correct character navigation and autosave on RC12.25; active-generation protection and deferred scheduling passed.
- [ ] Separate explicit inventory scan check, public provenance and publisher review remain pending where not independently verified.

# v1.0.0-rc.12.22 — Live generation monitor recovery

- [x] Active-job following, four media-transition combinations, cancellation and stale revision rejection; six permanent regression cases.
- [x] Complete cumulative regression gate: 409 passed, zero failed, two retired Docker checks skipped, 411 collected, 88 modules. Syntax, synthetic Git upgrade and external-data checks passed. Distribution and staged-index audits required before delivery.
- [x] Maintainer live RC12.22 monitor, image/video, cancellation, conversion, Workshop, vision inference, cleanup, character fidelity and caption checks.
- [ ] Live active-generation protection during vision analysis.

# v1.0.0-rc.12.21 — Identity captions

- [x] Focused checks for repeated toggles, every image model and subject category, stale/pasted caption instructions, saved templates, preview/export, native queue and manual final edits.
- [x] Complete final cumulative regression gate: 403 passed, zero failed, two retired Docker checks skipped, 405 collected, 87 modules. Python/inline JS syntax, synthetic exact Git upgrade and external data checks passed. See TEST_RESULTS.txt for measured results and distribution audit.
- [ ] Live Safari, actual generation, native vision and conversion remain installation checks.

# v1.0.0-rc.12.16 — Spit and polish

- [x] Seven permanent Chromium regressions for missing preferred engine, valid selections, explicit portrayal year, old review, temporary monitor disconnect, out-of-order status and missing job.
- [x] Final cumulative gate: 379 passed, zero failed, two retired Docker skips, 381 collected; fingerprints unchanged. See TEST_RESULTS.txt.
- [x] Git fast-forward, restart, external state preservation and syntax.
- [ ] Live GPU, real WanGP download/reference paths, Safari, public licensing and documentation.
- Distribution ZIP and staged Git index privacy gate required before delivery.

# v1.0.0-rc.12.15 — Sequel-oriented character prompts

- [x] H3 six ordered sections, fixed portrayal traits once per shot, reference-role separation, independent scene actions and nested wardrobe.
- [x] All eight still model options, P-H3-Image opening, clean native prompt bodies, optional public live-action caption and final custom prompt preservation.
- [x] Vision instructions cover finished anatomical topology, pigmentation and irises, without new inference for ordinary prompts.
- [x] Final cumulative gate: 372 passed, zero failed, two retired Docker skips, 374 collected; fingerprints unchanged. See TEST_RESULTS.txt.
- [x] Git fast-forward, restart, external state preservation, syntax and additional browser caption checks.
- [ ] Live GPU rendering, reference numbering, prompt fidelity and Safari validation.
- Distribution ZIP and staged Git index privacy gate required before delivery.

# v1.0.0-rc.12.14 — Direct character editing and library conversion

- [x] Direct character navigation independent of casting selection; catalog portrayal/year validation and existing identity/vision regression coverage.
- [x] Explicit library scan, plan fingerprint, native conversion, existing counterpart skip, private consent, source-change validation, unsupported model handling and cancellation.
- [x] Final cumulative gate: 369 passed, zero failed, two retired Docker skips, 371 collected; fingerprints unchanged. See TEST_RESULTS.txt.
- [x] Git fast-forward, restart, external state preservation and syntax checks.
- [ ] Actual WanGP GPU/VAE conversion, downloads, real library and Safari validation.
- Distribution ZIP and staged Git index privacy gate required before delivery.

# v1.0.0-rc.12.13 — Character appearance profiles

- [x] Full cumulative test collection on final source: 360 passed, zero failed, two retired Docker skips; fingerprints unchanged. See TEST_RESULTS.txt.
- [x] Simulated preferred 4B, model selector, exact portrayal scoping, single and batch review, native model reuse and cleanup, missing assets and busy GPU, cancellation, invalid or changed references, changed profile, expiry, existing prompt templates, no background vision calls, and backward-compatible upgrade. Gradio relay registration smoke passed.
- [ ] On real WanGP: ensure the vision relay opens with installed 4B files; run one character and a small batch; verify GPU/RAM usage and cleanup; confirm active jobs are not interrupted; verify generation prompt and actual results in H3 and FLUX. The simulated regression suite does not establish GPU compatibility or appearance fidelity.

# v1.0.0-rc.12.12 — Visible feedback and Workshop resilience release gate

- [x] Pinned queue and reference collection feedback; one pinned dismiss control; last job receipt survives next-selection setup.
- [x] Concurrent reference saves, bounded review retry and stale collection failures.
- [x] Native Workshop operation label, stale encoder discovery and status retry without duplicate submission.
- [x] Seven new targeted cases included in the cumulative suite; focused run 17 passed.
- [x] Final complete suite: 353 passed, 0 failed, 2 retired Docker cases skipped, 355 collected, 167.42 seconds wall time. All four exit codes zero; unchanged application and test fingerprints.
- [x] Git fast-forward upgrade from RC12.11, restart, external data preservation, SQLite integrity and clean installed working tree.
- [x] Python and inline JavaScript syntax checks.
- [ ] Live WanGP/GPU and actual user library verification.
- Final source and installation archive privacy checks and exact staged source index audit required before delivery. See TEST_RESULTS.txt.

# v1.0.0-rc.12.10 — People library reliability release gate

- [x] Explicit public registration persists after RefMod removal; saved public profiles support markers and identity correction without a RefMod.
- [x] Repeated aliases, distinct-profile collisions, private-name rejection, categories, markers, optional profile symbol and current search preservation.
- [x] Reject punctuation-only names; canonical identity used for H3 and FLUX edits; fictional-character human profile/credit lookup guards.
- [x] Eleven new targeted regression cases passed separately on the final code.
- [x] Complete cumulative native suite on the final corrected code: 338 passed, 0 failed, 2 retired Docker cases skipped (190.49 seconds wall time, four disjoint test groups covering 340 collected cases). All four exit codes zero; application and test fingerprints unchanged.
- [x] Native mount, actual source-tree Git fast-forward from RC12.9, restart and synthetic external data preservation, clean working tree.
- [x] Python and inline JavaScript syntax checks.
- [ ] Live WanGP update, GPU generation and actual user library verification.
- Final source and installation archive privacy checks and exact staged source index audit are required before delivery. See TEST_RESULTS.txt.

# v1.0.0-rc.12.9 — People library release gate

- [x] Direct local public performer registration; independent of productions and installed RefMods.
- [x] Duplicate normalization, invalid/private name rejection, concurrent add safety and explicit role research.
- [x] Browser save failure recovery; delayed save does not override a newer search, Clear or tab navigation.
- [x] Responsive registration controls at 1440, 800 and 420px; synthetic 1,343-person library and role search.
- [x] Final complete native test directory: 327 passed, 0 failed, 2 retired standalone Docker tests skipped (325.19 seconds).
- [x] Seven focused RC12.9 cases passed separately on final code; the cumulative suite includes them and all prior adversarial cases.
- [x] Native mount, simulated Git fast-forward from RC12.8, restart and external data preservation, clean working tree.
- [x] Python and inline JavaScript syntax checks; final application/test source fingerprint verified unchanged after full regression.
- [ ] Real WanGP native update, GPU generation and actual user library verification.
- No arbitrary repeated stress rounds required. Full cumulative suite after final code changes and meaningful targeted/adversarial testing remain mandatory. See TEST_RESULTS.txt.

# v1.0.0-rc.12.8 — Persistent workflow and navigation release gate

- [x] Persistent gallery across restart, unchanged-file validation, playback and active-job independence.
- [x] Explicit historical failure retry, original settings/prompt snapshot and dependency/consent checks.
- [x] Technical reference quality ranking, near-duplicate grouping and opt-in test portrait workflow.
- [x] Saved public production collections in private backup, validated merge/restore.
- [x] Performer/production navigation, including missing RefMods and private-name guard.
- [x] Final complete native test directory: 320 passed, 0 failed, 2 explicitly retired standalone Docker tests skipped, 451 warnings (330.09 seconds).
- [x] Final MOAB+: 25 fresh-process rounds, 37 passing cases per round, 925 successful executions, zero failed.
- [x] Final Git fast-forward simulation from RC12.7, native mount and external-state preservation through restart; clean working tree.
- [x] Python and inline JavaScript syntax checks.
- [ ] Real WanGP native update, GPU generation, actual photo/model libraries and user-data verification.
- Full regression is mandatory after the final application or fixture correction; do not deliver ZIPs if an applicable test fails. Distribution audit performed during packaging. See TEST_RESULTS.txt.

# v1.0.0-rc.12.7 — Workspace Edition release gate

- [x] Tabbed generator workspace, shared image-set character identity, exact legacy factory action migration, RefMod variant selection, saved production sets, gallery and batch history: focused tests.
- [x] Five previously reproduced UX defects corrected; new gallery identity and stale inventory/variant cases covered by adversarial tests.
- [x] Final MOAB+: 25 isolated fresh-process rounds, 31 cases each, 775 passed, zero failed.
- [x] Earlier cumulative candidate: 251 passed, five failed. All five subsequently passed in focused reruns (four updated UI fixtures and one corrected gallery defect).
- [ ] Single full cumulative regression on the final corrected code (not rerun after final fixes).
- [x] Actual source-tree Git fast-forward simulation from RC12.6, native mount and synthetic external-state preservation through restart.
- [x] Python and JavaScript syntax checks.
- [ ] Actual live WanGP native update, GPU generation, and real user data preservation.
- Distribution archive and staged-index privacy checks run at packaging. See TEST_RESULTS.txt.

# v1.0.0-rc.12.6 — Release gate

- [x] Multi-image prompt preview, per-scene edits, save-before-queue and preview/save failure blocking (targeted Chromium tests).
- [x] Exact-model preferences, server round trip, invalid input protection, global override restoration and fresh browser fallback/restore (targeted tests).
- [x] Default collapsed filmographies, independent expansion, selected-role counts, role search, keyboard focus and no research on expansion (targeted Chromium tests).
- [x] Final cumulative regression: 235 passed, zero failed; 346 warnings.
- [x] Ten fresh-process MOAB rounds: 180 successful executions.
- [x] Actual source-tree Git upgrade simulation and model-state restart preservation.
- [x] Python and JavaScript syntax checks; package privacy checks and exact staged index audit. See measured TEST_RESULTS.txt.
- [ ] Real WanGP plugin-manager update, Pinokio credential persistence, GPU generation, browser-specific behavior and user's existing data verification.

# v1.0.0-rc.12.5 — GitHub edition

- Cast coverage, search, empty results, compact preference and recent productions: targeted browser test.
- Approved photo counts isolated by performer, production and role, missing file excluded: targeted API test.
- Repeat startup preserves prompts and production records in external storage: targeted simulated native host test.
- Repository-root local Git clone, fast-forward, clean working tree and external sentinel: targeted Git test.
- Inspect and audit source ZIP, manual install ZIP and exact staged files with corrected privacy checker.
- See TEST_RESULTS.txt for cumulative and MOAB status; do not infer unrun tests passed.
- Outstanding real WanGP: first native install, Refmod-Fork discovery, GPU generation, user data preservation, Safari, private repository access and actual native update/rollback.

# v1.0.0-rc.12.4 — Cast workflow and private settings

- [x] Cast collector reachable without leaving production; no search before explicit choice; performer/character scopes and Workshop return tested.
- [x] Separate role photo collections and duplicate matching, role-aware export, filtered Workshop sources; legacy collection behavior retained in targeted tests.
- [x] Prompt backup round trip; malformed template and final edit rejected; previous settings retained; private edits require matching local profile consent.
- [x] Browser backup format/export, rollback after rejected import and prototype-key rejection.
- [x] Persistent model preference storage with session fallback, image model recall, separate checkpoint memory.
- [x] Final targeted test run: 31 passed, including 18 MOAB cases; earlier 13 targeted and six new-feature cases passed separately.
- [ ] Full cumulative gate: timed out without completion after 14 cases; rerun before declaring a complete release gate pass.
- [ ] Actual native host, GPU/Refmod-Fork, Safari, real photo search quality and storage under an actual browser/server restart require live testing.

# v1.0.0-rc.12.3 — Workflow edition

Before the final playback-only change: 204 cumulative tests and four additional workflow-action tests passed separately (208 distinct gate cases). Ten MOAB backend rounds passed. After the playback change: four targeted browser tests passed, including one new test (209 distinct gate cases across the staged runs). Python and JavaScript syntax checks passed. The complete gate and MOAB were not rerun after the playback-only change.

- [x] Completed video loads paused; live inference autoplay retained; manual playback is not restarted by identical status polls; retained results remain paused on new load (Chromium with simulated media methods).
- [x] Batch preflight: ready tasks and missing-RefMod blocking; no submission side effects; blocked UI cannot submit.
- [x] Exact failure retry: explicit indices, correct original prompt, duplicate-retry guard, no retry when outcomes are ambiguous; history retained when in-memory state is cleared.
- [x] Preset save/load round-trip with isolated browser Storage fixture.
- [x] Undo individual and production-wide removals; retain unrelated roles; select-all behavior remains functional.
- [x] Basic/Advanced toggle, diagnostics and single-image submission; no automatic queueing from setup.
- [x] Keyboard shortcut submits only outside editable fields.
- [x] Batch history UI only offers retry for explicitly retryable jobs.
- [x] Selected cards: buttons remain within card bounds at 1400, 700 and 420 pixel viewports; visual inspection in Chromium.
- [x] Targeted workflow/production browser tests: 12 passed; additional workflow-action tests: 4 passed.
- [x] MOAB backend suite: ten fresh-process rounds, 18 tests per round, 180 successful executions.
- [ ] Live WanGP v20.20 host/GPU and Refmod-Fork validation, cross-browser storage and shortcut behavior, real user observation and independent security assessment.

# v1.0.0-rc.12.2 — Persona audit and live monitor

- [x] Six failures reproduced against untouched RC12.1; all six repaired in targeted tests.
- [x] Power user: temporary image-count reduction preserves hidden shot drafts; closing dirty image editor prompts; failed video override deletion preserves the override and reports failure.
- [x] Novice: failed image template load blocks stale saves; failed reset reports error; failed video template load blocks saves.
- [x] Image-set, generator settings, production selection, model-family, long-video and conversion regression checks: 17 passed, 18 warnings in 32.89s.
- [x] Retained media metadata stays with the corresponding completed task even while another task is selected or running; live task identity follows the active preview. Unknown identity is not guessed.
- [x] Compact responsive preview details; long prompts collapsed by default; empty metadata hidden. Optional metadata does not prevent generation. Final monitor and MOAB combined gate: 28 passed, 48 warnings in 13.48s.
- [x] Final ten consecutive MOAB fresh-process runs: 18 cases per round; 180 passing executions, zero failures or skips.
- [x] Final cumulative release gate: 192 passed, 326 warnings in 159.90s (0:02:39); Python and JavaScript syntax checked.
- [ ] Actual WanGP v20.20 host/GPU integration, Refmod-Fork integration, cross-platform installs, Safari, real user observation and independent security assessment.

# v1.0.0-rc.12.1 — MOAB Edition

- [x] 17 failing test cases reproduced against uploaded RC12 across two baseline runs; one valid-preview control passed.
- [x] 18 new permanent cases cover conflicting native metadata, malformed artwork cache, failed worker startup, failed portrait write and oversized status.
- [x] 31 targeted regression tests passed, including related cancellation and preview handoff tests.
- [x] Ten consecutive fresh-process MOAB runs, 18 tests each, hash seeds 1–10, zero failures or skips (180 executions). Existing startup warnings remained.
- [x] Full cumulative gate: 183 passed, 324 warnings, exit 0, 143.92 seconds. Python and JavaScript syntax checked. No runtime changes after gate.
- [ ] Exact WanGP v20.20 and live GPU/Refmod-Fork integration, Safari, Windows/macOS installs, actual power loss and independent security assessment. Simulated native sessions are not equivalent to hardware integration testing.

# v1.0.0-rc.12 Nuclear Edition

- [x] Six failures reproduced against untouched RC11, subsequently repaired.
- [x] Single cancellation before/during native handle submission; batch cancellation during preparation; conversion cancellation after decode; Workshop cancellation during native submit; missing native session handled.
- [x] Terminal history retains 100 most recently completed jobs plus active jobs; long-running jobs retained when completed.
- [x] Photo cache SQLite rejection, interrupted downloads, disk-full simulation, same-URL concurrent requests (32), and untracked filename collision preservation.
- [x] 12 new targeted tests pass; full cumulative gate 161 passed, exit 0.
- [x] Four additional distinct clean adversarial rounds on final runtime: network (3), concurrency (8), storage (4), UI and recovery (5). 2,048 concurrent completions across 12 workers; 180 seeded navigation/resizes; real SQLite competing write lock. All 20 executions passed, including four newly added probes. 165 distinct tests verified across separate runs. Future runner includes all 165.
- [ ] Live GPU, actual power interruption, Safari, cross-platform installations, independent security assessment; startup deprecation warnings remain.

# v1.0.0-rc.11 Failure Cascade Testing

- [x] Accepted whole-batch cancellation is retained even when a native chunk finishes successfully; no later chunk submitted in the tested case; prior file records preserved.
- [x] Native success plus cancellation stops the batch unless the errors are explicitly confirmed individual skips.
- [x] Delayed task-indexed progress and status events cannot overwrite current task telemetry in the tested sequence.
- [x] Native cancellation exception returns controlled HTTP 409; retry succeeds; duplicate rejected.
- [x] Cancellation during native handle creation attempts cancellation when the handle becomes available and prevents later chunks in the tested case.
- [x] Cancellation during revalidation between chunks leaves the finished handle alone and preserves completed files.
- [x] Final targeted run 20 passed; complete final cumulative gate 149 passed, exit 0, no runtime modifications after gate.
- [ ] Live GPU/native cancellation timing, real power loss, Safari, cross-platform installs and independent security review.

# v1.0.0-rc.10 Nitroglycerin edition

- [x] Privacy transition after the first 250-job manifest chunk prevents subsequent invalid submission and retains previous outputs.
- [x] Exception during a later chunk retains previously completed output records.
- [x] NaN, infinity and malformed native progress/step values cannot break status JSON; valid progress remains intact.
- [x] Real SQLite trigger rejects a reference upload: controlled 503, previous files unchanged, no abandoned image and SQLite integrity OK.
- [x] Preview progress does not replace aggregate batch progress.
- [x] Delayed callbacks cannot mutate completed job status.
- [x] 120 parallel telemetry/poll operations, eight workers, all returned valid status.
- [x] 16 simultaneous conversion apply attempts: one success, fifteen conflicts; original model library remains separate.
- [x] Initial cumulative gate: 140 passed; final 27 targeted tests passed after terminal-state and conversion-apply adjustments.
- [ ] Full final cumulative rerun, actual native GPU, abrupt power loss, Safari, cross-platform and independent security testing.

# v1.0.0-rc.9 Demolition edition

- [x] Corrupt public/local categories and cast JSON preserve original records; valid catalog remains usable.
- [x] Stale settings temporary symlink does not modify unrelated sentinel.
- [x] Actual SQLite insert rejection returns controlled error, preserves existing artwork mapping and removes uncommitted image.
- [x] Injected settings rename failure retains committed bytes and removes temporary file.
- [x] Catalog and Workshop scan-history writes bypass stale temporary symlinks.
- [x] Chromium warning appears on default workspace and disappears on recovery.
- [x] Final targeted tests: 11 passed, including all seven RC9 tests.
- [x] Cumulative gate: 134 passed before final warning adjustments; final adjustments covered by targeted tests.
- [ ] Actual abrupt power-loss, native GPU, Safari and other OS integration testing; independent security assessment.

# v1.0.0-rc.8 Jackhammer round two

- [x] Damaged selection JSON, null and invalid shape preserve original bytes, load valid choices, block affected preview and unsafe bulk queue, and survive reconciliation.
- [x] Damaged unrelated choices do not prevent Personal rename or deletion.
- [x] Stale public selections cannot generate or export using a Personal profile; explicit private selection works with consent.
- [x] Registered alias privacy prevents public reference access and Workshop enumeration after Personal registration.
- [x] Native handoff revalidates a staged public task after Personal registration; model bytes preserved.
- [x] Workshop rejects duplicate physical reference sources even when IDs differ.
- [x] Chromium recovery warning and explicit reset with zero valid selections; cancelled reset preserves rows.
- [x] 120 malformed requests on eight workers: controlled 4xx, no choices/profiles/queue jobs, SQLite integrity OK.
- [x] Non-finite numeric inputs return controlled 422 instead of response serialization error.
- [x] Empty profile markers on fresh install; explicit user marker changes persist.
- [x] Cumulative regression run (before final validation/marker changes): 122 passed. Final targeted test run: 19 passed. Full final cumulative gate not rerun; all new tests registered for future gates.

# v1.0.0-rc.7 recovery and reference integrity

- [x] Shared reference files survive deletion of one record; last record deletion removes file.
- [x] Stale audit result cannot overwrite repaired reference; changed-file count returned.
- [x] Personal registration blocks public reference serving, approval and deletion without deleting existing photos.
- [x] Corrupt video settings return safe editor view with warning, original row retained; preview and queue blocked until explicit repair. Corrupt image settings produce actionable error; reset recovers. Damaged per-role override blocks only the affected selection.
- [x] Phone image and portrait EXIF rotation preserved, metadata removed.
- [x] Chromium: disable quick music during recovery; explicit reset restores it; delayed reference response cannot paint the wrong collection.
- [x] Cumulative gate 116 passed before final browser adjustment; 23 final targeted tests passed (including eight new tests). Full gate with eighth test and final HTML not rerun.
- [ ] Actual WanGP/GPU execution, Safari and cross-platform behavior, independent security review.

# v1.0.0-rc.6 upgrade cache

- [x] Native iframe URL contains the current release version; old RC1 URL serves current shell with no-store headers.
- [x] Integration status and changelog no-store; native relay, version consistency and fresh namespace preserved.
- [x] RC5 public prompt tests retained and passed; icon caching preserved. Eight targeted tests passed. Python and JavaScript syntax checked.
- [ ] Full cumulative gate not rerun; verify actual upgrade and browser reload in Safari/WanGP.

# v1.0.0-rc.5 public cinematic factory defaults

- [x] Verify five scenes across all eight image-model options and four H3 video definitions; two videos enabled and music off by default.
- [x] Verify identity, reference syntax, production year, wardrobe and caption preservation; no former scenario directions in generated defaults.
- [x] Neutral Personal video/image defaults and unchanged dedicated portrait prompts.
- [x] Save/reset behavior preserves customized templates for other models and saved final prompts; arbitrary scene edits do not inherit prior actions.
- [x] Browser-added slots 1–10 match server defaults; historical fictional-game-character regression passes after shared wardrobe wording correction.
- [x] Final cumulative gate: 108 passed; Python and JavaScript syntax verified.
- [ ] Actual generated imagery, live host integration and cross-platform behavior remain unverified.

# v1.0.0-rc.4 illustrated navigation

- [x] All five People categories have distinct bundled leading artwork; selected icon visible when closed; Productions, Workshop and logo retained.
- [x] Keyboard selection, arrow keys, Home/End, Escape, focus restoration and responsive widths 360–1440 px tested.
- [x] Eight distinct mounted PNG responses verified and decoded in Chromium from exact response bytes; direct browser navigation restricted by test environment.
- [x] RC3 unified native root and GPU temperature tests included in the cumulative gate.
- [x] 104 cumulative tests passed; 16 separately executed targeted tests passed. Python and JavaScript syntax checked.
- [ ] Real Safari/WanGP rendering, hardware temperature readings and cross-platform installations remain unverified.

# v1.0.0-rc.3 unified root and GPU telemetry

- [x] Single root field, detected-root reset, read-only derived paths, native mount equivalence and linked-family handling.
- [x] Reject invalid or unrelated root without overwriting the prior settings; preserve model bytes and private/public separation; support legacy FLUX root files.
- [x] Simulated GPU sensor readings: threshold boundaries, multiple GPUs, invalid rows, cache reuse, timeout and missing executable.
- [x] Chromium: GPU numbers and their color classes visible both collapsed and expanded, N/A on unavailable data.
- [x] Root-change cumulative gate: 100 passed; final targeted root and GPU checks: 7 passed; Python and JavaScript syntax verified.
- [ ] Actual hardware sensor readings, native WanGP integration, non-NVIDIA telemetry and cross-platform behavior remain unverified or unsupported.

# v1.0.0-rc.2 adversarial additions

- [x] Corrupt scan paths (wrong JSON type, invalid values, malformed submissions) recover without destroying the settings file.
- [x] Hard-rejected/pending/missing reference states cannot bypass approval. Hard audit failures take precedence over duplicate detection.
- [x] Corrupt reference and portrait records and symlink-shaped photos cannot read or delete unrelated sentinel files in the tested scenarios.
- [x] Invalid upload length and image decompression errors produce client errors.
- [x] 120 simultaneous-scheduled requests across 12 workers yield 20 unique profiles, 100 duplicate conflicts, and a clean SQLite integrity check.
- [x] Recover corrupt browser preferences, preserve a valid unrelated preference, and complete 250 seeded workspace switches without lost selections or JavaScript errors.
- [x] Four extra historical tests passed: browser session restoration, model path isolation, cancellation before native trigger, Workshop file preservation.
- [x] Cumulative regression gate: 95 passed in 77.85 seconds; Python and JavaScript syntax checks passed. Distribution privacy guard verified on the final ZIP.
- [ ] Actual WanGP/Refmod-Fork/GPU integration, full historical suite outside the gate, Windows/macOS and independent security review.

# v1.0.0-rc.1 additions

- [x] RC1 metadata, native route, tab and displayed version agree.
- [x] New icon renders in native tab and application asset.
- [x] New namespace initializes cleanly without touching beta data or model files.
- [x] Cumulative regression gate: 87 passed; 4 additional targeted checks passed. Distribution privacy guard passed on release ZIP. Python and JavaScript syntax checked.
- [ ] Live WanGP/Refmod-Fork integration on actual installation (manual).

# v1b5.2.18 additions

- Tested: hidden relay remains mounted; manual retry does not duplicate a staged job.
- Tested: fresh external data directory and restoration preserve model file bytes and existing records.
- Tested: native queue listing, exact task cancellation, stale status rejection, batch skip bookkeeping, text-only prompt rendering and collapsed manager behavior in Chromium with simulated host.
- Tested: navigation category icons, minimum 16px text, native selection/keyboard behavior and no horizontal overflow at five viewport widths.
- Cumulative gate before the footer addition: 86 passed (69.92 seconds). Seven targeted tests passed after adding the footer. Footer visibility, fixed positioning and dialog clearance checked across all workspaces at three viewport widths. Python and JavaScript syntax verified.
- Open: actual WanGP host relay, queue operations and cross-platform native picker appearance; full historical suite beyond cumulative gate.

# Regression checklist — v1b5.2.15

Legend: Tested = current local automated check; inspected = present in code but not fully re-executed; open = needs additional verification. GPU completion is outside the plugin's acceptance criterion.

Current cumulative gate (v1b5.2.15): 70 passed, 122 warnings, 46.29 seconds. Two additional historical tests passed. Live WanGP and full historical tests outside the gate remain unverified.

| Requirement | Current status |
|---|---|
| Television Personalities: public discovery, confirm registration, station cast and actual-person prompts | Tested using API and simulated public lookup |
| Television workflow: no startup lookup; private-profile rejection; batch reference selection and quality rejection | Tested in Chromium/API; live public providers and image downloads not exercised |
| No legacy header or selection JSON/CSV/TXT export buttons; About SVG icon | Tested by HTML structure and Chromium regressions |
| Productions startup, blank search, explicitly added synthetic cast, People dropdown | Tested in Chromium harness and API |
| Discovery without installed RefMods, public credits and private exclusion | Tested in API |
| Personal consent gate, linked private file browsing, private notes excluded | Tested API and Chromium harness |
| Personal shared templates with neutral studio | Tested: shared video action/wardrobe and studio in export and preview; image parity inspected |
| Global LoRA exact-model picker, local storage and default entry | Tested in Chromium harness; real model catalogs and cross-model switching need live verification |
| Per-window LoRA native prompt directives and validation | Tested with simulated native queue; sequence mode only |
| H3/FLUX native queue handoff and consent revalidation | Tested with fake WanGP session |
| 1–10 independent images and 128×5 batching | Tested using simulated queue |
| 15–60s sliding window controls and continuous native job | Tested with simulated queue |
| H3→FLUX conversion, yellow status and Workshop | Tested: six conversion and three picture-stack/Workshop/game classification checks |
| Monitor starts collapsed; current prompt/stage timeline visible; no stale job/task preview | Tested in Chromium and API; maintenance colors, cinematic layout and tooltips inspected |
| No automatic network research or production prepopulation | Inspected; initial empty search tested |
| Empty catalog and no private runtime state in ZIP | Package inspection |
| macOS and Windows native host acceptance | Open — only local Linux simulated host tested |
| Live provider results and coverage | Open — external sources not exercised; coverage not guaranteed |
| Existing installation HTTP 500 and legacy database | Open — path handling and schema initialization hardened; actual user's database/traceback unavailable |

## Repeatable local gate
Use a Python environment with plugin dependencies, pytest and optional Playwright/Chromium. The older test files are historical regression references, some assert previous UI layouts or removed packaging; don't interpret them as a current full-suite certification. See `run_regression.py` for the current targeted gate.


## Personal portrait regression checks
- Personal cards show Upload/Replace portrait actions.
- Personal cards show Generate portrait when consent is recorded and a linked or convertible Personal RefMod exists.
- Generate portrait opens a dedicated compatible image-model picker and submits exactly one native task without modifying selections/templates. Successful output is saved to the profile; missing/multiple outputs, duplicate requests and consent revocation are tested.
- Personal portrait generation remains blocked when consent is not recorded.

- v1b5.2.3: 34 tests passed in the cumulative gate, including Chromium portrait workflow and repeated portrait replacements. Actual WanGP runtime and Windows/macOS remain unverified.

- v1b5.2.4: 36 cumulative tests passed; additional preview-streaming check passed. Actual WanGP callback ordering and Status Lite host rendering still require live testing. Untagged late callbacks within one manifest chunk cannot always be distinguished by task; previews reset when the native task transition is observed.

- v1b5.2.5: 39 cumulative tests passed; television source discovery, confirmed registration, and bulk collection tested against simulated providers. Real public search availability and downloads remain unverified.

## v1b5.2.6 final prompt editing
- [x] Persist edited prompt by role/model/scene, keep other prompts unchanged, reset to template.
- [x] Batch preview and native manifest use the edit; staged prompt survives later edits.
- [x] Sequence window count and LoRA command validation; private consent and removal.
- [x] Chromium edit, refresh, scene switch and reset with mocked API.
- Gate: 42 passed, 78 FastAPI deprecation warnings, 40.67 seconds. Actual WanGP and public providers remain unverified.

## v1b5.2.7 sliding windows
- [x] Browser: add/remove windows with collapsed session settings; four-window limit; add LoRA to Window 2, retain zero elsewhere.
- [x] API: explicit two-window schedule, one queue job, correct LoRA order and strengths, 690 requested output frames, reject conflicting duration commands.
- [x] Standard geometry defaults override competing model defaults for new sessions; missing fixed-window API geometry uses 362/18/8.
- Gate: 44 passed, 80 warnings, 41.23 seconds before final default changes; both targeted tests rerun successfully afterward. Live WanGP scheduling, native frame alignment and rendered duration unverified.

## v1b5.2.8 Workshop path repair
- [x] H3 and FLUX extraction in ordinary, linked family, and linked public directories; mocked native output, inventory discovery and logical identifiers.
- [x] Existing file and dangling destination symlink rejection; public/Personal overlap; linked decompile listing/download and retargeted destination rejection.
- Gate: 52 passed, 96 warnings, 41.43 seconds. Native execution on user installation remains unverified.

## v1b5.2.9 manual image workflow
- URL and upload controls appear before online results; explicit Load more only.
- Manual URL save requires a local archived image; failed retrieval preserves existing selection.
- Manual images take priority over suggestions, including legacy name and role aliases.
- Browser shows save failures without dismissing the dialog.

## v1b5.2.9 responsiveness
- [x] Synthetic 1,500 RefMods and 20,000 roles; reuse indexed snapshot and unchanged card elements across five tab switches; invalidate on catalog replacement.
- [x] 100 collapsed progress updates without media sources; unchanged Status Lite stage nodes retained; expanded monitor requests new preview.
- [x] 100 disabled preview callbacks produce no stored image; enabled bursts throttled; new task resets throttling; expired interest stops capture.
- Gate: 59 passed, 106 warnings, 45.87 seconds. Native WanGP performance and live source availability remain unverified.

## v1b5.2.10 legacy export cleanup
- Verify no legacy selection TXT, JSON or CSV export controls or TXT export handler; retain queue, prompt editors and reference downloads.

## v1b5.2.11 preview handoff and abort
- [x] Actual completed output retained across task boundaries; stale callbacks and unregistered output paths rejected.
- [x] Exact native queue task cancellation; duplicate and stale requests rejected; unsupported task cancellation does not cancel an entire batch.
- [x] Simulated three-task batch continues after cancellation of task two, with the completed third output retained.
- [x] Chromium: default retain/step 1, configurable step 6, static waiting mode, saved preferences, final result display, collapsed media suspension, Abort POST identity.
- [ ] Real WanGP server: verify native current-task cancellation and live output/preview events with installed model and browser.

## Documentation gate
- README contains responsible-use disclaimer, AI collaboration acknowledgment, user responsibility and legally qualified warranty/liability limits. Verified by archive inspection.

## Distribution privacy
- [x] Source, seed catalog schema, test fixtures, README, historical changelog and all seven icon assets inspected; no private runtime files or developer-specific identifiers found.
- [x] Synthetic workload counts generalized; normalized ZIP metadata; automated archive allowlist and privacy checks added.
- [ ] Public release outside ZIP: audit repository history, publisher account/profile, commit identity, release attachments and any screenshots/logs separately.

- [x] Privacy-release targeted regression: 12 passing tests across batch, image-set and performance modules; Python/JavaScript syntax and ZIP gate passed. Full cumulative runtime suite not rerun for this packaging-focused release.

## v1b5.2.14 Workshop visibility
- [x] Chromium: hide selection panel completely in Workshop, restore it in Productions and all People categories; retain selections, model, expansion and live monitor.
- [x] Five targeted regression checks passed; new navigation test included in cumulative runner.

## v1b5.2.15 empty catalog and reference recovery
- [x] Fresh installation contains no bundled casting or alias records; existing user data survives startup.
- [x] Runtime storage resolves outside the plugin, including symlink checks.
- [x] Same collection duplicate returns the existing record; another collection can reuse its pixels; missing files can be restored.
- [x] Cleanup is manual and age-limited; preserve final images, unknown files and linked files.

## v1b5.2.16 cast actions and character identity
- [x] Chromium: installed and convertible cast rows hide collection, creation and download controls; missing roles retain preparation actions.
- [x] Synthetic character encyclopedia and Wikipedia fixture: species, skin and anatomy extracted, unrelated characters and wardrobe excluded, cached by production, propagated through image/video prompts.
- [x] Manual identity override, privacy guard and failed-refresh preservation tested.
- [x] Chromium: delayed automatic character lookup completes before showing the generated prompt; trait panel opens when populated.
- [ ] Verify live public-source results and generated appearance in the user's WanGP installation.
- [x] Cumulative regression gate: 73 passed; Python/JavaScript syntax and distribution privacy checked.

## v1b5.2.17 misuse resistance and percentage preview
- [x] Seeded Chromium stress: 160 randomized keystrokes, 140 rapid workspace switches, 50 concurrent queue attempts and 50 concurrent Workshop attempts. No duplicate writes in the tested click storms.
- [x] Modal focus and Escape behavior, malformed API parameters, Unicode identity keys, Workshop destination reservation, invalid draft recovery, and exact image-set counts despite inherited native repeat settings.
- [x] Percentage handoff: 75% switches at step 6/8 and 30/40, not at 29/40. Unknown totals and newer progress events do not prematurely advance the displayed frame. Static mode, old preference migration, numeric bounds and collapsed media suspension tested.
- [ ] Live WanGP event timing, hardware-specific behavior and arbitrary untested input sequences remain unverified.
- [x] Final combined cumulative regression gate: 80 passed; Python and JavaScript syntax checked.

- [x] Workshop optional test image: explicit image checkpoint choice (not encoder), family/readiness filters, stale discovery rejection, exact second checkpoint dispatch, unavailable-at-dispatch handling, and unchecked creation with no image task.


## RC12.17 Character analysis collection
- [x] Synthetic API: local portrait dimensions, source/quality metadata, performer-photo exclusion, wrong-year collection isolation, wrong-year analysis rejection, corrupt portrait fallback.
- [x] Chromium: inspect/actual-size view, no automatic search on analysis open, explicit count/warning, character-only collector, preserve selections/engine/drafts, empty collection recovery, refresh failure, mutation guard, removed selection not silently replaced.
- [ ] Actual WanGP GPU inference, character pigmentation quality and Safari verification remain live-installation checks.

- [x] Native lifecycle: omitted, early, late and repeated hooks; actual host-order nested Blocks/tab simulation; exactly one registered event for each native relay; failed binding cannot report ready. No GPU inference in synthetic tests.

## RC12.18 Licensing
- Local legal routes, About links and current MIT label, missing/unknown documents, required archive legal files and tamper rejection. Public release requires ownership and provenance confirmation.

## RC12.19 Nested dialog stacking
- [x] Reproduce parent intercepting collector pointer events on RC12.18.
- [x] Chromium: actual return clicks over character editor, repeat collection, draft/engine retention, lightbox, Escape, 420px viewport, pending mutation dismissal guard, layer cleanup.
- [ ] Live WanGP/Safari confirmation and actual vision inference. See TEST_RESULTS.txt for final cumulative gate and archive audits.

## RC12.20 Native session state
- Synthetic host lifecycle: one and two main-form injection passes before tab creation, original shared component retained, wrapper resolves state before H3-to-FLUX conversion dispatch.
- Live conversion, actual GPU execution and current host revision verification remain required. See TEST_RESULTS.txt for measured gate.

## v1.0.1 provider and download safeguards
- Synthetic private/mixed DNS responses, pinned IPv4 and IPv6 connections with original TLS/HTTP hostname, policy gates on manual photo save, reference export and legacy photo archiving; exclude private keys from archive worker, exact private-name lookup and artwork isolation, persisted cast provenance.
- Verify existing metadata, photo collection, cache, prompt, navigation, generation, licensing, native bridge and data-preservation behavior in the complete final cumulative gate.
- Live acceptance: new first-use prompt, classification/legacy records, attribution links, real HTTPS image downloads and provider compatibility, explicit local analysis/generation, preserved Personal profiles and consent. Private vulnerability reporting and lawful promotional material clearance are publisher-side.

- [x] Final v1.0.1 cumulative gate: 458 passed, zero failed, 2 approved skips; 460 collected in 97 modules. See TEST_RESULTS.txt.
- [x] Final synthetic upgrade, fresh installation and staged-source audit passed.
