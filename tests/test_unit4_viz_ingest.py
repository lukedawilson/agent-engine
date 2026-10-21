"""Unit-4 viz ingest — the token-authenticated stage-event surface (BR-9)."""

from __future__ import annotations

import http.client
import json
import subprocess
from pathlib import Path

from agentic_dev_loop.viz import (VizBus, issue_ingest_token, make_ingest_event,
                                  serve_viz)


def test_make_ingest_event_shape():
    event = make_ingest_event("test", "finished", "3 passed")
    assert event == {"type": "stage", "step": "test", "status": "finished",
                     "output": "3 passed"}


def test_make_ingest_event_is_deterministic():
    a = make_ingest_event("qa", "failed", "boom")
    b = make_ingest_event("qa", "failed", "boom")
    assert a == b


def test_serve_viz_issues_token_by_default():
    bus = VizBus()
    httpd, _thread = serve_viz(bus, "graph TD;", "subject", 0, [])
    try:
        assert httpd.ingest_token
        assert len(httpd.ingest_token) >= 32
    finally:
        httpd.shutdown()


def test_ingest_accepts_valid_token_and_publishes():
    bus = VizBus()
    token = "test-token-123"
    httpd, _thread = serve_viz(bus, "graph TD;", "subject", 0, [],
                               ingest_token=token)
    port = httpd.server_address[1]
    sub = bus.subscribe()
    conn = http.client.HTTPConnection("127.0.0.1", port)
    try:
        event = make_ingest_event("test", "started", "running")
        body = json.dumps(event)
        conn.request("POST", "/ingest", body=body,
                     headers={"Content-Type": "application/json",
                              "X-Ingest-Token": token})
        resp = conn.getresponse()
        assert resp.status == 200
        delivered = sub.get(timeout=2)
        assert delivered["type"] == "stage"
        assert delivered["step"] == "test"
        assert delivered["status"] == "started"
    finally:
        conn.close()
        httpd.shutdown()


def test_ingest_rejects_bad_token():
    bus = VizBus()
    httpd, _thread = serve_viz(bus, "graph TD;", "subject", 0, [],
                               ingest_token="good-token")
    port = httpd.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    try:
        conn.request("POST", "/ingest", body=json.dumps({}),
                     headers={"Content-Type": "application/json",
                              "X-Ingest-Token": "wrong"})
        resp = conn.getresponse()
        assert resp.status == 403
    finally:
        conn.close()
        httpd.shutdown()


def test_ingest_rejects_malformed_json():
    bus = VizBus()
    httpd, _thread = serve_viz(bus, "graph TD;", "subject", 0, [],
                               ingest_token="tok")
    port = httpd.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    try:
        conn.request("POST", "/ingest", body="not json",
                     headers={"Content-Type": "application/json",
                              "X-Ingest-Token": "tok"})
        resp = conn.getresponse()
        assert resp.status == 400
    finally:
        conn.close()
        httpd.shutdown()
