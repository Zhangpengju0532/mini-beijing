import os
import sys

import demand
import sim

TOTAL = 15000


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL
    rows = demand.trips(total)
    os.makedirs("runs", exist_ok=True)
    trips_file = os.path.join("runs", "trips_%d.xml" % total)
    demand.write(rows, trips_file)
    z = demand.zones()
    print("zones: %d home nodes, %d job nodes, %d gates" % (len(z["homes"]), len(z["jobs"]), len(z["gates"])))
    print("trips: %d in total over %d min" % (len(rows), (demand.RISE + demand.PEAK + demand.FALL) // 60))
    for purpose in demand.SHARES:
        print("  %-8s %6d" % (purpose, sum(r["purpose"] == purpose for r in rows)))
    north = sum(r["purpose"] == "commute" and r["origin"] in demand.NORTH_GATES for r in rows)
    print("commute trips entering through the three north gates: %d" % north)
    peak = sum(demand.RISE <= r["depart"] < demand.RISE + demand.PEAK for r in rows)
    print("departures in the peak half hour: %d (%.0f per hour)" % (peak, peak * 3600.0 / demand.PEAK))
    print("running the simulation, this takes a few minutes...")
    for line in sim.lines(sim.run("peak_%d" % total, trips_file)):
        print(line)


if __name__ == "__main__":
    main()