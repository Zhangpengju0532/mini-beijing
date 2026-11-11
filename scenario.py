import os
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
import sumolib

import demand
import network
import sim

PRIORITY = {"arterial": 2, "axis": 3, "ring2": 4, "ring3": 4, "ring4": 4, "radial": 3}
DEFAULTS = {"total": 25000, "open_block": False, "closed": "none", "ring_control": "traffic_light",
            "cycle": 90, "left_green": 12, "av_share": 0.0}
CLOSURES = {
    "none": lambda e, nodes: False,
    "axis_centre": lambda e, nodes: e["kind"] == "axis" and abs(nodes[e["from"]]["x"]) <= 1000 and abs(nodes[e["to"]]["x"]) <= 1000,
    "ring2_north": lambda e, nodes: e["kind"] == "ring2" and nodes[e["from"]]["y"] == 1000 and nodes[e["to"]]["y"] == 1000,
}


def layout(open_block, closed):
    nodes, edges = network.build()
    if open_block:
        x, y = network.PALACE
        key = network.name(x, y)
        nodes[key] = {"x": x, "y": y, "kind": "junction"}
        for other in ((x + network.STEP, y), (x - network.STEP, y), (x, y + network.STEP), (x, y - network.STEP)):
            for start, end in ((key, network.name(*other)), (network.name(*other), key)):
                edges.append({"id": "%s__%s" % (start, end), "from": start, "to": end, "kind": "arterial",
                              "lanes": network.SPEC["arterial"]["lanes"], "speed": network.SPEC["arterial"]["speed"], "length": float(network.STEP)})
    edges = [e for e in edges if not CLOSURES[closed](e, nodes)]
    return nodes, edges


def control(node, kinds, ring_control):
    if node["kind"] == "gate":
        return "priority"
    if any(k.startswith("ring") for k in kinds):
        return ring_control
    return "traffic_light"


def build(tag, options):
    nodes, edges = layout(options["open_block"], options["closed"])
    touching = {key: set() for key in nodes}
    for e in edges:
        touching[e["from"]].add(e["kind"])
        touching[e["to"]].add(e["kind"])
    folder = os.path.join("runs", tag)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.join(folder, "city")
    with open(stem + ".nod.xml", "w") as fh:
        fh.write("<nodes>\n")
        for key, n in nodes.items():
            fh.write('    <node id="%s" x="%.1f" y="%.1f" type="%s"/>\n' % (key, n["x"], n["y"], control(n, touching[key], options["ring_control"])))
        fh.write("</nodes>\n")
    with open(stem + ".typ.xml", "w") as fh:
        fh.write("<types>\n")
        for kind, spec in network.SPEC.items():
            fh.write('    <type id="%s" priority="%d" numLanes="%d" speed="%.2f"/>\n' % (kind, PRIORITY[kind], spec["lanes"], spec["speed"]))
        fh.write("</types>\n")
    with open(stem + ".edg.xml", "w") as fh:
        fh.write("<edges>\n")
        for e in edges:
            fh.write('    <edge id="%s" from="%s" to="%s" type="%s"/>\n' % (e["id"], e["from"], e["to"], e["kind"]))
        fh.write("</edges>\n")
    command = [sumolib.checkBinary("netconvert"), "--node-files", stem + ".nod.xml", "--edge-files", stem + ".edg.xml",
               "--type-files", stem + ".typ.xml", "--output-file", stem + ".net.xml",
               "--roundabouts.guess", "false", "--no-turnarounds.except-deadend", "true",
               "--tls.default-type", "static", "--tls.cycle.time", str(options["cycle"]),
               "--tls.left-green.time", str(options["left_green"]), "--tls.minor-left.max-speed", "28.0",
               "--junctions.corner-detail", "5"]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("netconvert failed: " + " | ".join((done.stdout + done.stderr).strip().splitlines()[-4:]))
    return stem + ".net.xml", nodes, edges


def trips(tag, options, edges):
    rows = demand.trips(options["total"])
    known = {e["id"] for e in edges}
    leaving, entering = {}, {}
    for e in edges:
        leaving.setdefault(e["from"], []).append(e["id"])
        entering.setdefault(e["to"], []).append(e["id"])
    rng = np.random.default_rng(7)
    automated = rng.random(len(rows)) < options["av_share"]
    path = os.path.join("runs", tag, "trips.xml")
    moved = 0
    with open(path, "w") as fh:
        fh.write("<routes>\n")
        fh.write('    <vType id="car" vClass="passenger" sigma="0.5" tau="1.0"/>\n')
        fh.write('    <vType id="av" vClass="passenger" sigma="0.0" tau="0.6" speedDev="0.0" color="0,200,255"/>\n')
        for r, auto in zip(rows, automated):
            start, end = r["from"], r["to"]
            if start not in known:
                start = sorted(leaving[r["origin"]])[0]
                moved += 1
            if end not in known:
                end = sorted(entering[r["destination"]])[0]
                moved += 1
            fh.write('    <trip id="%s" type="%s" depart="%.2f" from="%s" to="%s" departLane="best" departSpeed="max"/>\n' % (
                r["id"], "av" if auto else "car", r["depart"], start, end))
        fh.write("</routes>\n")
    return path, moved


def complete(stats_file):
    if not os.path.exists(stats_file):
        return False
    try:
        performance = ET.parse(stats_file).getroot().find("performance")
    except ET.ParseError:
        return False
    return performance is not None and float(performance.get("end", "0")) >= sim.END - 1


def run(tag, **changes):
    options = dict(DEFAULTS, **changes)
    stats_file = os.path.join("runs", tag, "stats.xml")
    if complete(stats_file):
        result = {"code": 0, "seconds": 0.0, "folder": os.path.join("runs", tag)}
        result.update(sim.read(stats_file))
        return result
    net, nodes, edges = build(tag, options)
    trips_file, moved = trips(tag, options, edges)
    sim.NET = net
    return sim.run(tag, trips_file)