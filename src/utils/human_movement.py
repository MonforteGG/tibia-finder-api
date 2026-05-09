import time
import pyautogui
from random import randint, uniform
from pytweening import easeInOutQuad


def cubic_bezier(t, p0, p1, p2, p3):
    u = 1 - t
    return u**3*p0 + 3*u**2*t*p1 + 3*u*t**2*p2 + t**3*p3


def _noseq_waypoints(sx, sy, ex, ey):
    """Generate intermediate waypoints with noseq cycles for unpredictable movement."""
    dx, dy = ex - sx, ey - sy
    distance = (dx**2 + dy**2) ** 0.5
    if distance < 40:
        return [(ex, ey)]

    # Normalized perpendicular vector
    px, py = -dy / distance, dx / distance
    n_cycles = randint(2, 4)
    waypoints = []

    for i in range(1, n_cycles):
        t = i / n_cycles
        bx = sx + dx * t
        by = sy + dy * t
        # Perpendicular amplitude that decreases toward the destination
        amplitude = distance * uniform(0.04, 0.14) * (1.0 - t * 0.6)
        sign = 1 if i % 2 == 0 else -1
        waypoints.append((int(bx + px * amplitude * sign),
                          int(by + py * amplitude * sign)))

    waypoints.append((ex, ey))
    return waypoints


def _move_segment(x0, y0, x1, y1):
    """Move the cursor along a cubic Bézier segment."""
    vx, vy = x1 - x0, y1 - y0
    distance = (vx**2 + vy**2) ** 0.5
    if distance < 1:
        return

    steps = max(5, int((max(distance, 80) + randint(-20, 20)) / 10))

    cp1x = x0 + vx * uniform(0.3, 0.5) + vy * uniform(-0.08, 0.08)
    cp1y = y0 + vy * uniform(0.3, 0.5) + vx * uniform(-0.08, 0.08)
    cp2x = x0 + vx * uniform(0.7, 0.9)
    cp2y = y0 + vy * uniform(0.7, 0.9)

    prog = [easeInOutQuad(t / (steps - 1)) for t in range(steps)]
    for t in prog:
        pyautogui.moveTo(
            cubic_bezier(t, x0, cp1x, cp2x, x1),
            cubic_bezier(t, y0, cp1y, cp2y, y1),
        )


def move_mouse_like_human(x: int, y: int, target_deviation: int = 5):
    """Move the mouse in noseq cycles — chained Bézier segments with perpendicular offsets."""
    cur = pyautogui.position()
    if abs(cur.x - x) <= target_deviation and abs(cur.y - y) <= target_deviation:
        return

    dest_x = x + randint(-target_deviation, target_deviation)
    dest_y = y + randint(-target_deviation, target_deviation)
    waypoints = _noseq_waypoints(cur.x, cur.y, dest_x, dest_y)

    prev_pause = pyautogui.PAUSE
    pyautogui.PAUSE = 0.01

    cx, cy = cur.x, cur.y
    for wx, wy in waypoints:
        _move_segment(cx, cy, wx, wy)
        cx, cy = wx, wy
        if uniform(0, 1) < 0.25:
            time.sleep(uniform(0.008, 0.040))

    pyautogui.PAUSE = prev_pause
