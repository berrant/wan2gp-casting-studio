## v1.0.10 — Global portrayal scene scope

- Load a separate wardrobe and setting panel for every selected public character role in the video editor's global scope, regardless of generation queue/pass state. Individual scope loads only the selected role. Run public lookups sequentially; stop starting new lookups on scope change or close. Retain unsaved scene drafts by choice key and ignore stale responses.
- Add global refresh, save-edited-scenes and batch AI review controls. Protect reviewed and unsaved descriptions from bulk refresh; do not copy one character's scene to another. Batch AI opens the explicit reference-selection workflow, restricted to the captured roles, with existing batch limits. Opening or changing editor scope does not submit generation or AI analysis.
- No new database schema, upstream modifications or default prompt changes. Source-dependent details may remain unavailable; previous live checks remain outstanding.

## v1.0.9 — Portrayal-specific wardrobe and scene context

- Resolve unchanged factory wardrobe and setting fields independently from the selected dated public fictional portrayal, shared across stills and videos. Custom template, per-shot and final prompt edits retain precedence. Personal, broadcast and game prompt defaults are unchanged.
- Automatically check locally cached public scene details on opening a selected role's editor or generator. Extract only attributed wardrobe and explicit story-world setting clauses from a matching production article and year, distinguish filming locations, retain previous data on provider errors, and cache successful lookups. No new background library scan or generation-time network lookup. Display source attribution, missing details and neutral fallback; never claim a missing location is canonical.
- Add separately reviewed local WanGP vision scene analysis using approved character references, with explicit descriptive wardrobe/location instructions, native GPU scheduling and stale-source/profile safeguards. Identity-only analysis remains independent. Review inferred AI details before approval.
- Add one local SQLite table and optional backward-compatible prompt backup data. Preserve existing templates, profiles, selections and prompts; no bundled character data or upstream changes. Live provider, local model and generation quality checks remain necessary.

## v1.0.8 — Character-first generation defaults (Option D)

- Name the character and recorded production/year in generated fictional live-action prompts; the selected RefMod supplies reference-derived facial likeness and apparent age. Do not name the performer in factory identity prose or invent a second subject or numbered picture assignment.
- Fixed production-specific appearance defines pigmentation, irises, hair or biological head structures, anatomy and permanent markings; preserve the selected portrayal across frames and visible skin surfaces. H3 retains its structured video sections and reference-role descriptions; FLUX uses concise character-first prose.
- Replace the legacy factory natural-skin-texture style in fictional live-action still prompts with character-accurate surface texture and coloration. Explicit user style edits, final prompt overrides, role-specific identity records, wardrobe/action fields, captions and performer/RefMod selection remain intact. No data migration, model or upstream changes.
- Verify Hera/Ahsoka prompt rendering for every supported model family, saved custom style and exact final override preservation; actual generation quality still requires live model testing.

## v1.0.7 — Explicit research maintenance

- Add confirmed force and error-only screen-role sync and role error CSV; expose due unclassified-only and forced classification research alongside existing retry controls.
- Explain scope, eligibility and cooldown exclusions. Save bounded aggregate run history in additive local SQLite tables; show interrupted runs without resuming them.
- Require a user-reviewed Wikidata QID for single-character public stage names, validate human entity and exact alias, and import only from the linked verified-title article. No automatic identity selection or replacement.
- Preserve manual category choices and previously matched profiles on ambiguous/conflicting refresh. Report discovered screen-credit counts as classification review evidence, not automatic Actor classification. Guard error CSV cells against formula interpretation and exclude private/fictional identities.
- Retain v1.0.6 scroll-preserving selection controls. No automatic research, new queue behavior, upstream changes or licensing changes.

## v1.0.6 — Selection stability and research reporting

- Preserve performer role DOM on choice-only changes, retaining scroll anchors, focus, open menus and model variant pickers.
- Display last-run role sync counts and persistent research history from the existing database; make lookup cooldowns explicit.
- No classification inference, automatic research, data migration or model changes.

## v1.0.5 — Compact application header
- Group branding, release version, inventory scan status and maintenance state alongside a smaller logo. Keep Rescan RefMods, Settings, Getting started, Batch history, mode toggle and About in a single desktop toolbar, with responsive wrapping when necessary.
- Reduce primary navigation height without removing labels, keyboard access, the People category menu, or the established 16px minimum navigation text size. Preserve visible appearance-analysis activity and sticky navigation/maintenance/selection bands.
- Scoped application masthead styles do not change nested panel headers, generation behavior, persisted data, licensing or upstream plugins. Live host acceptance and publisher clearance remain separate.

## v1.0.4 — Production integrity follow-up
- Keep same-title TV adaptations with conflicting premiere years in separate production keys, preserve existing metadata and cast, and reuse the qualified record on repeat imports. Select the matching TVMaze premiere for cast suggestions and artwork; refuse ambiguous title-only suggestions.
- Validate explicit cast release years against production metadata, qualified titles and legacy credits. Reject conflicting or invalid bulk imports atomically, with no cast changes; yearless manual entries remain supported.
- Verify film poster lookup using the same film title/alias/year checks as the cast importer, without fetching cast sections. Preserve manually selected artwork. Qualified production labels use the recorded release year in prompts.
- Existing mixed historical records are not automatically split or rewritten. Local live acceptance and publisher clearance remain required.

## v1.0.3 — Queue-pass and cast coverage repairs
- Consolidate the primary queue actions into Queue & Next and Queue All, with remaining-selection and image-job counts, receipt-based queue-pass tracking, explicit new pass and protection against repeated last-selection submission. Queue All checks and stages only remaining selections in the current scope using their individual saved prompts. Tab-session progress is separate per model/checkpoint; native job completion and retry history remain separate.
- Verified remakes with the same base title receive distinct local production keys; fill an unknown release year only when existing credits do not conflict. Keep existing cast records and keys intact. Do not guess which release a conflicting legacy record describes.
- Read explicit cast roles from nested lists, actor/character tables, voice and additional cast sections, and recognized cast-enumeration paragraphs. Report missing billed roles, partial provider errors and TVMaze main-cast scope; do not invent missing roles or claim exhaustive coverage. Exact Personal matches remain excluded from public cast suggestions and bulk saves/imports.
- Responsible-use dialog hides disabled acknowledgment controls after acceptance and shows a clear acknowledged status and Close button; policy and saved acknowledgment unchanged.
- Local live acceptance remains required; no upstream changes, schema changes, license changes or publication authorization.

## v1.0.2 — Film title discovery repair

- Resolve film titles using Wikipedia direct lookup, redirects and a bounded title-search fallback. Check film lead metadata and documented titles, including alternate subtitles, punctuation, capitalization and optional episode notation. Reject explicit year/episode mismatches and ambiguous matches rather than importing a search hit blindly.
- The explicit film button no longer searches TVMaze first; reuse the reviewed result in the cast picker. Ignore obsolete responses after a search changes. Preserve release years in new production and cast records; do not overwrite conflicting existing production metadata. Failed or empty lookups are not cached.
- Preserve source attribution. Separate slash-delimited performer credits and stop role names at descriptive text, retaining parenthetical role names. Complex prose-only or table-only casts still require manual entry. No changes to upstream code, model settings, database schema or licensing.
- The maintainer reported a live v1.0.1 failed lookup for the 1977 Star Wars film. v1.0.2 still requires live provider and host acceptance before publication.

## v1.0.1 — Legal, privacy and responsible-use update

- Move the optional Adult Entertainer classification into the normal multi-category editor; preserve the existing local markers and other categories. Remove the dedicated navigation entry and special card flag. Retain legacy navigation compatibility as an ordinary filter. No change to search, generation or RefMod files.
- Add visible TVMaze, Wikipedia and Wikidata links and third-party data/media notices. Add SECURITY.md with private reporting instructions and a privacy/likeness/copyright reporting procedure. Clarify historic private-testing language.
- Add a versioned, explicit local responsible-use acknowledgment, enforced on covered generation, prompt export, reference collection, analysis and Workshop submission routes. No personal identification or telemetry; browsing, cancellation, deletion and consent revocation remain available. Acknowledgment does not verify consent or prevent misuse.
- Require fresh explicit confirmation when a consented Personal profile changes name or linked RefMods. Keep existing unchanged consent records and all profile/model data; improve consent wording and clarify already submitted native jobs cannot necessarily be recalled.
- Add source-level links for new cast credits, Wikipedia trait suggestions and collected reference images. Preserve existing local records and their legacy provenance; no automated Fandom scraping or search-excerpt identity suggestions. Use a project URL in Wikimedia client identification. Request strict safe search for DDGS queries; provider rights and result accuracy are not guaranteed.
- Pin server image downloads to checked public addresses, retain TLS/HTTP hostname, reject private/mixed DNS, proxies, redirects, compressed transfer and over-limit streams. Guard manual photo save, reference export and legacy photo archiving with the acknowledgment; extend exact Personal-name/alias guards across photo keys and public research fields; skip matching keys in legacy archive and prefetch workers. No data deletion.
- Maintainer reported 5/5 final v1.0.0 live acceptance passes and a satisfactory repository history audit. v1.0.1 live acceptance, actual provider compatibility, applicable rights and publisher settings remain separate checks. No public release authorized by the working copy.

## v1.0.0 — Initial stable release preparation

- Maintainer selected MIT instead of the prior noncommercial license, using generic project attribution without personal names or email. Update About, notices, contribution policy, documentation and archive license integrity check. No generation or workflow changes.
- Maintainer reported 6/6 RC12.26 focused live checks passed. Public repository privacy review, rights clearance and launch approval remain outstanding. Version metadata synchronized to v1.0.0.

## RC12.26 — Pre-release reference validation

- Exclude unreadable or oversized character artwork and approved reference images from AI appearance selection; cache bounded file metadata, not pixels, with file-change invalidation.
- Decode actual selected bytes before staging; handle references removed between listing and reading without an unhandled server error. Preserve valid alternatives, stored photos and approved profiles.
- Report all-failed analysis batches as failed; retain successful drafts and describe partial failures. No upstream, model, schema or default-prompt changes.
- Record the maintainer's 13/13 RC12.25 live acceptance results. Full cumulative gate passed (440 passed, two approved skips, zero failures). Public release remains gated on focused live checks, final rights/attribution and publisher-account review. Maintainer confirmed ChatGPT-created artwork; independent historical creation records were not examined.

## RC12.25 — Deferred appearance analysis

- Retain an explicitly submitted appearance batch while generation or its GPU lock is busy; retry only transient contention without interrupting generation.
- Expose waiting, running, cancellation and review in the header and a distinct queue-manager row. Reopen the current server-side batch after page reload.
- Recheck the native queue after acquiring the non-interrupting lock, reject duplicate batches, and revalidate model and reference inputs at execution.
- Keep approval explicit, retain existing saved profiles, and do not persist pending jobs across host restart.

## RC12.24 — Physical identity, not wardrobe

- Strengthen native vision instructions to distinguish stable character anatomy and pigmentation from removable wardrobe, equipment and lighting. Avoid contradictory iris colors and unsupported hidden traits. Flag obvious wardrobe terms on review, reject flagged approvals without modifying saved profiles, preserve editable drafts. Existing manual profiles and final prompts are untouched; no extra inference or model loads.

## RC12.23 — Final stabilization: inventory concurrency, appearance navigation and autosave

- Manual physical-appearance edits in the character card, image and video editors save automatically after a short idle period. Flush edits before switching portrayals, closing or analysis; keep failed drafts available for retry. Do not infer deletion from blank text; AI analysis still requires explicit approval.
- Opening Analyze with AI after approving a previous portrayal now opens the requested role directly. Unapproved reviews remain protected; the pending destination is clearly named and captured by exact role, with an explicit switch and confirmation. Stale portrayal changes fail closed.

- Reproduce concurrent cold scan duplication and a stale public inventory response after Personal registration on RC12.22. Serialize cold inventory scans, retain cached reads during forced refresh, recheck Personal exclusions, and retain concurrent cache invalidation.
- Preserve explicit refresh and recover from scanner failures. Three new permanent tests. Update public-facing quick start, supported model list and troubleshooting; record RC12.22 maintainer live results. No changes to generation prompts, upstream code or database schema. Public release remains gated on live active-generation protection, asset and copyright clearance, and publisher-account review.

## RC12.22 — Live generation monitor recovery

- Follow native casting activity across overlapping submissions rather than redirecting the monitor to a staged job. Keep submission receipts and exact job-status lookups separate from monitor following. Continue polling across cancellations and mixed image/video jobs while other casting work remains.
- Bind transient preview requests to the exact task and revision; reject superseded or aborted frames, drop terminal preview bytes, and unload the inactive media element when changing media types. Preserve completed-result handoff preferences and private data.
- The monitor follows observed Casting Studio generation callbacks, not unrelated native jobs or maintenance operations. Live Safari and GPU behavior still require installation testing.

## RC12.21 — Identity caption ownership

- The existing image and video caption toggles now apply to every subject category, including performer-only, game, broadcast and Personal. Enabled generates one current identity caption per generated scene or image; disabled generates none. Personal relationship labels remain available when enabled.
- Recognize pasted identity-caption instructions in the two existing generated formats and remove them from generated prompt bodies before adding the single current caption. Stored custom templates and manually edited final prompts are not rewritten. Other scene text remains intact.
- Clarify the caption controls and Personal labels. Correct the authoritative baseline declaration. No native bridge, model, license, database schema or upstream changes. Character pigmentation and live GPU/Safari verification remain open.

## RC12.20 — Native session state injection

- Request WanGP’s shared Gradio state during initial plugin setup, before host component injection. The host’s automatic request at tab construction can be too late. Prevent the native wrapper from failing before the conversion, generation or Workshop callback can begin. No private session patch or replacement state.
- Reproduce the missing-state failure in a synthetic host lifecycle and test native conversion dispatch with the actual injected component. Live GPU conversion requires installation testing.

## RC12.19 — Nested dialog stacking

- Fix live report: character reference collector could open behind the still-open character identity editor. Assign visual layer order from the existing modal stack, keep the fixed footer above dialogs, and clear temporary layers on dismissal. Preserve keyboard handling, return state, and collection mutation safeguards.
- Chromium reproduces the nested parent interception on RC12.18; add real click, repeat return, lightbox/Escape, narrow viewport and pending mutation regressions.
- Publisher confirmed live WanGP 20.20 vision relay readiness, six discovered engines and preferred default ID 3. Actual inference remains unverified.

## RC12.18 — Licensing and distribution

- Select PolyForm Noncommercial 1.0.0, retain separate commercial permissions, and document contribution rights and upstream terms. Public release remains subject to provenance clearance.
- Include license, notices and contribution policy in both archives; local About links and release audit. No runtime entitlement, model, schema or prompt changes.

## RC12.17 — Character image review and collection

- Open the existing character-only reference collector directly from each AI analysis portrayal, including roles with no usable local pictures. Return to the same analysis dialog with the engine, prior selections and unsaved review drafts intact. No automatic collection or analysis.
- Inspect every available local image at fit-to-window or actual saved size; show image source, dimensions, available technical quality, and whether portrayal confirmation is needed. The analysis button shows the total number of selected images. Warn when relying solely on a character portrait under 600 pixels on its short side or 500,000 total pixels. Technical quality is not identity validation.
- Explicitly dated character reference collections exclude other explicitly dated adaptations. Legacy undated images and portraits remain eligible for visual confirmation; portraits are not year-specific. A removed selection is never silently replaced, and an unreadable portrait is excluded.
- Preserve the existing four-images-per-role, 20-role batch limits, native vision bridge, Qwen3.5VL 4B preference, explicit approval, and customized prompt behavior. No schema, generation prompt, native model, or upstream edits.
- Fix live WanGP 20.20 (`72d50753`) empty vision-engine picker: register the Gradio vision event inside the owning tab constructor, not the earlier main-form `post_ui_setup` hook. No inference or asset discovery is triggered by registration. Live GPU inference remains an installation check.

## RC12.16 — Impatient-user polish

- A missing preferred vision engine now requires explicit selection; no automatic switch to a larger model. Analysis is disabled for empty/invalid role and image selections.
- A dated character card never resolves to an undated casting choice. Previous appearance reviews are preserved and labeled when a different character is requested; choose another batch before starting new analysis.
- Generation monitor retries temporary status failures without resubmitting, ignores out-of-order replies, and stops polling missing jobs.
- No changes to default prompts, model settings, native GPU operations, schema, or upstream files.

# v1.0.0-rc.12.15 — Sequel-oriented character prompts (2026-11-25)

- Public fictional live-action defaults separate performer facial identity from portrayal-specific phenotype and anatomy, with the fixed description stated once. Distinguish everyday performer photos from in-character evidence; retain aggregate reference wording instead of guessing Refmod-Fork runtime labels.
- H3 Ref2VA uses six ordered sections, with wardrobe in a nested detailed-description field. Each independent scene stands alone; long-video sequences retain the native sliding-window workflow. H3-Image describes the complete target, while P-H3-Image starts with `subject_definitions:` to avoid the native automatic edit prefix. FLUX uses descriptive prose with positive finished-state language.
- Optional identity captions in public live-action image/video templates, off by default for clean footage. Existing final custom prompts, wardrobe and action settings are retained. Personal, game and broadcast templates otherwise retain their established behavior.
- Strengthen local vision analysis directions for visible anatomy, count, attachment, scalp silhouette, iris appearance and pigmentation closure. No new model load, inference call or dependency for normal generation.

# v1.0.0-rc.12.14 — Direct character editing and library conversion (2026-11-25)

- Make public character names on cast cards, selections, credits and preview metadata open the portrayal-specific identity and AI appearance editor, without adding a casting selection.
- Settings: manually preview and convert missing H3 still-picture RefMods to shared FLUX format using the native queue; existing counterparts are skipped, source files and choices retained. Optional consented Personal sources; no automatic linking. Limit each reviewed batch to 500. Unsupported reverse and video/audio conversions are explicitly identified.

# v1.0.0-rc.12.13 — Experimental AI character appearance profiles (2026-11-25)

- Add optional local WanGP vision compatibility bridge with Qwen3.5 4B preferred, compatible model discovery and explicit batch execution. Verify assets and shared idle GPU state; no automatic downloads, global LLM configuration changes or background model loading.
- Analyze up to four locally saved character references per portrayal, up to 20 portrayals per batch. Reuse one temporary native vision runtime; release it after completion, cancellation or errors. Drafts require individual approval.
- Scope saved appearance traits to performer, character, production and year, preserving legacy fallback descriptions. Integrate into the existing image and video template paths without rewriting custom final prompts.
- Revalidate source identity, approval and image fingerprints; prevent accidental overwrites from stale review drafts. Store local provenance and preserve existing prompt backups. Add targeted API, simulated native runtime and Chromium regressions.

# v1.0.0-rc.12.12 — Visible feedback and Workshop resilience (2026-11-25)

- Remove redundant Close controls where the pinned × already dismisses the dialog; retain keyboard dismiss and existing save/confirmation workflows.
- Pin queue acknowledgements and reference collection feedback, retaining the last submission receipt during next-selection setup and polling.
- Serialize overlapping reference saves within the same collection, allow at most one explicit review override retry, and guard collection-specific responses after navigation.
- Label native H3/FLUX extraction and H3 decompilation with their operation rather than an unrelated previous generation prompt. Clear stale Workshop encoder selections on failed discovery, block incompatible or unavailable encoder selection, and retry status polling without enabling duplicate submission after a transient failure.
- Add seven targeted regression cases. See TEST_RESULTS.txt for measured verification and live-host limitations.

# v1.0.0-rc.12.11 — Reference collection and test image controls (2026-11-25)

- Enable native multi-file selection in reference collections, sequential validation and per-batch progress and outcome reporting.
- Keep single-image artwork selection and individual quality-review approval. Stop sending remaining files when navigating away; keep already saved files.
- Add three browser regression cases covering mixed results, navigation and single-artwork handling.
- Label the optional Workshop test image explicitly and expose a separate compatible image-checkpoint selector. Do not silently replace a selected checkpoint. Validate the choice on submission and again after extraction; the completed RefMod is retained if the test cannot run.

# v1.0.0-rc.12.10 — People library reliability (2026-11-25)

- Persist explicit performer registration regardless of installed model inventory; retain existing classifications and duplicate-name behavior.
- Permit public saved-profile markers and identity corrections without a RefMod. Reject distinct public identity collisions and private-name corrections; normalize repeated aliases and keep category, marker and optional symbol associated with the corrected identity.
- Preserve current search after a successful identity correction without overwriting a later navigation context. Refresh the public profile metadata after the correction.
- Suppress human profile links on saved fictional characters; reject direct human-profile lookup and online human filmography discovery for classified fictional or damaged classifications. Reject punctuation-only display names; use the canonical profile name for H3 and FLUX identity edits. Local credit browsing remains available.
- Extend the cumulative regression suite with eleven targeted cases for these workflows. No generation defaults, model formats or external storage schema changed. See TEST_RESULTS.txt for measured verification and limitations.

# v1.0.0-rc.12.9 — People library (2026-11-25)

- Register a public performer directly from People without requiring an installed RefMod or a production. Add All known people and Missing RefMods filters. Preserve installed-only default and existing casting choices.
- Explicitly collect references or refresh credits for saved people. Normalize duplicate names, reject private identities and invalid names, and serialize concurrent additions.
- Prevent a delayed add response from overriding a newer search or tab navigation; show save outcome and retain failed drafts.
- Release gates: full cumulative suite on final code, targeted workflow and failure cases, upgrade simulation, privacy and syntax checks. See measured test results.

# v1.0.0-rc.12.8 — Persistent workflow and navigation (2026-11-25)

- Persist the last 30 completed result records in external SQLite storage; restore only existing unchanged native files. Keep completed videos paused and gallery browsing independent of active generation.
- Persist confirmed failed-task retry snapshots locally; revalidate identity, authorization, exact RefMod path and recorded file metadata before explicit retry. Exclude successful, cancelled, unknown or already claimed tasks. Older session-only history is not retroactively reconstructible.
- Rank photo candidates using existing technical metrics, group near-duplicates by perceptual hash within their collection, preselect high-quality distinct candidates in Workshop without deleting any photos or initiating online research.
- Add opt-in neutral test portrait after successful Workshop extraction with the exact created RefMod and a compatible installed image model; report the follow-up outcome separately.
- Include saved public production selection sets in validated private settings/prompt export and merge import; preserve legacy backup compatibility and reject unsafe model identifiers.
- Make public cast and monitor performer labels navigate directly to People, including missing RefMods; role production links navigate to the corresponding cast. Preserve current selections and keep private identities unlinked.
- Require the complete cumulative regression suite and all new targeted/adversarial tests on the final corrected code before delivering any release ZIP. See current measured TEST_RESULTS.txt for release status.

# v1.0.0-rc.12.7 — Workspace Edition (2026-11-25)

- Approved UX priorities 1–8: dedicated wide generator workspace with Prompts, Model settings, Identity and Batch review tabs; explicit same-performer RefMod picker and character variant naming; grouped secondary cast/role actions and filtered selection; continuous collection/Workshop navigation; recent completed result gallery; saved production selections; settings navigation and individual fine-tune reset; searchable batch history and expandable public casting labels.
- Image-set template editor exposes shared public character identity, with explicit research/save/reset, error feedback and unsaved-edit confirmation. Identity storage is shared with video; saved final prompt edits are not silently rewritten.
- Separate legacy factory image action/pose, framing and expression; migrate exact old factory actions while retaining explicitly customized framing, expression and action text. Video templates retain time-coded scene directions; no separate video framing input exists.
- Fix stale or invalidated batch reviews, failed prompt reset losing a draft, per-prompt saved indicators, and submission enabled during a reset. Maintain per-fine-tune server settings.
- Exact RefMod path is authoritative in live prompts and exports. Never guess a character-specific cross-family counterpart. Role-specific files use the `__role__` naming marker; explicit choices supported even when several files share a performer. Re-scan local inventory on save/restore; skip missing references and preserve unrelated/existing selections. Reject corrupted saved-set keys and payloads.
- Gallery is session-local, bounded to 30 recently recorded native outputs; reject missing/changed media; deduplicate notifications; preserve late outputs without rewinding current live monitor. Completed clips do not autoplay.
- History stores public role labels and existing settings for up to 100 batches; no new persistent prompt snapshots or persistent retry. Existing native retry safety remains unchanged. Production sets are local SQLite data, separate from public package and existing settings backup. No additional keyboard shortcuts. No new automatic online research, no WanGP/Refmod-Fork core changes.
- Limits: no automatic character-specific counterpart guessing, no cross-restart gallery, no historical prompt replay, no automatic reference quality ranking or duplicate grouping. Existing library and settings remain in external runtime storage. See measured TEST_RESULTS.txt for regression and MOAB+ outcomes; actual live host integration requires user verification.

# v1.0.0-rc.12.6 — Prompt review and model persistence (2026-11-25)

- Review and edit every configured image prompt in one responsive grid. Preserve independent custom prompts, reset each individually, save all pending edits and block whole-set queueing on preview or save failures. Preserve the existing video prompt editor.
- Persist per-family/per-fine-tune generation settings and global LoRA preferences in external server state, with browser migration/fallback and private backup integration. Retain global LoRA overrides on reopen. Report save failures; validate payloads and retain unreadable prior state. Settings are shared by browsers on the same server, not per-user accounts.
- Collapse performer filmographies by default; display role and selected-role counts with independent keyboard-accessible controls. Role-only searches reveal matching roles. Maintain expansion state during browsing; refreshing roles is separate and explicit.
- Update the native plugin version, UI About and user-agent versions; preserve repository-root installation layout and external data. Retain the staged-file privacy checker. Update older browser fixtures to account for disclosure and catalog snapshots.
- See TEST_RESULTS.txt for the measured release gates and remaining real-host verification.

# v1.0.0-rc.12.5 — GitHub edition (2026-11-25)

- Keep the GitHub-native repository-root plugin layout and synchronize version metadata across the host plugin, UI and HTTP agents.
- Include the corrected privacy checker supporting both archive layouts and the staged Git index.
- Add production cast coverage filters, installed coverage progress, approved local photo counts scoped to performer/role, compact cast view, cast-name search and browser-local recent productions.
- Explicit coverage refresh rescans model inventory; stale cast responses are ignored when the production or model changes. Returning from Workshop retains cast filters; closing collection refreshes counts.
- Preserve external database, model libraries, browser preference keys and factory prompt defaults. Compact preference is exportable; recent production history is not.
- No queue submission or RefMod conversion changes. Multiple RefMods per role, import preview, backup reminders and reference candidate resume remain follow-up work.
- Repair two stale Workshop test fixtures: the role-scoped third argument and the updated browse section markup. Include the maintenance-layout case in the cumulative gate.
- See TEST_RESULTS.txt for measured verification; native live host installation is not certified by the simulated tests.

# v1.0.0-rc.12.4 — Cast workflow and private settings (2026-11-25)

- Add reference collection directly to every production cast card, installed or missing. Choose general performer photos, role/production-specific character photos, or both through separate collection scopes; retain the cast context when entering and returning from Workshop. Refresh availability on return and successful creation. The collector uses explicit user actions and existing quality review.
- Separate reference matching, duplicate detection, listing, audit, ZIP export and Workshop validation by character where requested. Legacy production-level collections remain supported. Prevent stale collection results from replacing the current Workshop view; clear unavailable sources and avoid approval prompts for a closed or switched collection.
- Add Settings export/import of a private, versioned JSON backup, separate from distribution archives. Include saved video/image templates, overrides, final prompt edits, character traits, browser model and generation settings, global LoRAs, presets, preview and UI preferences. Validate before merging; reject malformed input, protect prototype keys, roll back browser preference changes on rejected import where storage permits, skip private final edits without matching consent. Machine-specific paths, identity/profile records, consent, photos, model files, history and credentials are not imported. Backups are sensitive and user-controlled.
- Persist generator preferences in browser local storage with legacy session fallback. Remember last image family and actual checkpoint per model family, and provide an Image/Video selector; retain selected model across a restart on the same origin. Warn if the saved checkpoint is unavailable. Do not assume the backup can restore models missing from a new machine.
- Verification: final targeted suite 31 passed (18 MOAB + six RC12.4 tests + seven related reference and identity cases). Earlier targeted suite 13 passed, including legacy generator-session coverage; new-feature suite six passed. Full cumulative runner stalled after 14 completed cases and timed out without a final result; do not treat it as passed. Browser tests use Chromium and isolated/mocked storage and native responses; actual WanGP v20.20, real GPU, Safari, photo-provider and Refmod-Fork integration remain unverified.

# v1.0.0-rc.12.3 — Workflow Edition (2026-11-25)

Before the final playback-only change: 204 cumulative tests and four additional workflow-action tests passed separately (208 distinct gate cases). Ten MOAB backend rounds passed. After the playback change: four targeted browser tests passed, including one new test (209 distinct gate cases across the staged runs). Python and JavaScript syntax checks passed. The complete gate and MOAB were not rerun after the playback-only change.

Compatibility target: WanGP v20.20. Baseline RC12.2; implements the power-user and novice-user recommendations from that release.

- Completed monitor videos now load paused with controls; live inference video retains autoplay. Repeated status polls do not interrupt manual playback of the same result. Chromium regression uses simulated media methods.
- Add a batch preflight report with per-task blocking issues, model, effective LoRAs, resolution, steps, counts and native relay availability. Preflight performs no native submission. A blocked report cannot approve the batch; live validation still occurs on submission and before generation.
- Add named browser-local generation presets for model family/checkpoint, effective LoRA stack and multipliers, resolution, steps, seed, sliding windows and extra settings; require the matching family and an available checkpoint. Load uses a temporary global-default override to preserve saved effective LoRAs.
- Add bounded local SQLite history for the last 100 casting jobs, including submitted settings and results. State changes, not progress events, update history. Unconfirmed active records after restart are marked unknown. Do not store full positive-prompt snapshots or performer metadata in this table.
- Add explicit failed-task retry using validated native failure indices only. Exclude known successful output tasks, cancellations and ambiguous failure reports. Retain original prompt snapshots in RAM, recheck live dependencies, prevent duplicate retries and do not automatically replay skipped work. Retry is available only in the same process while snapshots are retained.
- Add undo for individual and production-wide selection removals (20 actions per page session); preserve the destructive Remove all confirmation and do not change queued tasks. Fix a regression discovered in Select All when wiring the production-wide undo path.
- Add Alt+N (queue and next), Alt+P (refresh prompt), Alt+Left/Right (selection navigation), Alt+U (undo removal); ignore shortcut handling inside editable fields and other dialogs.
- Add optional Getting started walkthrough, setup diagnostics, reversible Basic/Advanced modes, plain-language explanations, empty-state guidance and Basic-mode single-task submission. Advanced remains the default and switching modes does not reset existing model settings. No new automatic research or download jobs.
- Selected combinations now use responsive grid cards and wrap long text; Remove remains inside the card at narrow and wide widths. RC12.2 live preview identity and template-editor recovery are retained.
- New permanent tests cover backend preflight, exact retry and history, undo, responsive cards, mode switching, preset round-trip, blocked browser preflight, single-task novice submission, keyboard isolation, and the history retry UI. Preset tests use an isolated Storage interface because the browser sandbox denies localStorage on about:blank and blocks arbitrary HTTP navigation. Existing production workflow and bulk-review browser tests are added to the release gate; mock native preflight is explicitly provided.
- Ten independent MOAB backend rounds passed 18 cases each; targeted workflow and production browser suite passed 12 tests; four additional action tests passed. Live WanGP v20.20, actual GPU and Refmod-Fork integration, Safari and other OS/browser combinations remain unverified. See release test results for the cumulative regression outcome.

# v1.0.0-rc.12.2 — Persona audit and live monitor accuracy

- Built directly from RC12.1. Six new Chromium persona regression tests reproduced six distinct defects on the unmodified baseline; all six pass after fixes.
- Image template editor: retain temporarily hidden shot drafts when reducing and re-expanding image count within an editing session; confirm before discarding unsaved edits on close. Saving a reduced count persists only active shots, intentionally.
- Image template editor: clear stale draft before loading another model; bind writes to the model actually loaded; prevent saves/resets after load failure, serialize in-flight editor operations, report reset failures without replacing existing drafts.
- Video template editor: validate both template and override HTTP responses before enabling writes; prevent saving after failed loads; serialize in-flight operations; retain overrides when a reset request fails; report errors rather than falsely claiming success.
- Correct an outdated production browser fixture to enter a search and explicitly reopen the production on returning to the workspace, matching the existing search-first behavior. No navigation behavior changed.
- Live monitor: snapshot submitted identity, role, production, scene and final prompt per generation; bind retained completed results to the exact native task when known; never infer unknown output identity from the currently edited selection or latest queued task. Reference lookup follows the displayed task; personal profiles remain excluded from public photo lookup. Unknown outputs are labeled honestly.
- Rework the right-hand monitor into a compact identity hierarchy, optional submitted prompt, and independent tracked-generation progress. Hide empty fields and redundant status copy; retain existing previous-result handoff and abort controls. Add responsive layout/long-prompt coverage.
- During the post-preview MOAB run, four existing cases detected a new regression caused by assuming optional monitor metadata was always present. Fix the single and batch paths to accept missing metadata without blocking generation. All four cases pass again.
- Verification: RC12.1 persona baseline 6 failed in 10.26s; repaired persona tests 6 passed in 9.08s; related browser and conversion checks 17 passed, 18 warnings in 32.89s; initial cumulative gate 189 passed, 324 warnings in 177.43s (0:02:57); final combined monitor/MOAB run 28 passed, 48 warnings in 13.48s; final cumulative gate 192 passed, 326 warnings in 159.90s (0:02:39); ten consecutive fresh-process MOAB rounds after the last code change (18 cases each, 180 passing executions). Python and JavaScript syntax checks passed. Existing FastAPI startup deprecation warnings remain.
- Recommendations only, not implemented: power-user batch preflight, named generation presets, retry failed jobs only, selection undo, keyboard shortcuts, persistent batch history; novice first-run setup, guided first generation, Basic/Advanced mode, actionable empty states, inline terminology, integration diagnostics.
- Compatibility target WanGP v20.20. Browser tests use headless Chromium and simulated backend responses. Actual host, live GPU/Refmod-Fork integration, Safari, other platforms, real-user observations and independent security verification remain outstanding. No persistent template, preference, user library or namespace migration.

# v1.0.0-rc.12.1 — MOAB Edition

- Reconstructed directly from the uploaded RC12 distribution, not the interrupted RC12.1 working tree. Initially 13 failures and one passing control; four additional baseline probes subsequently failed, for 17 confirmed failing cases in 18 new permanent tests.
- Reject inconsistent preview indices and counts; validate native chunk metadata before mapping to aggregate task numbers; ignore oversized or malformed batch status messages. Preview callbacks without identifiers still depend on native ordering.
- Refresh invalid artwork cache entries instead of trusting damaged timestamps, non-text values or non-HTTPS URLs. Failed manual portrait writes return HTTP 503 and retain the previous mapping; cleanup is best-effort if storage itself fails.
- Failed performer enrichment, enrichment retry, image prefetch, photo archive and credit synchronization worker launches return controlled errors and clear stalled state. Retrying remains possible. No changes to existing catalog, prompts, preferences, model libraries or storage namespaces.
- Verification: 31 targeted regression tests passed; 10 consecutive fresh-process MOAB runs with PYTHONHASHSEED 1–10 each passed all 18 cases (180 executions, zero failures). Full cumulative runner on final runtime: 183 passed, exit 0, 324 FastAPI startup deprecation warnings in 143.92 seconds. Python and JavaScript syntax checks passed. No runtime changes after the final gate.
- WanGP v20.20 is the intended compatibility target; public native API documentation reviewed, but exact v20.20 checkout, live GPU/Refmod-Fork integration, Safari, cross-platform installations, actual power-loss behavior and independent security auditing remain unverified. Ten runs repeated the MOAB suite, not the complete cumulative suite ten times.

# v1.0.0-rc.12 — Nuclear Edition

- Reconstructed from the verified RC11 distribution; the interrupted earlier RC12 working tree was not used. Six new baseline failures reproduced, two baseline controls passed. Fix single and batch cancellation during preparation/handle creation; respect cancellation between H3 decoding and FLUX encoding and Workshop handoff. Missing native conversion session becomes a controlled failed job. Accepted native tasks remain subject to native cancellation behavior; no guarantee of immediate GPU termination. Cancelled conversion files are retained, not automatically applied.
- Retain up to 100 terminal jobs in completion order, separately from active jobs. Do not revive pruned or terminal jobs through late callbacks. This is a job-count bound, not a byte limit or a physical GPU memory guarantee.
- Online photograph cache: recheck same-URL cache under the local write lock; exclusively create temporary files, avoid overwriting preexisting untracked files, roll back newly published files on SQLite failure and clean incomplete temporary writes when possible. Interrupted streams and malformed provider responses do not publish a cache record. No changes to templates, model roots, profile defaults or persistent namespaces.
- Verification: 12 new targeted tests pass; full cumulative gate 161 passed in 85.99s, exit 0, 282 FastAPI startup deprecation warnings. Four further independent adversarial rounds passed against the same runtime code: network boundaries (3 tests), concurrency and 2,048 job completions (8), real SQLite write contention and storage fault injection (4), browser resize/navigation and privacy recovery (5). Four new probes added to the future cumulative runner after the full gate; 165 distinct cases verified across the full gate and the four rounds. No runtime changes after the full gate. Four consecutive clean rounds achieved for these tested scenarios, not proof of zero defects. Live GPU, actual power loss, Safari, Windows/macOS and independent security auditing remain unverified.

# v1.0.0-rc.11 — Failure Cascade Testing

- Built directly from RC10. Four new failure-injection tests failed on untouched RC10: whole-batch cancel lost when the native handle returned success, native cancelled flag ignored when accompanied by success, stale task-indexed callbacks overwrote later task telemetry, and native cancellation refusal escaped the HTTP endpoint.
- Persist whole-batch cancel requests across chunks; stop further chunks at the next cancellation boundary and preserve completed output records. Reject repeated cancellation requests; remove completed chunk handles before the next chunk. If cancellation arrives while a handle is being created, attempt native cancellation as soon as it exists. A native chunk already entering or accepted by WanGP may run until its native cancellation is processed. The plugin cannot guarantee immediate GPU termination. Explicit individual skips retain existing behavior.
- Validate identified status/progress events and update under the same lock; reject stale and conflicting task indices. Native events without task identifiers still depend on native ordering. Return HTTP 409 for cancellation refusal and allow retries. Disable individual Abort while whole-job cancellation is pending.
- Six permanent new tests (four baseline failures, plus cancellation during native handle creation and between chunks). Final targeted run: 20 passed in 8.72s. Complete final cumulative gate: 149 passed in 106.66s, exit 0. 258 FastAPI startup deprecation warnings; no failures. No runtime code changes after this gate. Simulated native integration, not live GPU, actual power-loss, Safari, cross-platform or independent security testing.
- Synchronize release metadata and README title; keep empty catalog, external data paths, model library, prompts and preferences unchanged.

# v1.0.0-rc.10 — Nitroglycerin edition

- Built directly from RC9. Four failures reproduced against the original archive: later native manifest chunks did not revalidate casting eligibility after a privacy transition; a native exception discarded earlier completed-file records; non-finite/malformed telemetry broke status serialization; and a real SQLite reference insert rejection escaped as an unhandled exception.
- Revalidate each later manifest chunk while retaining staged settings. Already accepted native tasks cannot be retroactively stopped by this check. Preserve completed chunk outputs on later failures. Sanitize progress/step telemetry, maintain independent aggregate batch progress, and ignore callbacks after terminal state. An additional regression exposed the legitimate conversion-applied update being blocked by the terminal guard; retain that explicit update and serialize the conversion apply transaction and marker to reject repeated requests.
- Exclusively create reference temporary files, clean up uncommitted files after write failure, return controlled 503, and offload local reference quality/save work to a threadpool. Preserve existing image collections.
- Verification: four baseline failures, then four passing fixes. Additional batch progress, late callbacks, concurrent malformed telemetry (120 operations, eight workers) and concurrent conversion apply (16 requests, one successful apply) tested. Cumulative gate exit 0: 140 passed in 106.58s, started before final terminal callback and conversion apply adjustments. Final targeted run: 27 passed in 11.71s, including all eight new tests and prior conversion, privacy handoff, cancellation, monitor and update tests. A complete final cumulative rerun was not performed. Simulated native integration, not real GPU or Safari/cross-platform verification. FastAPI startup deprecation warnings remain.
- No changes to default prompts, model library, data namespace or empty starter catalog.

# v1.0.0-rc.9 — Demolition edition

- Built directly from RC8. Keep plugin identity, data/model locations, saved preferences, factory prompts and empty starter catalog unchanged.
- Four failures reproduced on untouched RC8: corrupt classification JSON, malformed cast rows, stale settings temporary symlink overwriting an unrelated sentinel file, and SQLite rejection of an artwork save leaving an orphan. Safely decode saved catalog rows without changing corrupt records, expose a recovery count and warning, and exclude damaged local classifications from automated human research without treating them as fictional for prompts.
- Exclusively create same-directory temporary files, flush and sync settings/history writes before atomic replacement. Preserve previous settings on a failed rename. Clean up new uncommitted artwork on failed local upload/database write; keep the original mapping. Recognize the new stale temporary-file naming convention in manual cleanup.
- Correct hidden recovery-warning styling; the browser test verifies the warning appears on the default workspace and disappears after recovery.
- Verification: four baseline failures reproduced; six backend demolition tests and one browser demolition test pass. Cumulative gate: 134 passed, exit 0 (started before final browser-warning changes). Final targeted run: 11 passed, including all seven new tests, update cache and prior recovery checks. FastAPI startup deprecation warnings remain. Tests use isolated fixtures and simulated integrations; actual GPU, Safari, cross-platform and hostile-local-user/network security verification remain outstanding. Interrupted-write tests simulate SQLite and rename failures, not actual power loss.

# v1.0.0-rc.8 — Jackhammer round two

- Built directly from RC7. Keep the plugin identity, data/model paths, browser storage, factory prompts and empty catalog unchanged.
- Reproduce five failures: malformed selection payloads breaking the list or unrelated Personal editing/removal, a formerly public choice silently selecting a private model, and a registered alias bypassing Personal reference restrictions. Preserve damaged rows, display a recovery warning, block unsafe batch/exports, and require explicit Personal selections. Revalidate profile eligibility and consent at queue handoff, and expand registered aliases conservatively for Personal exclusions.
- Browser recovery works even when all saved choices are malformed. Reset is explicitly confirmed. The duplicate-source Workshop guard already rejects multiple records for one physical image. Model files remain unchanged in the simulated native handoff test.
- A 120-request malformed-input storm across six endpoints and eight workers passed with no staged tasks, profiles, or choices created. Non-finite numeric values caused an unhandled validation-response serialization exception; now return controlled 422 details without raw invalid input. Remove three legacy hard-coded adult profile markers; retain user-assigned local markers. The distribution checker requires empty shipped identity presets.
- Verification: five initial failures reproduced on RC7; five passed after repair. All three recovery-edge tests passed. Non-finite input failure reproduced before repair. Cumulative regression run: 122 passed before the final non-finite validation/marker changes; subsequent targeted run: 19 passed, covering all eleven new tests, update cache and previous misuse testing. Final version/package checks are separate. Full final cumulative suite was not rerun. Hardware, Safari, cross-platform and independent security verification remain outstanding; startup deprecation warnings remain.

# v1.0.0-rc.7 — Recovery and reference integrity

- Built directly from RC6. Keep the same plugin identity, external data, model root, browser storage, empty catalog and cinematic factory scenarios. Correct a stale README release candidate label.
- Reproduce five failures in RC6: shared-photo deletion, stale audit result overwriting a replacement, public reference access after Personal registration, corrupt saved templates breaking the API, and sideways EXIF-rotated photos. Preserve shared files until the last reference is removed, condition audit writes on the current filename, recheck public eligibility, and honor EXIF orientation before metadata-free derived image saves. No automatic migration or deletion on Personal registration.
- Damaged video templates allow catalog startup with an explicit editor warning; disable quick music until correction. Invalid saved image templates and affected role overrides return actionable 409 responses. Block affected generation and queue staging until explicit repair or reset, retain original stored data, and do not block unrelated selections due to a damaged role override. Ignore delayed reference responses from an earlier collection.
- Verification: five new tests failed against RC6 and passed after repair; eight RC7 tests passed on final code. Cumulative gate returned 116 passed (before final browser shortcut adjustment and eighth test); final 23-test targeted run passed including all eight RC7 tests, RC6 cache, RC5 defaults, prompt editing and misuse checks. No actual GPU, Safari, Windows/macOS host integration or Internet-exposed security verification. FastAPI startup deprecation warnings remain.

# v1.0.0-rc.6 — Upgrade cache correction

- RC5 packaged version was correct, but the iframe URL was identical across releases and the HTML had no explicit cache policy. Add a release-version query parameter to the embedded URL and no-store headers to the main HTML, integration status and changelog. Existing browser storage and external database/model paths remain unchanged. Icon caching is retained.
- Eight targeted tests passed (upgrade cache, branding, fresh namespace, native relay and RC5 factory prompts). Python and JavaScript syntax verified. Full cumulative gate not rerun; actual Safari/WanGP restart behavior remains unverified.

# v1.0.0-rc.5 — Public cinematic factory prompts

- Replace the original factory scenarios with five independent cinematic stills and four editable H3 video segments. Retain five images and two video segments enabled by default, with optional music off. Preserve reference conventions, production-specific identity, captions and model directions.
- Remove earlier scenario assumptions from runtime prompt construction and browser-created image slots; keep neutral Personal defaults and dedicated portrait generation. Keep all saved templates and final prompt edits; explicit reset operations adopt the new defaults without changing other models or saved final prompts.
- No change to application namespace, model locations, external data or starter catalog. The private archive of previous factory prompts is not bundled.
- Regression found and corrected a shared wardrobe phrase inappropriate for fictional game characters. Four new tests and the historical game-character regression passed after correction. Final cumulative gate: 108 passed in 89.17 seconds; Python and JavaScript syntax verified. FastAPI startup deprecation warnings remain. Actual WanGP/GPU generation and cross-platform installation are unverified.

# v1.0.0-rc.4 — Illustrated People navigation

- Replace the platform-dependent native emoji category dropdown with a locally illustrated, keyboard-accessible disclosure picker. Each category has a distinct leading image, including new television artwork, and the selected category icon remains visible when closed. Preserve the original application, Productions and Workshop artwork, larger navigation typography and responsive layout.
- Retain RC3's unified native RefMod root and GPU temperature monitor, with existing external data, model paths and browser preferences unchanged.
- Verification: 104 cumulative tests passed; 16 targeted navigation, portrait, television and discovery tests passed in a separate run. The eight mounted icon endpoints were checked for valid distinct PNG bytes and Chromium decoded those same bytes; direct browser navigation was blocked by the offline test environment, so API and browser checks were performed separately. Five viewport widths and keyboard selection/escape tested. Python and JavaScript syntax verified. FastAPI startup deprecation warnings remain. Actual Safari, WanGP and GPU sensor behavior remain unverified.

# v1.0.0-rc.3 — Unified library root and GPU temperature

- Replace four editable scan paths with one native RefMod root, defaulting to `WanGP/loras/refmods_plugin`; preserve the logical mount path and accept equivalent linked locations. Derived subfolders are read-only; preserve legacy FLUX root models and public/private separation. Prior per-folder scan filters are retired; the old settings file is retained until a root is saved. No model files are moved or created by this setting.
- Show server GPU core temperature in the live monitor header, including when collapsed and idle. Use cached, bounded NVIDIA driver readings, no CUDA initialization or new dependencies. Advisory green below 75°C, amber 75–84°C, red at 85°C or above. Multiple GPU readings are labelled; unsupported hardware shows N/A. No thermal control or job cancellation.
- Root-change cumulative gate: 100 passed. After adding temperature telemetry and preserving logical root paths, seven targeted tests passed (four root tests and three sensor/UI tests). Earlier 14 targeted root and compatibility tests passed. Python and JavaScript syntax verified. Actual GPU readings and live host integration remain unverified; no non-NVIDIA sensor provider in this release.

# v1.0.0-rc.2 — Adversarial hardening

- Built directly from RC1; preserve plugin identity, external data namespace, model paths and browser storage keys. No migration or catalog reset.
- Recover structurally invalid scan-path files and browser generation/LoRA preferences. Keep valid unrelated preferences and reject malformed path submissions with a client error.
- Enforce reference-review state transitions: missing, unscanned or hard-rejected images cannot be promoted by a review toggle; hard quality failures take precedence over duplicate warnings.
- Validate local media filenames and reject symlinks during photo serving, reference audit/export and portrait cleanup. Delete only portraits owned by the matching profile. Reject malformed upload lengths and image decompression errors.
- New adversarial tests reproduce four server-side failures and one browser preference failure before repair, plus a successful concurrent-write integrity test. Stress fixtures include 120 requests across 12 workers (20 unique records, 100 conflicts), 250 seeded workspace switches, and safe recovery from corrupt local records. All six new tests passed after repair. Four extra historical checks passed (browser session restoration, model path isolation, native queue cancellation, Workshop file preservation).
- Final local regression gate: 95 passed in 77.85 seconds, plus 4 separate targeted checks passed. Python and JavaScript syntax checks passed. FastAPI startup deprecation warnings remain.
- Actual GPU execution, WanGP production integration, hostile network access, full historical tests and cross-platform behavior remain unverified. The application is intended for trusted local use; these tests do not establish security for an Internet-exposed installation.

# v1.0.0-rc.1 — Casting Studio for WanGP (Release Candidate 1)

- Rebrand the application, native tab, metadata, UI, About, browser favicon and public research user agents to Casting Studio. Generic community authorship and responsible-use acknowledgments remain intact.
- New C/play/viewfinder icon uses matching native SVG and metadata-free PNG. RefMod Workshop retains its separate icon.
- Establish a clean public installation namespace: plugin folder `wan2gp-casting-studio`, route `/casting-studio`, tab ID `casting_studio`, external data `data/casting-studio`, browser preferences `casting-studio:`, and `CASTING_STUDIO_*` environment overrides. No automatic import or deletion of beta records. Existing Refmod-Fork model locations and native relay callback IDs are unchanged. Stop WanGP and move the old beta plugin out of the plugins directory before installing RC1.
- Empty distribution catalog and privacy guard retained; no new bundled user records. Historical development notes retained as history.
- Local validation: 87 cumulative regression tests passed; four additional branding, isolated data, native SVG and mounted route tests passed. Python and JavaScript syntax verified. FastAPI startup deprecation warnings remain. No actual WanGP/GPU or cross-platform installation verification; public name/trademark availability not assessed.

# v1b5.2.18 — Native queue management and readable navigation

- Hide the native Gradio queue relay and redundant status display without unmounting their callbacks. Settings → Troubleshooting provides a retry of already staged jobs, not a new submission.
- Add a collapsed WanGP Queue Manager below the live monitor. It reads the native queue only while expanded, supports individual queued-task removal and active-task abort with confirmation and stale-task validation, and uses the browser's native Gradio relay. Reordering and editing remain in WanGP's main interface; older host versions may not expose these operations.
- Add a persistent red responsible-use footer across Casting Board workspaces and dialogs, reserving its height to avoid obstructing controls. No forced host tab ordering.
- Enlarge Productions, People and RefMod Workshop navigation text and add category-specific icons to the native People dropdown. Responsive layout and native keyboard controls retained. Native emoji rendering depends on the operating system/browser.
- Cumulative gate before the footer addition: 86 passed (69.92 seconds). After adding the footer, seven targeted tests passed, including the new footer test. Python and JavaScript syntax verified.
- Test reversible first-run data-directory isolation, hidden callback and retry, queue list/cancel, safe prompt display, and responsive navigation at five viewport widths. No live host or GPU verification.

# v1b5.2.17 — Misuse resistance and model-independent preview handoff

- Replace the absolute preview step with a 0–100% denoising progress setting. Default 0% means the first available live preview. Preserve the legacy retain/static mode but reset the obsolete step threshold to 0%; no model-specific conversion is assumed. Use captured preview step/total rather than batch progress, and wait for known totals at positive thresholds.
- Guard queue and Workshop submissions against concurrent clicks and duplicate reservations. Force independent still-image queue jobs to native repeat and batch size one. Validate malformed generation and Workshop inputs before staging.
- Contain focus in modal dialogs, close only the topmost dialog on Escape, protect cancellation paths, reject empty identifiers and distinguish non-Latin identity keys. Recover failed prompt previews and permit discarding an invalid draft without deleting the saved prompt.
- Limit decoded portrait sizes and protect concurrent replacement writes.
- Add deterministic randomized keyboard/navigation, request-storm, invalid-input and recovery tests. All 12 targeted preview/misuse tests passed after the percentage change. Final cumulative regression gate: 80 passed. Python and JavaScript syntax verified. Live WanGP/GPU execution and exhaustive historical tests outside the gate remain unverified.

# v1b5.2.16 — Character appearance research and streamlined cast actions

- Simplify cast rows: installed or convertible RefMods retain selection and artwork controls; missing RefMods retain reference collection, image-pack and Workshop creation controls.
- Expand on-demand character research to attributed visual clauses and structured public character encyclopedia fields, including species, skin, eyes, hair and distinguishing anatomy. Require matching character and production, cache outside the plugin, retry older cache entries, and preserve useful prior results and manual overrides. No bundled character records or private-profile research.
- Template-generated image and video prompts explicitly prioritize the character's on-screen anatomy and coloration over the performer's everyday appearance. Wardrobe remains separate. Custom final prompts remain unchanged; reset them to their template to incorporate updated traits.
- Wait for current character research before preview and staging; open the identity signature panel when traits are available. Bulk jobs use locally available traits without automatic bulk research.
- Verification: 73 cumulative regression tests passed, including three new targeted tests using Chromium and simulated public-source research. Python and JavaScript syntax checked. Live sources and GPU output remain unverified.

# v1b5.2.15 — Empty distribution, external storage and reference recovery

- Remove the bundled starter catalog and named curated identity, credit, year, character and game-world presets. Empty compatibility files replace older packaged catalogs on overlay installation; runtime no longer reads them. Generic production-aware prompts and user-recorded metadata remain available. Previously bundled-only entries are no longer shown; saved SQLite records are not deleted or reseeded.
- Enforce external runtime data paths, including resolved symlink targets. Existing databases, artwork, collected references, personal portraits and preferences stay in their external storage locations.
- Scope reference image deduplication to the normalized person/production collection. Return an existing valid image ID for duplicates rather than rejecting the selection; allow a user-requested source URL to be reused from an approved local image for the same person in another collection without a network download. Recover missing reference files on recollection. Preserve independent collection files and technical image QA.
- Add manual Settings → Temporary file cleanup, with a count and size check and confirmation. Only recognized abandoned temporary writes older than 24 hours are removed; never delete saved photos, unknown files, symlinks, databases or RefMods. No automatic cleanup.
- Privacy release gate now requires zero bundled catalog entries. Cumulative requirements and test fixtures updated.
- Validation: 70 cumulative gate tests passed (including four new storage/reference/cleanup tests); two additional historical tests passed using locally registered or researched fixtures. Python/JavaScript syntax checks passed. No live server or GPU tests; not all historical tests outside the gate were rerun.

# v1b5.2.14 — Workshop workspace cleanup

- Hide the entire My Selections panel while RefMod Workshop is active. Restore it in Productions and all People categories without altering saved selections, the current model or the expanded state. The live generation monitor remains available.
- Validation: five targeted tests passed, including Chromium navigation through all six casting workspaces, legacy export controls and preview responsiveness. Full cumulative suite and live WanGP execution not rerun for this UI-only change.

# v1b5.2.13 — Distribution privacy audit

- Inspect all distributed code, public catalog records, documentation, test fixtures and seven generic icon images for developer-specific identifiers, credentials, private data and metadata.
- Replace inventory-sized and batch-sized fixtures with generic synthetic workloads (1,500 model entries / 20,000 roles and 128 selections / 640 image jobs). Generalize previous workload descriptions without changing their historical pass counts.
- Package only approved source, assets, documentation and tests; normalize ZIP member timestamps and permissions and omit archive comments and extra fields.
- Add a repeatable `check_release_privacy.py` gate and README guidance about local data, external research providers and publisher-account/commit metadata. Retain the responsible-use disclaimer and public starter catalog.
- Validation: 12 targeted batch/image-set/performance tests passed (22 pre-existing FastAPI deprecation warnings); Python and JavaScript syntax checks and the archive privacy gate passed. No functional runtime changes other than version identifiers. Full cumulative gate not rerun; no live-machine, repository-history or external account audit performed.

# v1b5.2.12 — Responsible use and AI-assisted development acknowledgment

- Add a prominent README disclaimer covering lawful and ethical use, consent, privacy, intellectual property, user responsibility, warranty and liability limitations subject to applicable law, and acknowledgment of the project creator and ChatGPT collaboration.
- Preserve the disclaimer in the cumulative requirements and regression checklist; synchronize the authoritative baseline.
- Documentation and version metadata update only. Archive integrity and changed-file inspection performed; functional regression suite not rerun. Prior v1b5.2.11 cumulative gate: 65 passed.

# v1b5.2.11 — Live preview handoff and targeted Abort

- Add a red Abort button to the generation-monitor heading, available when a tracked generation can be safely cancelled. Native single jobs use the job handle; batches use the exact active native queue ID and leave remaining tasks queued. Stale, duplicate, and unsupported cancellations are rejected rather than cancelling a whole batch.
- Default to displaying the last completed native output until a new inference preview reaches step 1. Settings → Live generation preview lets the user choose a different handoff step or a static waiting placeholder until the first available live preview. Preferences persist in the browser.
- Clearly label retained completed results; current generation status and progress remain independent. Both image and video outputs use bounded opaque native-output references. Collapsed/hidden media suspension and existing preview throttling remain intact.
- Verification: 65 cumulative regression tests passed (114 pre-existing FastAPI deprecation warnings), including five new handoff and cancellation checks. Native WanGP installation, actual GPU preview/output callbacks and native per-task cancellation remain to be verified on the user's server. Older WanGP versions without per-task queue cancellation cannot use the batch Abort control safely.

# v1b5.2.10 — Legacy prompt export cleanup

- Remove the selected-model TXT prompt export button and browser handler. Keep native queue submission, prompt editing, batch review manifests and reference-image downloads. The existing server export API remains for compatibility.
- Build directly from v1b5.2.9; no queue or data changes.
- Verification: five targeted header and persistent prompt-editor tests passed, plus JavaScript syntax check. Full cumulative gate not rerun.

# v1b5.2.9 — Artwork persistence & interface performance

- Move manual URL and upload controls above online image results. Load more results only on request.
- Archive manual public image selections locally before committing; preserve the previous image on failure, honor manual selections over automatic suggestions, and resolve legacy artwork aliases without deleting old keys.
- Cache performer and role indexes by catalog snapshot; deduplicate roles using sets, avoid repeated full scans for model lookup, reduce initial performer cards to 20, debounce search, reuse unchanged card markup and defer offscreen rendering.
- Diff live stage telemetry instead of rebuilding unchanged stages. Suspend Casting Board preview transfers/encoding when collapsed or page hidden via a short-lived interest lease; throttle opted-in preview capture to at most once per 1.25 seconds. Legacy consumers remain compatible. Upstream WanGP preview generation itself is not altered.
- Prevent overlapping scheduled maintenance/status polls and unnecessary sticky layout rewrites. Retain live stage timings and stale-preview protections.
- Verification: 59 cumulative regression tests passed, 106 FastAPI deprecation warnings, 45.87 seconds. Includes large-batch queue simulation, 100 collapsed preview updates, 100-preview bursts, a large synthetic Chromium catalog workload, image persistence/failure, and earlier workflow tests. Actual WanGP/GPU contention, network performance and Windows/macOS are not verified.

# v1b5.2.8 — Workshop output path repair

- Corrected the Workshop output-path comparison for configured RefMod directories that are symbolic links. Resolve the approved family/public folder before checking the destination; preserve the native `celebs/` identifier.
- Apply the same resolved-directory validation to H3 decompile and downloads. Reject unexpected destination links, collisions, changed staged destinations and public/Personal directory overlap.
- Resolve logical identifiers for generation in linked family or public folders; support explicitly linked FLUX public folders during inventory scanning and path validation. Correct the displayed H3 Workshop output path (previously appended a duplicate `celebs` directory).
- Verification: 52 cumulative automated tests passed, including eight new ordinary/symlinked H3/FLUX Workshop cases and security/decompile checks. Python compilation and JavaScript syntax passed. Tests use simulated WanGP on Linux; real Refmod-Fork output on the user's server and Windows/macOS installations are not verified.

# v1b5.2.7 — Explicit sliding windows and per-window LoRA controls

- Move the window builder and LoRA matrix outside collapsed session settings. Add/remove 15-second script sections (one to four). Select an installed LoRA for a specific window, with zero base strength for newly added window-only LoRAs and independent strengths for each window.
- H3 sequence mode sends explicit native duration commands with one prompt per selected window, and a single continuous queue job. Do not request an extra window to meet a nominal 30/45/60-second duration. Repeat-prompt mode retains native automatic window planning.
- Default H3 geometry: 362 generated frames, 18 overlap frames, 8 discarded tail frames per window. Previously saved session geometry is preserved; Use standard window settings restores these defaults. Show an estimated output length before native frame alignment/trim. Two explicit windows request 690 output frames (28.75 seconds at 24 fps), since the current scheduler budgets discard for each window including the last.
- Verification: cumulative gate 44 passed before the final default-setting adjustment; both targeted window tests passed again afterward, including absent API geometry and competing model defaults. Actual native WanGP queue execution and generated frame counts remain unverified.

# v1b5.2.6 — Persistent final prompt editor

- Editable queue preview with debounced SQLite persistence by selection, exact model and scene; continuous sequence scripts are isolated by duration. Explicit Save prompt and Reset to template actions. Refresh preserves edits.
- Flush saves before closing, reviewing or submitting, invalidate stale batch reviews, and freeze staged prompts while revalidating RefMods and consent. Native window LoRA directives are applied after editing.
- The separate template-based text export is unchanged. A browser crash or reload before an autosave finishes can lose unsaved text; the Save prompt status confirms persistence.
- Retain v1b5.2.5 television discovery and v1b5.2.4 telemetry and legacy export cleanup.

- Validation: 42 cumulative local tests passed (including three new prompt edit tests), Python compilation and JavaScript syntax passed. Simulated WanGP and mocked public providers; no live host queue test.

# v1b5.2.5 — Television personalities and guided reference collection

- Add Television Personalities under People for public news anchors, reporters, presenters and similar on-air talent. Dedicated debounced local search, independent of installed RefMods. Public name and optional station lookup only after a user requests it. Suggested roles and source links require identity/credit confirmation; a manual public identity is possible if lookup fails. No new automatic background scanning.
- Confirmed registration stores the category and optional station/program and on-air role without duplicate credits. Credits appear in the universal Productions workspace; user-confirmed broadcast prompts identify the person as themselves. Existing actor credits retain character-first prompting.
- Confirm, research credits and collect images opens targeted public image search and looks up further screen credits on request. Check up to 20 candidate photos and submit them through the existing quality screening path; borderline images are skipped, not auto-approved. One-click Workshop access for the active collection. The user remains responsible for confirming identity and image-use rights.
- Retain v1b5.2.4 removal of legacy JSON/CSV selection exports, About SVG icon, collapsed stage timing indicators, and preview clearing between jobs/tasks.
- Testing: 39 cumulative regression tests passed, including three new television and collection tests with mocked public search/credit sources and Chromium flow. Live search provider coverage, real public image downloads, native WanGP queue and Status Lite on the user's machine are not verified.

# v1b5.2.4 — Compact live telemetry and preview lifecycle

- Remove legacy JSON/CSV buttons from My Selections; retain text prompt export and batch review manifest export.
- Replace font-dependent About glyph with an inline SVG information icon.
- Keep Status Lite active prompt text and stage timeline visible even when the live preview is collapsed. Full metrics remain available when expanded; no new telemetry backend or network calls.
- Clear image/video sources, hide old media and reset progress when a new job is tracked; clear prior-task frames on manifest transitions and completed/failed/cancelled jobs. Include task identity in preview requests and media revision keys; ignore superseded polling responses, reject explicitly marked late frames and callbacks from previous manifest chunks. Portrait jobs participate in the live monitor.
- Validation: 36 tests passed in the cumulative local gate, plus the existing live still/video preview streaming test. Chromium and simulated native queue/API only; actual WanGP and Status Lite integration remains to be checked on the installed host. Native callbacks without task identifiers cannot always be attributed to a specific task within a chunk. Updates remain subject to polling latency.

# v1b5.2.3 — Dedicated single-profile portrait generation

- Generate portrait opens a compact, independent model picker for installed compatible image models with a linked private RefMod. No casting selection, image set editor, or shared template is altered.
- Dedicated neutral studio chest-up portrait prompt, one native job, batch_size=1 and repeat_generation=1. Model-specific global LoRA defaults and override are supported.
- On successful native completion, save the one returned image as the private profile portrait. Confirm before replacing an existing portrait. Recheck identity, consent, linked RefMod and existing portrait; preserve it on failure, cancellation, or intervening changes. No client-supplied output paths.
- Direct photo upload remains available. Models requiring conversion must first have a compatible private RefMod linked; no implicit conversion from this dialog.
- Validation: 34 tests passed in the current cumulative gate (including five new portrait tests, Chromium flow, 12 sequential replacements, native mock handoff and large image batch). FastAPI startup deprecation warnings remain. Actual live WanGP output delivery and native queue acceptance on other operating systems remain untested.
- WanGP settings reference: https://github.com/deepbeepmeep/WanGP/blob/main/docs/SETTINGS.md

# v1b5.2.2 — Personal portrait generation and upload workflow

Date: 2026-11-24

## Added
- Personal profile cards now expose a dedicated **Generate portrait** / **Generate new portrait** action when consent is recorded and a compatible Personal RefMod is linked or convertible.
- Portrait generation reuses the existing native WanGP generator flow and opens it in a Personal portrait context, scoped to that one profile.
- Personal profile cards now use the clearer **Upload portrait** / **Replace portrait** wording for local photo uploads.

## Changed
- The Personal privacy/help banner now explicitly explains that users can either upload their own portrait or generate one from a linked Personal RefMod.
- Portrait-generation entry flow defaults to an image model family matching the linked Personal RefMod when possible and opens the queue dialog with a neutral-studio portrait reminder.

## Retained
- Consent remains required for AI generation.
- Existing local portrait upload remains fully local.
- Shared Personal prompt logic remains intact; Personal image generation continues using neutral studio background handling.

## Validation performed
- Python compilation passed.
- Extracted inline JavaScript passed `node --check`.
- Targeted Personal, generator and browser workflow tests passed.
- ZIP integrity verified.

## Stress test notes
- Repeated Personal profile load/render cycles and generator previews were exercised alongside the existing regression tests.
- The feature was intentionally implemented by reusing the existing native generator path instead of introducing a second generation subsystem, reducing regression risk.


# v1b5.2.1 — Header cleanup

- Removed the obsolete Docker-era Export JSON button from the main header. Selection-level JSON/CSV exports and backend export functionality are unchanged.
- Built directly from v1b5.2.0; no queue or database changes.
- Validation: focused HTML structure regression, JavaScript syntax, Python compilation and ZIP integrity. Full historical regression gate not rerun for this UI-only patch.

# v1b5.2.0 — Universal discovery, Personal and model LoRA profiles

- Productions is the actual startup workspace. Local search is blank until typing, debounced and independent of installed RefMods. Title, person and character matches; cast/credits and known-title links; manual public TV, film and exact-name credit lookup. Reference collection and Workshop entry points are available without an installed RefMod.
- Models / Influencers is inside People. Preserve cinematic styling, collapsed monitor, hover explanations, conversion-aware role selection and maintenance colors.
- Personal profiles use compact cards, red/green consent labels, installed private RefMod pickers, shared actions/wardrobe and neutral studio backdrop/lighting. No theme music, private notes or public research. Hardened resolved-path handling and serialized database schema creation; actual previous HTTP 500 not reproduced with user's data.
- Global LoRA profiles are keyed by installed model, with catalog picker, multiplier and enabled checkbox. Legacy image/video profiles retained for manual reassignment; not automatically applied. Queue reminder and override; per-window directives for sequence-mode long H3 jobs, including preview. Global defaults take precedence over duplicate session strengths unless overridden.
- Added requirements, regression checklist and repeatable local test gate. Native-only distribution, no local private data.

Validation: 28 targeted automated checks passed in groups (10 native queue/consent/long video; 5 independent image set tests including a large image batch; 12 discovery/browser/window LoRA/conversion/Workshop checks; 1 shared Personal video template parity test). Python compilation and JavaScript syntax checked. Simulated native queue, no real macOS/Windows or live WanGP installation exercised. External lookup coverage varies; no specialist provider for all public personalities, adult-industry credits or games. Historical tests not all rerun; obsolete Docker and older UI assertions are not part of the current gate.

## v1b5.1.1 — Baseline restoration
- Restore People dropdown, production search, cinematic styling, conversion-aware selection and tooltips while retaining LoRA changes. Historical browser/queue verification incomplete.

## v1b5.1.0 — Global LoRAs and window strengths
- Initial image/video-wide defaults, submission override, maintenance red/green, native sequence LoRA directives. Built from an older baseline; superseded.

# v1b5.0.0 — Search on demand and control explanations

- Production results remain empty until a nonblank title is entered. No initial production-list request, matching pass or result-poster prefetch.
- Local search waits 300 ms after the last input, filters server-side and retains 60-result pagination. Clearing the query or leaving the tab invalidates pending results and clears queued poster lookups; already running requests may finish.
- Explicit TV lookup supersedes pending local results. Existing manual production and cast workflows remain available.
- Contextual native tooltips for ambiguous controls across navigation, productions, people, selections, prompt editors, workshop, maintenance and queue setup. Static and dynamic buttons use delegated hover/focus events; existing tooltips are preserved. No periodic tooltip scan.
- New pre-release numbering; native WanGP only. No changes to native queue payload construction or GPU handling.

Validation: five targeted tests passed (Chromium browser and simulated native API), JavaScript syntax and Python compilation checked. Full regression suite and live Windows/macOS installations not tested. Existing startup inventory and status polling are unchanged.

# v7b1 — Native beta / distribution cleanup

- First beta; subsequent builds use v7b2, v7b3, etc. Release candidates require explicit approval.
- Native WanGP only; removed container packaging, migration helper and machine-specific maintenance script.
- Removed hard-coded developer home paths, historical installed inventory, queue flags and filename registry from bundled data. Retained generic production/cast metadata; local aliases are resolved from the live database or catalog names.
- UTF-8 catalog and local configuration handling; installation-relative defaults.
- Existing dev5.14 functionality carried forward, including game-world prompts, cinematic UI, image sets, conversion-required selection and sliding-window video.
- Upgrades preserve external persistent data. Unusual legacy filenames may need a display-name correction because the old filename registry is no longer distributed.
- Cross-platform execution remains subject to host support; no physical GPU or macOS/Windows certification.
- Verification: 13 targeted image-set, long-video, conversion and game-world tests plus 6 native integration checks passed in a simulated Linux host. Two native checks were repeated after fixture sanitization. Python and JavaScript syntax checked. Native queue acceptance on actual Windows and macOS installations remains untested; GPU performance is outside the plugin acceptance criteria.


## Historical development versions (superseded)

# v7b1 — Native beta / distribution cleanup

- First beta; subsequent builds use v7b2, v7b3, etc. Release candidates require explicit approval.
- Native WanGP only; removed container packaging, migration helper and machine-specific maintenance script.
- Removed hard-coded developer home paths, historical installed inventory, queue flags and filename registry from bundled data. Retained generic production/cast metadata; local aliases are resolved from the live database or catalog names.
- UTF-8 catalog and local configuration handling; installation-relative defaults.
- Existing dev5.14 functionality carried forward, including game-world prompts, cinematic UI, image sets, conversion-required selection and sliding-window video.
- Upgrades preserve external persistent data. Unusual legacy filenames may need a display-name correction because the old filename registry is no longer distributed.
- Cross-platform execution remains subject to host support; no physical GPU or macOS/Windows certification.
- Verification: 13 targeted image-set, long-video, conversion and game-world tests plus 6 native integration checks passed in a simulated Linux host. Two native checks were repeated after fixture sanitization. Python and JavaScript syntax checked. Native queue acceptance on actual Windows and macOS installations remains untested; GPU performance is outside the plugin acceptance criteria.


# v6.9.0-dev5.14 — Game worlds & cinematic styling

- Game-character prompts include locally known production titles and game-world default environments for images and videos. Explicit settings take priority. Abby Anderson has a user-requested franchise anchor. No automatic network lookup.
- Refreshed header, navigation, primary actions and prompt previews with cinematic gradients and improved typography while preserving compact layout.

# v6.9.0-dev5.13 — People navigation, silent still images, selectable conversions (2026-11-24)

- **People navigation:** Models / Influencers is now an option in People rather than a fourth top-level workspace. Productions remains the default. RefMod Workshop stays separate.
- **Live monitor:** starts collapsed on each page load. Manual expansion and live telemetry polling still work.
- **Image-only interface:** the theme-music checkbox and video-template editor are hidden for all still-image models, even when the selected image model is restored from browser session settings. Image set editing and saved image count are restored. H3 still-image native RefMod payloads set `use_audio: false`; video retains reference audio and theme-music controls.
- **Conversion-ready roles:** green = installed in the current family; yellow = verified H3 picture RefMod requires conversion to FLUX; red = missing or not safely convertible. H3 still-picture stacks marked `kind: video` can qualify from picture metadata; temporal video, audio-bearing or malformed RefMods do not. An ambiguous set of sources is not arbitrarily selected when no source has previously been chosen.
- Conversion-ready roles can be selected individually, as themselves, or through Select all available roles. Personal profiles require consent and the existing private H3 link. Selection does not trigger GPU work. Model changes retain conversion-ready selections; truly incompatible selections follow the existing reconciliation behavior.
- Opening the native queue or explicitly exporting prompts automatically converts required selected sources using the Refmod-Fork VAE relay, limited to the relevant scope. Expansion to another queue scope checks that scope too. Progress is displayed, originals are preserved, successfully converted files are verified and linked, and the catalog is refreshed. Conversion errors block the dependent request rather than pretending a target file exists. No unrelated selections are pruned by scoped conversion apply.
- Conversion requires the native WanGP relay, compatible installed encoders and Refmod-Fork fork.58 or newer. Only the existing supported H3-picture-to-FLUX direction is advertised; standalone Docker can show and select eligible sources but cannot execute VAE conversion itself. There is no claimed FLUX-to-H3 conversion.
- All dev5.12 image-set and sliding-window features remain included. SQLite, photographs, RefMods and other runtime user data remain outside this archive.

### Validation
- 28 distinct targeted tests passed across two runs: 26 in the main run and 9 in the follow-up, with 7 overlapping tests. Coverage includes Chromium navigation, restored model settings, collapsed monitor, yellow status and select-all, mocked native relay conversion before queue preview, scoped conversion preservation, invalid source metadata, image queue audio flag, multi-image manifests, long-video behavior and existing family reconciliation.
- JavaScript syntax, Python compilation and ZIP integrity checked. The complete legacy suite has not been rerun. Native GPU/VAE conversion and audio behavior on the actual WanGP installation still need live verification.

---

# v6.9.0-dev5.12 — Productions, configurable image sets, sliding-window video (2026-11-24)

### Productions-first navigation
- Productions is the default, first-class workspace. The sticky navigation now has Productions, a **People** dropdown (Performers, Personal, Adult Entertainment), Models/Influencers, and RefMod Workshop.
- Removed numerical badges from the main navigation. The separate private Personal registry remains private and does not feed public cast research.

### Image-set repair
- Replaced the fixed 5-image editor with an **Image set builder** allowing 1–10 separately editable images.
- Each image has independent wardrobe, action, framing, expression, and setting. The saved image set is the source of truth for individual prompts and generation jobs.
- **Queue image set** sends one WanGP task per image, not only Image 1; selecting multiple roles multiplies jobs accordingly (ordered bounded manifests).
- Legacy five-image saved templates remain supported; later images do not falsely claim image chaining that WanGP has not implemented.

### H3 long video
- Duration picker supports **15, 30, 45, or 60 seconds** per video task using **one native WanGP sliding-window generation**, not independent 15-second clips concatenated in Casting Board.
- Added model-aware sliding-window controls: window size, overlap, color correction, overlap noise, discard tail frames and trim first frames. Factory values come from WanGP's resolved settings (`defaults/`, `finetunes/`, handler); when a model leaves a field unset, the UI offers a conservative fallback.
- At durations >15s choose **Use Video 1–4 in sequence** (WanGP's `PW` prompt-per-window mode) or **Repeat selected video** (`FG` mode). Existing saved video scenes and their separate actions/wardrobe remain intact. A saved template with fewer than four segments repeats its last configured prompt for remaining windows.
- Disables long-video settings for models that do not declare sliding-window support. Rejects invalid durations, unsupported settings, and impossible overlap/discard geometry.
- Session presets preserve the duration and sliding-window parameters per model, alongside LoRAs, seed, and resolution. Bulk queue of a continuous 60-second sequence produces **one movie per selected role**, not four unrelated 15-second videos.

### Validation
- Tested 60s video request with all four unique prompts and exactly one native session job, and 30s repeat-prompt request; invalid frame geometry is rejected.
- Tested Productions and People navigation in Chromium, and the image-set browser controls independently; syntax and ZIP integrity verified.
- The legacy combined regression runner stalls after many completed checks, so no claim of a clean full-suite run is made.
- **Hardware limitation:** live 60-second H3 GPU generation, audio overlap quality, and output duration normalization on the user’s WanGP installation have **not** been verified. The user should trial 30 seconds before running a full production.

---

# RefMod Casting Board for WanGP — Change Log

## v6.9.0-dev5.11 — Manual maintenance and activity indicator (2026-11-24)

- Removed the 30-second startup timer and recurring six-hour automatic public-credit synchronization. Research and classification now begin only from explicit buttons.
- Prevented the Performers tab from automatically queuing network portrait searches and IMDb/profile-link lookups. Existing saved images still display. Added an explicit Settings button to research up to 12 visible cards.
- Added a read-only, lightweight `/api/maintenance/activity` API and main-screen active-work banner with job name, progress, and **Manage / Stop**. Covers role sync, classification, photo prefetch, photo archiving, catalog inventory scans, and Workshop RefMod validation.
- Added a compact maintenance-state label to the header; activity appears on every tab.
- Fixed sticky layout collisions: selections toolbar now sits beneath both navigation and the maintenance-activity banner, with offsets recalculated at every responsive breakpoint and whenever the banner appears or disappears.
- After initial inventory indexing, model catalog now stays cached until manually rescanned or an explicit change invalidates the cache, instead of being re-enumerated every 90 seconds.
- Manual maintenance actions remain available in Settings. Never automatically stop an already active job when tabs change.

### Note
A one-time local inventory scan is necessary at initial launch to display installed RefMods; no remote research is started as a side effect. Existing background jobs from an older process must be stopped explicitly or via a WanGP restart.

# RefMod Casting Board for WanGP — Changelog

## v6.9.0-dev5.10 — FLUX Workshop, Conversion Repair & Game-Character Profiles (2026-11-24)

### Fixed
- **H3-to-FLUX conversion:** recognize Refmod-Fork's still-image stacks that are stored with `kind: video` when the metadata explicitly identifies picture-only content. Reject actual moving-video/audio sources. If conversion fails or no compatible GPU encoder is available, preserve saved selections and report the failure instead of deleting them.
- The conversion process still validates newly created FLUX `.safetensors` files and never overwrites the H3 source.
- **Screen-space cleanup:** moved photo prefetch, screen-role synchronization, and public performer classification into the expandable **Settings → Background research & maintenance** area.

### Added
- **FLUX RefMod Workshop:** choose H3 or FLUX.2/FLUX.3, collect and approve reference pictures, and create a new model-specific RefMod through Refmod-Fork's native `flux_refmod_state` extraction command. Select a compatible installed FLUX model, picture layout, and token budget. Output is validated and existing files are never overwritten.
- **Video game character category:** user-editable profile classification that distinguishes fictional game characters from actors and other real-world performers. Classified game identities are excluded from human filmography/Wikidata research and use character-preserving prompt wording, without inventing an actor. The UI presents **Find character art** and **Select character** instead of human-performer labels.
- For game-character entries with an explicitly provided production/year, prompts use that game portrayal; for entries without game metadata, prompts preserve the visual identity from **all images provided** without inventing an origin.

### Verification / limitations
- 53 backend regression checks and 22 Chromium browser checks passed locally, including H3-picture-stack detection, FLUX extraction payloads, preservation of failed-conversion selections, standalone Docker operation, and fictional-character classification.
- Model-family conversion, actual H3/FLUX extraction on a GPU, and live installation on the user's WanGP v20.x build remain **unverified**. User must explicitly classify video-game entries; it is not inferred from a photo.


## v6.9.0-dev5.9 — Responsive, No-Scroll Navigation (2026-11-24)

### Changed
- Rebuilt the sticky six-section Casting Board navigation as a responsive grid instead of an overflowing horizontal toolbar.
- All six tabs remain visible without sideways scrolling: one row on wide screens, two rows on laptop-width screens, and three rows on narrow phones.
- Tab icons and labels scale to the available width; no functionality, naming, or selected-tab behavior changes.
- Updated the sticky selection bar and production anchor offsets for different navigation heights.

### Verification
- Chromium UI checks cover widths of 390, 550, 850, 1120, 1440 and 1920 pixels, all six visible tabs, zero navigation overflow, and sticky operation when scrolling. This is a CSS/layout release; native GPU behavior is unchanged and remains unverified on the user's installation.


## v6.9.0-dev5.8 — Automatic RefMod Conversion & Navigation (2026-11-24)

### Added
- **Automatic H3 picture → FLUX RefMod conversion on model-family change**, when there is no existing compatible FLUX file for that performer. The native WanGP Gradio queue performs the same two VAE operations as Refmod-Fork's Library converter: decode the selected H3 pictures, encode them with the selected FLUX family's model, and verify the output's `klein9_refmod_meta.converted_from` provenance before applying it to the exact saved casting selection. The original H3 `.safetensors` is never overwritten.
- **No redundant conversions for repeat cast roles**: if several roles reference one H3 `.safetensors`, decode and encode it just once and link the verified FLUX output to each selected role. Public and Personal files remain in their own `celebs/` and `personal/` trees.
- Conversion runs through the *native Gradio queue relay* only, never in the FastAPI request thread. The model switch shows conversion counts and stage updates. Remaining incompatible or failed entries are reconciled only **after** conversion finishes.
- **Safety checks:** reject unverified source models, non-picture H3 RefMods, unsupported or missing H3/FLUX models, output outside configured scan folders, revoked Personal consent, mismatched target provenance, and requests to convert between unsupported model families. Revalidation occurs before and during conversion and again before saved choices are updated.

### Fixed / improved
- **Actual tab icon:** registers self-contained film/clapper SVG instead of a literal icon name shown as text.
- **Task-aware live preview:** when a WanGP manifest advances to another prompt, the prior task's image/video preview is cleared. Stale, explicitly labeled prior-task frames are ignored.
- **Performer role ranking:** known featured credits appear before lesser roles when searching an actor; year and role billing are stable tie-breakers, without inventing popularity rankings.
- **Navigation and preview:** tabs are moved above the live preview and remain sticky while scrolling. The preview itself can be collapsed; the tabs are usable without returning to the top.

### Limitations / testing
- Only Refmod-Fork's documented **H3 picture → FLUX.2/FLUX.3** conversion is automatic. H3 video/audio and FLUX → H3 have no verified direct conversion and are not attempted. The conversion requires an enabled Refmod-Fork fork.58+ and compatible H3/FLUX models in the *live* WanGP installation.
- Backend tests use a mock queue and fake `.safetensors` metadata; **actual H3 decoding and FLUX encoding on a GPU are not verified locally**. The original database, RefMods and Personal portraits are not included in the release ZIP.

## v6.9.0-dev5.7 — Production Discovery, Previews & Model Compatibility (2026-11-24)

- **Model-family switch reconciliation:** when switching H3 ↔ FLUX in My Selections, incompatible roles are automatically removed from saved active selections. When exactly one compatible alternate RefMod exists for the same performer, the selection is retained and its verified model filename is updated. A missing original file or multiple ambiguous alternatives are never silently substituted. The interface shows how many were removed or relinked, and the backend reconciles changes in one SQLite transaction.
- **H3 → FLUX conversion guidance:** Refmod-Fork already offers **Convert to Flux** for H3 picture RefMods from its own Library tab. Conversion is not performed automatically or as part of a model-family switch; no FLUX → H3 conversion is claimed.
- The **Live generation monitor** now appears beneath the app header with its preview visible by default; detailed prompts and logs remain collapsible.
- Long dialogs have a sticky close **X** at the upper-right, avoiding scrolling just to close them.
- The **Productions** view includes previously overlooked known-credit titles and paginates beyond the former 45-title cutoff; entries without verified character mapping are marked as pending discovery, not selectable cast entries.
- Automatically attempts to fill character identity signatures from exact-match Wikipedia character descriptions; accepts only appearance-specific passages with an explicit matching production reference. Caches successful and unsuccessful searches separately; saved manual descriptions always win.
- Adds a **Find character details** refresh action and source/status indicators; when the source is ambiguous or lacks stable appearance details, leaves the field empty rather than guessing.
- Automatically checks production artwork when opening a show, with manual artwork taking priority. Cast thumbnails use character-specific pictures only, never fallback performer headshots.
- Production casting controls say **Select** for a mapped role, and reserve **Add role manually** for genuinely new entries. 
- Detects the enabled Wan2GP Status Lite panel in the same-origin WanGP parent document; no additional plugin is required for Casting Board.
- Mirrors seven stage statuses (when supplied), live stage name, steps, elapsed time, ETA, stage progress, average step speed, activity text, and model download progress beside the inference preview.
- Clearly labels Status Lite information as **WanGP-wide telemetry**: the active WanGP generation might not be the casting job currently selected in the UI.
- Leaves the existing generation preview, native queue, RefMod integration, and batch workflow unchanged.
- Hides the optional panel in standalone Docker mode, when Status Lite is not mounted, or when the parent document is cross-origin.
- Uses read-only DOM snapshots from Status Lite 1.3.x, not a private Python API. Upstream changes to its UI markup can require adapter updates; no Status Lite source files are modified.
- When Status Lite is installed but idle, shows an awaiting-status message rather than stale last-run progress.

**Verification:** 50 regression tests passed in targeted backend and Chromium test groups, including API model-family reconciliation, ambiguous/missing-file rejection, H3→FLUX user-interface state, Status Lite presence/absence, earlier queue/batch safeguards, and standalone/Docker functionality. Local tests use mocks; live GPU telemetry, conversion and generation on the user's WanGP installation remain unverified. An attempted all-in-one test run exceeded the execution time limit, so the checks were completed in smaller groups.

## v6.9.0-dev5.6 — 2026-11-24

### Added
- **One-click reviewed bulk queue:** Select *All saved selections* or a single film/series, preview every task's individual H3 prompt, and submit one WanGP `submit_manifest()` batch. Supports up to **500 tasks** in one manifest, including a large selection batch.
- Choose **Video 1 only** per casting choice, or **all configured H3 video segments**. All segments are independent WanGP jobs; generated videos are not automatically chained from one segment to the next.
- Review each generated prompt and its matched `.safetensors` file before queueing; download a machine-readable JSON review manifest. Session-wide model, resolution, LoRAs and strength multipliers remain in effect.
- Production years appear in the character-first subject definition and the bottom caption when known, without guessing dates that are absent from the source catalog.
- **Character identity signature** (separate from wardrobe and action): per-production editable anatomical traits, colors, markings, and other persistent appearance cues. This signature is repeated in every video segment and applicable image prompt. An optional curated starting definition for **Ahsoka Tano (2023)** specifies orange Togruta skin, white facial markings, blue-and-white striped montrals, and three lekku. Unknown characters are not assigned invented traits.

### Fixed / safeguards
- Missing saved RefMod filenames now fail before queueing instead of silently choosing a different installed file. When switching model families (H3 ↔ FLUX), the app can use an alternative only if the saved file still exists in the other family **and exactly one** compatible file exists in the requested family; ambiguous choices must be resolved explicitly.
- At both staging and native callback execution, every task is rechecked for compatible model declarations, physical RefMod file, and Personal-profile consent. The entire batch fails preflight if a selected file is missing; it cannot quietly drop a task.
- Batch scope changes or session-setting edits invalidate earlier prompt review; explicit re-review is required.
- Character identity editor updates when switching performers or production scopes.
- New pi-H3 FL2VA models added in WanGP v20.12 are **not** treated as Refmod-Fork-compatible until the selected model exposes the required RefMod custom setting.

### Verification and limits
- **45 local tests passed**, including individually prompted batch tasks, production-scoped batches, four H3 video segments, missing-file rejection, consent revocation, model-family switching, and Chromium checks of bulk review and character identity editing. Python syntax, inline JavaScript syntax and ZIP integrity checked.
- Verified against publicly documented WanGP APIs, including `submit_manifest()` and plugin-injected sessions. **Not verified against the just-updated WanGP installation on the user's server**; actual queue acceptance and GPU identity fidelity require a live smoke test.
- Still-image scenes 2–5 are not queued as independent tasks because they require source-image chaining. The feature is deliberately blocked rather than silently producing unrelated images.
- Text instructions alone cannot guarantee model adherence to non-human anatomy; Ahsoka identity prompts should be compared using matching seeds, RefMods and model presets.

## v6.9.0-dev5.5 — 2026-11-24

### Added
- Production-first casting tools. Select roles directly from the series/film cast view, or choose **Select all available roles**. Missing RefMods are not eligible.
- **Remove this show's selections** removes only selections from the active production, after confirmation; selected roles from other shows or Personal profiles remain unchanged.
- **Queue selected from this show** opens the existing generator dialog filtered to that production; its **Queue & next selection** action advances only through matching roles. The scope selector can also switch back to **All selections**.
- Production selection totals and save/remove status are visible above the cast, without leaving the production screen.

### Fixed
- The production tab no longer displays **Select role** on previously selected entries; it shows **✓ Selected — remove** with synchronized state across both tabs.
- Choice removal now verifies the server response before updating local state; failed saves cannot appear successful.
- Role selection requires a real RefMod for the currently selected model family (H3 or FLUX).

### Verification
- **38 local tests passed**, including Chromium tests for tab synchronization, scope-restricted queueing, bulk selections, missing RefMods, preserving other productions, and save failures. Native GPU execution remains unverified.

## v6.9.0-dev5.4 — 2026-11-24

### Added
- Native WanGP `clapperboard` tab icon, complementing the custom full-color Casting Board logo.
- Last-scan timestamps and live file-check counters for installed RefMods and H3 Workshop validation, with persisted scan summary.
- Full inline decompile results gallery: inspect reconstructed images, play video/audio in the app, download individual media, or download a ZIP. Previous decompilations can be viewed without rerunning a job.
- WanGP `on_preview` image/Tiny VAE MP4 callback support, with bounded RAM cache and per-job protected media endpoint. Preview appears during inference only when WanGP publishes one.
- Read-only model factory defaults from WanGP and on-disk default/finetune definitions; session-wide overrides retained.

### Fixed
- Numbered duplicate cast roles suppressed when the same performer and production have an identical unnumbered character; no SQLite records are deleted.
- Workflow updates when RefMod scan paths change; added server-side path enforcement for reconstruction media.

### Verification
- 35 local regression tests (including Chromium UI, API security, role deduplication, preview payloads, standalone Docker) pass. Live GPU operations not verified.

## v6.9.0-dev5.3 — 2026-11-24

### Added
- New application branding, a clapper-and-film icon, an About screen, and an in-app changelog link.
- Inspect-first reference image viewer. Click search results, saved references, or Workshop photos to enlarge them before deciding to use them.
- Local JPEG/PNG/WebP uploads for performer portraits, production images, and public reference collections. Uploaded public references receive the existing quality checks, review confirmation, and duplicate screening. Max 15 MB for reference collections and 8 MB for portraits.
- Gear / Local paths settings. Set existing scan folders for public H3, public FLUX, private H3, and private FLUX, with filesystem containment checks. Saved preferences are retained under the independent Casting Board data directory.
- Type-to-filter fields for Workshop RefMod `.safetensors` filenames and collected photos.
- Expandable generation monitor, including selected casting image, prompt, WanGP-reported progress, outcome, and generated filename(s). The selected reference is **not** a live preview of unfinished GPU video frames.
- Resolution selection split into **Category** and **Resolution Budget**, with values drawn from the selected WanGP model's own supported-size catalog.

### Changed
- Moved the native Gradio Casting queue relay to a collapsed control after the Casting Board iframe, preserving its queue callback and fallback button.
- Renamed the app **RefMod Casting Board for WanGP** throughout its header, plugin metadata, and About screen.
- Workshop decompile selection now accepts only readable H3 `.safetensors` with valid RefMod metadata. Invalid/truncated files appear in a skipped-files count instead of a broken selector option.
- Existing session-wide settings, LoRA selections/multipliers, character-first H3 prompts, public-role refresh, Personal consent and privacy constraints, Docker install, and native queue callback are retained.

### Limits / verification
- GPU H3 creation, decompile, and live WanGP queue execution must be checked on a real WanGP installation; automated tests are local and mocked.
- The generation monitor shows **actual WanGP task status** and a reference photo while running. It does not claim to stream the GPU's intermediate generated frames.
- Configurable scan directories must be inside their configured model roots; this intentionally prevents arbitrary filesystem browsing or paths Refmod-Fork cannot load.
- Manual photo inspection remains necessary; an automated face detector cannot establish identity.

## v6.9.0-dev5.2 — 2026-11-24
- Automatic verified performer-credit discovery and periodic refresh. Added MiniMax H3 RefMod Workshop create/decompile workflows and non-destructive output validation.

## v6.9.0-dev5.1 — 2026-11-24
- Character-first H3 prompts and fully preserved character portrayal across video segments.

## v6.9.0-dev5 — 2026-11-24
- Persistent per-model browser-session generation presets, LoRA multipliers, Queue & Next, sticky action controls.

## v6.9.0-dev4 — 2026-11-23
- Native Gradio queue relay instead of direct FastAPI submissions.

## v6.9.0-dev3 — 2026-11-23
- Model discovery fallback; resolution presets and multiple LoRAs with separate multipliers.

## v6.9.0-dev2 — 2026-11-23
- First native Send to WanGP generation interface.

## v6.9.0-dev1 — 2026-11-23
- Native plugin wrapper with standalone Docker compatibility and a Refmod-Fork compatibility adapter.
