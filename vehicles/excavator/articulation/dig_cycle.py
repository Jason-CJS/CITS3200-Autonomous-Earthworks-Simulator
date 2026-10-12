"""A repeatable dig-and-dump articulation cycle for the excavator.

Targets are (swing, boom, arm, bucket) joint angles in radians, using the same
signs as the manual controller: +swing is left, +boom raises, +bucket curls.
"""

from __future__ import annotations

from bisect import bisect_right


TRAVEL_POSE = (0.0, 0.25, -0.45, 0.45)
# In this model a larger bucket angle tips the teeth down and a smaller one
# rolls the opening upwards: scooping lowers the angle and dumping raises it
# again, so the load pours out of the open side with the teeth pointing down.
APPROACH = (0.0, 0.15, 0.00, 1.25)    # teeth above the dig spot, pointing down
CARRY = (0.0, 0.15, -0.10, 0.40)      # boom up, opening facing the sky
DUMP = (1.2, 0.55, 0.80, 1.30)        # bucket high and fully open, opening facing down

# (time, targets). The cycle repeats from REPEAT_FROM_S once it reaches the end.
KEYFRAMES = (
    (0.0, TRAVEL_POSE),
    (1.5, APPROACH),
    (3.0, (0.0, 0.00, 0.10, 1.30)),                  # teeth touch down ~3 m out
    (5.0, (0.0, -0.25, 0.15, 1.05)),                 # drag towards the cab, ~0.3 m deep
    (6.5, (0.0, -0.30, 0.30, 0.25)),                 # roll the bucket up: scoop
    (8.0, CARRY),                                    # lift the load clear
    (10.0, (DUMP[0], *CARRY[1:])),                   # swing to the dump side
    (11.5, DUMP),                                    # open the bucket: pour the load out
    (12.5, DUMP),                                    # let it empty
    (14.0, APPROACH),                                # swing back for the next pass
)
REPEAT_FROM_S = 1.5
CYCLE_S = KEYFRAMES[-1][0] - REPEAT_FROM_S
# Each repeat digs deeper into the same trench: the touch, drag and scoop
# keyframes lower the boom a little more, up to a few extra passes.
DIG_KEYFRAMES = (2, 3, 4)
DEEPEN_BOOM_RAD = 0.06
MAX_DEEPER_PASSES = 4


def dig_cycle_targets(time_s: float) -> tuple[float, float, float, float]:
    """Joint targets at ``time_s``, eased between keyframes and repeating."""
    passes = 0
    if time_s >= KEYFRAMES[-1][0]:
        cycles, phase = divmod(time_s - REPEAT_FROM_S, CYCLE_S)
        passes, time_s = int(cycles), REPEAT_FROM_S + phase
    times = [time for time, _ in KEYFRAMES]
    index = max(1, min(bisect_right(times, time_s), len(KEYFRAMES) - 1))
    (t0, a), (t1, b) = KEYFRAMES[index - 1], KEYFRAMES[index]
    a, b = (_deepen(pose, i, passes) for pose, i in ((a, index - 1), (b, index)))
    s = min(max((time_s - t0) / (t1 - t0), 0.0), 1.0)
    s = s * s * (3.0 - 2.0 * s)  # smoothstep: start and stop each move gently
    return tuple(x + (y - x) * s for x, y in zip(a, b, strict=True))


def _deepen(pose: tuple[float, ...], index: int, passes: int) -> tuple[float, ...]:
    if index not in DIG_KEYFRAMES:
        return pose
    swing, boom, arm, bucket = pose
    return swing, boom - DEEPEN_BOOM_RAD * min(passes, MAX_DEEPER_PASSES), arm, bucket


# One-key helpers for manual mode. Both keep the cab's current swing angle and
# start by blending smoothly from wherever the arm is.
SCOOP_BLEND_S = 1.0
SCOOP_FROM_S, SCOOP_TO_S = KEYFRAMES[1][0], KEYFRAMES[5][0]  # approach ... carry
SCOOP_DURATION_S = SCOOP_BLEND_S + SCOOP_TO_S - SCOOP_FROM_S
DUMP_DURATION_S = 1.5


def _blend(start: tuple[float, ...], end: tuple[float, ...], fraction: float) -> tuple[float, ...]:
    s = min(max(fraction, 0.0), 1.0)
    s = s * s * (3.0 - 2.0 * s)
    return tuple(x + (y - x) * s for x, y in zip(start, end, strict=True))


def scoop_targets(time_s: float, start: tuple[float, ...]) -> tuple[float, float, float, float]:
    """Manual scoop: reach out, touch down, drag, roll the bucket up and lift to carry."""
    swing = start[0]
    if time_s < SCOOP_BLEND_S:
        return _blend(start, (swing, *APPROACH[1:]), time_s / SCOOP_BLEND_S)
    t = min(SCOOP_FROM_S + time_s - SCOOP_BLEND_S, SCOOP_TO_S)
    return (swing, *dig_cycle_targets(t)[1:])


def dump_targets(time_s: float, start: tuple[float, ...]) -> tuple[float, float, float, float]:
    """Manual dump: raise the boom, push the arm out and tip the bucket over."""
    return _blend(start, (start[0], *DUMP[1:]), time_s / DUMP_DURATION_S)
