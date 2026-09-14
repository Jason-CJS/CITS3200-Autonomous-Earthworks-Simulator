# =============================================================================
# Test GPS/GNSS sensor output.
#
# Confirms Chrono's chrono.sensor module can produce simulated GPS
# position data (latitude/longitude/altitude) at a specified sampling
# rate. Deliberately self-contained: no vehicle, no terrain, no
# visualization -- just a single kinematically-scripted body carrying a
# GPS sensor, so this is fast to run and verify.
#
# NOTE on scope: GPS itself only provides position, not orientation --
# orientation comes from an IMU, a separate sensor. This issue's
# acceptance criteria and "Maps to" both reference GPS/sensors/gps/
# specifically, so this script is scoped to position only. If
# orientation is actually needed here too, that's IMU sensor work
# (ChGyroscopeSensor / ChAccelerometerSensor / ChMagnetometerSensor),
# not something ChGPSSensor itself provides -- see the official
# demo_SEN_sensors.py for the pattern if that turns out to be needed.
#
# Adapted from the official example:
# https://github.com/projectchrono/chrono/blob/main/src/demos/python/sensor/demo_SEN_sensors.py
#
# Usage: python sensors/gps/test_gps_output.py
# =============================================================================

import pychrono.core as chrono
import pychrono.sensor as sens

# -----------------------------------------------------------------------
# Sensor and simulation parameters
# -----------------------------------------------------------------------
GPS_UPDATE_RATE = 5.0   # Hz
STEP_SIZE = 1e-3
END_TIME = 10.0         # seconds of simulated time

# GPS reference point (longitude, latitude, altitude) -- Chrono's
# ChGPSSensor convention is (lon, lat, alt). Using the AARP site
# reference coordinates identified in the project's handover notes,
# rather than an arbitrary placeholder, so the reference location is
# actually meaningful to this project.
GPS_REFERENCE = chrono.ChVector3d(115.7806170, -31.6739291, 0.0)

# Allowed deviation between expected and actual sample count before
# flagging a failure -- accounts for the sensor's update timing not
# landing on an exact simulation step boundary.
RATE_TOLERANCE = 0.2  # 20%


def main():
    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0, 0, -9.81))

    # A single body to carry the GPS sensor. Kinematically scripted
    # (position set directly each step) rather than given real dynamics
    # -- keeps this test deterministic and avoids depending on
    # velocity-setting API that isn't directly exercised elsewhere in
    # this codebase yet. The goal here is confirming GPS output tracks
    # changing position at the right rate, not testing rigid body
    # dynamics.
    body = chrono.ChBodyEasyBox(0.5, 0.5, 0.5, 1000, True, False)
    body.SetPos(chrono.ChVector3d(0, 0, 0))
    body.SetFixed(True)
    system.Add(body)

    manager = sens.ChSensorManager(system)

    offset_pose = chrono.ChFramed(
        chrono.ChVector3d(0, 0, 0),
        chrono.QuatFromAngleAxis(0, chrono.ChVector3d(0, 1, 0))
    )

    # No noise model -- this issue is about confirming GPS output exists
    # at the right rate, not modeling realistic GPS error. Noise
    # modeling (e.g. sens.ChNoiseRandomWalks, used in the official demo)
    # would be a separate, follow-up concern.
    noise_none = sens.ChNoiseNone()

    gps = sens.ChGPSSensor(
        body,               # body the sensor is attached to
        GPS_UPDATE_RATE,    # update rate in Hz
        offset_pose,        # offset pose relative to parent body
        GPS_REFERENCE,      # reference location (lon, lat, alt)
        noise_none          # noise model
    )
    gps.SetName("GPS Sensor")
    gps.SetLag(0)
    gps.SetCollectionWindow(0)  # instant
    gps.PushFilter(sens.ChFilterGPSAccess())
    manager.AddSensor(gps)

    ch_time = 0.0
    sample_count = 0
    last_reported_launches = 0

    print(f"Running GPS sensor test: {END_TIME}s simulated, "
          f"target rate {GPS_UPDATE_RATE} Hz...\n")

    while ch_time < END_TIME:
        # Move the body along a straight line at 2 m/s so GPS position
        # output actually changes over time, rather than reporting a
        # single static point repeatedly.
        body.SetPos(chrono.ChVector3d(2.0 * ch_time, 0, 0))

        manager.Update()
        system.DoStepDynamics(STEP_SIZE)
        ch_time = system.GetChTime()

        gps_data = gps.GetMostRecentGPSBuffer()
        if gps_data.HasData():
            launches = gps.GetNumLaunches()
            if launches != last_reported_launches:
                data = gps_data.GetGPSData()
                print(f"  t={ch_time:6.3f}s  GPS (lon, lat, alt): {data}")
                last_reported_launches = launches
                sample_count += 1

    expected_samples = int(GPS_UPDATE_RATE * END_TIME)
    print(f"\nGPS sensor produced {sample_count} distinct samples over "
          f"{END_TIME}s (expected ~{expected_samples} at "
          f"{GPS_UPDATE_RATE} Hz).")

    lower_bound = expected_samples * (1 - RATE_TOLERANCE)
    upper_bound = expected_samples * (1 + RATE_TOLERANCE)

    if lower_bound <= sample_count <= upper_bound:
        print("PASS: GPS output confirmed at expected sampling rate.")
        return 0
    else:
        print("FAIL: GPS sample count deviates from expected rate "
              f"(allowed range: {lower_bound:.0f}-{upper_bound:.0f}).")
        return 1


if __name__ == "__main__":
    exit(main())