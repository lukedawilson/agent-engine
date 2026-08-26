"""Viz module tests — translation, the pub/sub bus, and the HTTP/SSE server.

Everything here runs real: translation is exercised against a real tiny
StateGraph + MemorySaver, and HTTP/SSE over a real socket on port 0. Only the
three CLI-lifecycle seams (viz.serve_viz / viz.wait_for_interrupt /
webbrowser.open) are stubbed, and only in test_cli.py's main() lifecycle tests.
"""

import http.client
import json
import operator
import queue
import socket
import threading
from typing import Annotated, TypedDict

import pytest

from agent_engine.viz import PAGE, VizBus, serve_viz, translate

MERMAID = "graph TD;\n\tdev(dev)\n\tchecks(checks)\n"


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
        assert translate(tasks_start("checks")) == \
            [{"type": "node_started", "node": "checks"}]

    def test_finish_ok(self):
        assert translate(tasks_finish("checks")) == \
            [{"type": "node_finished", "node": "checks", "ok": True}]

    def test_finish_error(self):
        assert translate(tasks_finish("checks", error="boom")) == \
            [{"type": "node_finished", "node": "checks", "ok": False}]

    def test_updates_drops_non_whitelisted_keys(self):
        delta = {"docs": {"a": "x"}, "context": "long", "notes": ["n"],
                 "commit_allowed": True}
        assert translate(updates(delta)) == [{"type": "state"}]

    def test_updates_keeps_whitelisted_keys(self):
        delta = {"attempt": 2, "step_verdicts": {"checks": "fail"},
                 "outcome": None, "failed": False, "docs": {"a": "x"}}
        assert translate(updates(delta)) == [
            {"type": "state", "attempt": 2,
             "step_verdicts": {"checks": "fail"}, "outcome": None,
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
        assert json.loads(body) == {"mermaid": MERMAID, "subject": "plan plan.md"}

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
        bus.publish({"type": "node_started", "node": "checks"})
        sock, leftover = connect_sse(port)
        frame = read_frame(sock, leftover)
        sock.close()
        assert json.loads(frame.decode().split("data: ", 1)[1].strip()) == \
            {"type": "node_started", "node": "checks"}

    def test_bind_failure_is_loud(self, server):
        _bus, _httpd, _thread, port = server
        with pytest.raises(OSError, match="--viz-port"):
            serve_viz(VizBus(), MERMAID, "subject", port)

    def test_page_constant_has_fallback_hook(self):
        assert "onerror" in PAGE
        assert "mermaid" in PAGE
