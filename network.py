STEP = 500
HALF = 2000
RINGS = {"ring2": 1000, "ring3": 1500, "ring4": 2000}
GATE = 3200
DIAGONAL_GATE = 2750
SPEC = {
    "arterial": {"lanes": 2, "speed": 13.89},
    "axis": {"lanes": 4, "speed": 16.67},
    "ring2": {"lanes": 3, "speed": 22.22},
    "ring3": {"lanes": 3, "speed": 22.22},
    "ring4": {"lanes": 3, "speed": 25.00},
    "radial": {"lanes": 3, "speed": 27.78},
}
PALACE = (0, 500)


def name(x, y):
    return "n_%d_%d" % (x, y)


def ring_of(a, b):
    for kind, r in RINGS.items():
        on_a = max(abs(a[0]), abs(a[1])) == r
        on_b = max(abs(b[0]), abs(b[1])) == r
        same_side = (a[0] == b[0] and abs(a[0]) == r) or (a[1] == b[1] and abs(a[1]) == r)
        if on_a and on_b and same_side:
            return kind
    return None


def build():
    removed = {PALACE}
    for r in (RINGS["ring3"], RINGS["ring4"]):
        removed |= {(r, r), (r, -r), (-r, r), (-r, -r)}
    nodes = {}
    for x in range(-HALF, HALF + 1, STEP):
        for y in range(-HALF, HALF + 1, STEP):
            if (x, y) not in removed:
                nodes[name(x, y)] = {"x": x, "y": y, "kind": "junction"}
    links = []
    for x in range(-HALF, HALF + 1, STEP):
        for y in range(-HALF, HALF + 1, STEP):
            for other in ((x + STEP, y), (x, y + STEP)):
                if name(x, y) in nodes and name(*other) in nodes:
                    kind = ring_of((x, y), other)
                    if kind is None:
                        kind = "axis" if y == 0 and other[1] == 0 else "arterial"
                    links.append((name(x, y), name(*other), kind))
    r3, r4 = RINGS["ring3"], RINGS["ring4"]
    for sx in (1, -1):
        for sy in (1, -1):
            links.append((name(sx * (r3 - STEP), sy * r3), name(sx * r3, sy * (r3 - STEP)), "ring3"))
            corner = "c_%s%s" % ("n" if sy > 0 else "s", "e" if sx > 0 else "w")
            nodes[corner] = {"x": sx * (r4 - STEP / 2), "y": sy * (r4 - STEP / 2), "kind": "junction"}
            links.append((name(sx * (r4 - STEP), sy * r4), corner, "ring4"))
            links.append((corner, name(sx * r4, sy * (r4 - STEP)), "ring4"))
            gate = "g_%s%s" % ("n" if sy > 0 else "s", "e" if sx > 0 else "w")
            nodes[gate] = {"x": sx * DIAGONAL_GATE, "y": sy * DIAGONAL_GATE, "kind": "gate"}
            links.append((corner, gate, "radial"))
    for gate, (x, y) in (("g_n", (0, 1)), ("g_s", (0, -1)), ("g_e", (1, 0)), ("g_w", (-1, 0))):
        nodes[gate] = {"x": x * GATE, "y": y * GATE, "kind": "gate"}
        links.append((name(x * r4, y * r4), gate, "radial"))
    edges = []
    for a, b, kind in links:
        for start, end in ((a, b), (b, a)):
            dx = nodes[end]["x"] - nodes[start]["x"]
            dy = nodes[end]["y"] - nodes[start]["y"]
            edges.append({"id": "%s__%s" % (start, end), "from": start, "to": end, "kind": kind,
                          "lanes": SPEC[kind]["lanes"], "speed": SPEC[kind]["speed"], "length": (dx * dx + dy * dy) ** 0.5})
    return nodes, edges


def connected(nodes, edges):
    reach = {}
    for e in edges:
        reach.setdefault(e["from"], []).append(e["to"])
    seen = set()
    stack = [next(iter(nodes))]
    while stack:
        n = stack.pop()
        if n not in seen:
            seen.add(n)
            stack.extend(reach.get(n, []))
    return len(seen) == len(nodes)