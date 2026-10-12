# Autonomous Earthworks Simulator

**Project Leads:** Adrian Boeing, Fabian Deuser, Kieran Quirke-Brown

### Group Members

| **Student Number** | **Name** | **GitHub Username** |
| :--- | :--- | :--- |
| 24618514 | Jieh Shuen Chia (Jason) | Jason-CJS |
| 24270886 | Aron Zombori | CheggGH |
| 21111977 | Robin Candy | robinbmc |
| 23964287 | Houssein Marouff | Big-H-21 |
| 24441384 | Youhei Azuka Arya Arya | tera-A-A |

## Description

A 3D robotics simulation for studying deformable terrain and earthworks
vehicle interaction, with labelled outputs for comparison against
real-world datasets.

The simulator uses **Project Chrono**, **SCM deformable terrain**, and
labelled LiDAR data from the **GOOSE-Ex ALICE excavator** platform. It
converts recorded ground points into terrain with real semantic labels,
places label-derived vegetation with real collision, and lets you drive a
bulldozer or excavator across it — scripted or manually — while inspecting
every generated output afterward without re-running the simulation.

## Getting started

- **New to this repo?** Start with [INSTALLATION.md](INSTALLATION.md) —
  environment setup, dependencies, and preparing the GOOSE-Ex dataset.
- **Ready to run something?** See [USER_GUIDE.md](USER_GUIDE.md) — generating
  terrain, adding vegetation, driving a vehicle, running tests, and
  inspecting results.

## Repository structure

```text
CITS3200-AES/
├── README.md              # This file — project overview and pointers
├── INSTALLATION.md        # Environment setup and dataset preparation
├── USER_GUIDE.md          # Running scenarios, demos, and tests
├── environment.yml        # Shared Conda environment and dependencies
│
├── environments/
│   ├── README.md          # GOOSE setup, generation and launch guide
│   ├── terrain/           # GOOSE converter, dataset helper and Chrono loader
│   ├── scene_config/      # SCM terrain configuration
│   └── vegetation/        # Tree/vegetation/rural object placement and models
│
├── vehicles/
│   ├── excavator/
│   └── bulldozer/
│
├── sensors/                # GPS reference check; camera/LiDAR are future-team stretch goals
├── deformation/             # Terrain deformation export and output inspection
│
├── scenarios/
│   ├── bulldozer_earthmoving/  # Scripted hole-filling scenario
│   ├── goose_label_viewer/     # Semantic label visualisation
│   └── goose_navigation/       # Scripted/manual bulldozer or excavator traversal demo
│
├── scripts/                 # Every CLI tool here — see scripts/README.md
│
├── tests/                   # Automated test suite
├── data/goose/              # Prepared GOOSE-Ex dataset (not in Git)
├── outputs/                 # All generated run outputs (not in Git)
│
└── redundant-aarp/          # Archived pre-rescope AARP work, kept for record only
```

## Further documentation

- [GOOSE environment setup and terrain generation](environments/README.md)
- [Semantic label viewer](scenarios/goose_label_viewer/README.md)
- [GOOSE navigation demo](scenarios/goose_navigation/README.md)
- [Bulldozer hole-filling scenario](scenarios/bulldozer_earthmoving/README.md)
- [Output inspector and deformation export](deformation/README.md)
- [GOOSE-Ex dataset](data/goose/README.md)
- [Sensors (GPS reference, camera/LiDAR stretch goals)](sensors/README.md)
- [Script index](scripts/README.md)
- [Archived AARP work](redundant-aarp/README.md)
- [Third-party asset credits and licensing](ASSET_CREDITS.md)
