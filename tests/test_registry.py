"""Registry + extension-loading tests."""

import pytest

from agent_engine import actions
from agent_engine.registry import Registry, default_registry, load_extensions


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
        assert reg.actions["kill_listeners"] is actions.kill_listeners
        assert reg.actions["commit"] is actions.commit


class TestActionRegistration:
    def test_duplicate_action_name_raises(self):
        reg = Registry()
        reg.add_action("x", lambda s, p: {})
        with pytest.raises(ValueError, match="'x'"):
            reg.add_action("x", lambda s, p: {})


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
