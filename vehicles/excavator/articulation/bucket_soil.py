"""Scoop soil out of SCM terrain with the excavator bucket and pour it elsewhere.

SCM has no soil particles, so material moves as height changes on the SCM
grid: nodes under the bucket teeth are lowered into a tracked bucket load, and
tipping the bucket releases that load as a pile that slumps to its angle of
repose. ``SCMTerrain.SetModifiedNodes`` writes the new levels, so dug holes
and dumped piles are real terrain that the tracks then drive over.

The height operations below are plain numpy and conserve volume; only
``BucketSoil`` talks to PyChrono.
"""

from __future__ import annotations

import math

import numpy as np


def scm_node_spacing(size_x: float, requested: float) -> float:
    """The spacing SCM actually uses: a whole number of cells across the terrain."""
    return size_x / (2 * math.ceil(size_x / 2 / requested))


def cut_below(levels: np.ndarray, loose: np.ndarray, mask: np.ndarray,
              floor_z: float | np.ndarray, max_volume: float, cell_area: float) -> float:
    """Lower masked nodes towards ``floor_z`` (one height, or one per node) in place.

    Returns the volume removed.

    The cut is scaled down evenly when it would exceed ``max_volume``. Loose
    (previously dumped) material is taken first.
    """
    excess = np.where(mask, np.clip(levels - floor_z, 0.0, None), 0.0)
    volume = float(excess.sum()) * cell_area
    if volume <= 0.0 or max_volume <= 0.0:
        return 0.0
    if volume > max_volume:
        excess *= max_volume / volume
        volume = max_volume
    levels -= excess
    np.subtract(loose, np.minimum(loose, excess), out=loose)
    return volume


def box_bottom_heights(xs: np.ndarray, ys: np.ndarray, centre: np.ndarray,
                       axes: np.ndarray, half: np.ndarray) -> np.ndarray:
    """Lowest height of an oriented box above each (x, y) node; +inf where it is not.

    ``axes`` holds the box's local x, y and z directions as columns. Each node's
    vertical line is clipped against the box's three pairs of faces.
    """
    x, y = np.meshgrid(xs, ys, indexing="ij")
    offset = np.stack((x - centre[0], y - centre[1], np.full_like(x, -centre[2])), axis=-1)
    local = offset @ axes             # position of the z = 0 point in box coordinates
    up = axes[2]                      # how box coordinates change per metre of height
    low, high = np.full(x.shape, -np.inf), np.full(x.shape, np.inf)
    for i in range(3):
        if abs(up[i]) < 1e-9:
            outside = np.abs(local[..., i]) > half[i]
            low[outside], high[outside] = np.inf, -np.inf
            continue
        a = (-half[i] - local[..., i]) / up[i]
        b = (half[i] - local[..., i]) / up[i]
        low, high = np.maximum(low, np.minimum(a, b)), np.minimum(high, np.maximum(a, b))
    return np.where(low <= high, low, np.inf)


def push_aside(levels: np.ndarray, loose: np.ndarray, mask: np.ndarray, volume: float,
               cell_area: float) -> None:
    """Spread ``volume`` evenly over the ring of nodes just outside ``mask``, in place."""
    if volume <= 0.0:
        return
    grown = mask.copy()
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        grown |= np.roll(mask, shift, axis=axis)
    ring = grown & ~mask
    if not ring.any():
        ring = mask
    added = volume / (ring.sum() * cell_area)
    levels[ring] += added
    loose[ring] += added


def deposit_cone(levels: np.ndarray, loose: np.ndarray, center: tuple[float, float],
                 volume: float, spacing: float, radius: float) -> None:
    """Add ``volume`` in place as a cone centred at fractional node ``center``."""
    if volume <= 0.0:
        return
    rows, cols = np.indices(levels.shape)
    distance = np.hypot(rows - center[0], cols - center[1]) * spacing
    weights = np.clip(1.0 - distance / radius, 0.0, None)
    if weights.sum() <= 0.0:
        weights = (distance == distance.min()).astype(float)
    added = volume * weights / (weights.sum() * spacing * spacing)
    levels += added
    loose += added


def relax_loose(levels: np.ndarray, loose: np.ndarray, spacing: float,
                repose_slope: float, iterations: int = 40,
                blocked: np.ndarray | None = None) -> None:
    """Let loose material slide downhill in place until slopes reach repose.

    Only loose material moves, so the generated terrain keeps its own slopes.
    Each pass moves at most a quarter of a node's excess to each neighbour,
    which keeps the update stable; the total volume never changes.
    """
    limit = repose_slope * spacing
    for _ in range(iterations):
        moved = False
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            neighbour = np.roll(levels, shift, axis=axis)
            excess = levels - neighbour - limit
            # np.roll wraps around; never move material across the patch edge.
            edge = [slice(None), slice(None)]
            edge[axis] = 0 if shift == 1 else -1
            excess[tuple(edge)] = 0.0
            flow = np.minimum(np.clip(excess / 4.0, 0.0, None), loose / 4.0)
            if blocked is not None:  # nothing slides into space the bucket occupies
                flow[np.roll(blocked, shift, axis=axis)] = 0.0
            if not flow.any():
                continue
            moved = True
            levels -= flow
            loose -= flow
            arrived = np.roll(flow, -shift, axis=axis)
            levels += arrived
            loose += arrived
        if not moved:
            break


class BucketSoil:
    """Couples the excavator bucket to an SCM terrain: digging, carrying, dumping."""

    UPDATE_PERIOD_S = 0.02
    SPILL_BELOW_COS = 0.30      # opening normal's Z below this tips material out
    POUR_RATE_M3_S = 0.35
    REPOSE_SLOPE = math.tan(math.radians(34.0))
    PILE_RADIUS_M = 0.45
    CLOD_COUNT = 48
    CLOD_VOLUME_M3 = 0.0025     # one falling clod drawn per this much released soil

    def __init__(self, terrain, model, spacing: float, *, capacity_m3: float | None = None,
                 bulking: float = 1.2, seed: int = 0) -> None:
        import pychrono as chrono
        import pychrono.vehicle as veh

        from vehicles.excavator.articulation.excavator_model import (
            BUCKET_SCALE,
            VISUAL_UPDATE_PERIOD_S,
        )
        from vehicles.excavator.articulation.excavator_visuals import MutableMesh

        self._chrono, self._veh = chrono, veh
        self.terrain, self.model = terrain, model
        # This class now moves all soil the bucket touches. Left on, SCM would
        # also squash soil under the bucket's collision box, so the pit would
        # look several times larger than the load that reaches the pile.
        model.bucket.EnableCollision(False)
        self.spacing, self.cell_area = spacing, spacing * spacing
        self.bulking = bulking
        # 0.15 m3 fits the original bucket; capacity grows with the bucket's volume.
        self.bucket_scale = BUCKET_SCALE
        if capacity_m3 is None:
            capacity_m3 = 0.15 * BUCKET_SCALE ** 3
        self.capacity_m3 = capacity_m3
        self.load_m3 = 0.0
        self.excavated_m3 = 0.0
        self.deposited_m3 = 0.0
        self.loose: dict[tuple[int, int], float] = {}
        self._clock = 0.0
        self._visual_period = VISUAL_UPDATE_PERIOD_S
        self._time_since_visual_update = 0.0
        self._pour_debt = 0.0
        self._rng = np.random.default_rng(seed)
        self._clod_pos = np.zeros((self.CLOD_COUNT, 3))
        self._clod_vel = np.zeros((self.CLOD_COUNT, 3))
        self._clod_alive = np.zeros(self.CLOD_COUNT, dtype=bool)
        self._clod_size = self._rng.uniform(0.05, 0.09, self.CLOD_COUNT)

        soil = (0.42, 0.31, 0.20)
        self._mound_grid = (11, 7)
        self.mound = MutableMesh(model.bucket, self._mound_grid[0] * self._mound_grid[1],
                                 _grid_triangles(*self._mound_grid), soil)
        # Clods live in world coordinates on the model's fixed anchor body.
        self._world_origin = np.array(_xyz(model.ground.GetPos()))
        self.clods = MutableMesh(model.ground, 6 * self.CLOD_COUNT,
                                 _octahedron_triangles(self.CLOD_COUNT), (0.36, 0.26, 0.17))
        self.update_visuals()

    # -- physics-side update -------------------------------------------------

    def advance(self, step: float) -> None:
        """Dig, carry or pour on the physics clock; call after the model's advance()."""
        self._advance_clods(step)
        self._time_since_visual_update += step
        if self._time_since_visual_update >= self._visual_period:
            self.update_visuals()
        self._clock += step
        if self._clock + 1e-12 < self.UPDATE_PERIOD_S:
            return
        dt, self._clock = self._clock, 0.0
        teeth = self.model.get_bucket_teeth_position()
        opening = self.model.get_bucket_opening_normal()
        if opening.z < self.SPILL_BELOW_COS and self.load_m3 > 0.0:
            tilt = min(1.0, (self.SPILL_BELOW_COS - opening.z) / 0.5)
            self._pour(teeth, min(self.load_m3, self.POUR_RATE_M3_S * tilt * dt))
        else:
            self._dig()

    def _patch(self, x: float, y: float, radius: float):
        i0, j0 = round(x / self.spacing), round(y / self.spacing)
        n = math.ceil(radius / self.spacing)
        ii = np.arange(i0 - n, i0 + n + 1)
        jj = np.arange(j0 - n, j0 + n + 1)
        levels = np.array([[self.terrain.GetHeight(self._chrono.ChVector3d(
            i * self.spacing, j * self.spacing, 0.0)) for j in jj] for i in ii])
        loose = np.array([[self.loose.get((int(i), int(j)), 0.0) for j in jj] for i in ii])
        return ii, jj, levels, loose

    def _write(self, ii, jj, before: np.ndarray, levels: np.ndarray, loose: np.ndarray) -> None:
        nodes = self._veh.ChSCMTerrainNodeLevelList()
        for a, b in zip(*np.nonzero(np.abs(levels - before) > 1e-7)):
            key = (int(ii[a]), int(jj[b]))
            nodes.push_back(self._veh.ChSCMTerrainNodeLevel(
                self._chrono.ChVector2i(*key), float(levels[a, b])))
            if loose[a, b] > 1e-7:
                self.loose[key] = float(loose[a, b])
            else:
                self.loose.pop(key, None)
        if len(nodes):
            self.terrain.SetModifiedNodes(nodes)

    def _dig(self) -> None:
        """Move all soil inside the bucket's box: into the load while it has room, aside after."""
        centre, axes, half = self.model.get_bucket_box()
        centre = np.array(_xyz(centre))
        axes = np.array([_xyz(axis) for axis in axes]).T
        half = np.array(half)
        signs = np.array([(i, j, k) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])
        corners = centre + (signs * half) @ axes.T
        if all(z >= self.terrain.GetHeight(self._chrono.ChVector3d(x, y, 0.0)) for x, y, z in corners):
            return  # cheap early exit: the whole bucket is above the ground
        reach = float(np.max(np.hypot(corners[:, 0] - centre[0], corners[:, 1] - centre[1])))
        ii, jj, levels, loose = self._patch(centre[0], centre[1], reach + 2 * self.spacing)
        bottom = box_bottom_heights(ii * self.spacing, jj * self.spacing, centre, axes, half)
        inside = levels > bottom + 1e-6
        if not inside.any():
            return
        before = levels.copy()
        removed = cut_below(levels, loose, inside, bottom, np.inf, self.cell_area)
        scooped = min(removed, max(self.capacity_m3 - self.load_m3, 0.0))
        pushed = removed - scooped
        self.load_m3 += scooped
        self.excavated_m3 += scooped
        if pushed > 0.0:
            push_aside(levels, loose, inside, pushed, self.cell_area)
            relax_loose(levels, loose, self.spacing, self.REPOSE_SLOPE, blocked=inside)
        self._write(ii, jj, before, levels, loose)

    def _pour(self, teeth, volume: float) -> None:
        self.load_m3 -= volume
        placed = volume * self.bulking
        ii, jj, levels, loose = self._patch(teeth.x, teeth.y, 3.0 * self.PILE_RADIUS_M)
        before = levels.copy()
        centre = (teeth.x / self.spacing - ii[0], teeth.y / self.spacing - jj[0])
        deposit_cone(levels, loose, centre, placed, self.spacing, self.PILE_RADIUS_M)
        relax_loose(levels, loose, self.spacing, self.REPOSE_SLOPE)
        self.deposited_m3 += placed
        self._write(ii, jj, before, levels, loose)
        self._spawn_clods(teeth, volume)

    # -- falling clods (display only, but on the physics clock) -------------

    def _spawn_clods(self, teeth, volume: float) -> None:
        self._pour_debt += volume / self.CLOD_VOLUME_M3
        lip = np.array(_xyz(teeth))
        while self._pour_debt >= 1.0:
            self._pour_debt -= 1.0
            free = np.flatnonzero(~self._clod_alive)
            if not free.size:
                break
            k = free[0]
            self._clod_alive[k] = True
            self._clod_pos[k] = lip + self._rng.uniform(-0.2, 0.2, 3) * (1.0, 1.0, 0.3)
            self._clod_vel[k] = self._rng.normal(0.0, 0.35, 3) * (1.0, 1.0, 0.5)

    def _advance_clods(self, step: float) -> None:
        if not self._clod_alive.any():
            return
        alive = self._clod_alive
        self._clod_vel[alive, 2] -= 9.81 * step
        self._clod_pos[alive] += self._clod_vel[alive] * step
        for k in np.flatnonzero(alive):
            x, y, z = self._clod_pos[k]
            if z <= self.terrain.GetHeight(self._chrono.ChVector3d(x, y, 0.0)):
                self._clod_alive[k] = False

    # -- display -------------------------------------------------------------

    def update_visuals(self) -> None:
        """Redraw the soil in the bucket and the falling clods (display only)."""
        self._time_since_visual_update = 0.0
        fill = self.load_m3 / self.capacity_m3
        self.mound.set_vertices(self.bucket_scale * _mound_vertices(fill, *self._mound_grid))
        points = np.zeros((6 * self.CLOD_COUNT, 3))
        hidden = -self._world_origin + (0.0, 0.0, -50.0)
        for k in range(self.CLOD_COUNT):
            if self._clod_alive[k]:
                local = self._clod_pos[k] - self._world_origin
                points[6 * k:6 * k + 6] = local + self._clod_size[k] * _OCTAHEDRON
            else:
                points[6 * k:6 * k + 6] = hidden
        self.clods.set_vertices(points)


_OCTAHEDRON = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)],
                       dtype=float) * (1.0, 0.8, 0.7)


def _xyz(vector) -> tuple[float, float, float]:
    return float(vector.x), float(vector.y), float(vector.z)


def _octahedron_triangles(count: int) -> list[tuple[int, int, int]]:
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
             (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return [(6 * k + a, 6 * k + b, 6 * k + c) for k in range(count) for a, b, c in faces]


def _grid_triangles(nx: int, ny: int) -> list[tuple[int, int, int]]:
    triangles = []
    for a in range(nx - 1):
        for b in range(ny - 1):
            p = a * ny + b
            triangles += [(p, p + ny, p + ny + 1), (p, p + ny + 1, p + 1)]
    return triangles


def _cavity_x_limits(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inner back (lip side) and front (hinge side) wall positions at height z.

    Measured from stick_bucket_link.STL in the bucket frame: the cavity is
    narrowest at its floor and widens towards the opening.
    """
    t = np.clip((z + 0.30) / 0.40, 0.0, 1.0)
    return -0.70 - 0.06 * t, -0.21 + 0.09 * t


def _side_plate_top(x: np.ndarray) -> np.ndarray:
    """Top edge of the bucket's side plates: a straight line from the lip to the hinge end."""
    return 0.46 + (x + 0.78) * (0.0 - 0.46) / (-0.12 + 0.78)


def _mound_vertices(fill: float, nx: int, ny: int) -> np.ndarray:
    """Soil surface inside the bucket, in the bucket frame, for a fill fraction.

    Empty soil sits on the bucket floor. A full load stays just below the side
    plates' top edge, so nothing shows underneath it, with a low heap in the
    middle. At every height the surface spans the cavity from wall to wall.
    """
    fill = min(max(fill, 0.0), 1.0)
    u = np.linspace(0.0, 1.0, nx)[:, None]
    v = np.linspace(-1.0, 1.0, ny)[None, :]
    floor = -0.37
    heap = 0.05 * (1 - (2 * u - 1) ** 2) * (1 - v ** 2)
    z = np.full((nx, ny), floor)
    for _ in range(3):  # the walls depend on the height, the height on x
        back, front = _cavity_x_limits(z)
        x = back + u * (front - back)
        full = np.maximum(_side_plate_top(x) - 0.08, floor) + heap
        z = floor + fill * (full - floor)
    y = 0.235 * v * np.ones_like(x)
    if fill < 0.02:
        x, y, z = np.full_like(z, -0.4), np.zeros_like(z), np.full_like(z, floor)
    return np.stack((x, y, z), axis=-1).reshape(-1, 3)
