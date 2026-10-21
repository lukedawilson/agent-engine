"""Registry + extension-loading tests."""

import pytest

from agentic_dev_loop.engine import actions
from agentic_dev_loop.engine.registry import Registry, default_registry, load_extensions
from sample_ext import SampleTool


class _Loader:
    """Minimal document loader carrying one CLI option string."""

    def __init__(self, name: str, option: str, defaultable: bool = False):
        self.name = name
        self.option = option
        self.defaultable = defaultable

    def add_cli_args(self, parser):
        parser.add_argument(self.option)

    def resolve(self, args):  # pragma: no cover - selection flow is Task 7
        raise NotImplementedError


class TestBuiltinRegistration:
    def test_default_registry_has_builtin_actions(self):
        reg = default_registry()
        assert reg.actions["commit"] is actions.commit

    def test_kill_listeners_action_not_registered(self):
        """The port_sweep pipeline step that used the node-shaped wrapper is
        gone; the startup sweep calls kill_listeners_on_port directly."""
        assert "kill_listeners" not in default_registry().actions


class TestActionRegistration:
    def test_duplicate_action_name_raises(self):
        reg = Registry()
        reg.add_action("x", lambda s, p: {})
        with pytest.raises(ValueError, match="'x'"):
            reg.add_action("x", lambda s, p: {})


class TestToolRegistration:
    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="valid identifier"):
            Registry().add_tool("", SampleTool)

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValueError, match="valid identifier"):
            Registry().add_tool("  sample  ", SampleTool)

    def test_collision_with_sdk_registry_rejected(self):
        reg = Registry()
        reg.add_tool("proc_unique_tool", SampleTool)
        with pytest.raises(ValueError, match="already"):
            reg.add_tool("proc_unique_tool", SampleTool)

    def test_collision_via_extension_names_the_extension_and_owner(self):
        load_extensions(["sample_ext:CollisionExtension"], Registry())
        with pytest.raises(ValueError) as excinfo:
            load_extensions(["sample_ext:CollisionExtension"], Registry())
        message = str(excinfo.value)
        assert "collision-extension" in message
        assert "sample_ext" in message


class TestDocumentLoaderRegistration:
    def test_records_contributed_cli_options(self):
        reg = Registry()
        reg.add_document_loader(_Loader("alpha", "--alpha-flag"))
        assert reg.cli_option_owners["--alpha-flag"] == "alpha"

    def test_duplicate_cli_option_names_both_loaders(self):
        reg = Registry()
        reg.add_document_loader(_Loader("alpha", "--shared"))
        with pytest.raises(ValueError) as excinfo:
            reg.add_document_loader(_Loader("beta", "--shared"))
        message = str(excinfo.value)
        assert "alpha" in message and "beta" in message and "--shared" in message


class TestLoadExtensions:
    def test_fixture_extension_action_becomes_invocable(self):
        reg = Registry()
        load_extensions(["sample_ext:SampleExtension"], reg)
        assert reg.actions["sample_action"]({"s": 1}, {}) == {"ran": True}

    def test_extension_tool_registers_with_sdk(self):
        from openhands.sdk.tool import registry as sdk_registry
        reg = Registry()
        load_extensions(["sample_ext:ToolExtension"], reg)
        assert "sample" in sdk_registry.list_registered_tools()

    @pytest.mark.parametrize("ref", ["no_colon", ":NoModule", "nope:"])
    def test_malformed_ref_raises_naming_it(self, ref):
        with pytest.raises(ValueError) as excinfo:
            load_extensions([ref], Registry())
        assert ref in str(excinfo.value)

    def test_unknown_module_raises_naming_the_ref(self):
        with pytest.raises(ValueError) as excinfo:
            load_extensions(["no_such_module_xyz:Thing"], Registry())
        assert "no_such_module_xyz:Thing" in str(excinfo.value)

    def test_unknown_class_raises_naming_the_ref(self):
        with pytest.raises(ValueError) as excinfo:
            load_extensions(["sample_ext:NoSuchClass"], Registry())
        assert "sample_ext:NoSuchClass" in str(excinfo.value)

    def test_instantiation_failure_raises_naming_the_ref(self):
        with pytest.raises(ValueError) as excinfo:
            load_extensions(["sample_ext:BoomExtension"], Registry())
        assert "sample_ext:BoomExtension" in str(excinfo.value)
