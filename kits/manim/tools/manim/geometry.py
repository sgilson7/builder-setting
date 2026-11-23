"""Where edges and moving marks run, ported from FlowScene (the SnapClass
guide's engine.js, lines 102-120): a line between two boxes starts and
ends on their borders, and a mark's path through several nodes passes through each
middle node's centre. The exporter uses it for path lengths, the renderer to draw.
Stdlib only."""
import math


def border(nodes, a, toward):
    """The point where the line from node a's centre toward `toward` leaves its box."""
    n = nodes[a]
    x, y = n["x"], n["y"]
    dx, dy = toward[0] - x, toward[1] - y
    sx = (n["w"] / 2) / abs(dx) if dx else math.inf
    sy = (n["h"] / 2) / abs(dy) if dy else math.inf
    s = min(sx, sy)
    return (x + dx * s, y + dy * s)


def centre(nodes, a):
    return (nodes[a]["x"], nodes[a]["y"])


def segment(nodes, a, b):
    return [border(nodes, a, centre(nodes, b)), border(nodes, b, centre(nodes, a))]


def polyline(nodes, path):
    """engine.js polyline(): border to border, through each middle node's centre."""
    pts = []
    for i in range(len(path) - 1):
        s = segment(nodes, path[i], path[i + 1])
        pts = pts + [centre(nodes, path[i])] + s if pts else s
    return pts


def length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def at(pts, f):
    """The point a fraction f of the way along pts (engine.js place())."""
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    d = f * sum(lens)
    i = 0
    while i < len(lens) - 1 and d > lens[i]:
        d -= lens[i]
        i += 1
    a, b = pts[i], pts[i + 1]
    r = d / lens[i] if lens[i] else 1
    return (a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r)


def cubic_bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2) as a function of time in 0..1."""
    def bez(t, p1, p2):
        u = 1 - t
        return 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3

    def ease(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if bez(mid, x1, x2) < x:
                lo = mid
            else:
                hi = mid
        return bez((lo + hi) / 2, y1, y2)
    return ease
