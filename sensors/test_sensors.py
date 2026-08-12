#AI generated test code for camera and sensors

import pychrono.core as chrono
import pychrono.sensor as sens
import time


print("PyChrono imported successfully")

# ------------------------------------------------------------
# Chrono system
# ------------------------------------------------------------

system = chrono.ChSystemNSC()

# Ground
ground = chrono.ChBodyEasyBox(
    20, 20, 0.1,
    1000,
    True,
    False
)

ground.SetPos(chrono.ChVector3d(0, 0, -0.05))
ground.SetFixed(True)
system.Add(ground)

# Object for sensors to detect
box = chrono.ChBodyEasyBox(
    1, 1, 1,
    1000,
    True,
    False
)

box.SetPos(chrono.ChVector3d(0, 0, 0.5))
system.Add(box)


# ------------------------------------------------------------
# Sensor manager
# ------------------------------------------------------------

manager = sens.ChSensorManager(system)

manager.SetMaxEngines(1)


# ------------------------------------------------------------
# Camera
# ------------------------------------------------------------

camera = sens.ChCameraSensor(
    box,
    30,
    chrono.ChFramed(
        chrono.ChVector3d(3, -3, 2),
        chrono.QuatFromAngleAxis(
            chrono.CH_PI / 4,
            chrono.ChVector3d(1, 0, 0)
        )
    ),
    640,
    480,
    chrono.CH_PI / 3
)

camera.SetName("TestCamera")

manager.AddSensor(camera)


# ------------------------------------------------------------
# LiDAR
# ------------------------------------------------------------

lidar = sens.ChLidarSensor(
    box,
    10,
    chrono.ChFramed(
        chrono.ChVector3d(0, 0, 2),
        chrono.QUNIT
    ),
    64,
    16,
    chrono.CH_PI * 2,
    chrono.CH_PI / 6,
    10.0,
    0.1
)

lidar.SetName("TestLidar")

manager.AddSensor(lidar)


# ------------------------------------------------------------
# Run simulation
# ------------------------------------------------------------

print("Camera created:", camera.GetName())
print("LiDAR created:", lidar.GetName())
print()
print("Starting sensor simulation...")

for i in range(100):

    system.DoStepDynamics(0.01)
    manager.Update()

    if i % 10 == 0:
        print(
            f"Step {i:3d} | "
            f"Time {system.GetChTime():.2f}s"
        )

    time.sleep(0.001)


print()
print("Sensor simulation completed successfully.")