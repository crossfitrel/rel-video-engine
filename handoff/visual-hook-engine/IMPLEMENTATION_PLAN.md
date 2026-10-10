# Visual Hook Engine — implementation plan, file by file

2026-09-11. All create/modify instructions below describe **future work**, not changes made in this preparation. Implement the bounded MVP first; deferred recipes are not mandatory production scope.

## Delivery phases

1. **Baseline and contracts:** verify current files/digests, isolate copies in `_work/.e2e/visual-hook/`, capture legacy v1/v2 behavior; add typed contracts and disabled registry. Do not install packages.
2. **Shadow analysis:** resolve timeline, discover local evidence, produce candidates including NO_OP and transparent explanations. No final pixels change.
3. **Render parity:** common crop compiler; v1/v2 integration, immutable receipt, failure injection and legacy off parity. No auto rollout yet.
4. **Review and artifacts:** preference validation, preview comparison, concurrency/approval binding, frozen sidecars and learning events.
5. **Pilot:** Harel compares original/subtle candidates on copies. Calibrate taste envelope from actual choices; unresolved high preflight findings explicit. Activate only approved cohorts. Production use still follows normal app approval.
6. **Optional second release:** explicit canon exception for same-project silent payoff preview, tests and pilot. HyperFrames only if an approved recipe needs it; separate source-pinned/offline spike.

## Proposed files and interfaces

| File | Action / exact responsibility | Interfaces and compatibility | Required tests |
|---|---|---|---|
| `tools/relvid/visual_hook.py` | CREATE. Typed dataclasses `HookContext`, `HookAnalysis`, `HookCandidate`, `HookPlan`, `HookReceipt`; canonicalization, semantic validation, selection, evidence caching. Keep editorial decision separate from renderer. | `build_context(...)`, `analyze(context)`, `discover(context, analysis)`, `select(context,candidates,prefs)`, `validate_plan(plan,context)`, `digest_plan(plan)`. No network/model required. NO_OP always available. | Invalid versions/numbers/paths/frames, missing provenance, motion≠payoff, deterministic ordering, unknown subject→NO_OP, per-project policy freezing. |
| `tools/visual_hook.py` | CREATE thin CLI, no duplicate business logic. | `analyze --workdir PATH`; `plan --workdir PATH --mode shadow --output PATH`; `preview --workdir PATH --plan PATH --render-engine v1|v2 --output PATH`; `validate --workdir PATH --plan PATH`. Preview cannot write FINAL or publish. Mutating workdir commands use existing lock; readonly validate does not. | Parse/options, safe output destinations, stale plan error, lock behavior, no production API. |
| `tools/visual_hook_registry.json` | CREATE declarative11 entries (10 families plus NO_OP); only NO_OP/crop implemented. | schema_version1, id/version/status, evidence requirements, renderer capabilities, typed param limits, fallback IDs. Unknown/disabled recipe rejected. No executable filter strings. | Registry uniqueness, disabled recipe cannot activate via high score, fallbacks terminate in NO_OP. |
| `tools/visual_hook_policy.json` | CREATE frozen-default policy. | version, default_mode off, cohort allowlist empty, experimental weights, crop pilot envelope explicitly uncalibrated, no accent, banned assets. Do not put this into `edl-policy.json`. | Stable digest; music/time/history counts excluded; explicit disable wins; no global updates from individual approval. |
| `tools/relvid/hook_render.py` | CREATE shared deterministic crop IR/compiler and v1 adapter. | `compile_for_segment(plan,segment)->HookIR`; `render_v1(context,plan,output)->receipt`; `validate_render(...)`. Uses ffmpeg argument arrays, current color/audio conventions. No arbitrary shell expressions from model. | Speed1/1.15, segment crossing, exact frames, identity at boundaries, containment, no-op does not render, asset mismatch fails candidate. |
| `tools/local_finish_pipeline.py` | MODIFY mode argument, context creation after actual tighten/speed/reconcile, reservation resolution before selection, hook plan/receipt propagation; v1 explicit visual_base everywhere. | `--visual-hook off|shadow|auto`, default off. Later `--visual-hook-plan PATH` only for validated frozen plan, not arbitrary bypass. Explicit app prefs dominate. Preserve defaults music/engine/director/refinish. Resolve full-intro presence before plan using existing logic without moving intro rendering. | All v1 B-roll branches consume visual_base; EXPORT remains unchanged; v2 gets plan; refinish parity; fixed-intro NO_OP; approved plan never silently reselected. |
| `tools/relvid/render.py` | MODIFY optional per-segment hook IR; compile before B-roll/captions; add affected-fragment digest to key. | `build_timeline(..., hook_plan=None)` backward-compatible optional arg; Segment default empty hooks; retain current out_start/speed/n_frames logic. NO_OP/off old cache keys unchanged. | Existing render tests; source overrides, HDR normalization, word timings, no second speed division, only affected keys change, music-only refinish reuses video, v2→v1 fallback reproduces plan. |
| `tools/visual_hook_qa.py` | CREATE receipt validation, observed/expected events and independent glitch checks; structured gate results. | `check(context,plan,receipt,candidate)->report`; CLI `--workdir --video --plan --receipt`. Uses integer frame mapping and intro offset; source-aware defects. | One-frame black/white, wrong asset at right time, A-B-A burst on declared cut, invalid receipt, expected low-contrast cut, original black frame inherited, no plan legacy path. |
| `tools/qa_gates.py` | MODIFY optional hook context/report; retain original G8 on off and no plan. | Add structured observed events to hook-aware reporting, not global firstsecond exemptions. Current G8 warning-only remains warning-only. | No-plan legacy equality; ±1-frame matching only; intro offset; declared transition cannot mask injected glitch. |
| `tools/preflight_critic.py` | MODIFY optional hook findings: relevance, density, repeated movement, source/taste uncertainty. | Missing plan normal on legacy; distinguish shadow vs applied. Add natural-language “what would Harel correct?” reasoning; do not claim validated lift. | Correct ready_for_harel and reporting of unresolved high findings; no silent overriding existing P1–P15/illustration/B-roll findings. |
| `tools/relvid/registry.py` | MODIFY validated visual_hook preference group. Current whitelist only music/B-roll. | `visual_hook:{mode,enabled,selected_candidate_id,strength,plan_digest}`; old manifests deserialize as off; no bulk rewrite; reject unknown strength/recipe selection. | Save/read round-trip; existing groups preserved; explicit disabled survives rerun/CLI; no index-only source of truth. |
| `tools/relvid/runner.py` | MODIFY build_command propagation only. | Carry effective hook mode/frozen plan; preserve engine choice/default and lock. No hook-only alternate finalizer. | Command arguments and precedence, refinish, double-run lock, failure keeps existing artifact. |
| `tools/run_finish.py` | MODIFY only if parser/recording needs explicit hook fields; current pass-through may suffice. | Keep one locking owner and run records. Record plan digest in run provenance; don't add nested deadlocking acquisition. | Single lock lifecycle, retry/idempotency, cleanup of partial preview/candidate, failed run no output hash. |
| `review-app/server.py` | MODIFY GET project detail and finish-prefs validation; add read preview details and guarded choice route; bind `/api/approve` to viewed plan. | Proposed `GET /api/visual-hook/<name>` returns status/reasons/candidates/digest; `POST /api/visual-hook/<name>` accepts edit_token, expected_plan_digest, enabled, candidate_id; returns409 stale,423 locked or existing lock convention. Reuse current job mechanism. | Stale two-tab writes, approval races, no unseen candidate acceptance, missing preview, current artifact display preserved, no extra publish endpoint. |
| `review-app/index.html` | MODIFY inline existing UI scripts/styles (no separate app.js assumed). | Collapsed Hebrew status + comparison + disable; details/alternative optional. Same existing approve action; keyboard/RTL accessible. No uncalibrated confidence percent. | Manual narrow viewport, original/treatment same audio/time, disabled state persists, render error clear, pending candidate distinct from approved. |
| `tools/relvid/artifacts.py` | MODIFY SIDECARS to freeze applied hook plan/report/render receipt with candidate. | Existing sidecar names/provenance behavior preserved; old artifacts valid with no hook. Verify digests before schedule. Same-media dedup cannot mutate old immutable artifact; store shadow/no-op selection event separately if media reused. | Changed hook produces new media artifact where appropriate; sidecar tampering/stale checksum rejected; no-op dedup safe; previous artifact unchanged. |
| `tools/relvid/revisions.py` | MODIFY only minimal revision/approval metadata hook digest. | Bind existing edit approval token to selected plan; preserve older revision parsing. | Old approvals, changed plan invalidation, concurrent update handling. |
| `tools/learn_from_edits.py` | MODIFY to recognize hook event types without conflating with EDL RC_HOOK. | Append/aggregate hook decisions; separate hook-policy proposal file and explicit apply approval; --apply remains shadow alias for existing flow. Reuse existing ledger/dedup, no ML library. | Event retries, rejection vs render failure, implicit approval not strong positive, cohort separation, old events still readable, frozen plans unchanged. |
| `tools/gate_registry.py` | MODIFY only to register actual new gates with complete metadata. | Allocate IDs against current registry; binary only physical/approval invariants. | Audit plus failure injection for every new hard gate. |
| `tools/lesson_registry.py` | MODIFY to record newly implemented Harel feedback with enforceable code/test links. | Use new IDs assigned at implementation; don't claim hypothetical lessons as user feedback. | Audit catches removed enforcer; existing lessons pass. |
| `tests/test_visual_hook.py` | CREATE selection/schema/digest/policy tests. | Temporary dirs, synthetic media metadata and grounded real-fixture manifests. | Contracts and negative cases above. |
| `tests/test_visual_hook_render.py` | CREATE real FFmpeg integration tests plus mocked command tests. | Short deterministic generated patterns only inside tests; never treat them as publishable media. | Decode PTS/frame/audio checks, both engines, cross-segment cue, fallback parity. |
| `tests/test_visual_hook_qa.py` | CREATE failure-injection suite. | Small actual encoded fixtures. | Every hard gate both success and failure, plus declared-transition adversarial cases. |
| `tests/test_visual_hook_review.py` | CREATE app/approval/prefs/learning tests. | Test client with isolated registry/workdir; no real Monday/Metricool items. | Tokens, locks, immutable artifacts, API input validation and event idempotency. |
| Existing `tests/test_render_v2.py`, `test_render_engine_choice.py`, `test_artifacts.py`, `test_artifacts_api.py`, `test_full_intro.py`, `test_learning.py`, `test_preflight_critic.py` | MODIFY narrowly where optional interfaces require extension. | Existing assertions remain; do not replace legacy tests with feature-only tests. | Full legacy coverage plus new opt-in behavior. |

### Explicitly not modified in MVP

`edl_build.py`, `edl_cut.py`, `edl-policy.json`, align/Whisper models, `captions-app/captions_overlay.py` typography, music selection/loudness defaults, B-roll doctrine and `animation_overlay.py` rendering semantics. Reuse their interfaces. If code coupling forces a change, first show a failing concrete command and justify a minimal compatible seam; don't refactor them speculatively.

### Optional HyperFrames files, only after demonstrated need

Create `tools/relvid/hook_hyperframes.py` adapter and `tools/visual_hook_templates/<template_id>/` containing versioned HTML, local JS/fonts and asset license manifest. Interface `render_alpha(template_id,params,asset_manifest,frame_count,fps)->asset,receipt`. No speech, captions, audio mixing or finalization in the adapter. Use absolute pinned executable, timeout and process cleanup, strict media mode, environment telemetry opt-out, denied network test. Validate dimensions, alpha, exact frame count, local assets, no audio. Tests cover browser absent, missing font, blank frame, nested-video readiness, timeout and fallback. These are **not** dependency/install instructions for the initial release.

## Preview job: required before automatic application

Add `prepare_visual_hook_context(...)` as a minimal shared extraction from `local_finish_pipeline.py` and an internal `--prepare-visual-hook-review` early-exit mode. It snapshots saved EDL/prefs and produces a deterministic clean final-body context plus candidate preview without rendering/promoting FINAL, changing the EDL or rerunning editorial model decisions. Use a candidate namespace, not overwriting an approved plan. Reuse cached context only on matching semantic digest.

In `runner.py`/`run_finish.py`, add explicit `job_kind=hook_preview` with current locking/status/cancellation, and skip normal success artifact registration for this job. Test that an old FINAL cannot be registered as the preview's new output. In review-app, compare edit token and context digest before committing a finished preview job; stale jobs are discarded as candidates. Existing approve binds the previewed plan. Real finish recomputes/verifies the same context and fails candidate with `HOOK_REVIEW_STALE` on mismatch, retaining the last approved artifact. If the user approves before a hook candidate exists, the current finish remains unchanged. This prevents an unseen hook from applying after ordinary approval.

Extra tests: preview job never creates FINAL/cover/schedule state; preview uses same timing/IR as final; stale asynchronous completion cannot overwrite a newer selection; canceled preview releases lock; approval-before-preview yields no applied hook; matching preview context reused without extra ASR/model work.

## JSON schema implementation requirements

Use schema_version1 and a shared definitions module or JSON schemas under `tools/schemas/visual_hook/` if the project convention supports it. Do not require a new runtime validator package; system jsonschema availability differs from Whisper environment.

| Contract | Required fields and constraints | Semantic checks beyond JSON Schema |
|---|---|---|
| Analysis | project_id; input_digest; timeline; window summaries; hook word IDs/quote; evidence array; unknowns array | Word IDs exist in matching words file; windows refer to inspected media generation; no title-only payoff. |
| Candidate | candidate_id; recipe/version/status; eligibility; evidence_grade enum; feature ratings0..1; score parts; asset refs; params; reason codes | Disabled recipes cannot be selected; params conform to recipe; source content proves claim if needed. |
| Plan | schema_version1; project_id; input/policy/reservation digests; recipe/version; timeline fps30/1+frame_count>0+intro_frames>=0; audio_mode preserve; evidence; assets; cues; transitions; selection | All frames bounded and intervals half-open; crops aspect-correct/contained; keyframes ordered; audio immutable; NO_OP arrays empty; asset roots/checksums valid; digest excludes operational metadata. |
| Receipt | plan_digest; input/output content hashes; renderer+ABI; actual_frames; emitted_transition list; diagnostics | Actual decoded frame count and source mapping, not just self-reported values; compare candidate hash. |
| Report | applied boolean; mode; selected reason; candidate summaries; QA list; observed event classes; recommendation | Shadow never claims applied; high open findings included in preflight. |
| Learning event | event_id; project_id; artifact/plan/timeline IDs; event enum; actor; suggested/selected recipe; strengths; reasons; content_type; brand; topic tags; nullable speaker/performance; created_at | Dedup stable ID; frozen plan referenced; distinguish renderer failure from user dislike; no inferred identity. |

Allowed event enum: `hook_suggested`, `hook_selected`, `hook_approved`, `hook_disabled`, `hook_replaced`, `hook_strength_changed`, `hook_rejected`, `hook_render_failed`. Initial “approve all” is `hook_approved` with comparison_seen=false, not an explicit preference win.

Plan params must be data, not code. Validate finite numbers, bounded rects, monotonic frames, allowed roots, file hashes, supported version and renderer. Preserve unrecognized optional legacy metadata but reject unknown required hook schema versions. Use atomic JSON writes and lock-sensitive selection changes.

## Real test matrix

The source locator and measured metadata are in `evidence/sample_audit.json`. Create independent copies for E2E. Do not run a real finish on source projects during tests. The fixture copies must carry distinct test project IDs and isolated registries/artifact roots so a title lookup cannot reach production.

| Fixture | Coverage | Expected scenario | Extra acceptance |
|---|---|---|---|
| שינה-והתאוששות | Talking head / personal / intentional entrance | NO_OP | Empty0–.4s remains; no trim; all opening speech preserved. |
| על-הלוח-כוח-וגיל | Professional value / board | NO_OP initial camera movement; optional reviewed crop alternative only | Board/face never clipped; stale word/media pairing rejected before selection. |
| מי-אמר-שמאוחר-מידיי | Conversion | Subtle crop vs original comparison | No fake member/social proof; protect hands, first sentence and existing B-roll bed. |
| גאה-בצוות | Community subject but solo footage | NO_OP preferred; crop only if reviewed safe | No algorithmic inference that team members appear; preserve lean/gesture. |
| טיפ-אחד-HSPU | CrossFit movement/demo | NO_OP first motion; phase2 preview candidate later | Full movement safety, motion peak not treated as semantic proof, G8 real-motion warning handled honestly. |
| איך-הכרנו-הראל-ואוריה | Multi-person connection | NO_OP | Both people kept; no arbitrary active-speaker crop; no clothing identity inference. |
| מאסל-מן-רוטטור-קאף | Format intro / occlusion / illustration | NO_OP | Detect title-derived intro, body/final clock distinction, no printed-suit-face track, illustration gates remain. |

### Cross-product and failure cases

For each relevant recipe, test v1/v2, off/shadow/auto, speed1.0 and1.15, with/without tight export, manual/auto/empty B-roll, refinish and initial finish. Full intro, source override and illustration collision fixtures add coverage; do not render every expensive combination if a targeted case proves the same invariant.

1. Off: old command construction and v2 cache keys identical; same decoded media for deterministic baseline. Shadow: media and artifact checksum unchanged; only analysis/report files added.
2. NO_OP: no extra encode/decode or new media generation; report explains decision.
3. Crop: output same body n_frames,30fps,1080×1920; source audio samples unchanged at a comparable pre-music stage; words/cues identical. Existing final QA passes.
4. Cue crossing a source cut or speed transform: local/global conversion yields intended frame bounds and no extra frames. Source override respected.
5. No treatment outside reserved interval: v2 unaffected segments retain hashes; v1 compare matched identity-control encode rather than demand impossible lossy pixel identity. Record any boundary-local differences and inspect.
6. Same plan twice: same decoded frames/audio on pinned environment; plan digest stable. Change music only: no visual plan/cache change. Change source/words/crop/recipe: invalidates correct cache and approval.
7. Inject wrong image at exactly a declared transition, single black/white frame and A→B→A flash: new QA fails introduced corruption even if scene event is “expected”. Expected lowcontrast transition does not fail just for missing scene score.
8. Invalid asset/missing source or runtime after approval: candidate fails, last approved artifact intact. Before approval uncertain assets choose NO_OP with explanation.
9. Stale edit token/digest, two browser tabs, overlapping finish jobs: existing locks/concurrency block the mutation; no newer approval overwritten.
10. Sidecar tamper and changed media: artifact verify fails. Previously scheduled artifacts remain untouched. Never test real publish endpoints.
11. Layer collisions: captions retain exact profile; overlap with reserved manual B-roll forces eligible alternative/NO_OP, not a silent B-roll move.
12. Learning replay: repeated same event does not multiply preference; actor/model/human distinguished; future weights cannot change frozen plans.

### Creative acceptance and measurement

Have Harel compare original and treatment on the actual phone-sized opening with audio, then record: original/treatment/tie; supports promise; face/gesture safe; distracting; feels authentic; requested change. Use real per-example decisions, not a minimum approval count invented as a statistical guarantee. An effect can ship for reviewed individual projects while global auto remains disabled. Global rollout requires an explicitly approved crop envelope/cohort plus measured baseline comparison; no universal score threshold is pre-approved here.

Future platform measurement should distinguish viewed-vs-swiped, early retention and watch time, using platform-specific definitions and matched cohorts/variants. No causal claim from different organic posts without controlling distribution/topic. Preparation did not access performance data.

## Commands and verification order

Run from the project root; commands below are for the implementing session. New CLI examples become executable **only after those files exist**. Inspect CLI help first if current interfaces changed. Baseline gate/lesson commands already ran in preparation; full tests/doctor/golden did not.

```sh
python3 tools/gate_registry.py --audit
python3 tools/lesson_registry.py --audit
python3 -m unittest discover -s tests -p 'test_visual_hook*.py'
python3 -m unittest discover -s tests
python3 tools/golden.py run
python3 tools/system_doctor.py
```

Golden baseline before changing hook policy, and again afterward. Preserve failures as evidence; don't assert old documented counts. Rendering tests must exercise the **real ffmpeg command**, not only filter string assertions. Existing fixed intro, B-roll, captions and artifacts tests are relevant regression coverage. Restart review server after actual code update using its existing service workflow; do not kill an active finish job to restart the UI.

Future isolated CLI examples:

```sh
python3 tools/visual_hook.py analyze --workdir _work/.e2e/visual-hook/case01
python3 tools/visual_hook.py plan --workdir _work/.e2e/visual-hook/case01 --mode shadow --output _work/.e2e/visual-hook/case01/visual_hook_plan.json
python3 tools/visual_hook.py validate --workdir _work/.e2e/visual-hook/case01 --plan _work/.e2e/visual-hook/case01/visual_hook_plan.json
```

Measure walltime, peak memory, frames rendered, cache hits and subprocess state against the same baseline. No unmeasured performance blocker. A long zero-CPU stall is a failure to diagnose on the actual command, not a reason to leave a speculative FFmpeg flag change in production.

## Migration, rollback and documentation

No data migration is required for off-default optional fields. Old artifacts remain valid. New hook metadata is added only as new candidate/revision data. No retrospective re-render or scheduling update. Feature rollback sets effective mode off for future work and restores tested code if needed; keep existing approved artifact/checksum and historical hook sidecars readable. Never mutate an immutable artifact to erase a hook history.

After successful implementation and pilot, update local canonical SKILL, PIPELINE, ARCHITECTURE, DATA-SCHEMA, TESTING, decision log and relevant project pointer. Update external VIDEO-CANON only for a specifically approved exception. Exact proposed memory text is at the end of CLAUDE_OPUS_HANDOFF.md. Do not declare a deferred recipe implemented, or change music/B-roll policy while documenting this feature.
