"""Petit service de statut pour le portail (bibliothèque standard uniquement).
Expose /status.json : état et temps de réponse des outils + stats du serveur."""
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICES = {
    "pdf": "http://stirling-pdf:8080/",
    "tools": "http://it-tools:80/",
    "drop": "http://pairdrop:3000/",
    "files": "http://filestash:8334/",
    "budget": "http://actual:5006/",
    "auth": "http://authelia:9091/api/health",
}
INTERVAL = 5  # secondes entre deux mesures

state = {"services": {}, "system": {}, "updated": 0}


def check(item):
    key, url = item
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "portal-status"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            up = resp.status < 500
    except urllib.error.HTTPError as err:
        up = err.code < 500
    except Exception:
        up = False
    return key, {"up": up, "ms": round((time.time() - start) * 1000)}


def cpu_times():
    with open("/proc/stat") as f:
        values = list(map(int, f.readline().split()[1:]))
    return values[3] + values[4], sum(values)  # inactif, total


def meminfo():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            name, rest = line.split(":", 1)
            info[name] = int(rest.split()[0]) * 1024
    return info


def system_stats(cpu_pct):
    mem = meminfo()
    total = mem.get("MemTotal", 0)
    used = total - mem.get("MemAvailable", 0)
    swap_total = mem.get("SwapTotal", 0)
    swap_used = swap_total - mem.get("SwapFree", 0)
    disk = shutil.disk_usage("/")
    with open("/proc/loadavg") as f:
        load = [float(x) for x in f.read().split()[:3]]
    with open("/proc/uptime") as f:
        uptime = int(float(f.read().split()[0]))
    return {
        "cpu": round(cpu_pct, 1),
        "mem": {"used": used, "total": total},
        "swap": {"used": swap_used, "total": swap_total},
        "disk": {"used": disk.used, "total": disk.total},
        "load": load,
        "uptime": uptime,
        "cores": os.cpu_count(),
    }


def worker():
    prev_idle, prev_total = cpu_times()
    pool = ThreadPoolExecutor(max_workers=len(SERVICES))
    while True:
        time.sleep(INTERVAL)
        idle, total = cpu_times()
        d_total = total - prev_total
        cpu_pct = 100.0 * (1 - (idle - prev_idle) / d_total) if d_total else 0.0
        prev_idle, prev_total = idle, total
        services = dict(pool.map(check, SERVICES.items()))
        state.update(services=services, system=system_stats(cpu_pct), updated=int(time.time()))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] != "/status.json":
            self.send_error(404)
            return
        body = json.dumps(state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    # première mesure immédiate, puis boucle en arrière-plan
    state["services"] = dict(map(check, SERVICES.items()))
    state["system"] = system_stats(0.0)
    state["updated"] = int(time.time())
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
