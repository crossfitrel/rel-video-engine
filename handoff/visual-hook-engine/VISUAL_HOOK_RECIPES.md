# Visual Hook Engine — recipe registry

2026-09-11. Registry specification, not permission to activate every recipe. All timings are proposed experimental envelopes unless explicitly described as a system invariant. No creator-reference sample established a universal ideal frequency or duration.

## Registry contract

Each entry contains `id`, `version`, `status` (`mvp`, `pilot_pending_policy`, `deferred`, `excluded`), `intent`, eligible content and evidence, contraindications, supported renderers, required assets, typed parameter schema, layer reservations, declared-transition behavior, caption/audio contract, fallback list, quality checks and example fixture IDs. Runtime never executes arbitrary filter expressions or HTML returned by a selector.

Common conditions: exact quoted opening and media provenance; unchanged speech/EDL/duration; no generated humans, fake gym footage or unrelated stock; protect real gestures, all relevant people and exercise equipment; use current brand profile; no extra captions or typography. A library entry with `status != mvp` cannot run simply because it scores well.

Default treatment budget: at most one treatment, no accent for MVP. One secondary accent is a future pilot hypothesis and requires independent relevance; never an effect every half-second. NO_OP has no visual asset or render cost.

## 0. NO_OP — להשאיר את הפתיחה

- **Intent:** preserve an effective natural opening or avoid an unsupported intervention.
- **Eligible:** every content type; mandatory candidate in every selection run.
- **Contraindications:** none. It does not waive existing QA defects.
- **Timing:** full identity through 0–10s and beyond.
- **Assets:** existing clean body only; no new derived video.
- **Render:** return original base/legacy v2 segments and cache keys unchanged.
- **Fallback:** terminal safe decision before approval. A render failure after approval is an error, not permission to silently switch here.
- **AI-look risk:** none added.
- **Examples:** HSPU opening swing; the two-person introduction; protected sofa entrance; fixed-format intro. Reason codes distinguish `already_effective`, `intentional_entrance`, `fixed_intro_present`, `unsafe_crop`, `semantic_unknown`, `policy_disallowed`.
- **Acceptance:** off and selected NO_OP do not change legacy media commands, audio, captions, source selection or segment keys. Report whether shadow or applied=false.

## 1. PAYOFF_PREVIEW — הצצה להדגמה

- **Status:** `pilot_pending_policy`; disabled in MVP.
- **Intent:** make a spoken promise concrete using a later real moment that genuinely demonstrates it.
- **Eligible:** value/demo and sometimes conversion, only with a verified promise→visible-proof relationship. Same-project footage preferred. A trainer demonstrating technique is not automatically member social proof.
- **Contraindications:** withheld context makes the picture misleading; result implies guaranteed transformation; preview reveals the entire joke; unverified identity; source shot cropped/blurred/occluded; existing natural opening or full intro already does the job; protected B-roll/illustration reservation conflict.
- **Timing:** audition a short silent insert within the opening, for example18–36 frames (0.6–1.2s) at a meaningful word, then return to the uninterrupted speaker picture. These are candidate pilot values, not a hard duration rule or a requirement to start before0.8s. End before overlapping ordinary B-roll. One insert only.
- **Assets:** source media checksum, source frame range, output frame range, matched quoted words, visible evidence and crop-safe subject region. A title/tag alone is insufficient.
- **Render:** FFmpeg trimmed picture replacement; original speech and captions continue at original times. v2 compiles into source segments; v1 overlays picture on clean body. Source insert is mute. Never prepend media or add duration.
- **Transitions:** declare entry and exit frames with incoming/outgoing source identities. G8 retains independent glitch checks.
- **Fallback:** independently eligible subtle crop; otherwise NO_OP.
- **AI-look risk:** low for real footage, medium for deceptive context or repeated speed-ramped “hype”. No speed ramps or fake camera effects.
- **Example:** later wall handstand in `טיפ-אחד-HSPU` could support a specific technique promise only after checking the exact opening sentence. The opening hanging swing alone does not prove HSPU relevance.
- **Acceptance:** exact original body frame count/audio; source identities verified; entry/exit clean; semantic evidence reviewed; explicit narrow canon exception recorded before enabling.

## 2. SMART_PUNCH_IN — הדגשה עדינה

- **Status:** `mvp`, enabled only in pilot/approved cohorts; old projects default off.
- **Intent:** emphasize a meaningful spoken beat without changing scene or competing with the person.
- **Eligible:** static or gently moving talking head; known subject/gesture bounds; enough resolution; no competing early camera push. Content type alone does not qualify it.
- **Contraindications:** head near edge, hands/bar path outside safe crop, multiple untracked people, printed-face false positive, existing camera zoom, strong physical motion, low-quality source, fixed intro, captions baked into source without verified layout.
- **Timing:** one smooth emphasis anchored to words in roughly1–5s, finish by the relevant reservation boundary and within10s. Pilot envelope1.00→1.04–1.08→1.00 is a proposal to compare, not a measured safe maximum. Do not oscillate every sentence. An immediate reframe at frame0 is a separate candidate requiring first-frame review.
- **Assets:** clean source, word IDs, region trajectory/protected bounds, native resolution and existing crop context.
- **Render:** deterministic FFmpeg crop/scale; normalized rect keyframes with smoothstep interpolation; same compiler used by v1/v2; return exactly to identity at cue exit. Captions render afterward and do not enlarge.
- **Fallback:** smaller independently safe envelope or NO_OP. Unknown subject boundary does not authorize a center crop.
- **AI-look risk:** low; rises with robotic tracking, aggressive scale, softness, face clipping or unmotivated bounce.
- **Example:** `מי-אמר-שמאוחר-מידיי` medium talking head may support subtle emphasis; `על-הלוח-כוח-וגיל` already pushes closer and is a likely NO_OP.
- **Acceptance:** protected bounds contained at every output frame, smooth entry/exit, exact frames/audio, no change to caption glyph size/timing, controlled outside-window comparison. Harel's preference determines aesthetic envelope.

## 3. FREEZE_CALLOUT — עצירה על פרט

- **Status:** `deferred`.
- **Intent:** briefly inspect a visible detail that motion makes hard to understand.
- **Eligible:** a silent demonstration picture or object detail; spoken explanation continues naturally over it.
- **Contraindications:** freeze on a talking mouth, emotional conversation, unstable/blurred frame, artificial suspense, extra graphic text forbidden by canon.
- **Timing:** pilot only, perhaps6–12 frames within a meaningful demo beat, not mandatory first-second stutter. Duration-preserving replacement, not appended time.
- **Assets:** a sharp real frame, semantic detail region and original picture continuity.
- **Render:** FFmpeg frame hold; optional primitive only after a separate illustration/canon decision. Future hold explicitly declared so duplicate-frame QA understands it.
- **Fallback:** ordinary source shot, optional safe crop, NO_OP.
- **AI-look risk:** medium; a frozen person mid-speech looks broken.
- **Example:** a clear hand-position frame in a technique demonstration, not Harel explaining at a desk.
- **Acceptance:** exact hold count and original audio; no accidental extra holds; independent flash tests remain active. Not included in first implementation.

## 4. SUBJECT_POP — הפרדת אדם מהרקע

- **Status:** `excluded` from initial roadmap; reconsider only for a specific approved need.
- **Intent:** separate a subject from a genuinely useful explanatory layer.
- **Eligible:** rare, clean stable subject silhouette and a justified existing graphic; not ordinary gym talking heads.
- **Contraindications:** bars/racks crossing limbs, moving hair, fingers, multiple people, printed costume faces, no semantic need for depth, implied generated body/background.
- **Timing:** a short self-contained composition, no automatic opening trigger.
- **Assets:** real source, temporally consistent mask, approved graphic, verified occlusion order. No fake background completion.
- **Render:** optional HyperFrames authored template or FFmpeg alpha composition only after a separate segmentation quality spike. Upstream background removal requires additional model/native runtime; not justified for MVP.
- **Fallback:** flat approved overlay if safe, plain footage or NO_OP.
- **AI-look risk:** high: halos, missing hands and mask flicker.
- **Example:** not appropriate for `מאסל-מן-רוטטור-קאף` rack/suit shot.
- **Acceptance:** frame-by-frame silhouette audit and no hidden dependency downloads; not a current release deliverable.

## 5. SPLIT_OR_PIP — דובר והדגמה יחד

- **Status:** `deferred`, possible phase2 after payoff-preview evidence.
- **Intent:** preserve the person's explanation while showing the exact demonstrated movement or board detail.
- **Eligible:** professional/value content where both simultaneous views aid comprehension.
- **Contraindications:** exercise becomes too small, obscured face/hands, captions leave no room, two speakers already fill frame, second view is redundant, general conversion montage without specific evidence.
- **Timing:** proposed2–4s at a quoted reference, ending before ordinary layer reservations. No permanent split-screen default.
- **Assets:** two verified existing source intervals, safe rectangles and a fixed layout. Source audio remains off on added view.
- **Render:** FFmpeg scale/crop/overlay for simple composition; HyperFrames unnecessary. Only designed non-rectangular composition might justify a later template.
- **Fallback:** single-view payoff preview if permitted, then original footage.
- **AI-look risk:** low to medium; generic floating cards or busy borders look templated.
- **Example:** board detail plus speaker in `על-הלוח-כוח-וגיל`, after validating readable phone-size board and full subject/caption bounds.
- **Acceptance:** readable content at actual mobile size, no collision, time identity, no extra captions or audio.

## 6. BEFORE_AFTER — השוואה אמיתית

- **Status:** `deferred`; never automatic from topical similarity.
- **Intent:** show two comparable observed states, such as two demonstrated movement positions.
- **Eligible:** verified same exercise/object/context, with a truthful relationship that the narration actually explains.
- **Contraindications:** unrelated members, bodies or dates presented as transformation; differing angles create false difference; missing consent/provenance; medical or performance outcome invented by visual juxtaposition.
- **Timing:** one readable comparison at the relevant spoken phrase; no fixed universal cadence.
- **Assets:** verified pair, comparison reason, source intervals, any text permission. If labels are essential but not permitted, recipe is ineligible.
- **Render:** FFmpeg side-by-side or sequential comparison; source mute; captions unchanged.
- **Fallback:** show one real demonstration or NO_OP.
- **AI-look risk:** low synthetic risk, high misleading-story risk.
- **Example:** existing two technique positions, not an invented member “before and after” for the40+ conversion script.
- **Acceptance:** human verifies comparability and claim; no inferred chronology; no duration/audio changes.

## 7. PROGRESS_VISUAL — מספר שמסביר

- **Status:** `deferred`; graphic text exception needed where applicable.
- **Intent:** make an actual step, amount or countdown easier to follow.
- **Eligible:** an explicit spoken and verified number/sequence with educational value.
- **Contraindications:** fake countdown/urgency, unexplained number, competing subtitle, stats sourced only from memory, progress unrelated to what is visible.
- **Timing:** appear when the number is said and remain only long enough to understand; pilot readability study needed, not an arbitrary firstsecond event.
- **Assets:** exact transcript number/units and verified evidence; approved brand typography/layout if text is authorized.
- **Render:** existing PIL for a static number; optional local GSAP template only for a useful changing quantity. Do not use HyperFrames merely to draw one numeral.
- **Fallback:** rely on real bar/board and original captions; NO_OP.
- **AI-look risk:** medium if gamified, neon, or generic circular timer.
- **Example:** Danny reference demonstrates a real load embodying a numerical idea; R.E.L should prefer actual footage over an extra counter.
- **Acceptance:** numeric truth, Hebrew/RTL and units correct, no new marketing promise, no caption collision.

## 8. TRACKED_HIGHLIGHT — סימון פרט בתנועה

- **Status:** `deferred`.
- **Intent:** direct attention to a specific moving object, such as hand position, that the sentence explicitly identifies.
- **Eligible:** verified object region with stable local track; professional demonstration.
- **Contraindications:** uncertain object identity, occlusion, fast blur, false anatomical precision, medical diagram misstatement, arrow covering exercise execution.
- **Timing:** only while the referenced object is reliably visible. Remove immediately on track loss; no extrapolated arrow floating in space.
- **Assets:** reviewed initial object box/path, temporal track with uncertainty, quoted reference and approved minimal marker.
- **Render:** OpenCV local tracking plus FFmpeg/PIL primitive, deterministic saved path. No model per frame. No new tracker package by default; verify current build capability first.
- **Fallback:** static reviewed highlight on a stable frame if independently allowed; else no highlight.
- **AI-look risk:** medium from jitter and tracking drift.
- **Example:** specific hand placement in HSPU, not generic circle around the speaker's face.
- **Acceptance:** target containment and no wrong-target frames; authored track loss behavior; brand contrast; existing illustration permissions.

## 9. KINETIC_KEYWORD — מילה נעה

- **Status:** `excluded` as a separate opening layer.
- **Intent:** verbal emphasis; existing one-word captions already perform much of this role.
- **Eligible:** none in initial engine; only a future explicit typography-policy change could enable it.
- **Contraindications:** default R.E.L canon prohibits graphic text and moving subtitle styles; obscures face and duplicates content.
- **Timing:** not applicable while disabled; do not smuggle words into an “accent”.
- **Assets:** would require exact spoken words and approved layout/font; no hallucinated headline.
- **Render:** do not implement; existing captions own spoken words.
- **Fallback:** ordinary static Assistant ExtraBold captions, subtle picture crop or NO_OP.
- **AI-look risk:** high when paired with stock templates, oversized text or word-by-word bouncing.
- **Example:** the magenta Ananas emphasis is useful reference evidence but not a transferable R.E.L treatment.
- **Acceptance:** registry denial tested; selector cannot activate via score or user-supplied arbitrary params.

## 10. MICRO_MOTION_GRAPHIC — המחשה קצרה

- **Status:** `deferred` to existing illustration governance; no opening exemption.
- **Intent:** explain a relationship that real footage cannot show, e.g. a verified mechanism.
- **Eligible:** professional/value content with a specific explanatory statement, approved diagram assets and current illustration eligibility.
- **Contraindications:** merely decorative shapes, fabricated scientific anatomy, conversion filler, graphic labels that violate text policy, missing room, hook/CTA windows excluded by IL4.
- **Timing:** ordinary approved illustration window by default. A visual-hook window would require separate canon approval, not a renamed IL4 bypass.
- **Assets:** exact semantic entity→region mapping, vetted diagram, local fonts/JS and source ledger.
- **Render:** reuse existing illustration tools for simple cards. Optional pinned HyperFrames CLI behind own template contract for genuinely complex motion; emit silent alpha asset and composite through R.E.L.
- **Fallback:** static existing approved diagram if allowed, then plain footage.
- **AI-look risk:** medium to high if generic3D/glow, low when restrained and scientifically accurate.
- **Example:** rotator-cuff explanation belongs to the existing illustration path; suit/rack footage makes placement and face detection especially important.
- **Acceptance:** IL gates remain active, scientific labels verified, all assets offline-ready, exact frames, no double captions or body rerender ownership.

## Prioritization

Ship the ability to say “leave it” and one reliable crop before adding composition families. Evaluate same-footage payoff preview next because it can add actual visual information with no synthetic media. PIP can follow when dual views are demonstrably useful. The remaining families are registry design space, not an implementation checklist for the first release.
