import os
import subprocess
import sys

import sumolib

import network

FOLDER = "net"
NET = os.path.join(FOLDER, "mini_beijing.net.xml")
PRIORITY = {"arterial": 2, "axis": 3, "ring2": 4, "ring3": 4, "ring4": 4, "radial": 3}
RING_CONTROL = "traffic_light"
LEFT_GREEN = 12
PERMITTED_LEFT_SPEED = 28.0


def control(key, node, kinds):
    if node["kind"] == "gate":
        return "priority"
    if any(k.startswith("ring") for k in kinds):
        return RING_CONTROL
    return "traffic_light"


def plan():
    nodes, edges = network.build()
    touching = {key: set() for key in nodes}
    for e in edges:
        touching[e["from"]].add(e["kind"])
        touching[e["to"]].add(e["kind"])
    return nodes, edges, {key: control(key, nodes[key], touching[key]) for key in nodes}


def write(nodes, edges, controls):
    os.makedirs(FOLDER, exist_ok=True)
    with open(os.path.join(FOLDER, "mini_beijing.nod.xml"), "w") as fh:
        fh.write("<nodes>\n")
        for key, n in nodes.items():
            fh.write('    <node id="%s" x="%.1f" y="%.1f" type="%s"/>\n' % (key, n["x"], n["y"], controls[key]))
        fh.write("</nodes>\n")
    with open(os.path.join(FOLDER, "mini_beijing.typ.xml"), "w") as fh:
        fh.write("<types>\n")
        for kind, spec in network.SPEC.items():
            fh.write('    <type id="%s" priority="%d" numLanes="%d" speed="%.2f"/>\n' % (kind, PRIORITY[kind], spec["lanes"], spec["speed"]))
        fh.write("</types>\n")
    with open(os.path.join(FOLDER, "mini_beijing.edg.xml"), "w") as fh:
        fh.write("<edges>\n")
        for e in edges:
            fh.write('    <edge id="%s" from="%s" to="%s" type="%s"/>\n' % (e["id"], e["from"], e["to"], e["kind"]))
        fh.write("</edges>\n")


def convert():
    command = [sumolib.checkBinary("netconvert"),
               "--node-files", os.path.join(FOLDER, "mini_beijing.nod.xml"),
               "--edge-files", os.path.join(FOLDER, "mini_beijing.edg.xml"),
               "--type-files", os.path.join(FOLDER, "mini_beijing.typ.xml"),
               "--output-file", NET,
               "--roundabouts.guess", "false",
               "--no-turnarounds.except-deadend", "true",
               "--tls.default-type", "static",
               "--tls.cycle.time", "90",
               "--tls.left-green.time", str(LEFT_GREEN),
               "--tls.minor-left.max-speed", str(PERMITTED_LEFT_SPEED),
               "--junctions.corner-detail", "5"]
    done = subprocess.run(command, capture_output=True, text=True)
    notes = [line for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    return done.returncode, notes


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "view":
        subprocess.run([sumolib.checkBinary("sumo-gui"), "-n", NET])
        return
    nodes, edges, controls = plan()
    write(nodes, edges, controls)
    print("designed: %d nodes, %d edges, %d signalised junctions, %d priority junctions" % (
        len(nodes), len(edges), sum(c == "traffic_light" for c in controls.values()), sum(c == "priority" for c in controls.values())))
    code, notes = convert()
    print("netconvert finished with code %d, %d message lines" % (code, len(notes)))
    for line in notes[:8]:
        print("  " + line)
    if code != 0:
        return
    net = sumolib.net.readNet(NET)
    built = net.getEdges()
    kinds = {}
    for node in net.getNodes():
        kinds[node.getType()] = kinds.get(node.getType(), 0) + 1
    print("built: %d nodes, %d edges, %d lanes, %d traffic light programmes" % (
        len(net.getNodes()), len(built), sum(e.getLaneNumber() for e in built), len(net.getTrafficLights())))
    print("node types in the built network: %s" % ", ".join("%s %d" % item for item in sorted(kinds.items())))
    print("lane length: %.1f km" % (sum(e.getLength() * e.getLaneNumber() for e in built) / 1000.0))
    print("network written to %s" % NET)


main()