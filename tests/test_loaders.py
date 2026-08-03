"""Plan document loader + selection-flow tests."""

import argparse
from pathlib import Path

import pytest

from agent_engine.loaders import PlanDocumentLoader, resolve_plan_docs, select_loader
from agent_engine.registry import Registry, default_registry


class _Loader:
    def __init__(self, name, option, dest, defaultable=False):
        self.name = name
        self.option = option
        self.dest = dest
        self.defaultable = defaultable

    def add_cli_args(self, parser):
        parser.add_argument(self.option, dest=self.dest, default=None)

    def resolve(self, args):  # pragma: no cover
        raise NotImplementedError


def _args(**kw):
    return argparse.Namespace(**kw)


class TestResolvePlanDocs:
    def test_loads_plan_file_keyed_by_filename(self, tmp_path):
        plan = tmp_path / "001-scan-crawl.md"
        plan.write_text("# Plan\nDo the things.")

        docs = resolve_plan_docs(plan)

        assert docs == {"001-scan-crawl.md": "# Plan\nDo the things."}

    def test_accepts_string_path(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text("# Plan")

        assert resolve_plan_docs(str(plan)) == {"plan.md": "# Plan"}

    def test_raises_for_missing_plan(self, tmp_path):
        """Missing plan file must fail fast — no silent fallback to empty docs."""
        with pytest.raises(FileNotFoundError, match="plan"):
            resolve_plan_docs(tmp_path / "nonexistent.md")


class TestPlanDocumentLoader:
    def test_is_not_defaultable(self):
        assert PlanDocumentLoader.defaultable is False

    def test_contributes_plan_flag(self):
        reg = Registry()
        reg.add_document_loader(PlanDocumentLoader())
        assert reg.cli_option_owners["--plan"] == "plan"
        assert reg.cli_dests["plan"] == "plan"

    def test_resolve_returns_docs_and_plan_subject(self, tmp_path):
        plan = tmp_path / "009-export.md"
        plan.write_text("# Export")

        docs, subject = PlanDocumentLoader().resolve(_args(plan=plan))

        assert docs == {"009-export.md": "# Export"}
        assert subject == "plan 009-export.md"

    def test_default_registry_preregisters_plan_loader(self):
        reg = default_registry()
        assert [l.name for l in reg.document_loaders] == ["plan"]


class TestSelectLoader:
    def _registry_with(self, *loaders):
        reg = Registry()
        for loader in loaders:
            reg.add_document_loader(loader)
        return reg

    def test_flag_selects_its_loader(self):
        plan = _Loader("plan", "--plan", "plan")
        aidlc = _Loader("ai-dlc", "--ai-dlc-unit", "ai_dlc_unit", defaultable=True)
        reg = self._registry_with(plan, aidlc)

        assert select_loader(reg, _args(plan=Path("p.md"), ai_dlc_unit=None)) is plan
        assert select_loader(reg, _args(plan=None, ai_dlc_unit="U3")) is aidlc

    def test_flags_from_two_loaders_error_naming_both(self):
        reg = self._registry_with(
            _Loader("plan", "--plan", "plan"),
            _Loader("ai-dlc", "--ai-dlc-unit", "ai_dlc_unit", defaultable=True))

        with pytest.raises(ValueError) as excinfo:
            select_loader(reg, _args(plan=Path("p.md"), ai_dlc_unit="U3"))

        message = str(excinfo.value)
        assert "plan" in message and "ai-dlc" in message

    def test_sole_defaultable_autoruns_with_no_flag(self):
        aidlc = _Loader("ai-dlc", "--ai-dlc-unit", "ai_dlc_unit", defaultable=True)
        reg = self._registry_with(_Loader("plan", "--plan", "plan"), aidlc)

        assert select_loader(reg, _args(plan=None, ai_dlc_unit=None)) is aidlc

    def test_none_defaultable_returns_none_with_no_flag(self):
        reg = self._registry_with(_Loader("plan", "--plan", "plan"))

        assert select_loader(reg, _args(plan=None)) is None

    def test_multiple_defaultables_error(self):
        reg = self._registry_with(
            _Loader("a", "--a", "a", defaultable=True),
            _Loader("b", "--b", "b", defaultable=True))

        with pytest.raises(ValueError, match="[Dd]efaultable"):
            select_loader(reg, _args(a=None, b=None))
