# Casting Studio for WanGP

Version: v1.0.0-rc.12.11
Date: 2026-11-25


## RC12.11 Reference collection and test image controls

Select several local JPEG, PNG or WebP reference photos in one file picker (Ctrl-click, Command-click on Mac, or Shift-click). Each image uses the existing quality, duplicate and review checks; failures do not stop the remaining files. Closing or changing the collection stops subsequent uploads; an already submitted image may still save to its original collection. Portraits and posters remain single-image.

In Workshop, optionally enable **Generate one test portrait after creating the RefMod**, then select the exact installed compatible image checkpoint. The encoder and image checkpoint are independent. The selected image model is revalidated before test generation; no substitute is used. If it disappears after extraction, the created RefMod is retained.

## RC12.10 People library reliability

- Explicit Add person now saves a durable local entry even when an installed RefMod already identifies the performer. Removing a model no longer removes an explicitly registered person from the library.
- Identity corrections and public profile markers work for saved performers without RefMods. Repeated corrections retain category, marker and optional profile symbol; attempts to merge distinct public identities or target a Personal identity are rejected. The current performer search follows a successful correction without replacing a newer search or navigation context.
- Fictional characters no longer display a human profile search link in People, and both direct human-profile lookup and human credit discovery reject fictional classifications. Identity edits reject punctuation-only names and use the displayed canonical identity instead of guessing from H3 or FLUX filenames. No new automatic online research, generator changes or runtime schema changes.

## RC12.9 People library

- Open People → Performers, type a name and select Add person. A local public performer can be saved without a role, production or RefMod. Use All known people or Missing RefMods to find saved profiles; Installed RefMods only retains the previous fast view.
- Collect photos or refresh roles explicitly; adding a person never launches online research. Public and Personal profiles remain separate. Duplicate normalized names reuse the existing record.
- A delayed save cannot replace a newer search or navigation context. Failed saves retain the draft.

## RC12.8 persistence and navigation

- Completed results retain the newest 30 entries in external local storage. Restarting WanGP restores records for unchanged, existing native output files; the plugin does not copy media or preserve deleted output files. Completed videos remain paused.
- Historical retries are available for explicitly failed native tasks submitted with this version, if original snapshots remain available in the latest 100 history records. The original prompt and settings are retained privately in the runtime database. Retry validates current identity, consent, exact RefMod path and recorded file size/modification time. Replaced dependencies, unknown outcomes and pending retry claims are blocked; no automatic retry runs.
- Technical reference ranking uses recorded sharpness, dimensions, face count and quality status. Near-duplicate perceptual hashes are grouped within a collection; Workshop preselects the highest ranked unique candidates (up to 20). All candidates remain available for manual review. No photos are deleted or automatically researched.
- Workshop can optionally generate one neutral test portrait after successfully creating a RefMod, using a compatible installed image model and the exact newly created file. The option is off by default, and its failure does not discard a completed RefMod. Review the test result in the completed gallery.
- Private settings and prompts backup includes saved public production selection sets. Imports validate identifiers and merge the sets; restoring a saved set still checks current inventory. The backup does not bundle reference media, generated files, model weights or retry history.
- Click a public performer name on a cast card or result to open that person's People view, including performers with no installed RefMod. Click the production name on a role to return to its cast. Private identities remain unlinked. Existing selections are retained.

## RC12.7 workspace workflow (historical)

- Open the generator and use Prompts, Model settings, Identity, or Batch review. All configured image prompts stay independently editable; pending edits and blocked reviews still prevent unsafe submission.
- Select an exact compatible RefMod from the cast/role dropdown when multiple files are available. Character-specific Workshop names contain `__role__`; existing library files are not renamed. Ambiguous cross-family choices require explicit selection.
- Save selections from a production cast for the active RefMod family; restore merges available saved selections without replacing existing choices. Use the filtered selection control to select visible roles.
- Switch between performer and character reference collection and Workshop, then return to the original cast.
- Browse recent completed outputs from the monitor. The gallery originally retained up to 30 outputs in memory; RC12.8 persists these records; it never controls the live job, and video playback is manual.
- The image-set editor includes the same public character identity as the video workflow. Factory action, framing and expression now occupy their own fields. Personally edited final prompts are not overwritten.
- Settings has category navigation; reset an individual fine-tune without resetting the others. Batch history can be filtered by model, status, performer or production. RC12.8 adds cross-restart retry for newly recorded confirmed failures.
- No new keyboard shortcuts. No new automatic online collection. Native Git updates preserve external runtime data.

**Discover. Cast. Create.**

Native WanGP plugin · Release candidate 12.11.

## RC12.6 — prompt review and saved model settings

For still images, the generator presents the complete configured image set as numbered, individually editable prompts. All previews must load and all pending final-prompt edits must save before the set can be queued. Each prompt can be reset separately; Save all prompts commits outstanding edits. Video editing remains single-task. Bulk queue preflight remains separate.

**Saved model settings:** the exact fine-tune and model-family combination determines the stored generation settings. Steps, resolution, seed, strength, LoRAs, global override, duration, sliding windows and supported extra controls are remembered on this WanGP server, outside the plugin Git checkout. The browser cache remains a fallback; existing browser settings migrate when there is no server preference file. Settings backups include the saved model preferences. If server saving fails, the generator reports the failure; an unreadable server preference file is preserved rather than overwritten. Named presets remain optional and browser-local. The server preference file is shared by browsers connected to the same installation; simultaneous editors are not isolated profiles.

**People → Performers:** filmographies are collapsed by default. Each performer has a role count, selected-role count and independent disclosure control. Character searches reveal matching roles. Refresh roles is a separate, explicit research action.

Existing Git installations should use Apps & PlugIn Manager → Update, followed by a WanGP restart. Export private settings and back up external runtime data before updating. If GitHub credentials fail after a Pinokio restart, verify the repository-local credential helper in the installed plugin’s .git/config (not a tracked source file); do not remove the working installation or expose credentials in the repository URL.

## GitHub installation and cast coverage (RC12.5)

The repository root is directly installable through WanGP's native Apps & PlugIn Manager. Use the repository URL (not a release ZIP URL). A private repository requires Git access from the WanGP server; authentication on a separate computer does not grant server access. Keep the existing plugin folder backed up outside `plugins/` for the first Git installation; never delete the external runtime data or model directories. Future Git-based updates can use the native update control. Check the About version after restarting.

The production cast view offers a model-family coverage filter (installed, convertible, missing, or all), performer/character text filtering, an installed coverage progress indicator, and separate counts of locally available approved performer and character reference photos. The counters do not include unapproved or missing files. Bulk selection remains production-wide, not filter-wide. Compact view is remembered in browser local storage and included in settings backups. The last ten viewed productions are kept locally in the browser and can be cleared; viewing history is intentionally excluded from exported settings backups. Filtering and coverage display do not initiate online research. Use Refresh coverage to explicitly rescan installed models.

## Cast collection and private preferences (RC12.4)

From any production cast member, choose **Collect reference photos**, then **Performer**, **Character**, or **Both**. Both starts the performer collection and allows switching to the separately scoped character collection. General photos are stored by performer; character photos are scoped by performer, production and role. Review, export and Workshop creation use the same collection. Return to the original cast with the Workshop return button; the production search and selection context are retained, and installed RefMods are refreshed. No reference research begins until the user chooses a collection.

**Settings → Export / import settings and prompts:** explicitly export a private JSON backup and import it into another compatible installation/browser. It includes saved prompt templates, per-selection overrides, saved final prompt edits, character traits, generation settings and selected checkpoints, global LoRAs, named presets, UI mode and preview preferences. Backups are sensitive and must not be included in distributable plugin ZIPs. Restore merges matching saved entries after confirmation; it does not import photos, model files, profiles, consent, job history, credentials, or machine-specific library paths. Private final edits are skipped when their original profile or consent is unavailable. Invalid prompt backups are rejected before database writes. Browser preference writes are rolled back on a rejected import where storage remains available. The page reloads after successful restoration.

**Last model:** browser-local settings persist across reloads, tab closure and WanGP restarts on the same browser origin. Image and video remember their own checkpoint; the Image/Video selector recalls the last image model family. Legacy session settings are read when persistent settings are absent. If a remembered checkpoint is unavailable, review the fallback before queueing. Use the explicit backup for transfer between browsers or origins.

## Workflow tools (RC12.3)

The optional **Getting started** dialog offers setup checks, first-generation steps and a Basic/Advanced mode switch. Advanced remains the default; Basic hides advanced editing panels, but does not silently reset saved model settings. In the generator, switch back to Advanced to change those settings. The Basic-mode **Queue one task** action submits only the selected image or video job (including configured sliding windows), instead of a whole still-image set.

**Batch preflight:** open the bulk queue panel and select Review all prompts. The preflight checks the current model, selected RefMods, LoRAs, consent and task settings without queueing work. A blocked or unavailable native manifest relay prevents approval. The queue bridge rechecks live dependencies on submission and again before the native relay. This is not a guarantee against out-of-memory errors or downstream native failures.

**Named presets:** in the generator's session settings, save a name for the current checkpoint, steps, resolution, seed, effective LoRA stack and multipliers, extra settings and sliding windows. Select the same model family before loading. Loading applies the saved effective LoRA stack and temporarily overrides global defaults to avoid replacing the saved multipliers; global defaults may be reapplied when the generator is reopened, so reload the preset when necessary. Presets and mode are stored in browser local storage, not a shared server database. They are not bundled with the release.

**Undo removal:** restores up to the last 20 single-role or production-wide removal actions within the current page session, subject to current RefMod availability and consent. The destructive Remove all operation explicitly remains non-undoable because it also clears per-selection template overrides. Undo does not reverse already queued jobs.

**Keyboard shortcuts:** outside text-entry fields, Alt+N queues the current task and advances; Alt+P refreshes the prompt; Alt+Left/Right navigates the casting selection; Alt+U restores the most recent removal when no dialog is open. Browser/OS shortcut interception may vary; the original buttons remain available.

**Batch history:** local SQLite retains the most recent 100 casting-generation records and submitted settings. Refresh to see new states. RC12.8 retains private prompt/identity snapshots for confirmed failed tasks eligible for retry, as well as user-configured extra settings and LoRA filenames. Clear history removes stored records without cancelling jobs; in-flight jobs can create a new record when their state changes. Older versions' jobs cannot be reconstructed. Retry is enabled only for explicit, validated native failure indices while the original validated task snapshots are available; skipped, cancelled, unconfirmed, or known successful output tasks are excluded. The retry preserves submitted settings, including a random seed request if applicable, and rechecks live consent and RefMods. No retry is performed automatically. After a restart RC12.8 restores eligible confirmed-failure snapshots; unconfirmed in-flight outcomes are not retried.

## Recovery note

RC12.2 adds template-editor recovery safeguards: shrinking and expanding the image count during a single editing session retains temporarily hidden drafts until save or reset; closing a modified image template requests confirmation. Failed template loads disable editing and saving until a successful reopen. Failed resets preserve drafts and display the error. Image-template writes target the model loaded by the editor. Existing persistent templates and preferences are not migrated or overwritten by installation.

The live monitor uses submitted task metadata for the displayed frame or retained completed result, independently of the editable casting selection. The performer, role, production, scene and expandable submitted prompt are separated from the currently tracked generation progress. Unidentified outputs are explicitly marked unknown. Missing optional metadata never stops generation.

RC12.1 targets WanGP v20.20. Native callback task metadata is cross-checked, oversized batch status messages are discarded, damaged artwork cache entries are refreshed, failed portrait transactions return a retryable error, and failed maintenance worker starts clear their running state. Native API behavior is tested with isolated simulated sessions; live v20.20 and GPU verification remain outstanding.

Whole-job cancellation can be requested during preparation or native handle creation. Conversion stops before subsequent stages when cancellation is observed; existing RefMod files are preserved. Casting Studio retains up to 100 terminal job records plus active jobs in memory. Online image downloads use exclusive temporary files and roll back newly published files on failed cache writes.

A whole-batch cancellation prevents later manifest chunks from continuing once the request is accepted by Casting Studio. A chunk already entering or accepted by WanGP may still run until the native cancellation is processed; completed outputs are retained. A native cancellation refusal is reported as a conflict rather than a server crash. Individual Abort remains separate from whole-batch cancellation.

Damaged saved catalog rows (cast credits or performer categories) are skipped, counted in a visible warning, and preserved in SQLite. Re-register affected credits or categories to repair them; no automatic database cleanup is performed. Settings and scan-history updates use exclusively created temporary files and atomic replacement. A failed artwork save reports an error and preserves the prior artwork.

Damaged casting selection records are preserved and excluded from the visible selection list, with a warning in My Selections. Re-select an affected role and reload to refresh the recovery count, or explicitly confirm Remove all to reset selections (including damaged rows and selection overrides). Batch and export requests that include damaged rows return an actionable error. A previously public selection cannot silently become a private generation: select the profile explicitly from Personal after recording consent. Registered identity aliases also respect Personal restrictions. Profile markers are user-assigned only; no identity markers ship with the plugin.

If a saved prompt template is damaged, the catalog remains usable and the editor reports the problem. Preview and queue submission for affected selections are blocked until you explicitly save a corrected template or reset it. The quick music control is disabled while a damaged global template is detected. Existing stored data is not rewritten during recovery. Public reference photos associated with a Personal profile are no longer available through public reference routes; this does not delete the files or migrate them to the private library.

## Responsible use, ethics and disclaimer

Casting Studio is a community software project created through collaboration between the project creator and ChatGPT, an AI assistant developed by OpenAI. The project creator directed the design, requirements and testing, with ChatGPT assisting in writing, reviewing and refining the code. This acknowledgment is not an endorsement by OpenAI, WanGP or Refmod-Fork.

The software is intended for lawful, ethical and responsible creative work. Its availability does not grant permission to use another person's likeness, private photographs, copyrighted material or other protected content. Users are responsible for obtaining appropriate consent, permissions and licenses; respecting privacy, intellectual property and applicable laws; and reviewing any generated material before using, publishing or distributing it. A publicly available photograph is not, by itself, consent to AI-generated depictions. Do not use this software to create or distribute non-consensual intimate imagery, sexual content involving minors, deceptive impersonations, harassment, fraud or other unlawful or harmful material.

The software is provided **“AS IS” and “AS AVAILABLE,” without warranties of any kind, express or implied**, including fitness for a particular purpose, merchantability, non-infringement, accuracy, security or uninterrupted operation. To the maximum extent permitted by applicable law, the project creator, contributors and providers of AI assistance disclaim liability for misuse of the software, user-generated content, or losses or damages arising from its use, including inappropriate, unlawful or unethical use by others. Users are responsible for their own actions, their source materials and their generated outputs.

Nothing in this disclaimer excludes liability or limits rights that cannot lawfully be excluded or limited. The software's consent controls and other safeguards are aids, not a guarantee of consent, legality or ethical use. Neither the project creator nor ChatGPT approves or authorizes misuse of this software.

## Privacy and distribution

The distributed plugin ships with **zero performer, role, production and identity-alias records**. It includes code, generic assets, synthetic tests and empty compatibility placeholders only. Installed RefMods are discovered on the user’s machine; credits and pictures are collected only through the user’s local workflow. Upgrades within the Casting Studio namespace preserve saved SQLite records; historical bundled-only credits are no longer supplied.

Runtime information is separate from this release. Casting Studio stores its SQLite database, collected reference photos, selected artwork, personal portraits, and server settings in `WanGP/data/casting-studio/` (or the `CASTING_STUDIO_DATA_DIR` override). Paths resolving inside the plugin folder are rejected. Browser storage retains session and LoRA preferences; RefMod files remain in the host model directories. Do not move the existing runtime library during plugin upgrades. Do not publish these directories, generated output, browser data, screenshots or unredacted diagnostics. The plugin relies on the host’s access controls; keep private installations behind authentication and avoid exposing them directly to the internet.

Online public-credit and image research uses external services and image hosts. These may receive search terms, IP addresses and normal HTTP request metadata. Some public character-description lookups occur when opening the queue editor. External media requests may also occur when displaying remotely hosted artwork. Personal profiles are excluded from public identity research, but this is not an anonymity or network-isolation guarantee. The software does not contain an identified developer-specific reporting endpoint or analytics service. Git hosting accounts, commit metadata and release uploads are outside the ZIP and require their own privacy review.

## Factory prompt scenarios

All eight image-model options start with five independent, cinematic images: character portrait, full-body showcase, environmental portrait, natural action pose and dramatic close-up. MiniMax H3 Ref2VA includes four editable 15-second scene definitions: introduction and slow rotation, walking through the location, character performance and cinematic closing shot. Two video segments remain enabled by default to preserve existing queue size; choose up to four in the video template editor. Music is off by default. Character identity, production and year, native reference syntax and bottom captions remain part of the template builders. Personal factory prompts use neutral professional studio treatments; the dedicated one-image profile portrait generator is unchanged.

Saved global templates, per-model image templates, per-selection overrides and final prompt edits are not overwritten by an upgrade. To adopt the new defaults, open the video template editor and choose **Reset to factory template**, or select an image model and use **Reset image template** in its image-set editor. Resetting a template does not erase a saved final prompt; use **Reset to template** in that prompt's generation dialog when desired. Explicitly saved custom actions and wardrobe remain editable. No earlier factory scenario archive is included in this distribution.

## RefMod library root

Settings exposes one server-side **RefMod library root**. The default is the detected native `WanGP/loras/refmods_plugin` library (or the deployment-level `CASTING_STUDIO_REFMOD_ROOT` override). The root may be a linked location provided its H3 and FLUX paths resolve to the same native library. Casting Studio cannot remount Refmod-Fork from its web interface; configure the native mount first when relocating the library. The detected paths are available in a read-only expandable section:

- `minimax_h3/celebs/` — public H3
- `minimax_h3/personal/` — private H3
- `flux2/celebs/` and legacy public files under `flux2/` — public FLUX
- `flux2/personal/` — private FLUX

Missing subfolders are skipped; the settings screen does not create, move or delete model files. Existing per-folder scan filters from older releases are replaced by the standard native folders. The old settings file remains unchanged until Save root is pressed. Saved records and model files are retained. The single root setting is stored in the external data directory.

## GPU temperature

The live generation monitor displays server GPU core temperatures in its header, even when collapsed or idle. NVIDIA readings use the installed `nvidia-smi` utility with a two-second timeout and shared five-second cache; no CUDA initialization, external service, or additional Python dependency is required. Readings are requested only while the browser document is visible. Multiple supported GPUs show individually indexed values. Unsupported hardware or unavailable sensors show N/A, not an invented temperature. Advisory colors: below 75°C green, 75–84°C amber, 85°C and above red. These are conservative display thresholds, not manufacturer-specific safe limits, and do not throttle or abort jobs.

## Resuming reference collections

Collected reference photographs are persistent, not temporary. Existing photographs in the same person/production collection are recognized; the same photograph may be explicitly reused in another collection without overwriting the original. If the saved file is missing, collecting it again restores its record. In Workshop, select the saved collection to use approved images. In Settings → Temporary file cleanup, check and optionally remove recognized abandoned writes older than 24 hours. This never deletes collected reference images, portraits, final artwork, database records or models.

## Character appearance and cast controls

When opening a public character's queue editor, the application checks cached appearance details and, when necessary, researches public encyclopedia descriptions and structured appearance fields. The character's on-screen anatomy and coloration take precedence over the performer's everyday appearance in template-generated prompts. Review the suggested traits and source in Character identity signature. Manual identity overrides and custom final prompts are preserved; use Reset to template to incorporate updated traits into a previously customized prompt. No character records are shipped. Bulk generation uses locally available traits rather than initiating a large research operation.

Cast rows with installed or convertible RefMods display selection and artwork controls; image collection and creation remain available for missing RefMods and through the Workshop.

## Included in this build
- Native queue relay is hidden; Settings → Troubleshooting retries pending handoffs. The collapsed WanGP Queue Manager below the monitor reads and cancels native tasks when supported. Editing and reordering remain in WanGP.
- Larger navigation labels and a keyboard-accessible People picker with locally bundled illustrated category icons.
- Cached performer/role index, paginated cards, debounced search and non-overlapping status polls reduce interface work; collapsed monitors suspend Casting Studio media capture and downloads while retaining stage timings.
- Image picker starts with manual URL and upload controls. Successful manual URL saves archive the image locally; a blocked download leaves the previous picture in place.
- Editable final queue prompts with automatic local persistence, refresh without losing edits, and an explicit reset to template.
- Television Personalities workspace: explicit public lookup, confirm and register public on-air credits, automatic targeted photo search and optional credit research. No installed RefMod required to discover a person.
- Batch-collect checked reference images with existing quality safeguards, then open the Workshop.
- Live monitor has a red Abort button targeting the current generation, plus persistent Settings → Live generation preview controls. Default: display the actual previous completed output until the first available preview (0%); choose a denoising percentage from 0–100% or use the waiting placeholder instead. The percentage is calculated from the current model’s denoising steps, not batch progress. Legacy absolute-step preferences in the current namespace retain their display mode and reset to 0%; beta browser preferences are isolated from RC1. Collapsed preview retains Status Lite stage timings without downloading media. Legacy selection JSON/CSV/TXT controls removed; About has a vector icon.
- Personal profile cards support direct local portrait upload.
- Personal profile cards open a dedicated compatible image-model picker and generate exactly one neutral studio portrait, automatically saved after successful native queue completion. Consent and a compatible linked private RefMod are required.
- Portrait generation uses the existing Personal prompt behavior with neutral studio handling.
- The cumulative requirements, changelog and regression checklist remain bundled with the ZIP.

## Installation and transition from the beta

Finish active jobs and back up external runtime data. Preferred: install from the repository URL in the host Apps & PlugIn Manager, then restart WanGP. For manual/offline installation only, stop WanGP and extract the separately packaged installation ZIP into the `plugins/` directory. Both methods use `plugins/wan2gp-casting-studio/`. Do not overwrite a live manual installation with a Git clone.

If replacing the former RefMod Casting Board beta, disable it and move its entire plugin folder out of `plugins/` to a backup location before installing this release. Do not run both applications at once. The initial release candidate intentionally starts with a new default data directory (`data/casting-studio/`) and separate browser storage keys. It does not migrate or delete the beta's database or preferences. Existing model files remain in the same Refmod-Fork model library and can be discovered by Casting Studio. Custom beta scanning paths must be re-entered or supplied using the new `CASTING_STUDIO_*` environment overrides. Do not move, rename or delete RefMod model directories or their symlinks. To revert, disable Casting Studio, move its plugin directory aside, and restore/re-enable the beta; its data remains separate.

For Git-installed releases, use the native update control. For a manually installed release, stop WanGP, preserve the existing plugin folder outside `plugins/`, then install the new source through the native manager. Keep `data/casting-studio`, browser settings and model libraries unchanged.

## Reversible first-run testing

Stop WanGP and finish active work. Locate the external Casting Studio data directory (`data/casting-studio` relative to WanGP, or the configured `CASTING_STUDIO_DATA_DIR`). Rename it to a unique backup name without overwriting an existing directory. Keep all RefMod directories and WanGP model files unchanged. Restart WanGP and open Casting Studio in a fresh browser profile/private window. The new empty data directory will be initialized; installed RefMods may be discovered automatically. The RefMod root is auto-detected from the native mount; an equivalent custom root alias may be re-entered temporarily. To restore, stop WanGP, rename the fresh data directory to a separate unused name, then rename the backup to its original name. Restart and return to the original browser profile. This isolates Casting Studio's records, not the model library: new model files created during the test remain in that library.

## Packaging
The GitHub source archive is repository-root source; the separate WanGP ZIP is for manual installation only.

The responsible-use reminder remains visible at the bottom of every Casting Studio workspace and dialog. WanGP tab order remains a host preference.

### If the displayed version is stale after an upgrade
Stop WanGP completely before replacing the plugin folder, then restart and reopen the tab. RC6 and later use a versioned iframe URL and non-cacheable application HTML. If the displayed release still differs from the installed plugin metadata, test in a private browser window and verify that the active WanGP instance is loading the updated plugin directory. Do not reset browser storage or the local database to troubleshoot a stale page.
