# ClipForge — Project Specification

**Status:** Planning baseline  
**Version:** 0.1  
**Primary initial use case:** Gameplay videos  
**Long-term scope:** Multiple YouTube video genres, including podcasts, interviews, education, commentary, entertainment, tutorials and storytelling.

---

## 1. Project vision

ClipForge is a Python CLI and Claude Code-assisted workflow that investigates a YouTube video, identifies potentially engaging or viral moments, and presents timestamped candidates for human review.

The user starts by pasting a YouTube URL. ClipForge should do as much useful analysis as possible without downloading the full video or requiring anyone to watch it from beginning to end. It gathers publicly available signals, analyzes available captions and metadata, and can optionally analyze selected video frames. If the user owns or manages the channel, they may optionally connect authorized YouTube Analytics data for richer audience-retention signals.

ClipForge then produces a reviewable shortlist. The user can inspect, edit, approve or reject each candidate. Only approved clip ranges may be downloaded. Approved clips can later be assembled into platform-specific short-form videos, with captions, visual styles, music and sound effects.

**Core principle:** automate investigation and preparation; keep the human in control of rights, approvals, downloads and final rendering.

## 2. Initial scope and future flexibility

### Initial focus: gameplay

The first scoring and analysis presets should be optimized for gameplay videos. Examples of moments worth detecting include:

- Clutch wins, last-second saves and close finishes.
- Unexpected deaths, fails, glitches and funny accidents.
- Impressive skill, difficult shots, combos and speedruns.
- Surprising twists, rare events and unusual game behavior.
- Strong reactions, excitement, tension and comedic moments.
- Useful tips, strategies and explanations.
- Clear setup-and-payoff sequences that make sense as standalone clips.

The system must not be hard-coded for gaming. Use genre profiles and configurable scoring criteria so other video types can be added without redesigning the pipeline.

### Supported genres

The initial release can expose these profiles, even if gameplay is the only fully tuned profile:

- Gameplay and esports
- Podcasts and interviews
- Education and tutorials
- Commentary and reactions
- Entertainment and storytelling
- General / automatic genre detection

The user can choose a profile or allow ClipForge to suggest one. The chosen profile and confidence should be recorded with the analysis.

## 3. Product workflow

1. **Submit URL:** user pastes a YouTube video URL and confirms the rights basis for processing.
2. **Investigate:** retrieve metadata and all permitted public signals without downloading the full video.
3. **Analyze:** use captions/transcripts, chapters, comments and engagement signals; optionally inspect selected frames. Use authorized channel analytics only when the user connects an eligible account.
4. **Detect moments:** generate timestamped candidate windows and explain why each may hold attention.
5. **Shortlist:** bulk scoring narrows the candidates; Claude ranks the shortlist and explains the strongest candidates.
6. **Review:** write human-readable review files with stable candidate IDs, timestamps, evidence, scores and suggested edits.
7. **Approve:** user approves, rejects or edits candidates by ID. Every decision is recorded.
8. **Download selectively:** download only approved sections, never the whole source by default.
9. **Build concepts:** group approved clips into sets and propose hooks, styles, scripts or editing directions.
10. **Find audio:** search permitted sound and music catalogs; present licensed candidates for review.
11. **Edit:** build a timeline and use FFmpeg to cut, crop, caption, mix and assemble clips.
12. **Render:** produce platform-specific drafts. MoneyPrinterTurbo is optional and reserved for topic-based faceless videos, only after approval.
13. **Verify and export:** inspect output metadata, dimensions, duration, audio levels and rights/attribution records.

## 4. Video investigation strategy

### 4.1 No full-video download as the default

The investigation stage should prefer metadata, captions, APIs and lightweight analysis. It must not download the entire video just to find highlights.

Potential inputs, subject to availability, platform terms and API permissions:

| Signal | Source / method | What it can contribute | Availability caveat |
|---|---|---|---|
| Title, description, channel, duration, publish date | YouTube Data API or yt-dlp metadata | Topic, context, source identity | API quota and access rules apply |
| View, like and comment counts | Public video metadata | Broad engagement context | Some fields may be hidden or unavailable |
| Captions/subtitles | YouTube captions where accessible, creator-provided captions, or approved transcription of permitted audio | Spoken content, topic changes, punchlines, setup/payoff | Captions may be absent, inaccurate or inaccessible |
| Chapters | Description / metadata | Topic boundaries and navigation hints | Often absent or manually authored |
| Comments | Public comments where API access permits | Audience reactions, memorable moments, recurring topics | Comments are noisy, biased and may be disabled |
| Engagement over time | Authorized YouTube Analytics, if the user owns/manages the channel and grants access | Retention and performance signals | Not generally available for arbitrary public videos |
| Video frames | Optional extraction of selected frames after a permitted access path is established | On-screen action, game events, scene changes, visual context | Do not assume public APIs expose arbitrary frame access |
| Audio characteristics | Optional analysis of permitted audio or creator-provided media | Excitement, silence, laughter, shouting, music changes | Audio processing must respect rights and access restrictions |

Do not describe public view counts or comments as audience-retention data. Do not imply that detailed retention graphs are publicly available for arbitrary videos.

### 4.2 Analysis tiers

- **Tier 1 — Public metadata:** video details, available engagement counts, description and chapters.
- **Tier 2 — Text analysis:** captions/transcripts, transcript search, semantic and structural scoring.
- **Tier 3 — Optional visual/audio analysis:** selected frames and permitted audio features to understand gameplay events and reactions.
- **Tier 4 — Optional owner analytics:** OAuth-authorized YouTube Analytics data for channels the user is authorized to manage.

Each run must record which tiers were available, which were used, and which were unavailable. Missing signals must not be silently fabricated or treated as zero.

### 4.3 Gameplay-specific detection

A gameplay profile should combine evidence rather than rely on one signal. Candidate features may include:

- Transcript signals: excitement, surprise, laughter, strong claims, instructions, reactions and narrative setup/payoff.
- Text structure: question-to-answer, problem-to-solution, suspense-to-reveal, challenge-to-result.
- Visual signals, when available: rapid scene changes, HUD changes, score changes, kill/round indicators, health changes, camera movement and salient on-screen events.
- Audio signals, when available: sudden loudness changes, speech intensity, laughter, silence followed by reaction and sound-event changes.
- Public engagement context: comments that refer to a moment, where timestamps or reliable references are present.
- Creator analytics, when authorized: retention dips, replays or other available time-based performance signals.

Game-specific HUD interpretation is not universal. Treat visual detections as uncertain evidence and retain the reason and confidence for each detection.

### 4.4 Scoring and ranking

Every candidate should have a stable ID and a score breakdown. Suggested dimensions:

- Hook strength
- Payoff / completeness
- Emotional intensity
- Surprise or novelty
- Clarity without prior context
- Visual interest (if analyzed)
- Audio/reaction intensity (if analyzed)
- Useful information or entertainment value
- Standalone suitability
- Rights/access confidence

The final score should be configurable by genre. The system should distinguish:
- **Observed evidence:** what the data actually shows.
- **Model assessment:** the model's interpretation.
- **Prediction:** an uncertain estimate of short-form performance.

Never label a score as a guaranteed virality prediction. Provide concise reasons and uncertainty.

## 5. Platforms and output formats

Target platforms:

- YouTube Shorts
- TikTok
- Instagram Reels

Use platform presets rather than hard-coded output assumptions. Default vertical output:

- Aspect ratio: 9:16
- Resolution: 1080 × 1920 pixels
- Frame rate: preserve source where practical, with an explicit output setting
- Captions: editable, burned-in option, safe-area aware
- Audio: configurable loudness and ducking
- Export: MP4 with a widely supported H.264 video / AAC audio profile unless a platform preset requires otherwise

Platform duration limits, safe areas, codecs and upload requirements can change. Validate these against current platform documentation before implementing platform-specific constraints.

## 6. Rights, licensing and approvals

### 6.1 Source video rights

- Before processing, require the user to record a `license_note` describing their ownership, permission or other rights basis.
- Do not treat a public YouTube URL as permission to download, edit or republish the video.
- Do not bypass access controls, DRM, private-video restrictions or platform protections.
- Respect applicable platform terms, API policies and rate limits.
- Store the source rights note and processing provenance.
- Each downloaded clip inherits a source reference and records its own rights note / provenance.

### 6.2 Approval gates

No download, clip extraction, external render request or final render may occur unless the corresponding SQLite record is approved.

- Approval must be by stable ID, never by an ambiguous title or row position.
- Approval applies to a specific source, time range, version and intended operation.
- If an approved range or source changes, invalidate the approval and require review again.
- Record who/what approved it, when, the approved values and the previous/new state.
- Enforce gates in application code and Claude Code hooks. Hooks are defense in depth, not the only protection.
- A dry run may validate a proposed request without downloading or rendering.

### 6.3 Audio rights policy

Initial audio discovery providers:

- **Freesound:** search sound effects and ambience. For monetized output, allow CC0 by default. CC-BY may be allowed only if attribution can be preserved and the user explicitly accepts the obligation. Exclude CC-BY-NC and other non-commercial licenses.
- **Pixabay:** candidate music and sound effects under the applicable Pixabay Content License, subject to current terms and asset-specific restrictions. Record the asset page, license evidence and attribution text where available. Some tracks may trigger YouTube Content ID claims even when use is permitted.
- **YouTube Audio Library:** manual workflow initially; no automated API dependency unless an official supported integration becomes available.
- **Internet Archive / Free Music Archive:** future providers only after asset-level rights and current API terms can be verified.

Never call an asset simply “copyright-free” without qualification. Prefer the terms “licensed for this use,” “CC0,” or the exact license name.

Every audio asset must store:
- Provider and provider asset ID
- Title, creator and asset page URL
- Duration and tags
- Exact license name and license URL/evidence
- Commercial-use status
- Attribution requirement and full attribution text
- Content ID / claim warning if known
- Local path and file checksum after approved download
- Approval and usage history

Audio search results go to `review/05_audio.md`. No audio asset downloads until its stable asset ID is approved.

## 7. Technology decisions

| Area | Decision |
|---|---|
| Language | Python 3.11+ |
| Environment / packaging | `uv` |
| CLI | Typer |
| Database | SQLite (`sqlite3` standard library) |
| Transcript search | SQLite FTS5 |
| Validation | Pydantic or JSON Schema for structured runtime data; PyYAML plus explicit schema validation for YAML libraries |
| Video metadata / section downloads | yt-dlp, subject to current platform terms and permitted access |
| Media processing | FFmpeg and ffprobe |
| Transcription | Groq Whisper API, subject to current API limits and pricing |
| Bulk scoring | Groq-hosted model; exact model requires user approval before selection |
| Reasoning / concepts | Claude Code CLI, with skills and one scorer subagent |
| Vector search | Defer Chroma / sqlite-vec until a demonstrated need |
| Final faceless video generation | MoneyPrinterTurbo, optional and only for topic-based faceless videos |
| Audio discovery | Freesound first; Pixabay adapter after verifying current supported API endpoints and terms |
| Web app / orchestration framework | Start with CLI. Add FastAPI or LangGraph only when a concrete requirement justifies them |

Do not guess APIs. Read current official documentation and, for MoneyPrinterTurbo, inspect the documentation exposed by the running local instance before implementing its client.

## 8. Proposed repository structure

```text
clipforge/
  project.md
  README.md
  CLAUDE.md
  pyproject.toml
  uv.lock
  .env.example
  .gitignore

  .claude/
    settings.json
    agents/
      scorer.md
    skills/
      clip-scout/SKILL.md
      hook-library/SKILL.md
      style-library/SKILL.md
      concept-writer/SKILL.md
      mpt-brief/SKILL.md

  src/clipforge/
    __init__.py
    cli.py
    config.py
    checks.py
    db.py
    migrations/
    sources.py
    ingest.py
    analytics.py
    captions.py
    transcribe.py
    frames.py
    audio_analysis.py
    windows.py
    score.py
    shortlist.py
    review.py
    approve.py
    download.py
    libraries.py
    concepts.py
    timeline.py
    render_ffmpeg.py
    mpt_client.py
    audio/
      __init__.py
      models.py
      search.py
      licensing.py
      providers/
        freesound.py
        pixabay.py

  hooks/
    *.yaml
  styles/
    *.yaml

  kb/
    clipforge.db
    sources/
  review/
  output/
  tests/
```

Generated database files, downloaded media, secrets and render outputs should not be committed to Git.

## 9. Database design

Use migrations and foreign keys. Store times as seconds (REAL or integer milliseconds, consistently chosen); use metric units in human-readable output.

Core tables:

- `sources(id, url, title, channel_id, duration_s, published_at, license_note, genre, status, metadata_json, created_at)`
- `source_signals(source_id, signal_type, collected_at, availability, payload_json, provenance)`
- `transcript_segments(id, source_id, start_s, end_s, text, confidence, source_type)`
- `windows(id, source_id, start_s, end_s, score_bulk, score_final, score_breakdown_json, reason, evidence_json, status, version)`
- `clip_sets(id, name, source_id, status, created_at)`
- `clip_set_items(id, set_id, window_id, position)`
- `concepts(id, set_id, hook_id, style_id, script, platform, status, version)`
- `approvals(id, entity_type, entity_id, operation, approved_version, approved_payload_json, approved_by, approved_at, status)`
- `status_events(id, entity_type, entity_id, old_status, new_status, actor, reason, created_at)`
- `clips(id, window_id, start_s, end_s, local_path, license_note, status, checksum)`
- `renders(id, concept_id, render_type, external_task_id, status, output_path, request_json, result_json)`
- `audio_assets(id, provider, provider_id, title, creator, asset_url, duration_s, license, license_url, commercial_ok, attribution_required, attribution_text, content_id_warning, local_path, checksum, tags_json, status)`
- `audio_uses(id, audio_asset_id, render_id, start_s, end_s, gain_db, attribution_snapshot_json)`
- `libraries(id, library_type, item_id, file_path, version, status)`

Add FTS5 for transcript text and, if useful, searchable candidate reasons. Use indexes for source/time/status lookups. Keep raw provider responses where useful for auditability, but avoid storing secrets or unnecessary personal data.

## 10. Review artifacts

Each pipeline stage writes readable files to `review/`. Files should be regenerated deterministically and include a run ID, source ID and generation timestamp.

Suggested files:

- `review/01_source.md` — source metadata, rights note, data availability and provenance.
- `review/02_candidates.md` — candidate IDs, timestamps, scores, evidence, explanations and uncertainty.
- `review/03_concepts.md` — clip sets, hook/style choices, scripts and platform recommendations.
- `review/04_render.json` — validated render brief / dry-run request.
- `review/05_audio.md` — audio candidates, exact licenses, commercial-use status and attribution.
- `review/06_final_check.md` — render verification, asset inventory and rights/attribution summary.

Every candidate and audio item must have a stable ID. The review file is a human-readable view of database state, not the source of truth; SQLite remains authoritative.

## 11. CLI interface

Initial command design (names may be refined during implementation):

```bash
clipforge --help
clipforge doctor
clipforge db init
clipforge ingest <url> --license "<rights note>" [--genre gameplay]
clipforge investigate <source_id>
clipforge transcribe <source_id>
clipforge analyze-frames <source_id> [--sample-rate ...]
clipforge score <source_id>
clipforge shortlist <source_id>
clipforge review
clipforge approve clips <candidate_ids...>
clipforge reject clips <candidate_ids...>
clipforge edit clip <candidate_id> ...
clipforge approve set <set_id>
clipforge approve concept <concept_id>
clipforge download <clip_ids...>
clipforge audio search "<query>"
clipforge approve audio <asset_ids...>
clipforge audio download <asset_ids...>
clipforge timeline <set_id> --platform <platform>
clipforge render-ffmpeg <set_id>
clipforge brief <concept_id>       # dry-run only
clipforge render-mpt <concept_id>   # approved topic-based faceless concepts only
clipforge status <id>
```

The `doctor` command checks Python, uv, FFmpeg/ffprobe, yt-dlp, Claude Code, Docker/MPT when configured, and API-key presence without printing secret values. API connectivity tests should be explicit commands and should avoid paid calls unless the user has approved them.

## 12. Libraries

Store one YAML file per hook or style. Validate every file against a schema and report the filename and exact invalid field.

Example hook:

```yaml
id: hook_contradiction_01
name: Contradiction opener
duration_s: [2, 4]
pattern: Open on a claim that conflicts with expectations, then show proof quickly.
example_line: "Everyone says save more money. The data says they're wrong."
works_for: [gameplay, finance, advice, myth-busting]
caption_style: bold_top_text
status: active
notes: ""
```

Example style:

```yaml
id: style_fast_cut_dark_01
name: Fast cut, dark background
aspect: "9:16"
resolution: [1080, 1920]
cut_interval_s: [1.5, 3.0]
caption:
  font: "Inter Bold"
  position: lower_third
  highlight_keyword: true
transitions: [hard_cut, xfade_0.2s]
color:
  contrast: 1.1
  saturation: 0.9
music_ducking_db: -12
status: active
```

Gameplay-specific hooks and styles should be added first. Libraries must support tags, genre applicability, platform applicability, status and versioning.

## 13. Development principles and hard rules

1. SQLite is the source of truth.
2. Never download a source section, audio asset or render output without the matching approved record.
3. Enforce approvals in CLI/application code and Claude Code `PreToolUse` hooks.
4. Never send a full transcript to Claude. Use Groq for bulk transcription and first-pass scoring; send only shortlisted windows and necessary evidence to Claude.
5. Do not select the Groq scoring model without asking the user.
6. Do not add paid services beyond the agreed services without asking.
7. Do not delete data in `kb/` without asking.
8. Do not process content without a recorded rights basis.
9. Keep provenance and license information attached to source, clip, audio and render records.
10. Use strict structured output for model scoring; retry malformed output twice, then flag it for review.
11. Treat model scores as estimates, not guarantees.
12. Do not assume APIs, endpoints, quotas, licenses or platform rules. Verify current official documentation before implementation.
13. Build in phases. Stop after each phase and report files changed, commands run, tests and open issues. Wait for user approval before proceeding.
14. Begin with a CLI. Do not introduce a web server or orchestration framework without a demonstrated need.

---

# 14. Development task list

The phases below are intentionally sequential. Work on a phase, report its result, and stop for user approval before starting the next phase.

| ID | Phase / task | Deliverable | Acceptance criteria |
|---|---|---|---|
| T0 | Repository scaffold and environment | Project tree, `uv` project, Typer entry point, `.env.example`, `.gitignore`, `clipforge --help` | Clean environment installs; help command runs; secrets and generated media are ignored by Git |
| T1 | Prerequisite checker | `clipforge doctor` | Correctly reports Python, uv, FFmpeg/ffprobe, yt-dlp, Claude Code, optional Docker/MPT and key presence without exposing secrets |
| T2 | SQLite schema and migrations | `kb/clipforge.db`, migration system | `clipforge db init` creates all tables, indexes, FTS5 and foreign keys; repeat init is safe |
| T3 | Source ingest | Source row and metadata JSON | URL validation works; metadata can be collected with no full video download; rights note is mandatory; provenance is saved |
| T4 | Investigation signal adapters | Public metadata, chapters, comments/caption availability records | Each signal records source, timestamp, availability and failure reason; missing data is not fabricated |
| T5 | Optional YouTube Analytics connection design | OAuth/config flow and analytics adapter plan | Only authorized channel data can be requested; unavailable permissions fail clearly; no analytics are assumed for arbitrary videos |
| T6 | Caption/transcript acquisition | Transcript segments with timestamps | Prefer accessible captions; transcription fallback only uses permitted audio; global timestamps are correct |
| T7 | Optional audio extraction and chunking | 16 kHz mono FLAC chunks | Chunk sizes respect the configured API limit with safety margin; merged duration and timestamps align with source |
| T8 | Optional selected-frame analysis | Frame samples and visual evidence records | Sampling is configurable and sparse; no full video download is required by default; frame provenance and timestamps are retained |
| T9 | Window builder | 90-second windows with 30-second overlap (configurable) | No gaps across a 2-hour fixture; short final windows handled; timestamps stay within source duration |
| T10 | Gameplay feature extraction | Structured gameplay signals | Extracted signals have timestamps, confidence and evidence; uncertain HUD/event detections are not represented as facts |
| T11 | Genre-aware bulk scoring | Strict JSON score records | Gameplay profile works; other profiles can be configured; malformed JSON is retried twice then flagged; score breakdown is stored |
| T12 | Claude shortlist ranking | Ranked shortlist and reasons | Only top shortlist windows and relevant context are sent; full transcript is never sent; stable candidate IDs are retained |
| T13 | Review file generator | `review/01_source.md`, `02_candidates.md` | Human-readable, repeatable output; every candidate has ID, timestamps, evidence, score and uncertainty |
| T14 | Approval state machine | Approve/reject/edit CLI commands and event log | State transitions are validated; edits invalidate stale approvals; every transition is logged |
| T15 | Approval guard hooks | `.claude/settings.json` and guard implementation | Unapproved download/render/MPT operations are blocked; approved IDs and versions are checked; tests cover bypass attempts |
| T16 | Selective section download | Approved MP4 clips in `kb/sources/<source_id>/` | Download command refuses unapproved IDs; actual duration and timestamps are checked with ffprobe; source rights provenance is retained |
| T17 | Hook/style library loader | Validated YAML libraries | Valid files load; malformed files report filename and field; tags and genre/platform applicability work |
| T18 | Clip-set and concept generator | `review/03_concepts.md` | Concepts use approved clips only and include hook, style, platform, script outline and rationale |
| T19 | Timeline builder | Versioned `timeline.json` | Timeline references only approved downloaded clips; validates in/out points, ordering, transitions, captions and audio |
| T20 | FFmpeg renderer | Vertical draft MP4 | Produces configured 9:16 output, default 1080 × 1920; ffprobe validation confirms dimensions, duration and streams |
| T21 | Audio provider abstraction and schema | Normalized provider interface and `audio_assets` tables | Provider results normalize to one schema; exact license and attribution metadata are retained |
| T22 | Freesound search adapter | `clipforge audio search` for Freesound | Search and metadata work with a configured token; license filter excludes NC; only approved IDs can download |
| T23 | Pixabay adapter feasibility and implementation | Pixabay search adapter if official API supports required audio endpoints | Current official docs and terms are verified first; unsupported endpoints are not guessed; claims/Content ID caveats are recorded |
| T24 | Audio review and approval | `review/05_audio.md`, audio approve/download commands | Candidate IDs show license, commercial status, creator and attribution; no download before approval |
| T25 | Audio timeline integration | Audio tracks in timeline JSON | Gain, ducking, trims and attribution snapshots are stored; output mix is validated |
| T26 | MoneyPrinterTurbo documentation and dry run | `review/04_render.json` | Read docs from running local instance; validate request without sending a render job; only topic-based faceless-video workflow is supported |
| T27 | MoneyPrinterTurbo approved execution | Submit, poll and fetch client | Requires approved concept and approved render request; job ID/status and output path are recorded |
| T28 | Final verification and rights report | `review/06_final_check.md` | Verifies dimensions, duration, audio streams, clip provenance, licenses, attribution and approval records |
| T29 | Automated tests | Unit and integration test suite | Tests cover timestamps, windows, scoring validation, rights metadata, approval state machine, hooks, libraries, timeline and audio filtering |
| T30 | End-to-end gameplay test | Test report using a rights-cleared 2-hour gameplay video | Every stage works; review gates are enforced; only approved ranges/assets are downloaded; final draft passes validation |
| T31 | Genre expansion validation | Profiles for at least one non-gameplay genre | Existing pipeline supports another genre through configuration and scoring profile, without breaking gameplay behavior |

### Phase ordering

- **Foundation:** T0–T3
- **Investigation and evidence:** T4–T10
- **Scoring and human review:** T11–T15
- **Approved clip acquisition:** T16–T18
- **Editing and rendering:** T19–T20
- **Audio licensing and integration:** T21–T25
- **Optional faceless-video rendering:** T26–T27
- **Quality, tests and expansion:** T28–T31

T0–T15 are the first major milestone: the system can investigate, identify, explain and obtain approval for candidates without downloading clips. Do not begin section downloads until the approval system and guard tests pass.

---

## 15. Initial milestone definition

The first usable milestone is not a finished video editor. It is a trustworthy discovery and review tool.

A successful first milestone allows a user to:

1. Paste a YouTube URL.
2. Record a rights note.
3. Inspect the metadata and available public signals.
4. Analyze available captions and other permitted evidence.
5. Receive a ranked gameplay-oriented list of timestamped moments.
6. Read why each moment was selected and what evidence supports it.
7. Edit, approve or reject candidates by stable ID.
8. Confirm that no clip or full source video was downloaded during discovery.

Only after this milestone is reliable should ClipForge move into selective downloading and editing.
