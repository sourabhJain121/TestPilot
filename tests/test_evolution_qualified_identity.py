"""
Mandatory regression tests for qualified symbol identity and constructor resolution
in Repository Evolution Intelligence.
Verifies elimination of false positives from generic symbol names like __init__,
setUp, run, execute, get, update, handle, and process.
"""

from testpilot.evolution.engine import RepositoryEvolutionEngine
from testpilot.evolution.models import (
    ChangedSymbol,
    ChangeType,
    PriorityTier,
    SymbolId,
)


def test_symbol_id_canonical_representation():
    """Verify SymbolId produces canonical dot-path qualified representation."""
    sym_id = SymbolId(
        file_path="homeassistant/components/hue/event.py",
        name="__init__",
        class_name="HueButtonEventEntity",
    )
    assert sym_id.module_path == "homeassistant.components.hue.event"
    assert sym_id.qualified_name == "HueButtonEventEntity.__init__"
    assert sym_id.canonical_id == "homeassistant.components.hue.event.HueButtonEventEntity.__init__"

    top_sym = SymbolId(
        file_path="pkg/service.py",
        name="calculate_tax",
    )
    assert top_sym.qualified_name == "calculate_tax"
    assert top_sym.canonical_id == "pkg.service.calculate_tax"


def test_generic_init_collision_qualified_identity(tmp_path):
    """
    Test A: Generic __init__ collision test.
    Package A has HueButtonEventEntity.__init__.
    Package B has OtherClass.__init__.
    Tests instantiate both.
    Modifying only HueButtonEventEntity.__init__ must ONLY prioritize tests instantiating HueButtonEventEntity.
    """
    # Create package structure
    (tmp_path / "package").mkdir(parents=True)
    (tmp_path / "package" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "package" / "a.py").write_text(
        "class HueButtonEventEntity:\n"
        "    def __init__(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "package" / "b.py").write_text(
        "class OtherClass:\n"
        "    def __init__(self):\n"
        "        pass\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_hue.py").write_text(
        "from package.a import HueButtonEventEntity\n\n"
        "def test_hue_entity():\n"
        "    entity = HueButtonEventEntity()\n",
        encoding="utf-8",
    )
    (tests_dir / "test_other.py").write_text(
        "from package.b import OtherClass\n\n"
        "def test_other_entity():\n"
        "    other = OtherClass()\n",
        encoding="utf-8",
    )

    engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))
    changed_sym = ChangedSymbol(
        name="__init__",
        class_name="HueButtonEventEntity",
        file_path="package/a.py",
        line_start=2,
        line_end=4,
        change_type=ChangeType.MODIFIED,
    )

    prioritized = engine.prioritize_tests([changed_sym], [], [])
    p_names = {t.test_name for t in prioritized}

    # test_hue_entity must be prioritized for HueButtonEventEntity.__init__
    assert "test_hue_entity" in p_names
    hue_test = next(t for t in prioritized if t.test_name == "test_hue_entity")
    assert hue_test.priority_tier == PriorityTier.CRITICAL
    assert hue_test.confidence == 0.95
    assert hue_test.targeted_symbol == "HueButtonEventEntity.__init__"
    assert hue_test.evidence.match_quality == "CONFIRMED_CONSTRUCTOR_CALL"

    # test_other_entity must NOT be prioritized
    assert "test_other_entity" not in p_names


def test_cross_module_init_isolation(tmp_path):
    """
    Test B: Cross-module __init__ test.
    Two classes with __init__ in separate modules.
    Only one changes. Tests for the other module (or with mock __init__) must not match.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "service_a.py").write_text(
        "class ServiceA:\n"
        "    def __init__(self, val):\n"
        "        self.val = val\n",
        encoding="utf-8",
    )
    (pkg / "service_b.py").write_text(
        "class ServiceB:\n"
        "    def __init__(self, val):\n"
        "        self.val = val\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_b.py").write_text(
        "from pkg.service_b import ServiceB\n\n"
        "class MockHelper:\n"
        "    def __init__(self):\n"
        "        super().__init__()\n\n"
        "def test_service_b_run():\n"
        "    b = ServiceB(42)\n",
        encoding="utf-8",
    )

    engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))
    sym_a = ChangedSymbol(
        name="__init__",
        class_name="ServiceA",
        file_path="pkg/service_a.py",
        line_start=2,
        line_end=4,
        change_type=ChangeType.MODIFIED,
    )

    prioritized = engine.prioritize_tests([sym_a], [], [])
    # Zero tests should be prioritized because test_b only touches ServiceB and MockHelper
    assert len(prioritized) == 0


def test_constructor_resolution_and_rejection(tmp_path):
    """
    Test C: Constructor-resolution test.
    HueButtonEventEntity(...) constructor invocation in a test resolves to
    HueButtonEventEntity.__init__ when imported, but OtherClass(...) does not.
    """
    hue_pkg = tmp_path / "homeassistant" / "components" / "hue"
    hue_pkg.mkdir(parents=True)
    (hue_pkg / "event.py").write_text(
        "class HueButtonEventEntity:\n"
        "    def __init__(self, bridge, button):\n"
        "        self.bridge = bridge\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_event.py").write_text(
        "from homeassistant.components.hue.event import HueButtonEventEntity\n\n"
        "def test_button_instantiation():\n"
        "    entity = HueButtonEventEntity(None, 'button_1')\n\n"
        "def test_unrelated():\n"
        "    x = [1, 2, 3]\n",
        encoding="utf-8",
    )

    engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))
    cs = ChangedSymbol(
        name="__init__",
        class_name="HueButtonEventEntity",
        file_path="homeassistant/components/hue/event.py",
        line_start=2,
        line_end=4,
        change_type=ChangeType.MODIFIED,
    )

    prioritized = engine.prioritize_tests([cs], [], [])
    assert len(prioritized) == 1
    t = prioritized[0]
    assert t.test_name == "test_button_instantiation"
    assert t.targeted_symbol == "HueButtonEventEntity.__init__"
    assert t.priority_tier == PriorityTier.CRITICAL
    assert t.confidence == 0.95
    assert t.evidence.match_quality == "CONFIRMED_CONSTRUCTOR_CALL"


def test_ambiguous_unresolved_init_reference(tmp_path):
    """
    Test D: Ambiguous reference test.
    Unresolved some_object.__init__() must NOT receive EXACT_AST_CALL or CRITICAL or 0.95 confidence.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_dynamic.py").write_text(
        "def test_dynamic_call(some_object):\n"
        "    some_object.__init__()\n",
        encoding="utf-8",
    )

    engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))
    cs = ChangedSymbol(
        name="__init__",
        class_name="HueButtonEventEntity",
        file_path="homeassistant/components/hue/event.py",
        line_start=86,
        line_end=101,
        change_type=ChangeType.MODIFIED,
    )

    prioritized = engine.prioritize_tests([cs], [], [])
    # Unresolved some_object.__init__() must NOT match HueButtonEventEntity.__init__ as CRITICAL
    matching = [t for t in prioritized if t.test_name == "test_dynamic_call"]
    assert len(matching) == 0


def test_generic_method_names_distinguish_classes(tmp_path):
    """
    Verifies that other common methods (update, process, handle, run) distinguish classes:
    ClassA.update vs ClassB.update.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "entity.py").write_text(
        "class TargetEntity:\n"
        "    def update(self):\n"
        "        pass\n"
        "class OtherEntity:\n"
        "    def update(self):\n"
        "        pass\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_entities.py").write_text(
        "from pkg.entity import TargetEntity, OtherEntity\n\n"
        "def test_target():\n"
        "    t = TargetEntity()\n"
        "    t.update()\n\n"
        "def test_other():\n"
        "    o = OtherEntity()\n"
        "    o.update()\n",
        encoding="utf-8",
    )

    engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))
    cs = ChangedSymbol(
        name="update",
        class_name="TargetEntity",
        file_path="pkg/entity.py",
        line_start=2,
        line_end=4,
        change_type=ChangeType.MODIFIED,
    )

    prioritized = engine.prioritize_tests([cs], [], [])
    p_names = [t.test_name for t in prioritized]
    assert "test_target" in p_names
    assert "test_other" not in p_names
    target_match = next(t for t in prioritized if t.test_name == "test_target")
    assert target_match.targeted_symbol == "TargetEntity.update"
