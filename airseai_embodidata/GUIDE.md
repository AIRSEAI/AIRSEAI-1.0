# EmbodiData Hand-Trajectory Annotation: Complete Guide

**From head-mounted iPhone recordings to metric, world-frame 3D hand
trajectories — and from those to individualized skill learning.**

This guide covers the problem formulation, the pipeline design and the math
behind each stage, the core challenges and how the code addresses them, the
evaluation plan and baselines for an ICRA submission, and the path from
trajectories to individualized data collection and skill learning.

---

## 1. Problem formulation: why "reverse SLAM" is the right name

In SLAM, a camera moves through a **static** world and you solve for the
camera trajectory from observations of static structure. Your problem
inverts the roles: the interesting object (the hand) **moves**, and it is
observed from a sensor rig that is itself moving (the head). What you want
is the hand's trajectory in a fixed world frame, with the head's motion
removed.

The key insight that makes this tractable is that the problem **factorizes**
through the camera:

```
T_world_hand(t)  =  T_world_cam(t)  ·  T_cam_hand(t)
─────────────────   ────────────────   ─────────────────
what you want       ego-motion          per-frame monocular
(the annotation)    (forward SLAM)      hand pose estimation
```

Both factors are independently solvable, and on EmbodiData the first factor
is essentially **free**: the app already records ARKit's 6-DoF camera pose,
which is metric, gravity-aligned, and produced by a tightly-coupled
visual-inertial odometry system running with factory calibration at 60 Hz.
This is a real, defensible advantage over glasses-only pipelines that must
run SLAM in post (HaWoR, Dyn-HaMR) and inherit its failure modes and scale
ambiguity.

The second factor — metric hand pose from a single RGB frame — is where the
scientific difficulty lives, because monocular hand depth is only observable
through apparent size. That is exactly where the **personalization** feature
does double duty (section 5).

So the two steps you outlined map to:

1. **Recognize and trace hand movements** → per-frame detection + 2D/3D
   keypoints + left/right identity over time (stages 3, 6).
2. **Estimate hand trajectory via reverse SLAM** → metric lift to the camera
   frame, composition with ego-motion into the world frame, then physics-
   based smoothing (stages 4, 5, 6).

### Coordinate conventions (bugs live here — pin them down once)

| Frame | Convention | Used by |
|---|---|---|
| ARKit camera | +x right, +y up, +z **backward** (looks along −z) | pose.csv |
| OpenCV camera | +x right, +y down, +z **forward** | PnP, keypoints |
| ARKit world | +y up (gravity-aligned), metric | pose.csv |
| Output world | `arkit_yup` (default) or `zup` (robotics) | exports |
| Hand-rooted | backend's hand frame, camera-aligned axes | `kps_local` |

Conversion `R_arkitcam→cvcam = diag(1, −1, −1)` is applied once, in
`egomotion.py`, and nowhere else. Portrait-vs-landscape capture is handled by
`camera.video_rotation` (rotates intrinsics and composes an in-plane camera
rotation). **Every convention decision is verifiable in one place: the
overlay video** (section 6.7).

---

## 2. Architecture

```
episode folder (EmbodiData-EgoVIM release layout)
 video.mp4    imu.csv    pose.csv    calibration/   [frames.csv] [depth/]
    │            │           │             │
    ▼            ▼           ▼             ▼
┌─────────────────────────────────────────────────────────┐
│ 1 INGEST   robust CSV parsing, intrinsics, timestamps   │ ingest.py
├─────────────────────────────────────────────────────────┤
│ 2 SYNC     pose↔IMU consistency; video↔gyro anchoring;  │ sync.py
│            3-s stationary protocol checks               │
├─────────────────────────────────────────────────────────┤
│ 3 DETECT   per-frame 2D hands + local 3D shape          │ detect2d.py
│            MediaPipe (CPU default) / HaMeR (GPU hook)   │  (cached)
├─────────────────────────────────────────────────────────┤
│ 4 LIFT     metric T_cam_hand: personalized-scale PnP    │ lift3d.py
│            (+ optional LiDAR depth refinement)          │
├─────────────────────────────────────────────────────────┤
│ 5 COMPOSE  T_world_hand = T_world_cam · T_cam_hand      │ pipeline.py
│            (ego-motion from ARKit, SLERP-interpolated)  │ egomotion.py
├─────────────────────────────────────────────────────────┤
│ 6 TRACK    L/R association, χ² outlier gating,          │ tracking.py
│            const-velocity Kalman + RTS smoother,        │
│            gap filling, orientation SLERP, One-Euro     │
├─────────────────────────────────────────────────────────┤
│ 7 EXPORT   hands.csv / hands.npz / hand_annotation.json │ export.py
│    + QA    overlay.mp4, trajectory.png, PASS/WARN/FAIL  │ qa.py
└─────────────────────────────────────────────────────────┘
```

Outputs (per episode, in `<episode>/hand_annotation/`):

| File | Contents |
|---|---|
| `hands.csv` | one row per valid frame×hand: t, side, source (detected/filled), confidence, reprojection error, wrist world pose (xyz + quaternion), wrist camera-frame position, pinch aperture, κ |
| `hands.npz` | full arrays: 21 world/camera/2D keypoints, validity + provenance masks, per-frame `T_world_cam` |
| `hand_annotation.json` | schema version, user profile, config snapshot, QA report |
| `overlay.mp4` | 2D skeletons + **world-frame wrist trails re-projected into each frame** |
| `trajectory.png` | 3D + top-down plot of head and both wrists |
| `detections.npz` | cached raw detections (delete to force re-detection) |

---

## 3. Data requirements and app-side recommendations

Works out of the box with the v1.2 release layout (`video.mp4`, `imu.csv`
with `timestamp, acc_*, gyro_*`, `pose.csv` with `timestamp, tx..tz,
qx..qw`, `meta.json`, `calibration/`). Column-name variants and ms/µs/ns
timestamps are auto-detected; non-standard exports are handled by mapping,
never by rewriting raw data (consistent with your collection guide's rule).

Strongly recommended app-side additions, in priority order:

1. **Per-frame video timestamps (`frames.csv`)** — removes all timing
   guesswork. ARKit hands you `ARFrame.timestamp` anyway; log it per
   captured frame. Without it the pipeline anchors the video clock by
   correlating optical flow against the gyro, which works but is a fallback.
2. **Per-frame intrinsics** (`ARFrame.camera.intrinsics`) — metric hand
   depth inherits intrinsics error one-for-one.
3. **LiDAR depth on Pro devices** (`ARFrame.sceneDepth`, 256×192) — hands at
   0.2–0.8 m are squarely in range; exporting it upgrades hand depth from
   model-based to *measured* (`lift.depth_dir`). This is the single
   cheapest accuracy upgrade available to you and most competing systems
   cannot match it.
4. Keep recording the **3-s stationary segments** from your protocol — the
   pipeline checks them and uses them as sync/quality anchors.

Capture-protocol additions for hand-centric episodes: mount pitched slightly
down so the manipulation workspace is centered; keep hands inside the frame
during the task (peripheral clipping is the #1 coverage killer); prefer 60
fps + short exposure indoors if the app allows it (motion blur hurts the
keypoint quality more than resolution does).

---

## 4. Installation and first run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # numpy scipy opencv pandas yaml mediapipe

# verify the geometry stack before touching real data (no downloads needed)
python tests/test_synthetic.py
python tests/test_end_to_end.py

# then a real episode
python scripts/run_pipeline.py episodes/E000123 --user-profile profiles/you.json
```

Read the QA line it prints (`[PASS|WARN|FAIL] E000123: L 84% / R 92%
coverage ...`) and **watch `overlay.mp4`** before trusting anything. The
scipy dependency is optional (a pure-numpy rotation fallback is bundled);
MediaPipe is only needed for real detection, not for the tests.

---

## 5. Personalized hand calibration — the "individualized" core

### Why it exists

A monocular hand at distance z with true length L projects to size ∝ L/z.
An estimator assuming average length L̄ therefore mis-estimates depth
multiplicatively:

```
ẑ = z · L̄/L      →      relative depth error ≈ relative hand-size error
```

Adult hand lengths span roughly 16–21 cm (±13%), i.e. up to ~7 cm of
systematic depth bias at 50 cm. The included test quantifies it: a 10%
hand-size error produced a 10.0% depth bias (63 mm at 0.63 m). No amount of
filtering removes a bias — it must be calibrated out. **This turns
"individualized data collection" from a slogan into a measurable mechanism:
one ruler measurement per user makes that user's entire dataset metric.**

### Protocol (2 minutes, once per user)

1. Hand flat on a table, measure **distal wrist crease → middle fingertip**,
   each hand, in meters.

```bash
python -m handtraj.calibrate_user --user weiyu --left 0.181 --right 0.184 \
    --out profiles/weiyu.json
```

2. Validation (recommended): record a 20-s episode with the hand held flat
   at a marked, known distance (tape at 0.40 m), slowly rotating; then

```bash
python -m handtraj.calibrate_user --validate episodes/CAL01 \
    --profile profiles/weiyu.json --known-distance 0.40
```

Residual bias > 5% means the measurement, the intrinsics, or
`video_rotation` is wrong — in that order of likelihood.

### How κ enters the math

Backends output a hand-rooted 3D shape `X_local` scaled for an average hand.
Per frame the pipeline computes the pose-invariant polyline length along
wrist→middle-MCP→…→fingertip (bone lengths don't change with articulation),
sets `κ = L_user / L_model(frame)`, scales the object points, and solves
PnP. Translation — hence depth — scales linearly with object scale, so κ
calibrates depth directly. κ's variance across frames is itself a QA signal
(`kappa_cv` in the report): a jittery κ means the articulation estimates are
unreliable.

---

## 6. Method details, stage by stage

### 6.1 Ingest (`ingest.py`)

Tolerant column matching, timestamp-unit auto-detection, intrinsics from
`calibration/*.json` (with rescaling to the decoded video size and rotation
handling), and a three-tier strategy for per-frame times: `frames.csv` if
present, else 1:1 pose↔frame correspondence when row counts match (ARKit
logs one pose per `ARFrame`), else fps-derived times that stage 2 anchors.

### 6.2 Sync (`sync.py`)

Two distinct jobs. First, a **consistency check** between pose.csv and
imu.csv (same host clock, so recovered offset should be ≈0; if not, the QA
report flags an export bug). Method: normalized cross-correlation between
|gyro| and the angular speed implied by consecutive ARKit rotations —
rotation is observable by both sensors, no targets needed. The synthetic
test injects a 120 ms offset and recovers it to the sample.

Second, when frame times had to be fps-derived, **video↔IMU anchoring**:
sparse Lucas–Kanade optical flow gives per-frame visual angular speed
(median flow ≈ f·ω for a rotating camera), which is scanned against |gyro|
for the start time t₀ maximizing correlation.

Finally the protocol's stationary windows are verified via gyro RMS.

### 6.3 Detection (`detect2d.py`)

A thin `HandObs` interface (side, 21×2 pixels, 21×3 hand-rooted metric-ish
shape, confidence) with two backends:

* **MediaPipe Hands** (default): CPU, pip-installable, real-time. Two
  correctness traps are handled: handedness labels assume a mirrored selfie
  image (rear camera → labels flipped), and `world_landmarks` are scaled for
  an average hand (κ fixes this).
* **HaMeR / WiLoR hook**: transformer-based MANO mesh recovery,
  state-of-the-art on egocentric views and occlusion, needs a GPU. The class
  docstring contains the integration recipe: detector → crops → MANO joints
  → remap → wrist-rooted `kps_local`. Everything downstream is unchanged.
  For the paper this gives you the backend ablation row almost for free, and
  per-user MANO shape (β) is the natural upgrade of the single-length
  profile.

Detections are cached (`detections.npz`) so the expensive stage runs once
per episode regardless of how many times you re-tune the geometry stages.

### 6.4 Metric lift (`lift3d.py`)

Per detection: scale `kps_local` by κ, `solvePnP` (SQPnP for cold start +
LM refinement, iterative with warm start from the previous frame after
that), gate on mean reprojection error (default 10 px) and plausible depth
(0.12–1.5 m). Output is a full 6-DoF `T_cam_hand`, all 21 camera-frame
keypoints, and the **pinch aperture** (thumb-tip↔index-tip distance) — a
UMI-style gripper signal for later policy learning.

If per-frame depth maps exist (LiDAR), the translation is rescaled by the
median measured/predicted depth ratio at the quasi-rigid palm landmarks —
first-order correct because hand extent ≪ hand distance.

### 6.5 Ego-motion (`egomotion.py`)

ARKit poses → OpenCV camera convention → optional z-up world → continuous
time via SLERP + linear interpolation, queried at each frame's timestamp.
Head position at any time is also exported (head-relative hand trajectories
matter for skill learning).

### 6.6 Composition + tracking (`pipeline.py`, `tracking.py`)

Composition is one matrix product per frame — the point of the whole design
is that all difficulty was pushed into the two factors.

The temporal layer then enforces physics **in the world frame** (filtering
in the camera frame would alias head motion into hand velocity):

* **Association**: handedness score first; duplicate labels resolved toward
  the empty side; a swap test against each track's recent 2D wrist position
  (with 40 px hysteresis) undoes flagrant L/R flips; flips are counted for QA.
* **Gating**: χ²(3) Mahalanobis test (99.9%) rejects teleporting
  measurements (typically mis-associations or PnP failures that passed the
  reprojection gate).
* **Constant-velocity Kalman filter** per hand (σ_accel = 8 m/s² default —
  hands are fast), followed by an offline **RTS smoother**: post-processing
  buys the non-causal smoother for free, roughly halving lag-induced error
  vs. a causal filter.
* **Gap policy**: gaps ≤ 10 frames are bridged by the smoother and labeled
  `filled` (provenance is exported — consumers can always exclude them);
  longer absences re-initialize the filter (stale velocity is worse than no
  prior); gaps touching episode boundaries are never filled.
* **Orientation**: quaternion hemisphere fixing + SLERP; **keypoints**:
  One-Euro filter (adaptive low-pass, minimal lag).

### 6.7 The overlay as built-in verification

`overlay.mp4` re-projects the *smoothed world-frame* wrist trail into every
frame through that frame's camera pose. If any link is wrong — conventions,
sync, intrinsics, lift — the trail visibly swims against the scene when the
head moves. If it stays pinned to where the hand actually went, the whole
chain `detection → lift → ego-pose → composition` is consistent. Use it as
the first check on every new capture configuration.

---

## 7. Core challenges and how the code addresses them

1. **Monocular scale ambiguity** (the fundamental one). Hand depth is only
   observable through apparent size. → Personalized hand length κ
   (section 5) converts a per-user systematic bias into a calibrated
   constant; optional LiDAR depth makes depth measured rather than inferred;
   `kappa_cv` exposes residual instability. *(lift3d.py, calibrate_user.py)*

2. **Ego-motion/hand-motion entanglement.** Raw camera-frame trajectories
   mix head and hand motion inseparably; naive differencing double-counts
   rotation. → Factorized reverse-SLAM composition with ARKit VIO as the
   ego factor; filtering only after moving to the world frame.
   *(egomotion.py, pipeline.py)*

3. **Coordinate-convention traps.** ARKit (y-up, −z forward) vs OpenCV
   (y-down, +z forward) vs portrait/landscape rotation; quaternion sign
   flips. → All conversions in one module, hemisphere-continuity fixes,
   SLERP everywhere, and the overlay re-projection as an end-to-end visual
   proof. The synthetic tests would fail loudly on any convention error.
   *(egomotion.py, se3.py, tests/)*

4. **Time synchronization.** A 10 ms error at a 1 m/s hand sweep is 1 cm of
   phantom error; fps-derived frame times can be off by much more. →
   Host-clock consistency check (gyro↔pose-rate correlation), optical-flow↔
   gyro anchoring of the video clock when needed, stationary-segment
   verification, and QA warnings whenever timing is inferred rather than
   logged. *(sync.py)*

5. **Occlusion, blur, hands leaving FOV.** Egocentric manipulation
   guarantees intermittent observation. → Confidence + reprojection + depth
   gates keep bad fits out; the KF+RTS bridge labels short gaps `filled`
   (provenance preserved); long gaps re-initialize rather than hallucinate;
   coverage and max-gap statistics land in the QA report. *(tracking.py, qa.py)*

6. **Left/right identity switches.** MediaPipe handedness flips under
   crossing/blur, and its label convention assumes mirrored input. →
   Label flip for rear camera, duplicate-label resolution, position-based
   swap test with hysteresis, flip counting. *(detect2d.py, tracking.py)*

7. **Per-frame jitter vs. real dynamics.** Smoothing too hard destroys the
   fast strokes that make skill data valuable. → χ² gating separates
   outliers from dynamics; process noise tuned for hands (σ_accel
   configurable per task family); RTS instead of causal smoothing; One-Euro
   (velocity-adaptive) for keypoints; smoothness reported as jerk RMS, not
   silently enforced. *(tracking.py)*

8. **Intrinsics and rolling shutter.** Depth error tracks focal-length
   error; fast head yaw skews rows. → Per-episode intrinsics ingestion with
   rescaling/rotation; reprojection-error QA flags bad intrinsics; RS left
   as a documented limitation (short exposure + 60 fps mitigates; ARKit's
   own poses are RS-aware internally). *(ingest.py, qa.py)*

9. **Long-session drift.** ARKit relocalizes, but minutes-long episodes can
   drift centimeters. → Episodes are short by protocol; the eval tool
   reports RPE separately from ATE so drift is measured, not hidden; an
   ArUco board world anchor is the documented extension for multi-episode
   shared frames. *(eval_gt.py; section 11)*

10. **Trust and auditability at dataset scale.** 560 episodes will not be
    watched individually. → Every episode emits a machine-readable QA
    report with PASS/WARN/FAIL verdict (coverage, reprojection, κ stability,
    sync, protocol checks, flips), aggregated into
    `hand_annotation_summary.json` by the batch runner — mirroring the
    release-gating philosophy of your collection guide. *(qa.py)*

---

## 8. Verification and ground-truth evaluation

### Included synthetic verification (runs anywhere, no data)

* `tests/test_synthetic.py` — SE(3) interpolation, Umeyama, sync-offset
  recovery (120 ms injected → recovered exactly, corr 0.95), and the
  reverse-SLAM loop: known hand + head trajectories, projected with 0.7 px
  noise and 12 dropped frames → **wrist RMSE 0.83 mm, p95 1.26 mm** —
  i.e., the geometry/composition/filtering stack contributes ~1 mm; real
  error will be dominated by the neural detector and calibration quality.
* `tests/test_end_to_end.py` — the same scene written to disk as a real
  episode (video + CSVs + calibration) and run through `run_episode`:
  all outputs produced, QA PASS, **0.90 mm** raw world-frame RMSE.

### Real ground truth, in increasing order of effort

1. **ArUco/ChArUco wrist rig** (~$5): a printed cube on a wrist strap;
   detect with OpenCV from a fixed external camera (or the head camera
   itself for camera-frame checks); compare with `eval_gt.py`. Accuracy
   ~2–5 mm — good enough to expose centimeter-level pipeline errors.
2. **OptiTrack/Vicon** wrist markers: the reviewer-grade standard; report
   ATE RMSE/median/p95 and RPE@1s from `eval_gt.py` (it handles time
   alignment and rigid/sim(3) alignment; comparing the two isolates
   scale errors from shape errors).
3. **Public egocentric GT** for the components: HOT3D and AssemblyHands
   (multi-view/mocap hand GT from head-mounted rigs) let you benchmark the
   lift stage against published numbers without your own mocap; ARCTIC for
   hand-object sequences.

---

## 9. ICRA evaluation plan: baselines that convince reviewers

Positioning (per your choice): **the system is the contribution** — a
$25-mount + iPhone that produces metric world-frame hand trajectories with
per-user calibration, validated against ground truth and useful downstream.
Reviewers will ask three questions; each gets its own baseline family.

### Q1 — "Is it accurate?" → method baselines on the same videos

| Baseline | What it represents | Expected story |
|---|---|---|
| **HaWoR** (CVPR 2025, [arXiv:2501.02973](https://arxiv.org/abs/2501.02973), [code](https://github.com/ThunderVVV/HaWoR)) | SOTA world-space hand motion from egocentric RGB, SLAM-in-post | You match/beat world-frame accuracy **without** per-video SLAM, because ARKit VIO + IMU gives metric scale and robustness; HaWoR inherits monocular-SLAM scale ambiguity |
| **Dyn-HaMR** (CVPR 2025) | Same task, optimization-based, dynamic cameras | Same argument; also L/R robustness comparison |
| **HaMeR / WiLoR + your ego-motion** | Backend ablation (plug into the hook) | Quantifies what the GPU backend buys over MediaPipe *within your system* |
| **MediaPipe + naive depth** (average hand, no personalization) | The "just use MediaPipe" reviewer reflex | Personalization cuts depth bias by the hand-size deviation (~5–13% of depth); your ablation table makes this explicit |
| **No-IMU variant**: your pipeline with COLMAP/DROID-SLAM ego-motion, no ARKit | Isolates the value of the VIO/IMU | Scale drift + failures on low-texture home scenes |

Metrics: wrist ATE RMSE/median/p95 (cm), RPE@1s (drift), rotation geodesic
error (deg), MPJPE/PA-MPJPE (mm) where joint GT exists, coverage %, ID
switches per minute, and — uniquely available to you — κ stability.

### Q2 — "Why this hardware?" → system baselines

| System | Class | Compare on |
|---|---|---|
| **Apple Vision Pro** hand tracking (as used by Apple's EgoDex, [arXiv:2505.11709](https://arxiv.org/pdf/2505.11709)) | commercial headset, on-device hand pose | accuracy vs. **cost ($3500 vs ~$1000 phone people already own)**, comfort, deployability |
| **Project Aria + MPS + HaMeR** (EgoMimic-style) | research glasses | accuracy, availability (research-only hardware), IMU/pose quality |
| **UMI** (handheld gripper, RSS 2024) | gripper-mounted camera | data *type* (hand vs gripper), naturalness, per-demo throughput |
| **DexCap / ARCap** | portable mocap rigs | setup time, intrusiveness (gloves/rig vs bare hands), cost |
| **Quest 3 hand tracking** | consumer VR | accuracy, FOV constraints, ergonomics for real chores |

The honest framing: you will not beat Vision Pro on raw hand-pose accuracy;
you win on **cost, ubiquity, naturalness (bare hands, real homes), and
per-user metric calibration**. Reviewers respect a Pareto argument with
measurements more than a claimed sweep.

### Q3 — "Is the data useful?" → downstream validation

1. **Dataset-level**: add hand-trajectory annotations to EmbodiData-EgoVIM
   and extend your existing modality ablation (RGB / +IMU / +pose /
   **+hand-trajectory**) on task recognition, sub-task segmentation, and
   retrieval — hand trajectories should visibly help manipulation-heavy
   classes (C3–C11). This slots directly into the baseline section of your
   v1.2 guide.
2. **Skill-level** (ties to the OpenArm demo): parameterize skill cards with
   measured trajectories — e.g., the `wipe(table_area)` primitive replays
   the *demonstrated* wipe extent/direction/speed instead of a scripted
   rectangle; report execution success vs scripted baseline.
3. **Policy-level** (stretch, big payoff): retarget wrist pose + pinch
   aperture to a parallel gripper (UMI-style), train Diffusion Policy/ACT
   via the LeRobot export on a tabletop task, and compare against
   teleop-only data on demos-per-hour and success rate. EgoMimic and
   EgoDex give you the citation scaffolding that human egocentric data
   transfers.

Practical notes: ICRA 2027 is in Seoul with the deadline expected
~**Sep 15, 2026** (per the historical pattern; confirm at
[2027.ieee-icra.org](https://2027.ieee-icra.org/)). That's ~10 weeks: Q1
ablations + one GT rig + the dataset-level Q3 experiment are realistic; the
policy experiment is the first thing to cut. Also scan recent entries like
EgoGrasp (2026) in your related-work pass — this space moves monthly.

---

## 10. Individualized data collection and skill learning

The pipeline is deliberately shaped so that "one person + one phone" yields
personally-metric skill data:

**Per-user profiles.** `profiles/<user>.json` (hand lengths; MANO β with the
HaMeR backend later). Every episode processed with the profile is metric
*for that user* — cross-user aggregation then normalizes by hand size
explicitly instead of inheriting unknown biases.

**What a demonstration becomes.** Per hand per frame: wrist pose in a
gravity-aligned world frame, 21 keypoints, pinch aperture, head pose, and
head-relative hand pose. That is sufficient statistics for:

* **Task-frame skill libraries** — express trajectories relative to a task
  anchor (first-contact point, or an ArUco-anchored workspace); segment
  demos at low-velocity + pinch-change events; fit DMPs/ProMPs or keep raw
  trajectories per (user, task) as a skill memory that grows with use.
* **Policy learning** — `export.to_lerobot_arrays()` emits
  `observation.ee_pos/ee_quat/gripper` streams; retarget wrist→gripper with
  a fixed offset and pinch→width scaling; train ACT/Diffusion Policy in
  LeRobot (fits your existing OpenArm/LeRobot plan — the skill card selects
  *which* skill, the trajectory data now parameterizes *how*).
* **Skill assessment and coaching** — because different sessions of the same
  user share a metric world frame, you can compare attempts over time: DTW
  distance to the user's best demo, smoothness (jerk RMS is already in QA),
  path efficiency, bimanual coordination (phase lag between hands). This is
  the "individualized skill learning" story: the same pipeline that creates
  robot-training data also measures the human's own skill progression.

**Privacy carries over.** Hand trajectories are derived data; the release
gates from your collection guide (privacy review before release, QA scores)
apply unchanged — the QA report is designed to slot into `qc_report.json`.

---

## 11. Limitations and roadmap

* **Fingertip-level accuracy is backend-bound.** MediaPipe articulation is
  ~5–10 mm-class at these distances; the HaMeR hook is the upgrade path.
  Wrist trajectories (the skill-relevant signal) are much more robust.
* **Rolling shutter** is unmodeled; fast head yaw adds mm-level distortion.
  Mitigate with 60 fps/short exposure; model row-time if it ever dominates.
* **Single-length personalization** captures scale, not shape. MANO β
  fitting from a few calibration photos is the natural v2.
* **Hand-object occlusion**: gap filling bridges, but heavy tool occlusion
  degrades pose quality; object-aware backends (or EgoGrasp-style
  hand-object joint estimation) are the research extension.
* **World frame is per-episode.** For multi-episode spatial consistency, add
  a printed ChArUco board to the workspace and anchor `T_world_board` once
  per episode (one PnP call — the hook belongs in `egomotion.py`).
* **HaMeR/WiLoR integration** is a documented hook, not yet wired — it needs
  a GPU environment and checkpoints.

---

## 12. Code map

| File | Role | Key entry points |
|---|---|---|
| `handtraj/se3.py` | SE(3)/quaternion math, interpolation, Umeyama/ATE | `PoseInterpolator`, `umeyama` |
| `handtraj/_rot.py` | scipy Rotation/Slerp or pure-numpy fallback | — |
| `handtraj/config.py` | dataclass config + YAML overrides + user profiles | `PipelineCfg.load` |
| `handtraj/ingest.py` | episode IO, intrinsics, frame timestamps | `load_episode` |
| `handtraj/sync.py` | clock checks, video↔gyro anchoring, stillness | `estimate_offset`, `estimate_video_start` |
| `handtraj/detect2d.py` | detector interface, MediaPipe, HaMeR hook, cache | `make_detector`, `HandObs` |
| `handtraj/lift3d.py` | personalized PnP lift, depth refinement, pinch | `Lifter.lift` |
| `handtraj/egomotion.py` | conventions + continuous-time camera pose | `EgoMotion.T_world_cam` |
| `handtraj/tracking.py` | association, KF+RTS, gaps, One-Euro | `HandTrack`, `associate` |
| `handtraj/pipeline.py` | orchestration, composition | `run_episode` |
| `handtraj/export.py` | csv/npz/json, overlay, plots, LeRobot bridge | `write_outputs`, `to_lerobot_arrays` |
| `handtraj/qa.py` | per-episode QA report | `build_report` |
| `handtraj/eval_gt.py` | ATE/RPE vs GT with time alignment | CLI |
| `handtraj/calibrate_user.py` | profiles + known-distance validation | CLI |
| `scripts/run_pipeline.py` | batch CLI | — |
| `tests/` | synthetic unit + end-to-end verification | — |

---

*References: HaWoR ([arXiv:2501.02973](https://arxiv.org/abs/2501.02973));
Dyn-HaMR (CVPR 2025); HaMeR (CVPR 2024); WiLoR (2024); EgoDex
([arXiv:2505.11709](https://arxiv.org/pdf/2505.11709)); EgoMimic (2024);
UMI (RSS 2024); DexCap (2024); ARCap (2025); EgoZero (2025); EgoGrasp
(2026); HOT3D; AssemblyHands; ARCTIC; LeRobot
([docs](https://huggingface.co/docs/lerobot)); ICRA 2027
([site](https://2027.ieee-icra.org/)).*
