# AIRSEAI EmbodiData Post-Processing Toolkit

> **Path in AIRSEAI:** `AIRSEAI-1.0/airseai_embodidata/`
>
> **Purpose:** Convert exported EmbodiData iPhone sessions into reproducible, quality-aware hand annotations and machine-readable records for embodied-AI research.

## 1. What this project is

`airseai_embodidata` is the post-processing toolkit for **EmbodiData**, an iPhone-based egocentric data-capture workflow for everyday human manipulation. The iPhone application is used to record the human demonstration; this repository starts **after the session has been exported from the phone**.

The toolkit solves a practical gap between raw first-person recordings and datasets that can be inspected, filtered, modelled, and reused in embodied-AI pipelines. A raw egocentric video is visually useful, but by itself it does not provide frame-indexed hand landmarks, approximate camera-relative hand geometry, validity masks, training-quality metadata, or reproducible quality-control records. This package creates those derived products while preserving the raw session as the source of truth.

The current public baseline is deliberately conservative. It does **not** fabricate camera motion that was never recorded, and it does **not** present monocular hand estimates as physical ground truth. For current EmbodiData sessions without a six-degree-of-freedom camera-pose stream, the supported release mode is **camera-relative**.

## 2. Where the data comes from

### 2.1 Capture on an iPhone

A participant wears a head-mounted iPhone in an egocentric configuration and performs an everyday manipulation task using the EmbodiData capture application. A session can contain:

- encoded first-person video;
- camera callback timing records;
- Apple Core Motion inertial measurements;
- structured temporal annotations produced by the EmbodiData workflow;
- a session manifest and validation metadata.

The complete iOS application is **not** part of this post-processing repository.

**EmbodiData app access:** **[TODO: add the official App Store, TestFlight, enterprise-distribution, or project download link used by AIRSEAI.]**

After recording, export or download the session directory from the iPhone to a workstation. A typical current session has the following layout:

```text
SYYYYMMDD_HHMMSS/
├── raw/
│   ├── session_video.mov
│   ├── frame_timestamps.jsonl
│   └── motion_samples.jsonl
├── export/
│   └── annotations.jsonl          # optional but recommended
├── manifest.json                  # recommended
└── validation_report.json         # optional
```

The post-processing software reads this layout directly. No intermediate CSV conversion is required.

### 2.2 Why the encoded video timeline matters

The camera callback stream and the final encoded movie are produced through different paths. They should not be assumed to contain exactly the same number of records. The loader therefore prefers the presentation timestamps of the **actual encoded frames**, extracted with `ffprobe`, whenever a complete frame-time sequence is available.

The selection order is:

1. encoded-frame presentation timestamps from `ffprobe`;
2. an explicit frame table if present and complete;
3. sufficiently complete callback timestamps;
4. an FPS-derived time grid as a documented fallback.

The selected source is stored in the output metadata. Callback-versus-encoded frame-count differences are also recorded as a diagnostic rather than hidden.

## 3. What problem does `airseai_embodidata` solve?

Embodied-AI models need more than video pixels. They benefit from structured observations of **what action is happening**, **where the hands are**, **how reliable the observation is**, and **which values were measured versus reconstructed or filled**.

This toolkit turns one exported EmbodiData session into three logically separate layers:

```text
RAW OBSERVATIONS
video + IMU + timing + native annotations
        │
        ▼
POST-PROCESSING
encoded-frame timing → hand detection → approximate metric lifting
→ temporal association/filtering → semantic alignment → QA
        │
        ▼
DERIVED EMBODIED DATA
2D landmarks + camera-relative 3D hand estimates + pinch
+ validity/source masks + semantic fields + diagnostics
```

The design principle is **provenance preservation**: the raw data remains untouched, and the derived layer explicitly records what the algorithm detected, estimated, filled, rejected, and warned about.

## 4. What this toolkit produces

For each processed session, the default camera-mode output directory is:

```text
SESSION_DIR/hand_annotation/
├── detections.npz
├── hands_camera.csv
├── hands_camera.npz
├── camera_baseline.json
├── overlay_camera.mp4
└── trajectory_camera.png
```

### `detections.npz`

Cached per-frame MediaPipe Hands detections. Caching allows geometric, filtering, and export experiments to be rerun without repeatedly executing the neural hand detector.

Typical content includes:

- frame index;
- left/right handedness label;
- handedness score;
- 21 image-space hand landmarks;
- 21 local 3D hand landmarks.

### `hands_camera.csv`

A human-readable, row-oriented summary for valid wrist results. It includes fields such as:

- `frame`, `t`, `side`;
- `wrist_valid`, `keypoints_valid`, `pinch_valid`;
- `source` (`detected` or `filled`);
- `handedness_score`;
- `reproj_px`;
- smoothed and raw camera-relative wrist coordinates;
- PnP quaternion for reproducibility/debugging;
- pinch aperture in metres;
- personalization scale (`kappa`);
- aligned semantic segment fields.

### `hands_camera.npz`

The dense, frame-indexed machine-learning representation. It contains:

- selected frame-time vector;
- coordinate-frame declaration;
- ego-motion-compensation flag;
- semantic segment arrays;
- left/right wrist validity;
- keypoint validity;
- pinch validity;
- provenance/source codes;
- handedness scores;
- reprojection errors;
- 2D landmarks;
- raw and smoothed camera-relative 3D keypoints;
- raw and smoothed wrist positions;
- pinch aperture and personalization scale.

The source codes are:

```text
0 = missing
1 = directly detected
2 = wrist-only gap-filled
```

A gap-filled wrist does **not** imply valid 21-keypoint geometry or valid pinch. Use the field-specific validity masks.

### `camera_baseline.json`

The episode-level provenance and QA record. It stores:

- schema/configuration information;
- `coordinate_frame`;
- whether ego motion was compensated;
- frame-time source;
- video/callback diagnostics;
- intrinsics source and matrix;
- participant hand-length values used by the baseline;
- semantic segments;
- processing parameters;
- warnings and failure reasons;
- per-hand coverage and quality statistics.

This file is the recommended first place to inspect when deciding whether a processed episode is suitable for downstream training or evaluation.

### `overlay_camera.mp4`

A visual QA video containing hand skeletons and an image-space wrist trail. It is useful for human inspection of detection coverage, handedness, occlusion, and temporal continuity.

### `trajectory_camera.png`

A visualization of the estimated camera-relative wrist sequence. It is a diagnostic figure, not ground truth.

## 5. Scientific scope and coordinate-frame boundary

### The current public mode is camera-relative

Current EmbodiData legacy sessions do not contain a genuine six-degree-of-freedom camera-pose stream. Therefore:

```text
camera-relative hand motion
    = true hand motion
    + wearer/head/camera motion
```

The package must **not** describe these outputs as:

- world-frame hand trajectories;
- room-fixed trajectories;
- robot-base trajectories;
- motion-capture ground truth;
- directly executable robot actions.

In camera mode, `T_reference_cam` is an identity reference by definition. It is **not** an estimated camera trajectory.

The PnP quaternion is retained for reproducibility/debugging, but it is **not a validated anatomical wrist orientation**.

### Approximate metric scale

The baseline uses the detected hand geometry together with a participant hand-length profile to obtain approximate metric scale. The reference polyline follows landmarks:

```text
wrist → middle MCP → middle PIP → middle DIP → middle fingertip
0     → 9          → 10         → 11          → 12
```

If no user profile is supplied, the current baseline falls back to `0.185 m`. For scientific data releases, measured left/right hand length is strongly preferred.

Example profile:

```json
{
  "schema": "embodidata.user_profile.v1",
  "user_id": "P01",
  "hands": {
    "left":  {"hand_length_m": 0.184},
    "right": {"hand_length_m": 0.186}
  }
}
```

## 6. Processing pipeline

The current baseline performs the following stages.

### Stage 1 — Session ingestion and timing

- locate `raw/session_video.mov`;
- decode the video dimensions, frame count, and nominal FPS;
- extract encoded-frame presentation timestamps with `ffprobe` when possible;
- parse Core Motion samples;
- parse native semantic annotations when present;
- determine camera intrinsics source;
- record all timing and input diagnostics.

### Stage 2 — 2D hand detection

The release configuration uses:

```text
MediaPipe Hands 0.10.21
max hands              = 2
minimum detection conf = 0.45
minimum tracking conf  = 0.45
model complexity       = 1
```

Because EmbodiData uses the rear-facing, unmirrored camera path, the baseline flips the MediaPipe handedness convention before temporal association.

### Stage 3 — Approximate metric 3D lifting

The local 3D hand representation is scaled using the participant hand-length profile. A PnP solution aligns the scaled 3D hand to the observed image landmarks.

The first accepted pose uses SQPnP followed by Levenberg--Marquardt refinement; subsequent frames can use iterative PnP warm-started from the previous accepted solution.

Current geometric gates include:

```text
mean reprojection-error rejection > 12 px
accepted wrist depth             = 0.12–1.5 m
```

When measured camera calibration is unavailable, the current legacy loader uses documented heuristic intrinsics. This is one reason the exported 3D values are described as **approximate camera-relative estimates**, not ground truth.

### Stage 4 — Temporal association and filtering

The tracker combines:

- handedness and temporal wrist association;
- constant-velocity Kalman filtering;
- Mahalanobis gating;
- One Euro filtering for keypoints;
- offline Rauch--Tung--Striebel smoothing for wrist states;
- bounded wrist-only gap filling.

The release configuration currently uses:

```text
Kalman sigma_accel       = 14.0
Kalman sigma_meas        = 0.025 m
Mahalanobis gate         = 16.27
maximum filled wrist gap = 6 frames
reinitialize after gap   = 20 frames
One Euro min cutoff      = 1.8
One Euro beta            = 0.35
```

### Stage 5 — Semantic alignment

When `export/annotations.jsonl` exists, segment metadata is aligned to the encoded-frame time axis and propagated into the frame-level outputs. Current propagated fields include:

- segment index;
- usable-for-training flag;
- motion quality;
- visual quality;
- temporal quality;
- task type;
- language instruction.

This is an important property of the toolkit: hand estimates are not released in isolation from the task and quality context in which they were produced.

### Stage 6 — Quality assessment and export

Episode-level and per-hand QA statistics are computed and written into `camera_baseline.json`.

Current warnings include:

- camera-frame mode / head motion not removed;
- heuristic camera intrinsics;
- no stationary start or end interval;
- mismatch between callback records and encoded-frame count;
- wrist coverage below 30%;
- mean reprojection error above 6 px;
- unstable per-frame hand scale (`kappa` coefficient of variation above 0.15).

The current baseline fails an episode if no hand is detected in the entire episode. Dataset-level release decisions may impose additional privacy, task-completeness, integrity, and annotation-review requirements.

## 7. Why this is useful for embodied AI

Embodied AI requires models to connect perception, action, temporal structure, and data quality. `airseai_embodidata` helps turn low-cost human demonstrations into reusable inputs for several research directions.

### 7.1 Egocentric action understanding

The raw video and aligned semantic segments can be used for:

- action recognition;
- temporal segmentation;
- task-step recognition;
- language-to-video alignment;
- object/action interaction modelling.

### 7.2 Quality-aware data selection

The structured semantic and quality fields make it possible to study **which demonstrations should be used for training**, rather than assuming that all recorded data is equally useful.

Potential applications include:

- filtering low-quality demonstrations;
- curriculum construction;
- quality-conditioned representation learning;
- data valuation;
- active data curation;
- analysis of failure modes caused by blur, occlusion, fast motion, or temporal ambiguity.

### 7.3 Hand-centric representation learning

The HandTraj layer provides weak/intermediate supervision for:

- 2D hand detection and tracking;
- camera-relative wrist-motion modelling;
- hand-object interaction studies;
- pinch-state estimation;
- temporal completion under short occlusion;
- benchmarking alternative hand-reconstruction methods against a common processing interface.

### 7.4 Human demonstration data for robot learning

Human first-person demonstrations can inform imitation learning, representation learning, task understanding, and cross-embodiment research. This toolkit provides a low-cost path from smartphone observations to structured hand-centric signals.

However, **the current camera-relative output is not a robot action stream**. A robot-learning system that requires world-frame or robot-base actions must estimate or measure camera motion and establish the relevant spatial calibration separately.

### 7.5 Data engineering for large embodied datasets

The toolkit also provides reusable infrastructure for:

- batch episode ingestion;
- explicit timing provenance;
- field-level validity masks;
- cached detector results;
- machine-readable QA;
- semantic-to-frame alignment;
- reproducible configuration and environment checks.

These capabilities are useful when scaling embodied datasets, where data lineage and failure visibility become as important as the perception model itself.

## 8. Installation

### Requirements

The currently verified environment is:

```text
Python                    3.11
MediaPipe                 0.10.21
NumPy                     1.26.4
SciPy                     1.13.1
pandas                    2.2.3
PyYAML                    6.0.2
matplotlib                3.9.4
opencv-contrib-python     4.11.0.86
FFmpeg / ffprobe          required
```

The code intentionally uses the legacy `mediapipe.solutions.hands` API. Do not silently upgrade MediaPipe without rerunning the environment checks and tests.

### macOS

Install Python 3.11 and FFmpeg, for example with Homebrew:

```bash
brew install python@3.11 ffmpeg
```

Then, from `AIRSEAI-1.0/airseai_embodidata/`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --only-binary=:all: -r requirements.txt
python scripts/verify_environment.py
```

### Linux

Install Python 3.11 and FFmpeg using your distribution's package manager, then:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python scripts/verify_environment.py
```

Package availability for the pinned MediaPipe version can vary by OS/architecture. `scripts/verify_environment.py` is the source-of-truth runtime check.

## 9. Quick start

### 9.1 Inspect an exported session before running the hand detector

```bash
python scripts/check_legacy_input.py \
  /absolute/path/to/SYYYYMMDD_HHMMSS \
  --config configs/legacy_camera_baseline.yaml
```

This reports:

- decoded video size and frame count;
- FPS and duration;
- processing mode;
- whether ego motion is available;
- frame-time source;
- intrinsics source/matrix;
- number of IMU samples;
- semantic segments;
- callback/encoded-frame diagnostics.

### 9.2 Run one session

Without a hand-length profile:

```bash
python scripts/run_pipeline.py \
  /absolute/path/to/SYYYYMMDD_HHMMSS \
  --mode camera \
  --config configs/legacy_camera_baseline.yaml \
  -v
```

With a participant hand-length profile:

```bash
python scripts/run_pipeline.py \
  /absolute/path/to/SYYYYMMDD_HHMMSS \
  --mode camera \
  --config configs/legacy_camera_baseline.yaml \
  --user-profile /absolute/path/to/P01_profile.json \
  -v
```

### 9.3 Inspect the result

```bash
python scripts/inspect_baseline.py \
  /absolute/path/to/SYYYYMMDD_HHMMSS/hand_annotation/hands_camera.npz
```

Typical summary fields include:

- number of frames;
- duration;
- coordinate frame;
- whether ego motion was compensated;
- directly detected frames;
- wrist-only gap-filled frames;
- wrist/keypoint/pinch coverage;
- mean reprojection error.

### 9.4 Process multiple sessions

```bash
python scripts/run_pipeline.py \
  /absolute/path/to/EPISODES_ROOT \
  --all \
  --mode camera \
  --config configs/legacy_camera_baseline.yaml
```

A batch run additionally writes:

```text
EPISODES_ROOT/hand_annotation_summary.json
```

## 10. Reading the output correctly

### Use field-level validity masks

Do not treat every wrist-valid frame as having complete hand geometry.

```python
import numpy as np

d = np.load("hands_camera.npz")

right_wrist_ok = d["r_wrist_valid"]
right_keypoints_ok = d["r_keypoints_valid"]
right_pinch_ok = d["r_pinch_valid"]
right_source = d["r_source"]

# Direct detections only
right_direct = right_source == 1

# Wrist positions valid either by direct detection or bounded wrist-only filling
wrist_xyz = d["r_wrist_camera_smoothed"][right_wrist_ok]
```

### Use the encoded-frame time vector

For frame-indexed downstream processing, prefer:

```python
t = d["frame_times"]
```

Do not assume that callback `frameIndex` values map one-to-one to encoded movie frames.

### Do not convert camera mode directly to robot actions

The export utility intentionally refuses to interpret camera-mode data as a robot end-effector trajectory. Robot actions require an appropriate world/robot reference frame and calibration.

## 11. Reproducibility and tests

Run:

```bash
python scripts/verify_environment.py
python tests/test_synthetic.py
python tests/test_end_to_end.py
```

The tests validate software behavior such as:

- geometry and transforms;
- pipeline file flow;
- export structure;
- idealized PnP behavior;
- original world-mode transform geometry and generic pipeline file flow.

The bundled synthetic/integration tests exercise idealized geometry and, in the current codebase, include the original world-mode synthetic path with a fake detector. They are **software regression tests**, not evidence of real-video MediaPipe accuracy, camera-mode real-data accuracy, or physical 3D ground-truth accuracy. Before an AIRSEAI release, add or retain a small camera-mode smoke test that runs the public `legacy_camera_baseline.yaml` path on consent-cleared or synthetic example data.

For a scientific data release, we additionally recommend validating real episodes with:

- full video decode checks;
- encoded/callback frame-count statistics;
- empirical IMU sampling-rate checks;
- human review of semantic/quality annotations;
- a manually annotated 2D hand-validation subset;
- aggregate HandTraj coverage/reprojection statistics;
- privacy and checksum audits.

## 12. Relationship to EmbodiData datasets

A recommended dataset organization separates raw data, reviewed annotations, derived outputs, and release-level QA:

```text
EmbodiData-Daily-v1.0/
├── participants.tsv
├── tasks.csv
├── environments.csv
├── master_episode_index.csv
├── data_dictionary.md
├── episodes/
│   └── P01/
│       └── E000001/
│           ├── raw/
│           │   ├── session_video.mov
│           │   ├── frame_timestamps.jsonl
│           │   └── motion_samples.jsonl
│           ├── native_annotations/
│           │   └── annotations.jsonl
│           ├── reviewed_annotations/
│           │   ├── annotations_reviewed.jsonl
│           │   └── review_log.csv
│           ├── handtraj/
│           │   ├── detections.npz
│           │   ├── hands_camera.csv
│           │   ├── hands_camera.npz
│           │   └── camera_baseline.json
│           └── qc/
│               └── release_qc.json
└── checksums.sha256
```

The full participant dataset should normally be hosted in an appropriate scientific data repository. The AIRSEAI code repository should contain the post-processing software, documentation, tests, and only small example/synthetic data that are appropriate for source control.

## 13. Recommended AIRSEAI repository layout

```text
AIRSEAI-1.0/
└── airseai_embodidata/
    ├── README.md
    ├── LICENSE                    # [TODO: inherit/confirm AIRSEAI license]
    ├── CITATION.cff              # recommended
    ├── CHANGELOG.md               # recommended
    ├── requirements.txt
    ├── configs/
    │   ├── legacy_camera_baseline.yaml
    │   └── user_profile_example.json
    ├── handtraj/
    ├── scripts/
    │   ├── verify_environment.py
    │   ├── check_legacy_input.py
    │   ├── run_pipeline.py
    │   └── inspect_baseline.py
    ├── tests/
    ├── examples/                  # small, consent-cleared or synthetic example
    └── docs/
```

Before the first AIRSEAI release, remove or clearly isolate experimental code paths that are not supported by the public EmbodiData-Daily workflow.

## 14. Known limitations

1. **No native 6DoF camera trajectory in current legacy sessions.** Camera-mode 3D values mix hand motion and head/camera motion.
2. **Heuristic intrinsics may be used.** Metric depth is therefore approximate when calibrated intrinsics are unavailable.
3. **Monocular hand reconstruction is not ground truth.** Reprojection error is an internal consistency diagnostic, not an independent physical accuracy measurement.
4. **Hand scale depends on participant calibration.** Measured hand lengths are preferred over the default 0.185 m fallback.
5. **PnP rotation is not anatomical wrist orientation.** Do not use it as a validated wrist-pose label.
6. **Short gaps are wrist-only filled.** Keypoint/pinch masks remain separate and must be respected.
7. **MediaPipe handedness score is not general confidence.** It is a left/right classification score.
8. **The current output is not a robot action stream.** World/robot calibration must be supplied by downstream systems that need executable actions.

## 15. Citation

If you use this toolkit, please cite the AIRSEAI EmbodiData software release and the corresponding EmbodiData-Daily data descriptor when available.

```text
[TODO: add software citation / DOI]
[TODO: add Scientific Data paper citation / DOI]
```

A `CITATION.cff` file is recommended for the AIRSEAI release.

## 16. License

**[TODO: confirm the license inherited from or approved for AIRSEAI-1.0 before public release.]**

The data license and the software license may be different. Participant-derived datasets must also follow the applicable ethics, consent, privacy, and repository requirements.

## 17. Contact and contributions

Issues and pull requests should describe:

- operating system and CPU architecture;
- Python and MediaPipe versions;
- whether `scripts/verify_environment.py` passes;
- the processing mode (`camera` for current legacy sessions);
- a minimal description of the input session structure;
- relevant warning/error messages;
- whether the problem is reproducible on the provided example session.

**Maintainer/contact:** **[TODO: add AIRSEAI EmbodiData maintainer and contact details.]**

---

### One-sentence summary

**`airseai_embodidata` turns exported iPhone-based EmbodiData recordings into provenance-aware, quality-aware, camera-relative hand annotations that are easier to inspect, filter, reproduce, and reuse in embodied-AI research.**
