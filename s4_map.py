import os
import sys
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

import demand
import network
import sim

TOTAL = 25000
PERIOD = 900
PEAK = (2700, 3600)
SHIFT = 45.0
KINDS = ("arterial", "axis", "ring2", "ring3", "ring4", "radial")


def simulate(total):
    tag = "base_%d" % total
    folder = os.path.join("runs", tag)
    os.makedirs(folder, exist_ok=True)
    extra_file = os.path.join(folder, "extra.add.xml")
    with open(extra_file, "w") as fh:
        fh.write('<additional>\n    <edgeData id="roads" file="edgedata.xml" period="%d"/>\n</additional>\n' % PERIOD)
    trips_file = os.path.join("runs", "trips_%d.xml" % total)
    demand.write(demand.trips(total), trips_file)
    return sim.run(tag, trips_file, ["--additional-files", extra_file]), os.path.join(folder, "edgedata.xml")


def load(path):
    table = {}
    for interval in ET.parse(path).getroot().findall("interval"):
        begin = int(float(interval.get("begin")))
        rows = {}
        for edge in interval.findall("edge"):
            sampled = float(edge.get("sampledSeconds", "0"))
            if sampled > 0 and edge.get("speed") is not None:
                rows[edge.get("id")] = (float(edge.get("speed")), sampled)
        table[begin] = rows
    return table


def segments(nodes, edges):
    out = {}
    for e in edges:
        a, b = nodes[e["from"]], nodes[e["to"]]
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        size = (dx * dx + dy * dy) ** 0.5
        ox, oy = dy / size * SHIFT, -dx / size * SHIFT
        out[e["id"]] = [((a["x"] + ox) / 1000.0, (a["y"] + oy) / 1000.0), ((b["x"] + ox) / 1000.0, (b["y"] + oy) / 1000.0)]
    return out


def panel(ax, lines, values, low, high, title, label, cmap):
    quiet = [lines[key] for key in lines if key not in values]
    busy = [key for key in lines if key in values]
    ax.add_collection(LineCollection(quiet, colors="#ffffff", linewidths=1.0))
    shown = LineCollection([lines[key] for key in busy], cmap=cmap, linewidths=2.4)
    shown.set_array([values[key] for key in busy])
    shown.set_clim(low, high)
    ax.add_collection(shown)
    ax.set_facecolor("#e6e8ed")
    ax.set_aspect("equal")
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-3.5, 3.5)
    ax.set_xlabel("east (km)")
    ax.set_title(title, fontsize=10, loc="left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    bar = plt.colorbar(shown, ax=ax, fraction=0.04, pad=0.02)
    bar.set_label(label, fontsize=9)
    bar.outline.set_visible(False)


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL
    print("running the baseline with %d trips, this takes a few minutes..." % total)
    result, path = simulate(total)
    for line in sim.lines(result):
        print(line)
    if result["code"] != 0:
        return
    nodes, edges = network.build()
    table = load(path)
    by_id = {e["id"]: e for e in edges}
    peak = table.get(PEAK[0], {})
    last = table[max(table)]
    print()
    print("peak quarter hour, %d to %d min" % (PEAK[0] // 60, PEAK[1] // 60))
    print("kind      limit (km/h)  mean speed (km/h)  share of limit (%)  vehicles on the road")
    for kind in KINDS:
        chosen = [(by_id[key]["speed"], speed, sampled) for key, (speed, sampled) in peak.items() if by_id[key]["kind"] == kind]
        if not chosen:
            continue
        weight = sum(c[2] for c in chosen)
        mean = sum(c[1] * c[2] for c in chosen) / weight
        print("%-8s  %12.0f  %17.1f  %18.0f  %20.0f" % (kind, chosen[0][0] * 3.6, mean * 3.6, 100.0 * mean / chosen[0][0], weight / PERIOD))
    slow = sorted(((speed / by_id[key]["speed"], key) for key, (speed, sampled) in peak.items() if sampled > 5 * PERIOD))[:8]
    print()
    print("slowest roads in the peak quarter hour (speed as a share of the limit)")
    for ratio, key in slow:
        print("  %3.0f%%  %-8s  %s" % (100.0 * ratio, by_id[key]["kind"], key))
    left = sorted(((sampled / PERIOD, key) for key, (speed, sampled) in last.items()), reverse=True)[:8]
    print()
    print("roads that still hold vehicles in the last quarter hour: %d, vehicles on them: %.0f" % (len(last), sum(s for v, s in last.values()) / PERIOD))
    for count, key in left:
        print("  %5.1f vehicles  %-8s  %s" % (count, by_id[key]["kind"], key))

    lines = segments(nodes, edges)
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.4))
    panel(axes[0], lines, {key: 100.0 * speed / by_id[key]["speed"] for key, (speed, sampled) in peak.items()}, 0, 100,
          "Speed in the peak quarter hour", "speed as a share of the limit (%)", "YlOrRd_r")
    panel(axes[1], lines, {key: sampled / PERIOD / (by_id[key]["length"] * by_id[key]["lanes"] / 1000.0) for key, (speed, sampled) in peak.items()}, 0, 120,
          "Density in the peak quarter hour", "vehicles per km of lane", "YlOrRd")
    axes[0].set_ylabel("north (km)")
    fig.tight_layout()
    os.makedirs("results", exist_ok=True)
    fig.savefig("results/s4_map.png", dpi=200)
    print()
    print("figure written to results/s4_map.png")


if __name__ == "__main__":
    main()