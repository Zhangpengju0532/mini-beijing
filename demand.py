import numpy as np

import network

RISE = 1800
PEAK = 1800
FALL = 1800
SHARES = {"commute": 0.55, "reverse": 0.10, "local": 0.25, "through": 0.10}
NORTH_GATES = ("g_n", "g_nw", "g_ne")


def zones():
    nodes, edges = network.build()
    homes, jobs, anywhere, gates = {}, {}, {}, {}
    for key, n in nodes.items():
        x, y = n["x"], n["y"]
        if n["kind"] == "gate":
            gates[key] = 1.0
            homes[key] = 3.0 if key in NORTH_GATES else 1.5
            continue
        if key.startswith("c_"):
            continue
        anywhere[key] = 1.0
        if y >= 1500:
            homes[key] = 1.0
        if 500 <= abs(x) <= 1500 and abs(y) <= 500:
            jobs[key] = 1.0
        elif abs(x) <= 500 and abs(y) <= 500:
            jobs[key] = 0.5
    return {"homes": homes, "jobs": jobs, "anywhere": anywhere, "gates": gates}


def pick(rng, weights, size):
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return [keys[i] for i in rng.choice(len(keys), size=size, p=p / p.sum())]


def departures(rng, size):
    seconds = np.arange(RISE + PEAK + FALL)
    rate = np.where(seconds < RISE, 0.2 + 0.8 * seconds / RISE,
                    np.where(seconds < RISE + PEAK, 1.0, 1.0 - 0.8 * (seconds - RISE - PEAK) / FALL))
    return np.sort(rng.choice(seconds, size=size, p=rate / rate.sum()) + rng.random(size))


def trips(total, seed=1):
    rng = np.random.default_rng(seed)
    z = zones()
    nodes, edges = network.build()
    leaving, entering = {}, {}
    for e in edges:
        leaving.setdefault(e["from"], []).append(e["id"])
        entering.setdefault(e["to"], []).append(e["id"])
    pairs = []
    plan = {"commute": ("homes", "jobs"), "reverse": ("jobs", "homes"), "local": ("anywhere", "anywhere"), "through": ("gates", "gates")}
    for purpose, (source, sink) in plan.items():
        count = int(round(total * SHARES[purpose]))
        starts = pick(rng, z[source], count)
        ends = pick(rng, z[sink], count)
        for a, b in zip(starts, ends):
            while b == a:
                b = pick(rng, z[sink], 1)[0]
            pairs.append((purpose, a, b))
    order = rng.permutation(len(pairs))
    times = departures(rng, len(pairs))
    rows = []
    for t, i in zip(times, order):
        purpose, a, b = pairs[i]
        start = leaving[a][rng.integers(len(leaving[a]))]
        end = entering[b][rng.integers(len(entering[b]))]
        rows.append({"id": "%s_%d" % (purpose, len(rows)), "depart": float(t), "from": start, "to": end, "purpose": purpose, "origin": a, "destination": b})
    return rows


def write(rows, path):
    with open(path, "w") as fh:
        fh.write("<routes>\n")
        fh.write('    <vType id="car" vClass="passenger" sigma="0.5"/>\n')
        for r in rows:
            fh.write('    <trip id="%s" type="car" depart="%.2f" from="%s" to="%s" departLane="best" departSpeed="max"/>\n' % (r["id"], r["depart"], r["from"], r["to"]))
        fh.write("</routes>\n")