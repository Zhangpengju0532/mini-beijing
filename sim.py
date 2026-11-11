import os
import subprocess
import time
import xml.etree.ElementTree as ET

import sumolib

NET = os.path.join("net", "mini_beijing.net.xml")
END = 9000


def run(tag, trips_file, extra=()):
    folder = os.path.join("runs", tag)
    os.makedirs(folder, exist_ok=True)
    stats_file = os.path.join(folder, "stats.xml")
    command = [sumolib.checkBinary("sumo"), "-n", NET, "-r", trips_file,
               "--begin", "0", "--end", str(END), "--seed", "1",
               "--device.rerouting.probability", "1", "--device.rerouting.period", "120",
               "--ignore-route-errors", "true", "--no-warnings", "true", "--no-step-log", "true",
               "--duration-log.statistics", "true",
               "--statistic-output", stats_file,
               "--tripinfo-output", os.path.join(folder, "tripinfo.xml")] + list(extra)
    started = time.time()
    done = subprocess.run(command, capture_output=True, text=True)
    result = {"code": done.returncode, "seconds": time.time() - started, "folder": folder}
    if done.returncode != 0:
        result["error"] = (done.stdout + done.stderr).strip().splitlines()[-8:]
        return result
    result.update(read(stats_file))
    return result


def number(element, key):
    value = None if element is None else element.get(key)
    return float(value) if value not in (None, "") else float("nan")


def read(stats_file):
    root = ET.parse(stats_file).getroot()
    vehicles, teleports, trip = root.find("vehicles"), root.find("teleports"), root.find("vehicleTripStatistics")
    return {"loaded": number(vehicles, "loaded"), "inserted": number(vehicles, "inserted"), "running": number(vehicles, "running"),
            "waiting": number(vehicles, "waiting"), "teleports": number(teleports, "total"), "arrived": number(trip, "count"),
            "length": number(trip, "routeLength"), "duration": number(trip, "duration"), "speed": number(trip, "speed"),
            "loss": number(trip, "timeLoss"), "depart_delay": number(trip, "departDelay"), "stopped": number(trip, "waitingTime")}


def lines(result):
    if result["code"] != 0:
        return ["sumo failed with code %d" % result["code"]] + ["  " + line for line in result.get("error", [])]
    return ["simulation took %.0f s of computer time" % result["seconds"],
            "vehicles: loaded %d, inserted %d, arrived %d, still driving at the end %d, never inserted %d" % (
                result["loaded"], result["inserted"], result["arrived"], result["running"], result["waiting"]),
            "teleports (vehicles stuck for 5 minutes and moved by the simulator): %d" % result["teleports"],
            "mean trip: %.2f km in %.1f min, speed %.1f km/h" % (result["length"] / 1000.0, result["duration"] / 60.0, result["speed"] * 3.6),
            "mean time lost against free flow: %.1f min (%.0f%% of the trip), of which standing still %.1f min" % (
                result["loss"] / 60.0, 100.0 * result["loss"] / result["duration"], result["stopped"] / 60.0),
            "mean wait before entering the network: %.1f s" % result["depart_delay"]]