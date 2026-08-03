"""Sample consumer tool extension: a Figma read tool for the dev agent.

The library ships no domain tools — consumers register their own via the
Extension API. The example pipeline's dev.agent.md names `figma` in its
frontmatter, so this extension must be loaded for that agent to build.

Wire-up: put this module on the import path (e.g. PYTHONPATH=this dir) and
name it in the pipeline:

    extensions:
      - figma_tool:FigmaExtension

Ported verbatim from yosk's agent-dev-loop/tools.py, minus the built-in
tool re-registrations (agent_engine.agents registers terminal /
file_editor / task_tracker at import).
"""
import json
import os

import httpx

from openhands.sdk.tool import (Action, Observation, ToolDefinition,
                                ToolExecutor)

FIGMA_BASE = "https://api.figma.com/v1"


class FigmaAction(Action):
    file_key: str
    node_id: str | None = None


class FigmaObservation(Observation):
    pass


class FigmaExecutor(ToolExecutor):
    def __call__(self, action: FigmaAction, conversation=None) -> FigmaObservation:
        token = os.environ.get("FIGMA_ACCESS_TOKEN", "")
        if not token:
            return FigmaObservation.from_text(
                "FIGMA_ACCESS_TOKEN not configured.", is_error=True)

        file_key = action.file_key.strip()
        node_id = (action.node_id or "").strip()

        if node_id:
            url = f"{FIGMA_BASE}/files/{file_key}/nodes?ids={node_id}"
        else:
            url = f"{FIGMA_BASE}/files/{file_key}"

        try:
            resp = httpx.get(url, headers={"X-Figma-Token": token}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = json.dumps(data, indent=2)
            if len(text) > 12000:
                if node_id and "nodes" in data:
                    text = json.dumps(data["nodes"], indent=2)
                if len(text) > 12000:
                    text = text[:12000] + "\n\n... (truncated, use node_id to narrow scope)"
            return FigmaObservation.from_text(text)
        except httpx.HTTPStatusError as e:
            body = e.response.text[:1000]
            return FigmaObservation.from_text(
                f"Figma API error {e.response.status_code}: {body}", is_error=True)
        except httpx.HTTPError as e:
            return FigmaObservation.from_text(f"Figma API unreachable: {e}", is_error=True)
        except Exception as e:
            return FigmaObservation.from_text(f"Figma error: {e}", is_error=True)


FIGMA_DESCRIPTION = (
    "Read a Figma design file or a specific component node. "
    "Pass only file_key to get the full file, or file_key + node_id to get a specific node. "
    "Extract file_key from Figma URLs: figma.com/file/FILE_KEY/... or figma.com/design/FILE_KEY/... "
    "Node IDs look like '1:2' and come from ?node-id=1-2 in Figma URLs (replace - with :)."
)


class FigmaTool(ToolDefinition[FigmaAction, FigmaObservation]):
    # name auto-derived: FigmaTool → "figma" (ToolDefinition.__init_subclass__)

    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(description=FIGMA_DESCRIPTION,
                    action_type=FigmaAction,
                    observation_type=FigmaObservation,
                    executor=FigmaExecutor())]


class FigmaExtension:
    name = "figma"

    def register(self, registry) -> None:
        registry.add_tool("figma", FigmaTool)
