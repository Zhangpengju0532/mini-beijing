import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import demand
import sim

TOTALS = [5000, 10000, 15000, 20000, 25000, 30000]


def one(total):
    tag = "peak_%d" % total
    stats_file = os.path.join("runs", tag, "stats.xml")
    if os.path.exists(stats_file):
        result = {"code": 0, "seconds": 0.0, "folder": os.path.join("runs", tag)}
        result.update(sim.read(stats_file))
        return result
    trips_file = os.path.join("runs", "trips_%d.xml" % total)
    demand.write(demand.trips(total), trips_file)
    return sim.run(tag, trips_file)


def main():
    os.makedirs("runs", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    rows = []
    print("demand  arrived  unfinished (%)  teleports  trip (km)  trip (min)  speed (km/h)  time lost (min)  computer time (s)")
    for total in TOTALS:
        r = one(total)
        if r["code"] != 0:
            print("%6d  sumo failed: %s" % (total, " | ".join(r.get("error", []))))
            continue
        unfinished = 100.0 * (r["loaded"] - r["arrived"]) / r["loaded"]
        speed = r["length"] / r["duration"] * 3.6
        rows.append((total, unfinished, r["teleports"], r["duration"] / 60.0, speed, r["loss"] / 60.0))
        print("%6d  %7d  %14.1f  %9d  %9.2f  %10.1f  %12.1f  %15.1f  %17.0f" % (
            total, r["arrived"], unfinished, r["teleports"], r["length"] / 1000.0, r["duration"] / 60.0, speed, r["loss"] / 60.0, r["seconds"]))
    if len(rows) < 2:
        return
    x = [row[0] / 1000.0 for row in rows]
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.4))
    panels = (([row[3] for row in rows], "Mean trip time (min)"), ([row[4] for row in rows], "Mean trip speed (km/h)"),
              ([row[1] for row in rows], "Trips not finished (%)"))
    for ax, (values, title) in zip(axes, panels):
        ax.plot(x, values, color="#1f5fae", linewidth=2, marker="o", markersize=6)
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_xlabel("demand (thousand trips in 90 min)")
        ax.set_ylim(0, max(max(values) * 1.15, 1.0))
        ax.grid(axis="y", color="#e3e5ea", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig("results/s4_sweep.png", dpi=200)
    print("figure written to results/s4_sweep.png")


if __name__ == "__main__":
    main()