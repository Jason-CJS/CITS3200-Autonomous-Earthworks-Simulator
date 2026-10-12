# Sensors

Sensor simulation beyond vehicle navigation was explicitly scoped as
stretch goals for a future team — not part of the current GOOSE-Ex earthworks
MVP. This directory reflects that: one working capability check, and two
empty placeholders.

## `gps/`

`test_gps_output.py` confirms Chrono's `chrono.sensor` module can produce
simulated GPS position output (latitude/longitude/altitude) at a specified
sampling rate, using a single scripted body with no vehicle or terrain
involved. It's a capability reference, not a project feature — nothing in
the GOOSE-Ex pipeline consumes GPS output.

Despite the filename, it's a standalone script, not a `unittest.TestCase` —
run it directly rather than through test discovery, and it isn't part of
`scripts/run_tests.sh`:

```bash
python sensors/gps/test_gps_output.py
```

GPS alone only provides position, not orientation; that would need a
separate IMU sensor (`ChGyroscopeSensor`/`ChAccelerometerSensor`/
`ChMagnetometerSensor`), not implemented here.

## `camera/` and `lidar/`

Empty placeholders. Camera and LiDAR sensing were scoped out early
(they'd need NVIDIA ray-tracing support, listed as stretch-goal-only in the
project's rescope) and were never implemented. Here as a marker of where
that work would go if a future team picks it up.
