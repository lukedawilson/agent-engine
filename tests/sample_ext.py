"""Fixture extension module for test_registry — imported by ref string
('sample_ext:SampleExtension') exactly the way consumer extensions load."""

from openhands.sdk.tool import Action, Observation, ToolDefinition, ToolExecutor


class SampleExtension:
    name = "sample"

    def register(self, registry):
        registry.add_action("sample_action", lambda state, params: {"ran": True})


class BoomExtension:
    name = "boom"

    def __init__(self):
        raise RuntimeError("constructor exploded")

    def register(self, registry):
        pass


class SampleAction(Action):
    pass


class SampleObservation(Observation):
    pass


class SampleExecutor(ToolExecutor):
    def __call__(self, action, conversation=None):
        return SampleObservation.from_text("ok")


class SampleTool(ToolDefinition[SampleAction, SampleObservation]):
    # name auto-derived: SampleTool -> "sample" (ToolDefinition.__init_subclass__)

    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(description="sample",
                    action_type=SampleAction,
                    observation_type=SampleObservation,
                    executor=SampleExecutor())]


class ToolExtension:
    name = "tool-sample"

    def register(self, registry):
        registry.add_tool("sample", SampleTool)


class EmptyDocsLoader:
    """Loader whose resolve returns no docs — pins the U3 empty-load guard
    at the run_pipeline call site."""

    name = "empty"
    defaultable = False

    def add_cli_args(self, parser):
        parser.add_argument("--empty", action="store_true", default=None)

    def resolve(self, args):
        return {}, "empty subject"


class EmptyLoaderExtension:
    name = "empty-loader"

    def register(self, registry):
        registry.add_document_loader(EmptyDocsLoader())
