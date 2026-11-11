import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import scenario

CASES = [
    ("Baseline", "x_base", {}),
    ("Central block opened", "x_open_block", {"open_block": True}),
    ("East-west axis closed in the centre", "x_axis_closed", {"closed": "axis_centre"}),
    ("North side of ring 2 closed", "x_ring2_closed", {"closed": "ring2_north"}),
    ("Rings without signals", "x_rings_free", {"ring_control": "priority"}),
]


def main():
    os.makedirs("results", exist_ok=True)
    rows = []
    print("scenario                              arrived  unfinished (%)  teleports  trip (km)  trip (min)  entry wait (min)  total (min)  change (%)")
    for label, tag, changes in CASES:
        try:
            r = scenario.run(tag, **changes)
        except RuntimeError as problem:
            print("%-36s  %s" % (label, problem))
            continue
        if r["code"] != 0:
            print("%-36s  sumo failed: %s" % (label, " | ".join(r.get("error", []))))
            continue
        trip, wait = r["duration"] / 60.0, r["depart_delay"] / 60.0
        rows.append((label, trip, wait, 100.0 * (r["loaded"] - r["arrived"]) / r["loaded"]))
        change = 100.0 * ((trip + wait) / (rows[0][1] + rows[0][2]) - 1.0)
        print("%-36s  %7d  %14.1f  %9d  %9.2f  %10.1f  %16.1f  %11.1f  %+10.1f" % (
            label, r["arrived"], rows[-1][3], r["teleports"], r["length"] / 1000.0, trip, wait, trip + wait, change))
    if len(rows) < 2:
        return
    fig, ax = plt.subplots(figsize=(8.6, 0.62 * len(rows) + 1.5))
    labels = [row[0] for row in rows][::-1]
    trip = [row[1] for row in rows][::-1]
    wait = [row[2] for row in rows][::-1]
    ax.barh(labels, trip, height=0.55, color="#1f5fae", edgecolor="white", linewidth=2, label="Driving")
    ax.barh(labels, wait, left=trip, height=0.55, color="#d98a1f", edgecolor="white", linewidth=2, label="Waiting to enter the network")
    for i, (a, b) in enumerate(zip(trip, wait)):
        ax.text(a + b + 0.2, i, "%.1f" % (a + b), va="center", fontsize=9)
    ax.set_xlabel("mean time per trip (min)")
    ax.set_xlim(0, max(a + b for a, b in zip(trip, wait)) * 1.12)
    ax.grid(axis="x", color="#e3e5ea", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    fig.tight_layout()
    fig.savefig("results/s5_network.png", dpi=200)
    print("figure written to results/s5_network.png")


if __name__ == "__main__":
    main()