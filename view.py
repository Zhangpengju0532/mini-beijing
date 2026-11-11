import os
import subprocess
import sys

import sumolib


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "x_base"
    step = sys.argv[2] if len(sys.argv) > 2 else "1.0"
    folder = os.path.join("runs", tag)
    net, trips = os.path.join(folder, "city.net.xml"), os.path.join(folder, "trips.xml")
    if not (os.path.exists(net) and os.path.exists(trips)):
        found = sorted(name for name in os.listdir("runs") if os.path.exists(os.path.join("runs", name, "city.net.xml")))
        print("no scenario called %s; available: %s" % (tag, ", ".join(found)))
        return
    subprocess.run([sumolib.checkBinary("sumo-gui"), "-n", net, "-r", trips,
                    "--device.rerouting.probability", "1", "--device.rerouting.period", "120",
                    "--ignore-route-errors", "true", "--no-warnings", "true", "--seed", "1",
                    "--step-length", step, "--start", "--delay", "20"])


if __name__ == "__main__":
    main()