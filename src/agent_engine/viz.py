"""Live graph visualization: StreamPart translation, a thread-safe event
bus, and a stdlib-only HTTP/SSE server serving an embedded Mermaid page.

The graph itself is untouched — every live update is derived from LangGraph's
``tasks``/``updates`` stream modes. The viz surface is opt-in (``--viz``); the
only dependencies are the Python standard library and Mermaid.js v11 served
from a CDN by the browser.
"""

from __future__ import annotations

import json
import queue
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE_WHITELIST = ("attempt", "step_verdicts", "outcome", "failed")


def translate(part: dict) -> list[dict]:
    """Translate one v2 StreamPart into zero or more viz event dicts.

    ``tasks`` parts pair up by id: a part whose data carries ``triggers`` is a
    node start; one carrying ``error`` is the matching finish (``error`` is
    ``None`` on success). ``updates`` parts carry one LoopState delta per node
    and collapse to a single ``state`` event holding only whitelisted keys —
    ``docs``/``context``/``notes`` are large or internal and never shipped.
    """
    ptype = part.get("type")
    data = part.get("data")
    if not isinstance(data, dict):
        return []
    if ptype == "tasks":
        if "triggers" in data and "name" in data:
            return [{"type": "node_started", "node": data["name"]}]
        if "error" in data and "name" in data:
            return [{"type": "node_finished", "node": data["name"],
                     "ok": data["error"] is None}]
        return []
    if ptype == "updates":
        state: dict = {}
        for delta in data.values():
            if not isinstance(delta, dict):
                continue
            for key in STATE_WHITELIST:
                if key in delta:
                    state[key] = delta[key]
        return [{"type": "state", **state}]
    return []


class VizBus:
    """Thread-safe pub/sub with a bounded backlog.

    Nodes publish from the pipeline thread; each SSE connection consumes from
    its own thread. New subscribers first receive the backlog in order, so a
    browser tab opened mid-run catches up; ``maxlen`` bounds memory.
    """

    def __init__(self, maxlen: int = 500) -> None:
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._backlog: deque = deque(maxlen=maxlen)

    def publish(self, event: dict) -> None:
        with self._lock:
            self._backlog.append(event)
            subscribers = list(self._subscribers)
        for sub in subscribers:
            sub.put(event)

    def subscribe(self) -> queue.Queue:
        sub: queue.Queue = queue.Queue()
        with self._lock:
            for event in self._backlog:
                sub.put(event)
            self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(sub)


def _handler_class(bus: VizBus, topology_mermaid: str,
                   subject: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        viz_bus = bus
        viz_topology = topology_mermaid
        viz_subject = subject

        def log_message(self, *_args) -> None:  # keep test output quiet
            pass

        def do_GET(self) -> None:
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE)
            elif self.path == "/topology":
                body = json.dumps({"mermaid": self.viz_topology,
                                   "subject": self.viz_subject})
                self._send(200, "application/json", body)
            elif self.path == "/events":
                self._events()
            else:
                self.send_error(404)

        def _send(self, status: int, content_type: str, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            sub = self.viz_bus.subscribe()
            try:
                while True:
                    try:
                        event = sub.get(timeout=15)
                    except queue.Empty:
                        self.wfile.write(b":hb\n\n")
                        self.wfile.flush()
                        continue
                    frame = f"data: {json.dumps(event)}\n\n".encode("utf-8")
                    self.wfile.write(frame)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                self.viz_bus.unsubscribe(sub)

    return Handler


def serve_viz(bus: VizBus, topology_mermaid: str, subject: str,
              port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Bind a loopback HTTP server on ``port`` and serve it on a daemon
    thread. Returns ``(httpd, thread)``. Bind failure is loud and names
    ``--viz-port`` — the caller must never fall back to another port."""
    handler = _handler_class(bus, topology_mermaid, subject)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise OSError(
            f"Could not bind the viz server to 127.0.0.1:{port} — the "
            f"--viz-port may already be in use. ({exc})") from exc
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def wait_for_interrupt() -> None:
    """Block until Ctrl-C, then return — keeps the viz server alive after the
    pipeline finishes so the final graph stays inspectable."""
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-engine viz</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
         Roboto, Helvetica, Arial, sans-serif; display: flex; height: 100vh; }
  #graph-panel { flex: 1 1 auto; padding: 16px; overflow: auto; display: flex;
                 flex-direction: column; }
  #mermaid-container { flex: 1 1 auto; }
  #mermaid-container svg { max-width: 100%; height: auto; }
  #run-banner { font-size: 18px; font-weight: 700; padding: 10px 14px;
                border-radius: 6px; margin-top: 10px; display: none; }
  .banner-success { background: #e8f5e9; color: #2e7d32; }
  .banner-failure { background: #ffebee; color: #c62828; }
  #sidebar { flex: 0 0 320px; border-left: 1px solid #e0e0e0; padding: 16px;
             display: flex; flex-direction: column; gap: 12px; overflow: hidden; }
  #subject { margin: 0; font-size: 16px; word-break: break-word; }
  #attempt { font-size: 14px; color: #555; }
  #verdicts { display: flex; flex-wrap: wrap; gap: 6px; }
  .badge { font-size: 12px; padding: 3px 8px; border-radius: 10px;
           background: #f0f0f0; color: #333; }
  .badge-pass { background: #e8f5e9; color: #2e7d32; }
  .badge-fail { background: #ffebee; color: #c62828; }
  .badge-unclear { background: #fff8e1; color: #f57f17; }
  #log { list-style: none; margin: 0; padding: 0; flex: 1 1 auto; overflow-y: auto;
         font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  #log li { padding: 2px 0; border-bottom: 1px solid #f3f3f3; }
  .running > * { animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
        onerror="window.__mermaidFailed=true"></script>
</head>
<body>
  <div id="graph-panel">
    <div id="mermaid-container"><p>Loading graph…</p></div>
    <div id="run-banner"></div>
  </div>
  <aside id="sidebar">
    <h2 id="subject">agent-engine pipeline</h2>
    <div id="attempt">attempt –/–</div>
    <div id="verdicts"></div>
    <ul id="log"></ul>
  </aside>
<script>
(function () {
  var nodeStatus = {};
  var verdictSteps = new Set();
  var currentVerdicts = {};
  var maxAttempts = null;
  var attempt = null;
  var mermaidSource = null;
  var renderCount = 0;
  var mermaidFailed = !!window.__mermaidFailed;

  function el(id) { return document.getElementById(id); }

  function logLine(text) {
    var li = document.createElement("li");
    li.textContent = text;
    var log = el("log");
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
  }

  function updateAttempt() {
    el("attempt").textContent = attempt === null
      ? "attempt \u2013/\u2013"
      : "attempt " + attempt + "/" + (maxAttempts === null ? "?" : maxAttempts);
  }

  function updateBadges() {
    var box = el("verdicts");
    box.innerHTML = "";
    Array.from(verdictSteps).forEach(function (step) {
      var b = document.createElement("span");
      var v = currentVerdicts[step];
      b.className = "badge";
      if (v === "pass") b.className += " badge-pass";
      else if (v === "fail") b.className += " badge-fail";
      else b.className += " badge-unclear";
      b.textContent = step + ": " + (v === null || v === undefined ? "unclear" : v);
      box.appendChild(b);
    });
  }

  function renderGraph() {
    var container = el("mermaid-container");
    if (mermaidFailed || typeof mermaid === "undefined" || !mermaidSource) {
      container.innerHTML = "<p>Graph unavailable (mermaid CDN unreachable) "
        + "\u2014 the event log below is still live.</p>";
      return;
    }
    var classDefs = [
      "classDef running fill:#ffb300,stroke:#ffb300,color:#fff",
      "classDef passed fill:#2e7d32,stroke:#2e7d32,color:#fff",
      "classDef failed fill:#c62828,stroke:#c62828,color:#fff",
      "classDef pending fill:#f2f0ff,stroke:#555,color:#000"
    ];
    var classLines = Object.keys(nodeStatus).map(function (n) {
      return "class " + n + " " + (nodeStatus[n] || "pending") + ";";
    });
    var src = mermaidSource + "\\n" + classDefs.join("\\n") + "\\n" + classLines.join("\\n");
    mermaid.render("graph-" + (renderCount++), src).then(function (res) {
      container.innerHTML = res.svg;
      if (res.bindFunctions) { res.bindFunctions(container); }
    }).catch(function (err) {
      container.innerHTML = "<p>Graph render failed.</p>";
      logLine("graph render failed: " + err);
    });
  }

  function handle(ev) {
    switch (ev.type) {
      case "run_started":
        maxAttempts = ev.max_attempts;
        el("subject").textContent = ev.subject;
        logLine("run started: " + ev.subject + " (thread " + ev.thread_id + ")");
        updateAttempt();
        break;
      case "node_started":
        nodeStatus[ev.node] = "running";
        logLine("\u25b6 " + ev.node + " running");
        renderGraph();
        break;
      case "node_finished":
        nodeStatus[ev.node] = ev.ok ? "passed" : "failed";
        logLine((ev.ok ? "\u2714 " : "\u2718 ") + ev.node
          + (ev.ok ? " passed" : " failed"));
        renderGraph();
        break;
      case "state":
        if (ev.attempt !== undefined) { attempt = ev.attempt; }
        if (ev.step_verdicts !== undefined) {
          Object.keys(ev.step_verdicts).forEach(function (k) { verdictSteps.add(k); });
          currentVerdicts = ev.step_verdicts;
          updateBadges();
        }
        if (ev.failed) { logLine("state: failed"); }
        updateAttempt();
        break;
      case "run_finished":
        logLine("run finished: " + (ev.success ? "success" : "failure"));
        var banner = el("run-banner");
        banner.textContent = ev.success ? "\u2713 SUCCESS" : "\u2718 FAILURE";
        banner.className = ev.success ? "banner-success" : "banner-failure";
        banner.style.display = "block";
        break;
    }
  }

  fetch("/topology").then(function (r) { return r.json(); }).then(function (d) {
    el("subject").textContent = d.subject;
    mermaidSource = d.mermaid;
    if (!mermaidFailed && typeof mermaid !== "undefined") {
      mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
    }
    renderGraph();
  }).catch(function () { logLine("failed to load topology"); });

  var es = new EventSource("/events");
  es.onmessage = function (e) {
    try { handle(JSON.parse(e.data)); }
    catch (err) { logLine("bad event: " + e.data); }
  };
  es.onerror = function () { logLine("event stream interrupted"); };
})();
</script>
</body>
</html>
"""
