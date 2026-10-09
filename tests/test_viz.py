"""Viz module tests — translation, the pub/sub bus, and the HTTP/SSE server.

Everything here runs real: translation is exercised against a real tiny
StateGraph + MemorySaver, and HTTP/SSE over a real socket on port 0. Only the
two CLI-lifecycle seams (viz.serve_viz / webbrowser.open) are stubbed, and
only in test_cli.py's main() lifecycle tests.
"""

import http.client
import io
import json
import operator
import queue
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Annotated, TypedDict

import pytest

from agent_engine import viz
from agent_engine.config import PipelineConfig, load_config
from agent_engine.viz import (MAX_LINE, PAGE, ConsoleCapture, HeartbeatThread,
                              NodeWatch, VizBus, _Tee, _handler_class,
                              serve_viz, topology_mermaid, translate)

MERMAID = "graph TD;\n\tdev(dev)\n\ttest(test)\n"
SELF_PIPELINE = Path(__file__).parent.parent / "examples" / "self" / "pipeline.yaml"


def tasks_start(name):
    return {"type": "tasks", "ns": (), "data": {"id": "id-1", "name": name,
                                                 "triggers": ("branch:to:x",)}}


def tasks_finish(name, error=None):
    return {"type": "tasks", "ns": (), "data": {"id": "id-1", "name": name,
                                                 "error": error}}


def updates(delta):
    return {"type": "updates", "ns": (), "data": {"n": delta}}


class TestTranslate:
    def test_start_part(self):
        assert translate(tasks_start("test")) == \
            [{"type": "node_started", "node": "test"}]

    def test_finish_ok(self):
        assert translate(tasks_finish("test")) == \
            [{"type": "node_finished", "node": "test", "ok": True}]

    def test_finish_error(self):
        assert translate(tasks_finish("test", error="boom")) == \
            [{"type": "node_finished", "node": "test", "ok": False}]

    def test_updates_drops_non_whitelisted_keys(self):
        delta = {"docs": {"a": "x"}, "context": "long", "notes": ["n"],
                 "commit_allowed": True}
        assert translate(updates(delta)) == [{"type": "state"}]

    def test_updates_keeps_whitelisted_keys(self):
        delta = {"attempt": 2, "step_verdicts": {"test": "fail"},
                 "outcome": None, "failed": False, "docs": {"a": "x"}}
        assert translate(updates(delta)) == [
            {"type": "state", "attempt": 2,
             "step_verdicts": {"test": "fail"}, "outcome": None,
             "failed": False}]

    def test_unknown_parts_are_empty(self):
        assert translate({"type": "custom", "ns": (), "data": {"x": 1}}) == []
        assert translate({"type": "tasks", "ns": (), "data": {"id": "id-1"}}) == []
        assert translate({"type": "updates", "ns": (), "data": {}}) == \
            [{"type": "state"}]

    def test_end_to_end_stream_sequence(self):
        class TinyState(TypedDict):
            vals: Annotated[list[str], operator.add]
            attempt: int

        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, START, StateGraph

        def node_a(state):
            return {"vals": ["a"], "attempt": state.get("attempt", 0) + 1}

        def node_b(_state):
            return {"vals": ["b"]}

        graph = StateGraph(TinyState)
        graph.add_node("a", node_a)
        graph.add_node("b", node_b)
        graph.add_edge(START, "a")
        graph.add_edge("a", "b")
        graph.add_edge("b", END)
        compiled = graph.compile(checkpointer=MemorySaver())

        events = []
        for part in compiled.stream({"vals": [], "attempt": 1},
                                    {"configurable": {"thread_id": "viz-e2e"}},
                                    stream_mode=["tasks", "updates"],
                                    version="v2"):
            events.extend(translate(part))

        assert events == [
            {"type": "node_started", "node": "a"},
            {"type": "state", "attempt": 2},
            {"type": "node_finished", "node": "a", "ok": True},
            {"type": "node_started", "node": "b"},
            {"type": "state"},
            {"type": "node_finished", "node": "b", "ok": True},
        ]


class TestTopologyMermaid:
    def _pipeline(self, steps: list[dict]) -> PipelineConfig:
        return PipelineConfig.model_validate({
            "name": "viz-topology",
            "llm": {"model": "m", "api_key_env": "K"},
            "agents_dir": "sdk_agents",
            "steps": steps,
        })

    def test_shipped_self_loop_topology(self):
        cfg = load_config(SELF_PIPELINE)
        source, nodes = topology_mermaid(cfg)

        chain = ["dev", "review", "port_sweep", "qa", "commit", "success"]
        for src, dst in zip(chain, chain[1:]):
            assert f"{src} --> {dst};" in source

        assert "review -. &nbsp;NEEDS CHANGES&nbsp; .-> dev;" in source
        assert "qa -. &nbsp;FAIL&nbsp; .-> dev;" in source

        assert "__start__" not in source
        assert "__end__" not in source
        assert "bump" not in source
        assert "(dev)" not in source

        assert nodes == chain

    def test_route_on_pass_and_nonretry_fail(self):
        cfg = self._pipeline([{
            "name": "dev",
            "agent": "dev",
            "on_pass": {"goto": "success"},
            "on_fail": "failure",
        }])
        source, nodes = topology_mermaid(cfg)

        assert "dev --> success;" in source
        assert "dev -.-> failure;" in source
        assert nodes == ["dev", "success", "failure"]

    def test_retry_without_verdicts_falls_back_to_retry(self):
        cfg = self._pipeline([{
            "name": "dev",
            "agent": "dev",
            "on_pass": "success",
            "on_fail": {"goto": "dev", "retry": True},
        }])
        source, _nodes = topology_mermaid(cfg)

        assert "dev -. &nbsp;retry&nbsp; .-> dev;" in source


class TestVizBus:
    def test_fanout_to_two_subscribers(self):
        bus = VizBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish({"x": 1})
        assert q1.get(timeout=1) == {"x": 1}
        assert q2.get(timeout=1) == {"x": 1}

    def test_late_subscriber_gets_backlog_in_order(self):
        bus = VizBus(maxlen=10)
        for i in range(3):
            bus.publish({"x": i})
        q = bus.subscribe()
        assert [q.get(timeout=1) for _ in range(3)] == \
            [{"x": 0}, {"x": 1}, {"x": 2}]
        assert q.empty()

    def test_unsubscribe_stops_delivery(self):
        bus = VizBus()
        q = bus.subscribe()
        bus.unsubscribe(q)
        bus.publish({"x": 1})
        assert q.empty()

    def test_backlog_evicts_oldest_beyond_maxlen(self):
        bus = VizBus(maxlen=3)
        for i in range(5):
            bus.publish({"x": i})
        q = bus.subscribe()
        received = []
        while not q.empty():
            received.append(q.get_nowait())
        assert [e["x"] for e in received] == [2, 3, 4]

    def test_concurrent_publish_loses_no_events(self):
        bus = VizBus()
        q = bus.subscribe()
        threads = 10
        per_thread = 20

        def worker(offset):
            for i in range(per_thread):
                bus.publish({"i": offset * per_thread + i})

        workers = [threading.Thread(target=worker, args=(t,))
                   for t in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        received = []
        while not q.empty():
            received.append(q.get_nowait())
        assert len(received) == threads * per_thread
        assert {e["i"] for e in received} == set(range(threads * per_thread))

    def test_console_spam_evicts_only_console(self):
        bus = VizBus()
        bus.publish({"type": "run_started"})
        for i in range(600):
            bus.publish({"type": "console", "text": i})
        bus.publish({"type": "node_started", "node": "dev"})
        q = bus.subscribe()
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        assert [e["type"] for e in events] == \
            ["run_started"] + ["console"] * 500 + ["node_started"]
        console_texts = [e["text"] for e in events if e["type"] == "console"]
        assert console_texts == list(range(100, 600))

    def test_console_maxlen_is_configurable(self):
        bus = VizBus(console_maxlen=2)
        for i in range(5):
            bus.publish({"type": "console", "text": i})
        q = bus.subscribe()
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        assert [e["text"] for e in events] == [3, 4]

    def test_heartbeat_live_only_not_replayed(self):
        bus = VizBus()
        bus.publish({"type": "heartbeat", "node": "dev", "elapsed_seconds": 1})
        q = bus.subscribe()
        assert q.empty()
        bus.publish({"type": "heartbeat", "node": "dev", "elapsed_seconds": 2})
        assert q.get(timeout=1) == \
            {"type": "heartbeat", "node": "dev", "elapsed_seconds": 2}


class StubWatch:
    def __init__(self, node=None):
        self.node = node

    def current(self):
        return self.node


class TestConsoleCapture:
    def _attach(self, bus, watch, monkeypatch):
        out = io.StringIO()
        err = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        cap = ConsoleCapture(bus, watch)
        cap.attach()
        return cap, out, err

    def _events(self, bus):
        q = bus.subscribe()
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        return events

    def test_complete_lines_split_and_attributed(self, monkeypatch):
        bus = VizBus()
        watch = StubWatch("dev")
        cap, out, _err = self._attach(bus, watch, monkeypatch)
        sys.stdout.write("hello\nworld\n")
        cap.detach()
        assert out.getvalue() == "hello\nworld\n"
        assert self._events(bus) == [
            {"type": "console", "node": "dev", "stream": "stdout",
             "text": "hello"},
            {"type": "console", "node": "dev", "stream": "stdout",
             "text": "world"},
        ]

    def test_ansi_preserved_verbatim(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch(None), monkeypatch)
        sys.stdout.write("\x1b[32mhi\x1b[0m\n")
        cap.detach()
        assert self._events(bus)[0]["text"] == "\x1b[32mhi\x1b[0m"

    def test_write_through_to_target(self, monkeypatch):
        bus = VizBus()
        cap, out, err = self._attach(bus, StubWatch("dev"), monkeypatch)
        sys.stdout.write("out\n")
        sys.stderr.write("err\n")
        cap.detach()
        assert out.getvalue() == "out\n"
        assert err.getvalue() == "err\n"
        events = self._events(bus)
        assert {e["stream"] for e in events} == {"stdout", "stderr"}

    def test_partial_writes_join_into_one_line(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch("dev"), monkeypatch)
        sys.stdout.write("hel")
        sys.stdout.write("lo\n")
        cap.detach()
        assert self._events(bus) == [
            {"type": "console", "node": "dev", "stream": "stdout",
             "text": "hello"},
        ]

    def test_crlf_stripped(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch("dev"), monkeypatch)
        sys.stdout.write("hi\r\n")
        cap.detach()
        assert self._events(bus)[0]["text"] == "hi"

    def test_node_attribution_none_is_null(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch(None), monkeypatch)
        sys.stdout.write("idle\n")
        cap.detach()
        assert self._events(bus)[0]["node"] is None

    def test_attach_swap_and_restore(self, monkeypatch):
        bus = VizBus()
        out = io.StringIO()
        err = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        cap = ConsoleCapture(bus, StubWatch(None))
        cap.attach()
        assert sys.stdout is not out
        assert sys.stderr is not err
        cap.detach()
        assert sys.stdout is out
        assert sys.stderr is err

    def test_double_attach_raises(self, monkeypatch):
        bus = VizBus()
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        cap = ConsoleCapture(bus, StubWatch(None))
        cap.attach()
        with pytest.raises(RuntimeError):
            cap.attach()
        cap.detach()

    def test_detach_idempotent(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch(None), monkeypatch)
        cap.detach()
        cap.detach()

    def test_long_line_truncated(self, monkeypatch):
        bus = VizBus()
        cap, _out, _err = self._attach(bus, StubWatch(None), monkeypatch)
        sys.stdout.write("x" * (MAX_LINE + 1) + "\n")
        cap.detach()
        assert self._events(bus)[0]["text"] == "x" * MAX_LINE + "…"

    def test_isatty_delegates_to_target(self):
        class TtyTarget:
            def isatty(self):
                return True

            def write(self, _s):
                return 0

            def flush(self):
                pass

        cap = ConsoleCapture(VizBus(), StubWatch(None))
        tee = _Tee(cap, "stdout", TtyTarget())
        assert tee.isatty() is True


class TestHandleOneRequest:
    def _handler(self):
        return _handler_class(VizBus(), MERMAID, "subject", [])

    def test_swallows_connection_reset(self):
        cls = self._handler()
        handler = cls.__new__(cls)

        class FakeRfile:
            def readline(self, _limit=-1):
                raise ConnectionResetError

        handler.rfile = FakeRfile()
        assert handler.handle_one_request() is None

    def test_propagates_other_errors(self):
        cls = self._handler()
        handler = cls.__new__(cls)

        class FakeRfile:
            def readline(self, _limit=-1):
                raise ValueError("boom")

        handler.rfile = FakeRfile()
        with pytest.raises(ValueError):
            handler.handle_one_request()


class TestNodeWatch:
    def test_idle_before_start(self):
        watch = NodeWatch()
        assert watch.current() is None
        assert watch.elapsed_seconds() is None

    def test_start_then_finish(self):
        watch = NodeWatch()
        watch.start("dev")
        assert watch.current() == "dev"
        assert isinstance(watch.elapsed_seconds(), int)
        watch.finish("dev")
        assert watch.current() is None
        assert watch.elapsed_seconds() is None

    def test_elapsed_grows(self, monkeypatch):
        clock = [0.0]
        monkeypatch.setattr(viz.time, "monotonic", lambda: clock[0])
        watch = NodeWatch()
        watch.start("dev")
        assert watch.elapsed_seconds() == 0
        clock[0] = 26.0
        assert watch.elapsed_seconds() == 26

    def test_finish_only_clears_matching_node(self):
        watch = NodeWatch()
        watch.start("dev")
        watch.finish("test")
        assert watch.current() == "dev"
        watch.finish("dev")
        assert watch.current() is None


class TestHeartbeatThread:
    class StubWatch:
        def __init__(self, node="dev", elapsed=7):
            self._node = node
            self._elapsed = elapsed

        def current(self):
            return self._node

        def elapsed_seconds(self):
            return self._elapsed

    def test_publishes_while_running_and_stops(self):
        bus = VizBus()
        thread = HeartbeatThread(self.StubWatch(), bus, interval=0.01)
        q = bus.subscribe()
        thread.start()
        deadline = time.monotonic() + 0.2
        events = []
        while time.monotonic() < deadline:
            try:
                events.append(q.get(timeout=0.05))
            except queue.Empty:
                pass
        thread.stop()
        thread.join(timeout=1)
        assert not thread.is_alive()

        heartbeats = [e for e in events if e["type"] == "heartbeat"]
        assert len(heartbeats) >= 2
        assert heartbeats[0] == {"type": "heartbeat", "node": "dev",
                                 "elapsed_seconds": 7}
        assert all(e == heartbeats[0] for e in heartbeats)

        while not q.empty():
            q.get_nowait()
        time.sleep(0.05)
        assert q.empty()


@pytest.fixture
def server():
    bus = VizBus()
    httpd, thread = serve_viz(bus, MERMAID, "plan plan.md", 0)
    port = httpd.server_address[1]
    yield bus, httpd, thread, port
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def http_get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return resp.status, body


def connect_sse(port):
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                 b"Accept: text/event-stream\r\n\r\n")
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        assert chunk, "connection closed before response headers"
        data += chunk
    sock.settimeout(5)
    _headers, _sep, leftover = data.partition(b"\r\n\r\n")
    return sock, leftover


def read_frame(sock, leftover=b""):
    data = leftover
    while b"\n\n" not in data:
        chunk = sock.recv(4096)
        assert chunk, "connection closed before SSE frame"
        data += chunk
    return data


class TestServer:
    def test_index_serves_page(self, server):
        _bus, _httpd, _thread, port = server
        status, body = http_get(port, "/")
        assert status == 200
        assert 'id="mermaid-container"' in body
        assert 'id="subject"' in body
        assert "agent-engine pipeline" in body  # topic placeholder

    def test_topology_json_round_trip(self, server):
        _bus, _httpd, _thread, port = server
        status, body = http_get(port, "/topology")
        assert status == 200
        assert json.loads(body) == {"mermaid": MERMAID, "subject": "plan plan.md",
                                    "nodes": []}

    def test_topology_round_trip_includes_nodes(self):
        bus = VizBus()
        httpd, thread = serve_viz(bus, MERMAID, "subject", 0,
                                  ["dev", "success"])
        port = httpd.server_address[1]
        try:
            status, body = http_get(port, "/topology")
            assert status == 200
            assert json.loads(body) == {"mermaid": MERMAID, "subject": "subject",
                                        "nodes": ["dev", "success"]}
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_sse_streams_published_events(self, server):
        bus, _httpd, _thread, port = server
        sock, leftover = connect_sse(port)
        bus.publish({"type": "node_started", "node": "dev"})
        frame = read_frame(sock, leftover)
        sock.close()
        assert json.loads(frame.decode().split("data: ", 1)[1].strip()) == \
            {"type": "node_started", "node": "dev"}

    def test_sse_replays_backlog(self, server):
        bus, _httpd, _thread, port = server
        bus.publish({"type": "node_started", "node": "test"})
        sock, leftover = connect_sse(port)
        frame = read_frame(sock, leftover)
        sock.close()
        assert json.loads(frame.decode().split("data: ", 1)[1].strip()) == \
            {"type": "node_started", "node": "test"}

    def test_bind_failure_is_loud(self, server):
        _bus, _httpd, _thread, port = server
        with pytest.raises(OSError, match="--viz-port"):
            serve_viz(VizBus(), MERMAID, "subject", port)

    def test_connection_reset_on_request_path_is_silent(self, server, monkeypatch):
        _bus, _httpd, _thread, port = server
        captured = io.StringIO()
        monkeypatch.setattr("sys.stderr", captured)
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack("ii", 1, 0))
        sock.close()
        for _ in range(20):
            if "Exception occurred during processing" in captured.getvalue():
                break
            time.sleep(0.05)
        status, _body = http_get(port, "/topology")
        assert status == 200
        assert "Exception occurred during processing" not in captured.getvalue()

    def test_page_constant_has_fallback_hook(self):
        assert "onerror" in PAGE
        assert "mermaid" in PAGE

    def test_page_constant_has_nodes_filter_hook(self):
        assert "nodeIds" in PAGE
        assert "nodeIds.has(n)" in PAGE

    def test_page_constant_has_mobile_media_query(self):
        assert "@media" in PAGE
        assert "max-width: 768px" in PAGE
        assert "flex-direction: column" in PAGE

    def test_page_constant_attempt_fallback_has_no_em_dash(self):
        assert "attempt ?/" in PAGE
        assert "\u2013/\u2013" not in PAGE

    def test_page_constant_logs_only_drawn_nodes(self):
        assert "nodeIds.has(ev.node)" in PAGE

    def test_page_constant_completion_wording(self):
        assert "completed" in PAGE
        assert "errored" in PAGE
        assert "verdict" in PAGE
        assert " passed" not in PAGE

    def test_page_constant_verdict_status_precedence(self):
        assert "statusOf" in PAGE
        assert "verdictFail" in PAGE
        assert "verdictPass" in PAGE

    def test_page_constant_color_palette(self):
        assert 'classDef running fill:#1976d2' in PAGE
        assert 'classDef fail fill:#ffb300' in PAGE
        assert 'classDef fatal fill:#c62828' in PAGE

    def test_page_constant_terminal_failure_marking(self):
        assert "fatalNodes" in PAGE
        assert "ev.failed" in PAGE

    def test_page_constant_has_heartbeat(self):
        assert "heartbeat" in PAGE
        assert "elapsed_seconds" in PAGE
        assert "elapsed" in PAGE

    def test_page_constant_clears_elapsed(self):
        assert "clearElapsed" in PAGE
        assert 'id="elapsed"' in PAGE

    def test_page_constant_buffers_sse_until_topology_ready(self):
        assert "topologyReady" in PAGE
        assert "pendingEvents" in PAGE
        assert "pendingEvents.push(ev)" in PAGE
        assert "pendingEvents.forEach(handle)" in PAGE

    def test_page_constant_flushes_on_topology_failure_and_timeout(self):
        assert "failed to load topology" in PAGE
        assert "topology load timed out" in PAGE
        assert "5000" in PAGE

    def test_page_constant_has_stage_sections(self):
        assert "stage-header" in PAGE
        assert "stage-console" in PAGE
        assert "collapsed" in PAGE

    def test_page_constant_has_console_live_tail(self):
        assert "scrollHeight" in PAGE
        assert "scrollTop" in PAGE
        assert "MAX_CONSOLE" in PAGE
        assert '"console"' in PAGE

    def test_page_constant_routes_console_through_node_guard(self):
        assert "nodeIds.has(ev.node)" in PAGE

    def test_page_constant_has_ansi_renderer(self):
        assert "ansiToHtml" in PAGE
        assert "\\x1b" in PAGE
        assert "38;5" in PAGE
        assert "38;2" in PAGE

    def test_page_constant_restores_running_pulse(self):
        assert ".running > *" in PAGE
        assert "animation: pulse" in PAGE
        assert "@keyframes pulse" in PAGE

    def test_page_constant_stage_placeholder(self):
        assert "stage-placeholder" in PAGE
        assert "No output" in PAGE

    def test_page_constant_console_tail_robust(self):
        assert "nearBottom" in PAGE
        assert "requestAnimationFrame" in PAGE


class TestDemo:
    def test_run_started_carries_attempt(self, monkeypatch):
        import viz_demo

        monkeypatch.setattr(viz_demo.time, "sleep", lambda *_a: None)
        bus = VizBus()
        viz_demo.run_scenario(bus, "success")
        q = bus.subscribe()
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        run_started = next(e for e in events if e["type"] == "run_started")
        assert run_started["attempt"] == 1

    def test_demo_emits_heartbeats(self, monkeypatch):
        import viz_demo

        monkeypatch.setattr(viz_demo.time, "sleep", lambda *_a: None)
        bus = VizBus()
        q = bus.subscribe()  # heartbeats are live-only, never replayed
        viz_demo.run_scenario(bus, "success")
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        heartbeats = [e for e in events if e["type"] == "heartbeat"]
        assert heartbeats
        assert all("node" in e and "elapsed_seconds" in e for e in heartbeats)

    def test_demo_emits_node_console(self, monkeypatch):
        import viz_demo

        monkeypatch.setattr(viz_demo.time, "sleep", lambda *_a: None)
        bus = VizBus()
        q = bus.subscribe()
        viz_demo.run_scenario(bus, "success")
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        consoles = [e for e in events if e["type"] == "console"]
        assert consoles
        assert all(e["stream"] in ("stdout", "stderr") for e in consoles)
        dev_stdout = [e for e in consoles if e["node"] == "dev"
                      and e["stream"] == "stdout"]
        assert dev_stdout
        assert any("Running dev agent..." in e["text"] for e in dev_stdout)
        ansi = [e for e in consoles if e["stream"] == "stderr"]
        assert ansi
        assert any("\x1b[33m" in e["text"] for e in ansi)
        assert any(e["node"] is None for e in consoles)

