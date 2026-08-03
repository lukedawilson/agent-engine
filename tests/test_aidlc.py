"""AI-DLC document loader tests — ported from yosk's TestResolveUnitDocs /
TestGetCurrentUnit (docs_dir parameterised instead of a monkeypatched module
constant; coding-standards cases dropped — the pipeline's `additional_files:`
now owns those)."""

import argparse

import pytest

from agent_engine.extensions.aidlc import (
    AidlcDocumentLoader, AidlcExtension, get_current_unit, resolve_unit_docs,
)
from agent_engine.registry import Registry


class TestResolveUnitDocs:
    def test_loads_docs_for_unit(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-2"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design\nContent")
        (unit_dir / "tasks.md").write_text("# Tasks\nList")
        other_dir = tmp_path / "construction" / "unit-1"
        other_dir.mkdir(parents=True)
        (other_dir / "other.md").write_text("# Other")

        docs = resolve_unit_docs(tmp_path, "2")

        assert "design.md" in docs
        assert "tasks.md" in docs
        assert "other.md" not in docs

    def test_accepts_u_prefixed_unit_id(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-2"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")

        assert "design.md" in resolve_unit_docs(tmp_path, "U2")

    def test_accepts_lowercase_u_prefixed_unit_id(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-3"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")

        assert "design.md" in resolve_unit_docs(tmp_path, "u3")

    def test_raises_for_missing_unit(self, tmp_path):
        """Unknown unit must fail fast — silently running the pipeline with
        zero design docs is a forbidden silent fallback."""
        with pytest.raises(FileNotFoundError, match="unit"):
            resolve_unit_docs(tmp_path, "99")

    def test_includes_inception_docs(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-1"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")  # unit dirs may not be empty
        inception = tmp_path / "inception" / "application-design"
        inception.mkdir(parents=True)
        (inception / "architecture.md").write_text("# Arch")

        docs = resolve_unit_docs(tmp_path, "1")

        assert "inception/architecture.md" in docs
        assert "Arch" in docs["inception/architecture.md"]

    def test_unit_and_inception_name_collision_kept_separate(self, tmp_path):
        """A unit doc and an inception doc with the same filename must both
        survive — inception docs are namespaced to avoid silent overwrite."""
        unit_dir = tmp_path / "construction" / "unit-1"
        unit_dir.mkdir(parents=True)
        (unit_dir / "architecture.md").write_text("unit version")
        inception = tmp_path / "inception" / "application-design"
        inception.mkdir(parents=True)
        (inception / "architecture.md").write_text("inception version")

        docs = resolve_unit_docs(tmp_path, "1")

        assert docs["architecture.md"] == "unit version"
        assert docs["inception/architecture.md"] == "inception version"

    def test_loads_docs_recursively_from_subdirs(self, tmp_path):
        """Unit dirs may nest docs in subdirectories (unit-3 layout:
        functional-design/business-rules.md). Non-recursive loading silently
        injected zero unit docs — the 2026-07-19 U3 context bug."""
        unit_dir = tmp_path / "construction" / "unit-3"
        (unit_dir / "functional-design").mkdir(parents=True)
        (unit_dir / "functional-design" / "business-rules.md").write_text("# Rules")

        docs = resolve_unit_docs(tmp_path, "U3")

        assert docs["functional-design/business-rules.md"] == "# Rules"

    def test_raises_when_unit_dir_yields_no_docs(self, tmp_path):
        """A matched unit dir with no loadable files is a forbidden silent
        fallback — fail fast like a missing dir does."""
        (tmp_path / "construction" / "unit-3" / "functional-design").mkdir(parents=True)

        with pytest.raises(RuntimeError, match="no.*docs|zero"):
            resolve_unit_docs(tmp_path, "U3")

    def test_includes_code_generation_plans(self, tmp_path):
        """The unit's *-code-generation-plan.md files are the build spec."""
        unit_dir = tmp_path / "construction" / "unit-3"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")
        plans = tmp_path / "construction" / "plans"
        plans.mkdir(parents=True)
        (plans / "unit-3-scan-core-types-code-generation-plan.md").write_text("# Core types")
        (plans / "unit-3-scan-frontend-code-generation-plan.md").write_text("# Frontend")
        (plans / "unit-3-scan-nfr-design-plan.md").write_text("# NOT a code-gen plan")
        (plans / "unit-2-onboarding-code-generation-plan.md").write_text("# Wrong unit")

        docs = resolve_unit_docs(tmp_path, "U3")

        assert docs["plans/unit-3-scan-core-types-code-generation-plan.md"] == "# Core types"
        assert docs["plans/unit-3-scan-frontend-code-generation-plan.md"] == "# Frontend"
        assert not any("nfr-design" in k for k in docs)
        assert not any("unit-2" in k for k in docs)

    def test_missing_plans_dir_is_not_an_error(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-2"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")

        assert resolve_unit_docs(tmp_path, "U2")["design.md"] == "# Design"


class TestGetCurrentUnit:
    def _write_state(self, tmp_path, stage_line: str):
        state = tmp_path / "aidlc-state.md"
        state.write_text(f"# AI-DLC State Tracking\n\n{stage_line}\n")
        return state

    def test_parses_unit_from_current_stage(self, tmp_path):
        self._write_state(
            tmp_path,
            "- **Current Stage**: CONSTRUCTION — Unit 3 (SCAN) — Code Generation in progress.")
        assert get_current_unit(tmp_path) == "U3"

    def test_parses_different_unit_number(self, tmp_path):
        self._write_state(
            tmp_path, "- **Current Stage**: CONSTRUCTION — Unit 12 (REPORT).")
        assert get_current_unit(tmp_path) == "U12"

    def test_ignores_unit_mentions_before_the_stage_line(self, tmp_path):
        """The state file accumulates history; only the Current Stage line
        decides the unit — an earlier 'Unit N' mention must not win."""
        state = tmp_path / "aidlc-state.md"
        state.write_text(
            "# AI-DLC State Tracking\n\n"
            "- Finished Unit 9 (REPORT) last week.\n"
            "- **Current Stage**: CONSTRUCTION — Unit 3 (SCAN) — Code Generation.\n")
        assert get_current_unit(tmp_path) == "U3"

    def test_stage_line_without_unit_raises_despite_earlier_mention(self, tmp_path):
        """A 'Unit N' somewhere else in the file is not a Current Stage —
        falling back to it would silently construct the wrong unit."""
        state = tmp_path / "aidlc-state.md"
        state.write_text(
            "# AI-DLC State Tracking\n\n"
            "- Previously worked on Unit 9.\n"
            "- **Current Stage**: INCEPTION — requirements gathering.\n")
        with pytest.raises(RuntimeError, match="current unit"):
            get_current_unit(tmp_path)

    def test_raises_when_no_unit_in_stage_line(self, tmp_path):
        """A stage line with no unit must fail fast — no silent default."""
        self._write_state(tmp_path, "- **Current Stage**: INCEPTION — requirements.")
        with pytest.raises(RuntimeError, match="current unit"):
            get_current_unit(tmp_path)

    def test_raises_when_state_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="aidlc-state"):
            get_current_unit(tmp_path)


class TestAidlcDocumentLoader:
    def _unit_docs(self, tmp_path):
        unit_dir = tmp_path / "construction" / "unit-3"
        unit_dir.mkdir(parents=True)
        (unit_dir / "design.md").write_text("# Design")

    def test_is_defaultable(self):
        assert AidlcDocumentLoader.defaultable is True

    def test_resolve_with_explicit_unit_normalises_subject(self, tmp_path):
        self._unit_docs(tmp_path)
        loader = AidlcDocumentLoader(docs_dir=tmp_path)

        docs, subject = loader.resolve(argparse.Namespace(ai_dlc_unit="u3"))

        assert docs["design.md"] == "# Design"
        assert subject == "unit U3"

    def test_resolve_without_unit_autodetects_current(self, tmp_path):
        self._unit_docs(tmp_path)
        (tmp_path / "aidlc-state.md").write_text(
            "# State\n\n- **Current Stage**: CONSTRUCTION — Unit 3 (SCAN).\n")
        loader = AidlcDocumentLoader(docs_dir=tmp_path)

        docs, subject = loader.resolve(argparse.Namespace(ai_dlc_unit=None))

        assert docs["design.md"] == "# Design"
        assert subject == "unit U3"

    def test_extension_registers_loader_and_flag(self):
        reg = Registry()
        AidlcExtension().register(reg)

        assert [l.name for l in reg.document_loaders] == ["ai-dlc"]
        assert reg.cli_option_owners["--ai-dlc-unit"] == "ai-dlc"
        assert reg.cli_dests["ai_dlc_unit"] == "ai-dlc"
