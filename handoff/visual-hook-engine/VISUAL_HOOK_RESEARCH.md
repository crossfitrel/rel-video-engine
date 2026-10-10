# Visual Hook Engine — research and audit

Prepared 2026-09-11. Status: specification, not implemented. Audience: Harel and the implementing architect. Research does not establish a retention uplift for R.E.L.

## Recommendation

Start with a selector that can confidently leave a good opening alone. Implement **NO_OP and SMART_PUNCH_IN** first, with no new runtime dependency. Test a duration-preserving, silent **PAYOFF_PREVIEW** later, after an explicit narrow canon exception. Reserve HyperFrames for genuinely complex, approved compositions. Do not migrate editing, Hebrew captions, audio, or QA into it.

The seven local examples contain several openings with useful natural motion already. A new visual event in the first 0.8 seconds is therefore not a universal requirement. One principal treatment and at most one supporting accent is a proposed pilot limit, not an evidence-based optimum; the MVP needs no accent at all.

## Evidence levels and limitations

- **Code inspected:** repository files, actual branches, parameter defaults, cache and artifact handling; no inference from documentation alone.
- **Local frames inspected:** seven contact sheets, source file probes and sampled motion measurements. These are sparse visual audits, not full playback approval or audience experiments. Original exports were not modified.
- **Public visual observations:** public Instagram pages, individual reel frames and displayed captions, viewed through the browser. Search fetches alone failed on Instagram; direct browser pages worked after closing the sign-up overlay. No login bypass, downloaded media, or platform interaction was used.
- **Documented capability:** official vendor docs or source code, not a successful local product benchmark.
- **Hypothesis:** an editorial interpretation or proposed pilot setting. No percentages below should be understood as measured retention lift.

Browser samples do **not** establish exact first-frame composition, first-cut latency, effect duration, or cut cadence for an entire creator. A screenshot at 5.5 seconds is not evidence of what happened at zero. Those quantities remain unmeasured for the public corpus; they are deliberately not used as gating thresholds. Local sample timings below are directly extracted from local files.

## Mandatory references and additional visual samples

| Source and concrete example | What was actually observed | Transferable mechanism | Reject / limit |
|---|---|---|---|
| [Avia Reznikov profile](https://www.instagram.com/aviareznikov/), [Tel Aviv POV reel](https://www.instagram.com/aviareznikov/reel/DEKN-3Lodfm/) | Browser sample around 5.58 s of 27.77 s: seated participant, printed receipts and a foreground hand holding receipts; conversational framing. | An ordinary physical object makes an abstract complaint immediately tangible. Use an existing bar, board or exercise as evidence. | Do not infer a timed opening sequence from this sample or stage extra shots by default. |
| [Danny Voronov profile](https://www.instagram.com/dannyvoronov/), [barbell / test-block reel](https://www.instagram.com/dannyvoronov/reel/Dc_mYyrJzp7/) | Around 6.23 s of 17.07 s: full-body snatch footage, number/load concept expressed through a real barbell and large text. This account is a fitness coach, not simply an editing reference. | Show the real action that gives the number meaning; preserve hands, bar path and feet. | Do not copy multi-line top text or convert any motion peak into a relevant payoff. |
| [Ananas Social profile](https://www.instagram.com/ananas.social/), [conversation reel](https://www.instagram.com/ananas.social/reel/DdB_VHTKiLm/) | Around 5.52 s of 69.80 s: female speaker with mic, close-medium framing, small context text plus a larger magenta phrase. | Legible face and conversational immediacy; a semantic emphasis can guide attention. | Two independent text tracks and magenta styling conflict with R.E.L caption and brand rules. |
| [Required post DcB7HAzsDnR](https://www.instagram.com/p/DcB7HAzsDnR/) | Resolves to Jessy Lopes Barreto. Public caption explicitly credits Seedance 2.5 / Higgsfield for generated scenes. Viewed frame includes outdoor presenter and a circular countdown; poster poses real-versus-AI question. | Question → viewer prediction → reveal is a useful structural pattern. | This is a **counterexample for media provenance**: do not reproduce generated people or synthetic scenes. No frame-accurate sequence was measured. |
| [Devin Jatho](https://www.instagram.com/devinjatho/), [Nexus POV reel](https://www.instagram.com/devinjatho/reel/DdB-xoiS5Mm/) | Around 11.90 s of 163.17 s: seated person, persistent POV heading and a revenue card over the lower body. Outside our 0–10 s measurement window. | A designed card can represent the concrete claim being discussed. | This sample is longer than R.E.L target duration and graphically dense. It does not prove a first-second rule; financial cards are not a gym visual language. |
| [Alex Hormozi](https://www.instagram.com/hormozi/), [overcomplication reel](https://www.instagram.com/hormozi/reel/DdHQrSWuK_b/) | Around 12.41 s of 24.91 s: standing speaker by board, visible arm gesture, simple white subtitles. Profile poster carries a question. | Content and an expressive speaker can carry business short-form without a complex composition in every sampled moment. | Do not treat the poster as a timed frame, or copy text positioning and word grouping. |

The dates shown by public pages are retrieval metadata, not evidence about retention. Views, follower totals, promotional captions and comments were excluded from scoring evidence.

### Wider reference patterns

[Jenny Hoyos in YouTube's official Shorts discussion](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/) stresses capturing interest immediately and telling compact stories. This supports paying attention to the first readable frame; it does not establish that every edit needs a generated event before 0.8 seconds. The [producer's interview index](https://www.mfmpod.com/videos/the-formula-to-break-100-million-views-on-shorts-ft-jenny-hoyos/) includes a first-frame discussion at 19:27. This is practitioner guidance, not a controlled R.E.L experiment.

[Devin's hook template offering](https://devinjatho.gumroad.com/l/hooks) and [APEX Editors](https://joinapexeditors.com/) demonstrate a commercial ecosystem of reusable visual treatments and editorial training. Template availability is useful inspiration for a registry; claims about growth or revenue are not validation of an automatic selector.

[Zach King’s team](https://www.zachkingteam.com/) is a reference for reveal and visual curiosity. That approach often depends on authored scenes; it is a poor default for repurposing ordinary gym footage. [Nas Daily](https://www.nasdaily.com/) is a reference for one clear idea and a concrete story. Neither was treated here as a frame-timed performance dataset.

[TikTok's creative guidance](https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads) and its [Creative Codes](https://www.tiktok.com/business/library/TikTok_CreativeCodes_May2023.pdf) emphasize the opening and a hook/body/close structure. Ad-recall statements from a platform's advertising research are not organic-view retention results, and cannot calibrate R.E.L cut-frequency thresholds.

## Pattern decisions

| Pattern | Useful condition | Local implementation | Decision |
|---|---|---|---|
| Real movement in first frame | Exercise, entrance, interaction already meaningful | Preserve it, inspect continuity | First-class NO_OP |
| Crop / subtle push | Static composition, safe subject bounds, verbal emphasis | FFmpeg crop/scale with deterministic trajectory | MVP |
| Later payoff preview | Later **visible proof of the opening promise** | Same-project silent insert over unchanged speech | Controlled second phase |
| Freeze | A stable exercise detail requires inspection | Hold video only; preserve body clock/audio | Deferred; talking mouths make this awkward |
| PIP / split | Speaker and real demonstration both needed | FFmpeg composition | Deferred, especially small-screen/caption collision |
| Mask / subject pop | Real reason for depth separation | Segmentation plus graphic layer | Exclude from MVP; hair/hands temporal artifacts |
| Before / after | Verified comparable states exist | Labeled comparison only after policy approval | Deferred; no invented transformation claim |
| Numbers / progress | Number is spoken, verified and adds comprehension | Existing PIL or approved overlay | Not a default second caption track |
| Tracked emphasis | A known object can be tracked reliably | Local tracking + minimal primitive | Deferred; confidence loss must remove overlay |
| Keyword typography | Usually duplicates existing subtitles | Existing caption system owns words | Reject as separate MVP layer |
| Small explanatory diagram | Footage cannot show the relationship | Existing illustration path or optional HyperFrames template | Use illustration eligibility, not hook loophole |

## Timing: a decision window, not an effects schedule

| Window on the actual delivered timeline | Editorial question | R.E.L implication |
|---|---|---|
| 0–1 s | Is the first decoded image valid, understandable, and already active? | Preserve the swing, entrance or human interaction. Do not add a flash to satisfy a timer. |
| 1–3 s | Does the visual support the opening sentence? | A single subtle emphasis can help a static head; avoid gesture clipping or competing overlays. |
| 3–5 s | Has the opening promise become concrete? | Consider a later demo only with exact semantic evidence and an approved exception. |
| 5–10 s | Is the viewer now in the explanation? | Hand back to ordinary composition and existing B-roll doctrine. A ten-second analysis window does not mandate a ten-second effect. |

A fixed intro is part of what viewers see first. A body treatment at body t=0 may be at final t=4, for example. Both clocks must be reported. Initial fixed-intro policy: leave it alone and do not pretend a body-only treatment is a scroll-stopping first frame.

## Product capability audit

| Product | Verified capability / evidence | Claims not established here | R.E.L use |
|---|---|---|---|
| OpusClip | Official [subject tracking](https://help.opus.pro/docs/article/subject-tracking) and [layout/reframing](https://help.opus.pro/docs/article/layout-and-reframing) describe subject-oriented reframing controls. | Semantic correctness, local execution, or automatic retention improvement. | Borrow subject-safe composition and an override, not the service dependency. |
| Submagic | Official [B-roll controls](https://care.submagic.co/en/article/how-to-add-b-rolls-in-submagic-1kk7vj0/) allow clip placement; [API upload configuration](https://docs.submagic.co/api-reference/upload-project) exposes magic zoom/B-roll/hook-title settings. | Vendor lift claims; suitability for Hebrew canon; an explanation of each selected visual. | Separate toggles are insufficient: R.E.L needs evidence and immutable plans. |
| Captions | Official [media documentation](https://captions.ai/help/docs/visual/media) describes media placement, including caption-aware positioning, imports and generation. | Guaranteed collision-free output or local deterministic results. | Reserve caption geometry explicitly; do not use generated stock people. |
| HyperFrames | Source supports local browser/FFmpeg rendering and authored HTML compositions; detailed audit below. | An out-of-box R.E.L editorial brain, tested Hebrew caption parity or performance on this machine. | Optional bounded renderer. |
| Existing R.E.L illustration renderer | Inspected local HTML→PNG frames→video path, placement solver and semantic illustration gates. | That it already runs automatically inside finishing, or is fully offline. | Reuse narrowly after fixing explicit asset/runtime contracts, not as a competing pipeline. |

No commercial product was installed, bought, given footage, or benchmarked. Documentation is evidence of interfaces, not proof that their marketing result will occur.

## HyperFrames source audit

Upstream inspected by cloning source only: [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes), commit `ea7e1dbd0bd2afb77370b946461c4ea16afdb387`, CLI package `0.8.34`. Apache-2.0 project; check bundled asset licenses separately before reuse. Temporary checkout: `/tmp/rel-visual-hook-hyperframes-audit`. No dependency install, CLI init, external transcription or render was run.

- [talking-head-recut skill](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/skills/talking-head-recut/SKILL.md): authored storyboard/layout packaging around a continuous talking-head video; it is not a drop-in replacement for R.E.L EDL decisions. Its frequent card structure is excessive for this canon. Its transcript/asset workflow does not justify retranscribing Hebrew.
- [motion-graphics skill](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/skills/motion-graphics/SKILL.md): useful concepts for reusable compositions; not instructions executed in this audit. Do not import its broad workflow or generated asset defaults into production.
- [render CLI](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/cli/src/commands/render.ts): explicit frame rate/output formats, strict missing-media option `--no-best-effort`, optional GPU/Docker controls. Pin version and arguments; never `npx latest` at finish time.
- [render format handling](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/producer/src/services/render/renderFormat.ts): alpha-capable formats make a transparent overlay a plausible integration boundary. A MOV/WebM layer should have no audio and a fixed frame count; R.E.L composites it before captions.
- [video-frame coverage checks](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/producer/src/services/render/videoFrameCoverage.ts): explicit media-frame coverage accounting is valuable. Its internal default ratio is not R.E.L acceptance; require independent exact output-frame verification.
- [background-removal manager](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/cli/src/background-removal/manager.ts) and [command](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/cli/src/commands/remove-background.ts): ONNX human segmentation, model download and native runtime costs. A background output is not magically inpainted scenery. This does not solve gym occlusion or temporal hair/hand consistency automatically.
- [telemetry policy](https://github.com/heygen-com/hyperframes/blob/ea7e1dbd0bd2afb77370b946461c4ea16afdb387/packages/cli/src/telemetry/policy.ts): explicit `HYPERFRAMES_NO_TELEMETRY=1` / `DO_NOT_TRACK=1` supported. For an offline claim, actually test with network denied and staged fonts/GSAP/media, not merely with telemetry disabled.

### A/B/C/D decision

**D now:** FFmpeg is simpler for crop, silent preview and PIP. **C later:** own small, versioned templates with fixed input schemas for approved diagrams. **A only behind that adapter:** pinned CLI executable, no network, bounded subprocess, deterministic asset manifest, strict output validation. **B selectively:** ideas such as explicit media readiness, frame accounting and seekable animation, without copying a broad agent orchestration stack.

Current local `tools/illustration/render_frames.js` uses Puppeteer and GSAP screenshot seeking. `illustration_build.py` strips the HyperFrames runtime because an earlier integration produced blank frames. The template still references CDN GSAP: current rendering is not fully offline. This historical workaround does **not** prove the current upstream release fails. Test it separately if a recipe truly needs it. Browser screenshot timing alone is insufficient for reliable nested video; prefer FFmpeg-extracted footage, or a verified upstream media-preprocessing path.

## Real local sample findings

Files, exact paths, probe results and sampled motion data are in `evidence/sample_audit.json`; `sample_01.jpg` through `sample_07.jpg` contain inspected frames. All seven clean samples are 1080×1920 at 30 fps. The listed duration is the inspected file, not a claim about its current approved FINAL.

| Sample / project_id | Duration | Evidence in first ten seconds | Expected initial decision |
|---|---:|---|---|
| שינה-והתאוששות / prj_c676626926c0 | 59.005 s | Empty sofa at 0/.4; person enters around .8, stands at 1.5, sits by 3, crosses legs by 5. | NO_OP: protect intentional entrance. A low-motion initial half-second is not automatically dead footage. |
| על-הלוח-כוח-וגיל / prj_7442d1160ded | 60.034 s | Natural close framing/camera movement already in first 3 s; looks at board and gestures later. | NO_OP early; a later board view is only a candidate after semantic/timeline validation. |
| מי-אמר-שמאוחר-מידיי / prj_e4208e603fa1 | 31.172 s | Medium gym talking head, hand movement; no demonstrated payoff in inspected later frames. | SMART_PUNCH_IN candidate or NO_OP. Do not fabricate older-member proof from its conversion topic. |
| גאה-בצוות / prj_29060bc9516e | 59.100 s | Solo desk/laptop conversation; turns toward camera, leans forward and back. | NO_OP or mild crop only if full gesture path is safe. Community topic is not community footage. |
| טיפ-אחד-HSPU / prj_2bb927f2efec | 49.446 s | Hanging/swinging legs at 0–.8; speaker by wall from1.5; actual inverted wall demo later (~17 s). | NO_OP baseline. Strong motion already exists; later HSPU preview requires exact promise match. |
| איך-הכרנו-הראל-ואוריה / prj_f07f86f80ea7 | 60.107 s | Woman moving around bench, man enters by3, both present by5; conversation follows. | NO_OP; preserve interaction and both people. |
| מאסל-מן-רוטטור-קאף / prj_2e9c043d6831 | 46.700 s | Rack occlusion, suit, real camera/framing changes and movement. | NO_OP; fixed-intro/illustration stress fixture. Printed faces on a suit must not become tracking targets. |

Some existing `words_final.json` timestamps may belong to a different edit generation than the inspected tight file. They were used for tentative topic context, not claimed as verified frame-level semantic labels. The engine must refuse to bind a plan until transcript/media provenance agrees.

Motion was sampled locally; neither high motion nor scene score proves interest. Camera motion, blur and a swinging leg can dominate a score. A payoff requires a semantic judgment tied to a quoted promise and visible evidence. Existing director/vision results should be reused if their digests match; no unconditional vision request is justified.

## Operational audit summary

The live skill is v9.21, while recent code carries v9.22 fixes. The pasted project guidance is v9.13; PIPELINE has older headings and counts. `gate_registry --audit` actually reports **137 gates, zero failures**; lesson audit reports **60 lessons /156 enforcers, zero problems**. Those are inventory checks, not proof that the system or proposed engine passes all tests.

The full flow, source anchors, conflicts, schemas and rollout are in the companion architecture and implementation plan. Crucial findings: render v2 rebuilds from INPUT/EDL rather than consuming an edited EXPORT; B-roll v1 has explicit `--base EXPORT` calls; full intros are attached late; G8 currently scans only 1.2 seconds and is warning-only; review preferences whitelist only music/B-roll; immutable artifact sidecars currently omit visual-hook data. These are the integration risks the proposal addresses.
