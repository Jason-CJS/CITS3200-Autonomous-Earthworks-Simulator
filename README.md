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