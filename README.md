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
To develop a 3D robotics simulation, using Gazebo Harmonic and/or Project Chrono, that realistically models deformable terrain and mining vehicle interaction, producing labelled simulation data suitable for comparison with real-world datasets. 

## Repository Structure

```
CITS3200-AES/
├── README.md                  # Project overview, setup, and run instructions
├── .gitignore
├── CMakeLists.txt             # Top-level build configuration
│
├── environments/
│   ├── goose/                 # GOOSE-aligned environment
│   │   ├── terrain/
│   │   ├── vegetation/
│   │   └── scene_config/
│   │
│   └── construction_zone/     # AARP-reflective construction zone environment
│       ├── terrain/
│       ├── vegetation/
│       └── scene_config/
│
├── vehicles/
│   ├── excavator/
│   │   ├── model/
│   │   └── articulation/
│   └── bulldozer/
│       ├── model/
│       └── articulation/
│
├── sensors/
│   ├── camera/
│   └── lidar/
│
├── deformation/                # Terrain deformation logic (Chrono SCM config)
│
├── labelling/                  # Object/asset labelling & metadata export pipeline
│
├── src/                        # Core application code
│   ├── main.cpp
│   ├── vehicle_control/
│   ├── terrain/
│   └── sensors/
│
├── scripts/                    # Build/setup automation, run scripts
│
└── tests/                      # Validation/test scripts
```

## Environment Setup (Conda)

This project uses PyChrono 10.0.0 and Python 3.12 for simulation. Dependencies are pinned via `environment.yml` to avoid version mismatches across machines.

### Prerequisites
- System running on native Linux or WSL2 with Ubuntu 24.04 LTS (Windows users)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda installed

### Setup (from Linux terminal)

1. Clone the repository:
```bash
   git clone https://github.com/<org-or-username>/CITS3200-Autonomous-Earthworks-Simulator
   cd CITS3200-Autonomous-Earthworks-Simulator
```

2. Create the conda environment from the provided file:
```bash
   conda env create -f environment.yml
```

3. Activate the environment:
```bash
   conda activate chrono
```

4. Verify PyChrono is installed correctly:
```bash
   conda list pychrono
```
   The pychrono version should be `10.0.0`

### Updating the environment
If you install a new package required for the project:
```bash
conda env export --no-builds | grep -v "^prefix:" > environment.yml
git add environment.yml
git commit -m "Update environment.yml: added <package-name>"
git push
```
Please avoid installing packages ad-hoc without updating `environment.yml` - this keeps everyone's environment in sync.
