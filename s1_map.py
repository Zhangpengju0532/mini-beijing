import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import network

STYLE = {
    "arterial": ("#b9bcc4", 1.2, "Arterial, 2 lanes, 50 km/h"),
    "axis": ("#c0392b", 3.4, "East-west axis, 4 lanes, 60 km/h"),
    "ring2": ("#1f5fae", 2.6, "Ring 2, 3 lanes, 80 km/h"),
    "ring3": ("#2a9d8f", 2.6, "Ring 3, 3 lanes, 80 km/h"),
    "ring4": ("#7b4fa3", 2.6, "Ring 4, 3 lanes, 90 km/h"),
    "radial": ("#d98a1f", 2.6, "Radial expressway, 3 lanes, 100 km/h"),
}


def main():
    nodes, edges = network.build()
    print("nodes: %d (junctions %d, gates %d)" % (len(nodes), sum(n["kind"] == "junction" for n in nodes.values()),
                                                  sum(n["kind"] == "gate" for n in nodes.values())))
    print("directed edges: %d" % len(edges))
    print("kind      edges  length (km)  lane-km")
    for kind in STYLE:
        chosen = [e for e in edges if e["kind"] == kind]
        km = sum(e["length"] for e in chosen) / 1000.0
        print("%-8s  %5d  %11.1f  %7.1f" % (kind, len(chosen), km, sum(e["length"] * e["lanes"] for e in chosen) / 1000.0))
    print("total road length: %.1f km, total lane length: %.1f km" % (sum(e["length"] for e in edges) / 1000.0,
                                                                     sum(e["length"] * e["lanes"] for e in edges) / 1000.0))
    print("every node reachable from every other: %s" % network.connected(nodes, edges))

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    for kind, (colour, width, label) in STYLE.items():
        first = True
        for e in edges:
            if e["kind"] == kind and e["from"] < e["to"]:
                a, b = nodes[e["from"]], nodes[e["to"]]
                ax.plot([a["x"] / 1000, b["x"] / 1000], [a["y"] / 1000, b["y"] / 1000], color=colour, linewidth=width,
                        solid_capstyle="round", zorder=1 if kind == "arterial" else 2, label=label if first else None)
                first = False
    px, py = network.PALACE
    ax.add_patch(plt.Rectangle((px / 1000 - 0.3, py / 1000 - 0.3), 0.6, 0.6, facecolor="#f3e3b3", edgecolor="#a8873a", linewidth=1.0, zorder=3))
    ax.text(px / 1000, py / 1000, "closed\nblock", ha="center", va="center", fontsize=7, color="#5f4b17", zorder=4)
    gates = [n for n in nodes.values() if n["kind"] == "gate"]
    ax.plot([n["x"] / 1000 for n in gates], [n["y"] / 1000 for n in gates], linestyle="none", marker="s", markersize=7,
            color="#d98a1f", markeredgecolor="white", zorder=5, label="Gate to the region")
    ax.set_aspect("equal")
    ax.set_xlim(-3.6, 3.6)
    ax.set_ylim(-3.6, 3.6)
    ax.set_xlabel("east (km)")
    ax.set_ylabel("north (km)")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)
    ax.set_title("Mini-Beijing network", fontsize=11, loc="left")
    os.makedirs("results", exist_ok=True)
    fig.savefig("results/s1_map.png", dpi=200, bbox_inches="tight")
    print("figure written to results/s1_map.png")


main()