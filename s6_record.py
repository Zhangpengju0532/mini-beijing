import json
import os
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import sumolib

import network
import sim

BEGIN = 1800
END = 4200
PERIOD = 5
SPAN = 3300.0
LABELS = {"x_base": "Baseline", "x_open_block": "Central block opened", "x_axis_closed": "East-west axis closed in the centre",
          "x_ring2_closed": "North side of ring 2 closed", "x_rings_free": "Rings without signals",
          "x_demand_80": "Demand reduced by 20%", "y_av_0": "Human drivers only (0.5 s step)", "y_av_100": "100% automated vehicles"}


def simulate(tag, step):
    folder = os.path.join("runs", tag)
    fcd = os.path.join(folder, "fcd.xml")
    command = [sumolib.checkBinary("sumo"), "-n", os.path.join(folder, "city.net.xml"), "-r", os.path.join(folder, "trips.xml"),
               "--begin", "0", "--end", str(END + PERIOD), "--seed", "1", "--step-length", step,
               "--device.rerouting.probability", "1", "--device.rerouting.period", "120",
               "--ignore-route-errors", "true", "--no-warnings", "true", "--no-step-log", "true",
               "--fcd-output", fcd, "--device.fcd.period", str(PERIOD), "--device.fcd.begin", str(BEGIN),
               "--fcd-output.attributes", "x,y,speed"]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(" | ".join((done.stdout + done.stderr).strip().splitlines()[-4:]))
    return fcd


def offset(tag):
    with open(os.path.join("runs", tag, "city.net.xml")) as fh:
        head = fh.read(20000)
    found = re.search(r'netOffset="([-0-9.]+),([-0-9.]+)"', head)
    return float(found.group(1)), float(found.group(2))


def roads(tag):
    kinds = {}
    for e in network.build()[1]:
        kinds[e["id"]] = e["kind"]
    nodes = {n.get("id"): (float(n.get("x")), float(n.get("y"))) for n in ET.parse(os.path.join("runs", tag, "city.nod.xml")).getroot()}
    lines = []
    for e in ET.parse(os.path.join("runs", tag, "city.edg.xml")).getroot():
        if e.get("from") < e.get("to"):
            a, b = nodes[e.get("from")], nodes[e.get("to")]
            lines.append([a[0], a[1], b[0], b[1], e.get("type")])
    return lines


def convert(tag, fcd, label, step):
    dx, dy = offset(tag)
    numbers = {}
    frames = []
    for event, element in ET.iterparse(fcd, events=("end",)):
        if element.tag != "timestep":
            continue
        t = float(element.get("time"))
        if BEGIN <= t <= END and abs(t / PERIOD - round(t / PERIOD)) < 1e-6:
            rows = []
            for v in element:
                if v.tag != "vehicle":
                    continue
                number = numbers.setdefault(v.get("id"), len(numbers))
                x = (float(v.get("x")) - dx + SPAN) / (2 * SPAN)
                y = (float(v.get("y")) - dy + SPAN) / (2 * SPAN)
                rows.append((number, int(round(min(max(x, 0.0), 1.0) * 65535)), int(round(min(max(y, 0.0), 1.0) * 65535)),
                             int(round(min(float(v.get("speed")), 60.0) * 10))))
            rows.sort()
            frames.append((int(round(t)), rows))
        element.clear()
    if len(numbers) > 65535:
        raise RuntimeError("too many vehicles for the file format")
    os.makedirs("web", exist_ok=True)
    with open(os.path.join("web", tag + ".bin"), "wb") as fh:
        fh.write(struct.pack("<I", len(frames)))
        for t, rows in frames:
            fh.write(struct.pack("<II", t, len(rows)))
            fh.write(struct.pack("<%dH" % (4 * len(rows)), *[value for row in rows for value in row]))
    meta = {"label": label, "begin": BEGIN, "end": END, "period": PERIOD, "span": SPAN, "step": float(step),
            "vehicles": len(numbers), "frames": len(frames), "roads": roads(tag)}
    with open(os.path.join("web", tag + ".json"), "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))
    listing = os.path.join("web", "scenarios.json")
    known = json.load(open(listing)) if os.path.exists(listing) else []
    known = [item for item in known if item["tag"] != tag] + [{"tag": tag, "label": label}]
    with open(listing, "w") as fh:
        json.dump(known, fh, indent=1)
    return frames, len(numbers)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "x_base"
    step = sys.argv[2] if len(sys.argv) > 2 else "1.0"
    if not os.path.exists(os.path.join("runs", tag, "trips.xml")):
        print("no scenario called %s in the runs folder" % tag)
        return
    label = LABELS.get(tag, tag)
    print("recording %s (%s), this takes a few minutes..." % (tag, label))
    fcd = simulate(tag, step)
    print("positions written to %s, %.0f MB" % (fcd, os.path.getsize(fcd) / 1e6))
    frames, count = convert(tag, fcd, label, step)
    sizes = [len(rows) for t, rows in frames]
    print("frames: %d, one every %d s, from minute %d to minute %d" % (len(frames), PERIOD, BEGIN // 60, END // 60))
    print("vehicles seen: %d, on the road at once: %d on average, %d at most" % (count, sum(sizes) / len(sizes), max(sizes)))
    print("web/%s.bin written, %.1f MB" % (tag, os.path.getsize(os.path.join("web", tag + ".bin")) / 1e6))
    print("web/scenarios.json now lists: %s" % ", ".join(item["tag"] for item in json.load(open(os.path.join("web", "scenarios.json")))))


if __name__ == "__main__":
    main()