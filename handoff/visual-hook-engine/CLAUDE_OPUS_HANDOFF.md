# Claude Opus 5 handoff — Visual Hook Engine for CrossFit R.E.L

Prepared 2026-09-11. This document is self-contained implementation guidance. The preparation session researched and inspected the system, extracted local contact sheets and wrote specifications. It **did not** implement the engine, install dependencies, alter canonical policy, render new production finals or publish anything.

## Assignment and scope

Implement a local-first **Visual Hook Engine** that chooses whether and how to strengthen the first5–10 seconds using real existing footage. It should reinforce the actual spoken promise and feel human-edited. It must be compatible with both existing render engines, Hebrew captions, audio, QA, app review and immutable publishing artifacts.

Start with a bounded release: **NO_OP + SMART_PUNCH_IN**, default off for existing projects, shadow analysis before auto rollout. The next candidate is duration-preserving silent PAYOFF_PREVIEW, but it is disabled until Harel explicitly approves a narrow canon exception and real examples. Other recipes are registry entries only. Do not build every effect just because it appears in the registry. Do not introduce a model/renderer dependency for the MVP.

Workspace root:

`/Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System`

Preparation package: `handoff/visual-hook-engine/`. Companion docs contain detailed research, architecture, all10 recipes and file-by-file plan. Evidence contains7 contact sheets, `sample_audit.json` with actual source paths, source SHA256 snapshot and gate/lesson audit logs. This workspace was not a Git repository at inspection; do not assume git rollback exists. Snapshot files before changes and use the project's backup discipline. Recheck current files because production may have advanced since this audit.

## How the existing system actually works

The canonical local skill is `skills/rel-social-video-editor/SKILL.md` (front matter v9.21, Aug22), not the root pointer. Recent code includes v9.22 Sept10 fixes. `tools/PIPELINE.md` has old headings/counts. The skill also refers to the broader canon at:

`/Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/00 - REL-OS/03_SKILLS/00_META/VIDEO-CANON.md`

Read current local instructions before editing. Canonical prose and code have drift, notably B-roll eligibility and music levels. Preserve existing behavior; do not silently resolve unrelated policy disagreements as part of this feature.

The actual finish path:

1. RAW/source plus project manifest; `project_id` is identity, files are truth, SQLite is rebuildable index.
2. `align_words.py` uses local faster-whisper with Hebrew glossary. Corrected transcript reconciliation is `align_reconcile.py` using sequence matching and timed interpolation, not a new phoneme-level aligner.
3. `edl_build.py` / director decisions / `edl-policy.json` create kept/cut intervals with first-sentence/visual-opening/retake protections. `edl_cut.py` renders a clean export. Tightening/speed and final-word reconciliation may create `EXPORT_TIGHT.mp4`.
4. In `local_finish_pipeline.py`, the Python variable `EXPORT` resolves the actual clean body. It can be EXPORT or EXPORT_TIGHT; do not hardcode only the latter.
5. B-roll plans honor manual/pinned choices, quoted sentence relevance, explicit empty director choices, content doctrine, source/people safeguards and snapping to cuts.
6. **v1:** B-roll overlays, format effect if applicable, music, PIL captions, loudness/delivery. Several B-roll branches call `animation_overlay.py --base EXPORT` explicitly.
7. **v2:** `tools/relvid/render.py` rebuilds from INPUT+EDL+tight/source mapping, renders cached source segments with B-roll and captions, PCM master, then music/loudness/delivery. It does not simply render a modified EXPORT. A stall can trigger v1 fallback.
8. Audio verification is from actual output audio before music; existing caption/canon/lexicon/coverage/cut/QA checks run. A full format intro can be prepended late, after delivery, with word/verification shifts and intro_offset provenance.
9. Preflight asks what Harel would fix; candidate promotion and immutable artifact creation follow existing logic. Review-app approval→locked `run_finish.py`/runner. Cover+caption approval binds artifact/checksum; schedule only through current ready_to_schedule checks. Never bypass this.

`tools/illustration_build.py`, `illustration_gate.py`, `illustration_place.py`, HTML template and Puppeteer renderer already exist, but no automatic illustration build invocation was found in the finish pipeline. The renderer strips an old HyperFrames runtime integration and still depends on CDN GSAP. Do not assume a fully offline or automatically integrated illustration stage.

## Critical findings to design around

- A single `base = hook_output` insertion will fail: v1 later base assignments and explicit B-roll `--base EXPORT` paths override it; v2 ignores patched EXPORT entirely. Implement a shared semantic plan and two rendering adapters.
- `render.py` has `Segment.out_start` on a pre-speed axis; `out_start_final = out_start/speed`, while caption/B-roll local data uses output timing. Cumulative frame rounding and n_frames already exist. Avoid double speed conversion.
- Existing v2 segment keys use source name/size/integer mtime, not full source hashes. Hook asset identity must use content hashes; don't turn this into a full unrelated cache rewrite.
- Current G8 scans **1.2 seconds**, counts `scene>0.45`, and is **warning-only**. It does not know intentional transitions. Do not suppress it broadly or pretend it is already a hard gate.
- Full intro may be inferred by title/format even when the manifest field is null. Resolve this before hook selection. Default NO_OP when a full intro is present.
- `registry.set_finish_prefs` currently whitelists only music and B-roll; a hook UI control will not persist without extending it.
- `artifacts.SIDECARS` currently freezes provenance/QA/B-roll, not hook plan/receipt/report. Add immutable hook provenance and bind approval to the plan seen in review.
- `learn_from_edits --apply` currently aliases proposal in shadow; don't invent an automatic policy-apply path.
- Current audio defaults differ from old docs; live CLI music default was -46 LUFS with ducking. Do not change audio while implementing visuals.
- Existing sample words files can be stale relative to a particular export generation. Verify media/timeline/words identity before generating semantic candidates.

Read-only diagnostics in preparation: gate audit137 entries,0 failures; lesson audit60 lessons/156 enforcers,0 problems. Full unittest suite, golden suite, system doctor, new hook render benchmarks and a HyperFrames runtime test were **not run**. These numbers are not future acceptance targets.

## Research decisions and evidence limits

Public examples inspected: [Avia receipt POV](https://www.instagram.com/aviareznikov/reel/DEKN-3Lodfm/), [Danny real barbell demonstration](https://www.instagram.com/dannyvoronov/reel/Dc_mYyrJzp7/), [Ananas conversation/keyword layer](https://www.instagram.com/ananas.social/reel/DdB_VHTKiLm/), [required Jessy Barreto post](https://www.instagram.com/p/DcB7HAzsDnR/), [Devin Jatho designed-card example](https://www.instagram.com/devinjatho/reel/DdB-xoiS5Mm/), [Hormozi speaking/board example](https://www.instagram.com/hormozi/reel/DdHQrSWuK_b/). These were sampled browser frames, not a frame-timed corpus; exact public first-cut/effect-duration statistics remain unmeasured. The required Jessy post explicitly credits generated Seedance/Higgsfield scenes: borrow question/reveal structure, not its media provenance.

The useful common principle is to make a promise visible with real evidence, preserve expressive humans, and avoid adding redundant movement. [YouTube's Jenny Hoyos discussion](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/) supports attention to the opening, not a universal mandated event before0.8s. Vendor docs from OpusClip, Submagic and Captions verify editing controls; they do not prove an automatic R.E.L retention uplift. No performance data was accessed.

Interpret windows as questions:0–1 valid/readable first image;1–3 support opening speech;3–5 concrete proof if helpful;5–10 transition into ordinary explanation. One treatment/no accent MVP is a conservative product decision. It is not a statistically validated optimal effect count. No motion/cut-count/score threshold may become a new creative blocker without measurement.

## Architecture to implement

Resolve clean **final-body** picture and word timeline after recut/tighten/speed/reconcile. Resolve existing B-roll and full-intro/layer reservations. Analyze local windows, discover assets, choose an eligible treatment, freeze a plan. Render the same plan through v1 or v2. Continue existing B-roll/music/captions/loudness/QA/artifact flow.

Use integer30fps half-open frame intervals on `body_final`; record `intro_frames` for delivered-final QA. Preserve total body n_frames and all original speech/word timing. All treatments are picture-only. Clean EXPORT remains unchanged for existing QA/cover contracts.

**v1:** create `visual_base` from clean body only for an applied non-NO_OP treatment. Every B-roll base branch consumes it. Caption burn remains after visual treatment. NO_OP returns original path without extra encoding.

**v2:** optional per-segment hook IR before B-roll/captions. Intersect global body-frame cues with existing segment spans; preserve cumulative rounding/n_frames/source overrides/color handling/audio. Hash only affected hook fragments into affected segment keys; no-op/off old keys unchanged. A v2→v1 fallback renders the same frozen plan. Missing approved asset/render failure stops candidate and leaves old approved artifact, not a silent NO_OP substitution.

Crop implementation: typed normalized rectangles `[x,y,w,h]`, aspect-preserving keyframes, smoothstep interpolation, exact identity at the exit. Initial pilot1.04–1.08 scale is an uncalibrated audition envelope, not an established safe maximum. No new scale is applied unless all relevant head/hand/body/object bounds are safe. Face detector alone is insufficient; unknown safety selects NO_OP. Existing motion/zoom or multi-person interaction favors NO_OP.

MVP has no graphics, generated media, PIP, masks, kinetic words or counters. Existing static one-word Assistant ExtraBold captions and atomic brand profiles stay intact. No new models/transcription requests. Use existing FFmpeg/ffprobe/Python/PIL/OpenCV; OpenCV availability does not prove robust subject identity/tracking. Reuse evidence from existing director/vision only if input digests match.

## Data contracts

Workdir files:

- `visual_hook_analysis.json`: schema_version, project_id, input_digest, final-body clock, exact quoted hook/word IDs, promise/payoff/emotion, local measurements/protected regions, evidence and unknowns.
- `visual_hook_candidates.json`: stable IDs, recipe/version, eligibility/reasons, source intervals, grounded feature ratings, evidence grade, score components and alternatives including NO_OP.
- `visual_hook_plan.json`: immutable semantic instruction; context/policy/reservation hashes, timeline, recipe/version, evidence, assets, crop cues, declared transitions, selection origin, audio_mode preserve.
- `visual_hook_render.json`: actual plan/input/output hashes, renderer/ABI, emitted transition frames, decoded frame count, diagnostics. Operational timestamps live here, not in semantic digest.
- `visual_hook_report.json`: applied/shadow distinction, why selected, QA, expected/unexpected events and preflight explanation.
- `VISUAL_HOOK_PREVIEW.mp4`: optional first10s comparison, never publish media; content-addressed temp/cache under `visual_hook/<digest>/`.

Plan schema minimal definition:

```text
schema_version: 1
project_id: nonempty existing project ID
input_digest, policy_digest, reservation_digest: canonical content hashes
recipe: NO_OP | SMART_PUNCH_IN in MVP
recipe_version: positive supported integer
timeline: {axis: body_final, fps_num:30, fps_den:1, frame_count:int>0, intro_frames:int>=0}
audio_mode: preserve
evidence: {word_ids:[int], quote:string, grade:verified|supported|unknown, reviewed_subjects:[region_id]}
assets: [{id, sha256, approved_root_relative_path, source_frame_range, role}]
cues: [{kind:crop, start_frame, end_frame, keyframes:[{frame, rect:[x,y,w,h]}]}
declared_transitions: [{cue_id, frame, type, from_source, to_source}]
selection: {actor:auto|harel, reason_codes:[string]}
```

Reject unknown required versions, NaN, bad paths/hashes, non-monotonic/out-of-range keyframes, wrong aspect/crop bounds, arbitrary code/HTML/filters and unsupported recipes. NO_OP requires empty assets/cues/transitions. Semantic validator additionally checks matching word/media generation and source/reservation constraints; JSON shape alone is insufficient.

Canonical digest includes source content+mapping, effective EDL/words/profile/reservations, recipe/renderer ABI and frozen policy. Exclude timestamps, machine load, music/history counts and mutable operational values. Stable sorted JSON and stable candidate ordering; no random selection. Do not insert self-referential digest fields into the digest input.

Learning events append to the existing correction/revision system: unique event_id, project/artifact/plan/timeline IDs, actor, suggested/selected recipe, approval/rejection/replacement/strength event, reasons, content_type/brand/topic, nullable verified speaker ID and future performance. Idempotent retries count once. Renderer errors are not preference rejections. “Approve all” without comparison is weak evidence, not a strong treatment win. Propose transparent cohort weights in shadow; never mutate global policy or frozen projects automatically.

Selection: eligibility first. Proposed shadow score benefits semantic_fit30%, reinforcement25%, visual_fit20%, authenticity15%, readiness10%; cost combines distraction35%, collision uncertainty25%, complexity20%, redundant motion20%. These are tentative weights, not calibrated probability. NO_OP has an explained baseline. Tie-break toward less intervention. Explicit disable/choice dominates. No87% confidence UI; use supported/unknown evidence and plain reasons.

## Review and approval UX

One collapsed Hebrew line: “פתיחה חזותית: ללא שינוי” or “פתיחה חזותית: הדגשה עדינה”. Optional comparison and disable; alternative only when one exists. No new mandatory approval step. Existing “אשר והמשך לגימור” binds the **visible** plan digest. A shadow suggestion that has never been previewed stays unapplied.

The current review approval happens **before** full finishing, so implement an internal prepare-preview job first. Extract only `prepare_visual_hook_context(...)` from the deterministic preparation portion of `local_finish_pipeline.py`; reuse it for preview and final. Internal `--prepare-visual-hook-review` stops before full rendering/music/FINAL/cover/artifact promotion. Snapshot saved EDL/prefs under the current lock, produce derived context/candidate preview without new editorial model decisions or rewriting saved EDL, and commit only if the edit token still matches. Runner `job_kind=hook_preview` must skip normal success artifact registration, especially when an old FINAL exists. Use current status/cancellation, not a second lock owner. Keep candidate plans in their own digest namespace until selected.

Existing approve binds the previewed plan digest. Final preparation must reproduce/verify its context; mismatch returns `HOOK_REVIEW_STALE` and preserves the last approved artifact. If the user approves before a hook preview exists, finish remains visually unchanged. No unseen late-selected hook is automatically applied. Test stale job completion, preview/final timing parity, canceled lock cleanup, approval-before-preview and zero FINAL/cover/schedule mutations from a preview job.

Extend validated finish-prefs `visual_hook` group; legacy absent=off. Carry edit token+expected plan digest on changes. Reject stale concurrent edits and respect finish lock. Generate candidates through the current locked job path, keep last approved artifact visible, and show candidate separately. EDL/words/assets/layer changes invalidate hook approval. Freeze applied hook plan/receipt/report with artifact. No new schedule endpoint; existing state/checksum rules remain mandatory. Content-identical NO_OP dedup must not mutate old immutable sidecars; record the selection event separately.

## QA: required behavior

Retain original G8 with no plan/off. For an applied hook, add timestamped event extraction over the hook window; validate plan/receipt/candidate hash; map body frames through actual intro offset. Classify exact declared events only with correct incoming/outgoing source identities. ±1frame tolerance is solely timestamp quantization.

A declared event **does not exempt** black/white corrupt frames, wrong source picture, A→B→A oneframe bursts, caption loss or decoding errors. Test those independently in cut neighborhoods, including expected cuts. Compare to clean source to avoid punishing inherited darkness. Lowcontrast expected cuts may not trigger scene score; report this without claiming a failed render.

Hard acceptance is physical/approval invariants: valid assets/frames, unchanged speech/time, correct approved source/plan, no introduced corruption, valid artifact. Face safety should reject a candidate when unproven; don't convert unreliable detector confidence into a new universal final blocker. Relevance/density/naturalness remain preflight judgments with explicit evidence and unresolved findings. Existing caption/RTL/canon/B-roll/cover gates still run. Every hard gate gets protects/cost_of_blocking/fallback and failure injection. Every implemented Harel lesson gets an actual code/test enforcer in lesson_registry.

## Exact files to implement

Create:

1. `tools/relvid/visual_hook.py` — dataclasses, context/provenance, analysis, candidates, selection, digest/validation.
2. `tools/visual_hook.py` — thin analyze/plan/preview/validate CLI, no FINAL/publish writes.
3. `tools/visual_hook_registry.json` and `tools/visual_hook_policy.json` — statuses, typed params, disabled defaults, shadow weights.
4. `tools/relvid/hook_render.py` — common crop IR, segment compiler and v1 adapter.
5. `tools/visual_hook_qa.py` — receipt/source-aware event and corruption checks.
6. `tests/test_visual_hook.py`, `tests/test_visual_hook_render.py`, `tests/test_visual_hook_qa.py`, `tests/test_visual_hook_review.py` — isolated contracts, real FFmpeg cases, failure injection, concurrency/artifacts/learning.

Modify narrowly:

- `tools/local_finish_pipeline.py`: `--visual-hook off|shadow|auto`, context/reservations, v1 visual_base, plan/receipt propagation, early intro resolution, refinish parity.
- `tools/relvid/render.py`: optional plan/IR and affected-segment key/filter integration, retaining old path exactly when absent.
- `tools/qa_gates.py`, `tools/preflight_critic.py`: optional hook-aware reporting/checks, original G8 behavior retained when off.
- `tools/relvid/registry.py`, `runner.py`, `revisions.py`: prefs, command propagation, approval token/digest.
- `tools/run_finish.py`: only minimal recording/pass-through changes if necessary; preserve single lock owner.
- `review-app/server.py`, `review-app/index.html`: minimal display, comparison, validated guarded choice and approval binding. Existing page owns inline JS; don't assume app.js exists.
- `tools/relvid/artifacts.py`: frozen hook sidecars and verification with legacy optional compatibility.
- `tools/learn_from_edits.py`: hook event/reason handling separate from EDL hook-cut reasons, shadow proposal only.
- `tools/gate_registry.py`, `tools/lesson_registry.py`: actual new checks/enforcers, allocate IDs from current registry.
- Relevant existing render, engine-choice, artifacts/API, full-intro, learning and preflight tests: extend rather than replacing assertions.

Do not modify EDL policy, ASR model, caption typography, B-roll doctrine, music levels, schedule integrations or existing source files for this feature. If a minimal seam is unavoidable, demonstrate the coupling with a failing real command and keep it backward-compatible.

Proposed CLI after implementation:

```sh
python3 tools/visual_hook.py analyze --workdir _work/.e2e/visual-hook/case01
python3 tools/visual_hook.py plan --workdir _work/.e2e/visual-hook/case01 --mode shadow --output _work/.e2e/visual-hook/case01/visual_hook_plan.json
python3 tools/visual_hook.py validate --workdir _work/.e2e/visual-hook/case01 --plan _work/.e2e/visual-hook/case01/visual_hook_plan.json
```

These commands do not exist yet. Preview CLI also accepts --plan, --render-engine and --output with test/preview destination validation. Plan/preview workdir mutations use current locks without nested deadlocks.

## Test and acceptance matrix

Copy actual sources from `/Users/hayon/rel-video-work/<project>/` using `evidence/sample_audit.json` exact source paths into isolated `_work/.e2e/visual-hook/` fixtures with test IDs/registry. No tests on real Monday/Metricool items or publish actions.

| Real sample | Expected initial treatment | Acceptance |
|---|---|---|
| שינה-והתאוששות, prj_c676626926c0 | NO_OP | Preserve empty sofa→entrance→sit; no trimming. |
| על-הלוח-כוח-וגיל, prj_7442d1160ded | NO_OP with existing early camera push | Preserve board/face; reject stale transcript timing. |
| מי-אמר-שמאוחר-מידיי, prj_e4208e603fa1 | Crop candidate vs NO_OP | Hands safe, no invented member proof, existing B-roll protections. |
| גאה-בצוות, prj_29060bc9516e | NO_OP preferred | Community topic must not imply team appears; preserve real gestures. |
| טיפ-אחד-HSPU, prj_2bb927f2efec | NO_OP natural movement | Motion is not semantic HSPU proof; later preview remains gated. |
| איך-הכרנו-הראל-ואוריה, prj_f07f86f80ea7 | NO_OP | Preserve both people and interaction. |
| מאסל-מן-רוטטור-קאף, prj_2e9c043d6831 | NO_OP | Title-derived full intro, suit/rack detection traps, illustration reservations. |

All inspected clean samples were1080×1920@30fps. These are candidate expectations from contact sheets, not approved new edits. Some source words files need provenance reconciliation before use.

Required tests:

- Off/shadow preserve legacy media/commands/cache keys; NO_OP adds no encoding. Old artifacts valid with absent hook fields.
- Both v1/v2, speed1 and1.15, source overrides, with/without tight export, cue crossing source cuts, fixed intro, manual/auto/empty B-roll, initial finish/refinish.
- Treatment preserves body n_frames/fps/dimensions, original pre-music speech samples on comparable engine path and all word/caption timing. Preserve existing final gates.
- Outside-window v2 segments unchanged. v1 lossy rerender compared to matched identity-control encoding; no false bitidentity promise.
- Same plan/inputs/pinned runtime yields same decoded frames/audio. Music-only change does not alter hook plan or render cache. Semantic input change invalidates plan/approval.
- Real FFmpeg failure fixtures: oneframe black/white, wrong asset at declared cut, A-B-A burst, expected lowcontrast cut, source-inherited darkness. No broad G8 exemption.
- Stale token, parallel app tabs, lock contention, missing approved asset, render stall fallback, sidecar tamper and candidate failure preserve last approved artifact.
- Learning dedup, weak implicit approval, explicit rejection and frozen policy behavior.
- Harel's actual phone-size original/treatment comparison records preference/reasons and requested corrections. Global auto stays off until an explicit approved envelope/cohort exists; no arbitrary sample-count gate.

Validation commands after implementation, from project root:

```sh
python3 tools/gate_registry.py --audit
python3 tools/lesson_registry.py --audit
python3 -m unittest discover -s tests -p 'test_visual_hook*.py'
python3 -m unittest discover -s tests
python3 tools/golden.py run
python3 tools/system_doctor.py
```

Run golden baseline before policy change and again after. Check current CLI help and read-only/isolation requirements. Exercise actual render commands; do not “fix” a stall with speculative flags that fail the real command. Record timing/memory/cache metrics against control but do not invent performance thresholds. Restart review-app via its current workflow after code changes, without killing an active finish job. No publishing tests.

## HyperFrames boundary, if a later recipe needs it

Inspected upstream source commit `ea7e1dbd0bd2afb77370b946461c4ea16afdb387`, CLI0.8.34, [repository](https://github.com/heygen-com/hyperframes). No runtime install or benchmark was performed. Its talking-head skill is designed packaging/storyboard authoring, not this selector. Motion templates can help complex diagrams; default frequent cards, generated assets and separate caption system are wrong for R.E.L.

Optional future `tools/relvid/hook_hyperframes.py` + versioned `tools/visual_hook_templates/`: fixed-schema authored template → silent alpha layer with exact frame count. Use pinned absolute executable, locally staged GSAP/fonts/media, strict missing-media behavior, telemetry opt-out and a real network-denied test. Verify alpha/dimensions/frames/readiness/no audio; don't hand it the whole edit. Background removal has model downloads/native costs and temporal artifact risk, so SUBJECT_POP is not justified now. FFmpeg handles crop/preview/PIP without HyperFrames.

## Migration and rollback

No bulk migration. Missing preference=off; missing sidecars valid for legacy. Add only new optional candidate/revision fields. Preserve source exports and all approved/scheduled artifact files. Off switch affects future renders, not historical media. If rollback is needed, restore snapshotted code and keep hook sidecars readable; don't erase or rewrite approved history. No auto scheduling/republication during rollout.

Implement phases in order: baseline/contracts → shadow → crop render parity → QA → review/artifact/learning → Harel pilot → narrow cohort activation. Do not mark complete until existing tests, real-command fixtures, registry audits and preflight pass or material pre-existing failures are clearly reported. “Ready for Opus” means ready to implement this plan, not already production-ready or retention-proven.

## PROJECT MEMORY UPDATE AFTER SUCCESS

Apply the following exact text **only after the corresponding implementation and tests succeed**. The first block describes the MVP; do not include future recipes as active. If implementation interfaces differ, reconcile the implementation to this contract or update this handoff explicitly before copying. Do not stamp success before Harel's required review. The system had no root CLAUDE.md found in this audit; update the actual project memory entry/pointer or AGENTS section rather than inventing a competing canonical file.

### Project documentation — ARCHITECTURE.md

> Visual Hook Engine is an optional local, video-only stage after the resolved recut/tighten/speed/word-reconciliation timeline and before body visual composition. It creates a frozen visual_hook_plan.json consumed by both v1 and v2. v1 routes the derived visual_base through existing B-roll; v2 compiles the same plan into source segments before B-roll and captions. Clean EXPORT remains unchanged. Speech, EDL, body frame count, caption timing and existing audio behavior are preserved. NO_OP and SMART_PUNCH_IN are supported; other registry recipes remain disabled unless explicitly released. Missing preference defaults to off; shadow creates evidence without changing media. Full format intros default to NO_OP. Applied plan, render receipt and report are frozen with the candidate artifact and bound to existing approval/checksum rules.

### DATA-SCHEMA.md

> Optional workdir files are visual_hook_analysis.json, visual_hook_candidates.json, visual_hook_plan.json, visual_hook_render.json and visual_hook_report.json. Hook plans use schema_version 1 and integer 30fps half-open intervals on body_final, with intro_frames mapping to delivered_final. A plan binds project_id, input/policy/reservation digests, recipe version, evidence, source asset checksums, cues and declared transitions; audio_mode is preserve. Operational timestamps are excluded from semantic digests. Missing hook files are valid for legacy projects. Applied hook sidecars are immutable artifact evidence. Hook learning events use stable event IDs and distinguish explicit preference, general approval and render failure; future learned weights cannot alter frozen plans.

### Canonical local SKILL — skills/rel-social-video-editor/SKILL.md

> **Visual Hook Engine:** optional and local-first; `--visual-hook off|shadow|auto`, with old projects defaulting to off. Current recipes are NO_OP and SMART_PUNCH_IN. NO_OP is a successful editorial decision, especially for existing motion, protected entrances, multiple people or uncertain crop safety. The engine changes picture only: never speech, EDL, duration, captions, music or publishing rules. Analysis binds the resolved final-body export and transcript provenance; the same approved plan must render in v1, v2 and fallback. No additional graphic text, generated humans, fake gym footage or automatic opening B-roll is authorized. A later PAYOFF_PREVIEW release requires a separate explicit canon exception. Review uses the existing app approval and immutable artifact checksum. Report preflight's verdict when saying a candidate is ready for Harel; unresolved high findings remain explicit. Every implemented lesson needs a registered enforcer.

### tools/PIPELINE.md

> After recut/tighten/speed and final-word reconciliation, resolve the clean body, B-roll/layer reservations and full-intro status. Off follows the legacy path unchanged. Shadow writes visual-hook analysis/candidates/plan/report without applying pixels. Applied hooks render from a frozen plan: v1 uses visual_base in all B-roll branches; v2 compiles per-segment hooks before B-roll/captions. Never overwrite EXPORT. Continue existing music/captions/loudness/delivery/intro/QA flow. Hook QA validates frame count, speech preservation, source identity, reservations and declared transitions; declared cuts never exempt accidental flashes or corrupt frames. Existing approval, locks, preflight, artifact promotion and schedule checksum checks remain mandatory. Use tools/visual_hook.py analyze/plan/preview/validate for isolated diagnostics; test E2E only on copies in _work/.e2e/.

### TESTING.md

> Visual-hook coverage includes off/shadow/NO_OP legacy parity, crop rendering in both engines, speed and source-cut mapping, full-intro offsets, B-roll/caption reservations, original speech preservation, stable digests/cache behavior, stale review tokens, locks and immutable artifacts. Real FFmpeg failure injection must detect black/white one-frame defects, wrong-source frames and A-B-A flashes even at declared transitions. Each new blocking gate has protects/cost_of_blocking/fallback and an injected failure test. Run test_visual_hook*.py, the existing full suite, golden checks, system doctor and gate/lesson audits. Creative thresholds require measured Harel-approved examples; scene energy and effect count alone are reporting metrics, not new blockers.

### Decision log / durable project memory — create docs/decisions/visual-hook-engine.md if no current equivalent exists

> Decision: Visual Hook Engine uses real footage first and preserves the existing R.E.L editing/audio/caption/approval pipeline. The initial release supports NO_OP and subtle crop only. One treatment and no accent is a pilot product constraint, not a proven retention optimum. Existing natural motion may be the best visual hook. Selection must cite actual words and verified visual evidence; motion does not prove payoff and face detection does not prove identity. HyperFrames is optional for a future justified composition, not a required renderer or editorial brain. G8 remains legacy-compatible and adds exact receipt-backed transition classification without hiding glitches. PAYOFF_PREVIEW, graphics and masking are not authorized merely by appearing in the registry. Global auto activation requires Harel-approved examples and a documented cohort/envelope. Do not claim measured retention uplift without actual performance evidence.

### Project instructions / AGENTS.md relevant project section, or actual existing external memory pointer

> The Social Video Editing System includes an optional Visual Hook Engine. Operational truth remains skills/rel-social-video-editor/SKILL.md and tools/PIPELINE.md. Read those before use. Missing hook preference means off; NO_OP is valid. Never change the spoken hook, add opening B-roll/graphic text outside explicit canon permission, or bypass review/artifact/checksum approval. Use the frozen visual_hook_plan and both renderer adapters; do not patch EXPORT and assume v2 will use it. The detailed implementation decision is documented in docs/decisions/visual-hook-engine.md.

### External VIDEO-CANON.md — only if a later PAYOFF_PREVIEW release is explicitly approved

> Exception — approved visual payoff preview: the Visual Hook Engine may show a short, same-project real picture excerpt over unchanged opening speech only when the exact spoken promise is visibly supported, source identity and frame ranges are verified, existing protected layers are respected, and the plan is reviewed through the existing app approval. The preview adds no duration or source audio and does not move the original payoff. This is not permission for generic B-roll on the Hook, generated media, graphic text or additional intros. Entry/exit transitions must be declared in the frozen plan and independently checked for glitches. Without this explicit exception and an enabled released recipe, the ordinary no-B-roll-on-Hook rule remains in force.
