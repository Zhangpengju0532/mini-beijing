import hashlib
import html
import json
import os
import time
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import s4_map
import scenario
import sim

PORT = 8770
FIELDS = [
    ("total", "Trips in the morning peak", ["15000", "20000", "25000", "30000"]),
    ("open_block", "Central block", [("no", "closed to traffic"), ("yes", "opened")]),
    ("closed", "Road closure", [("none", "none"), ("axis_centre", "east-west axis, centre"), ("ring2_north", "ring 2, north side")]),
    ("ring_control", "Ring junctions", [("traffic_light", "signals"), ("priority", "no signals")]),
    ("cycle", "Signal cycle (s)", ["60", "90", "120"]),
    ("left_green", "Left-turn green (s)", ["6", "12", "18"]),
    ("av_share", "Automated vehicles (%)", ["0", "25", "50", "75", "100"]),
]
START = {"total": "25000", "open_block": "no", "closed": "none", "ring_control": "traffic_light", "cycle": "90", "left_green": "12", "av_share": "0"}
STATE = {"form": dict(START), "result": None, "message": ""}
plain_run = sim.run

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mini-Beijing traffic lab</title>
<style>
body {{ margin: 0; background: #f4f5f8; color: #1d2433; font-family: "Segoe UI", system-ui, Arial, sans-serif; }}
main {{ display: flex; flex-wrap: wrap; gap: 24px; padding: 24px; max-width: 1280px; margin: 0 auto; align-items: flex-start; }}
form, .card {{ background: #ffffff; border: 1px solid #dfe2ea; border-radius: 6px; padding: 18px 20px; }}
form {{ width: 320px; }}
.stage {{ flex: 1; min-width: 520px; display: flex; flex-direction: column; gap: 18px; }}
h1 {{ font-size: 19px; margin: 0 0 4px 0; font-weight: 600; }}
h2 {{ font-size: 14px; margin: 0 0 10px 0; font-weight: 600; }}
p.sub {{ font-size: 12.5px; color: #5b6478; margin: 0 0 14px 0; line-height: 1.5; }}
label {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; margin: 9px 0; font-size: 13.5px; }}
select {{ width: 168px; padding: 5px 6px; font-size: 13.5px; border: 1px solid #c9cedb; border-radius: 4px; background: #ffffff; }}
button {{ margin-top: 14px; width: 100%; padding: 10px; font-size: 14.5px; background: #1f5fae; color: #ffffff; border: 0; border-radius: 4px; cursor: pointer; }}
button:disabled {{ background: #8d97ad; cursor: wait; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: right; padding: 6px 8px; border-bottom: 1px solid #eceef3; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ font-weight: 600; color: #5b6478; font-size: 12.5px; }}
.better {{ color: #1c7c54; }}
.worse {{ color: #b3261e; }}
.note {{ font-size: 12.5px; color: #5b6478; line-height: 1.5; margin-top: 10px; }}
.warn {{ background: #fff4e0; border: 1px solid #f0c36d; border-radius: 4px; padding: 8px 10px; font-size: 13px; margin-bottom: 12px; }}
.message {{ font-size: 13px; color: #5b6478; min-height: 18px; margin-top: 10px; }}
img {{ width: 100%; }}
</style>
</head>
<body>
<main>
<form method="post" action="/run" onsubmit="var b = document.getElementById('go'); b.disabled = true; b.textContent = 'Simulating, 2 to 6 minutes...';">
<h1>Mini-Beijing traffic lab</h1>
<p class="sub">Change one setting, run the morning peak, and compare with the calibrated baseline. A scenario that was run before is read from disk.</p>
{fields}
<button id="go" type="submit">Run scenario</button>
<div class="message">{message}</div>
</form>
<div class="stage">
{result}
</div>
</main>
</body>
</html>
"""


def options(form):
    return {"total": int(form["total"]), "open_block": form["open_block"] == "yes", "closed": form["closed"],
            "ring_control": form["ring_control"], "cycle": int(form["cycle"]), "left_green": int(form["left_green"]),
            "av_share": int(form["av_share"]) / 100.0}


def execute(tag, changes, step):
    def detailed(run_tag, trips_file, extra=()):
        extra_file = os.path.join("runs", run_tag, "extra.add.xml")
        with open(extra_file, "w") as fh:
            fh.write('<additional>\n    <edgeData id="roads" file="edgedata.xml" period="%d"/>\n</additional>\n' % s4_map.PERIOD)
        return plain_run(run_tag, trips_file, list(extra) + ["--step-length", step, "--additional-files", extra_file])
    sim.run = detailed
    try:
        return scenario.run(tag, **changes)
    finally:
        sim.run = plain_run


def measures(tag, r):
    safety = ET.parse(os.path.join("runs", tag, "stats.xml")).getroot().find("safety")
    crashes = int(float(safety.get("collisions", "0"))) if safety is not None else 0
    trip, wait = r["duration"] / 60.0, r["depart_delay"] / 60.0
    return {"total": trip + wait, "trip": trip, "wait": wait, "km": r["length"] / 1000.0, "speed": r["length"] / r["duration"] * 3.6,
            "lost": r["loss"] / 60.0, "unfinished": 100.0 * (r["loaded"] - r["arrived"]) / r["loaded"], "teleports": r["teleports"],
            "crashes": crashes, "loaded": r["loaded"]}


def draw(tag, chosen):
    data_file = os.path.join("runs", tag, "edgedata.xml")
    if not os.path.exists(data_file):
        return False
    nodes, edges = scenario.layout(chosen["open_block"], chosen["closed"])
    by_id = {e["id"]: e for e in edges}
    peak = s4_map.load(data_file).get(s4_map.PEAK[0], {})
    lines = s4_map.segments(nodes, edges)
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.4))
    s4_map.panel(axes[0], lines, {k: 100.0 * v[0] / by_id[k]["speed"] for k, v in peak.items() if k in by_id}, 0, 100,
                 "Speed in the peak quarter hour", "speed as a share of the limit (%)", "YlOrRd_r")
    s4_map.panel(axes[1], lines, {k: v[1] / s4_map.PERIOD / (by_id[k]["length"] * by_id[k]["lanes"] / 1000.0) for k, v in peak.items() if k in by_id}, 0, 120,
                 "Density in the peak quarter hour", "vehicles per km of lane", "YlOrRd")
    axes[0].set_ylabel("north (km)")
    fig.tight_layout()
    fig.savefig(os.path.join("runs", tag, "map.png"), dpi=110)
    plt.close(fig)
    return True


def make(form):
    chosen = options(form)
    step = "0.5" if chosen["av_share"] > 0 else "1.0"
    key = json.dumps([chosen, step], sort_keys=True)
    tag = "p_" + hashlib.sha1(key.encode()).hexdigest()[:10]
    started = time.time()
    reference_tag = "p_reference_" + step.replace(".", "")
    reference = execute(reference_tag, {}, step)
    result = execute(tag, chosen, step)
    if reference["code"] != 0 or result["code"] != 0:
        STATE["message"] = "The simulation failed: " + " | ".join((result.get("error") or reference.get("error") or [])[-3:])
        return
    STATE["result"] = {"tag": tag, "now": measures(tag, result), "base": measures(reference_tag, reference), "map": draw(tag, chosen), "step": step}
    STATE["message"] = "Finished in %.0f s." % (time.time() - started)
    print("scenario %s finished in %.0f s" % (tag, time.time() - started))


def fields():
    out = []
    for key, label, choices in FIELDS:
        items = []
        for choice in choices:
            value, text = choice if isinstance(choice, tuple) else (choice, choice)
            items.append('<option value="%s"%s>%s</option>' % (value, " selected" if STATE["form"][key] == value else "", html.escape(text)))
        out.append('<label>%s<select name="%s">%s</select></label>' % (html.escape(label), key, "".join(items)))
    return "\n".join(out)


def result():
    r = STATE["result"]
    if r is None:
        return '<div class="card"><h2>No scenario yet</h2><div class="note">Choose the settings on the left and press the button. The first run also simulates the baseline, so it takes twice as long.</div></div>'
    now, base = r["now"], r["base"]
    rows = [("Time per trip, door to door (min)", "total", "%.1f", True), ("of which driving (min)", "trip", "%.1f", True),
            ("of which waiting to enter the network (min)", "wait", "%.1f", True), ("Time lost against free flow (min)", "lost", "%.1f", True),
            ("Trip length (km)", "km", "%.2f", False), ("Mean speed (km/h)", "speed", "%.1f", False),
            ("Trips not finished (%)", "unfinished", "%.1f", False), ("Teleports", "teleports", "%d", False), ("Collisions", "crashes", "%d", False)]
    body = []
    for label, key, pattern, compare in rows:
        change = ""
        if compare and base[key] > 0:
            delta = 100.0 * (now[key] / base[key] - 1.0)
            change = '<span class="%s">%+.1f%%</span>' % ("better" if delta < 0 else "worse", delta)
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (label, pattern % base[key], pattern % now[key], change))
    problems = []
    for name, side in (("baseline", base), ("scenario", now)):
        if side["crashes"] > 0.001 * side["loaded"]:
            problems.append("%s: %d collisions, the car-following settings are not safe at this step length" % (name, side["crashes"]))
        if side["teleports"] > 0.01 * side["loaded"]:
            problems.append("%s: %d teleports, more than 1%% of the vehicles" % (name, side["teleports"]))
        if side["unfinished"] > 2.0:
            problems.append("%s: %.1f%% of the trips did not finish, so the averages cover only the vehicles that arrived" % (name, side["unfinished"]))
    warning = '<div class="warn">Read these numbers with care. %s.</div>' % "; ".join(problems) if problems else ""
    table = '<div class="card"><h2>Scenario against the baseline</h2>%s<table><tr><th>Measure</th><th>Baseline</th><th>Scenario</th><th>Change</th></tr>%s</table><div class="note">Baseline: 25000 trips, central block closed, signals on the rings, 90 s cycle, 12 s left-turn green, human drivers. Simulation step %s s%s.</div></div>' % (
        warning, "".join(body), r["step"], ", used for both runs because automated vehicles follow at 0.6 s" if r["step"] == "0.5" else "")
    picture = '<div class="card"><h2>Where the congestion is</h2><img src="/map/%s.png" alt="Speed and density by road in the peak quarter hour"></div>' % r["tag"] if r["map"] else ""
    return table + picture


class Handler(BaseHTTPRequestHandler):
    def send(self, body, kind, status=200):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/map/"):
            tag = self.path[5:].split(".")[0]
            path = os.path.join("runs", tag, "map.png")
            if tag.replace("_", "").isalnum() and os.path.exists(path):
                with open(path, "rb") as fh:
                    self.send(fh.read(), "image/png")
                return
        if self.path == "/" or self.path.startswith("/?"):
            self.send(PAGE.format(fields=fields(), result=result(), message=html.escape(STATE["message"])).encode("utf-8"), "text/html; charset=utf-8")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        sent = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        form = dict(START)
        for key, label, choices in FIELDS:
            allowed = [c[0] if isinstance(c, tuple) else c for c in choices]
            value = sent.get(key, [START[key]])[0]
            form[key] = value if value in allowed else START[key]
        STATE["form"] = form
        try:
            make(form)
        except Exception as problem:
            STATE["message"] = "The scenario could not be run: %s" % problem
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    address = "http://127.0.0.1:%d/" % PORT
    print("panel running at", address)
    print("press Ctrl+C in this terminal to stop it")
    try:
        webbrowser.open(address)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("panel stopped")


if __name__ == "__main__":
    main()