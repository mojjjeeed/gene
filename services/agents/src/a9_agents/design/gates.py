"""Cheap gates on a candidate structure: validity, uniqueness, novelty, structural alerts, property
windows and synthetic accessibility. Most candidates should die here, which costs almost nothing.

Each gate returns pass/fail WITH detail (which alert, which property, what value). A gate is hard (the
candidate fails if it fails) or soft (reported, never blocking). Brenk alerts are soft; PAINS, project
alerts, windows, validity, uniqueness, novelty and SA are hard."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

from rdkit import Chem as _Chem
from rdkit import RDLogger as _RDLogger
from rdkit.Chem import Descriptors as _Desc
from rdkit.Chem import Lipinski as _Lip
from rdkit.Chem import inchi as _inchi
from rdkit.Chem.FilterCatalog import FilterCatalog as _FC
from rdkit.Chem.FilterCatalog import FilterCatalogParams as _FCP
from rdkit.Contrib.SA_Score import sascorer as _sa  # type: ignore[import-untyped]

Chem: Any = _Chem  # RDKit ships no type information
Descriptors: Any = _Desc
Lipinski: Any = _Lip
inchi: Any = _inchi
FilterCatalog: Any = _FC
FilterCatalogParams: Any = _FCP
sascorer: Any = _sa
_RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]

DEFAULT_WINDOWS: dict[str, tuple[float, float]] = {
    "mw": (150.0, 600.0), "logp": (-1.0, 5.5), "hbd": (0, 5), "hba": (0, 10), "tpsa": (0.0, 140.0), "rotb": (0, 10),
}  # fmt: skip
SA_MAX = 6.0  # 1 (easy) to 10 (hard)
MIN_HEAVY_ATOMS = 6


@dataclass(frozen=True)
class GateResult:
    gate: str
    hard: bool
    passed: bool
    detail: dict[str, Any]


@dataclass
class GateReport:
    smiles: str
    canonical: str | None
    inchikey: str | None
    results: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.hard)

    @property
    def failed(self) -> list[str]:
        return [r.gate for r in self.results if r.hard and not r.passed]

    @property
    def warnings(self) -> list[str]:
        return [r.gate for r in self.results if not r.hard and not r.passed]


@cache
def _catalog(name: str) -> Any:
    params = FilterCatalogParams()
    params.AddCatalog(getattr(FilterCatalogParams.FilterCatalogs, name))
    return FilterCatalog(params)


def properties(mol: Any) -> dict[str, float]:
    return {
        "mw": Descriptors.MolWt(mol), "logp": Descriptors.MolLogP(mol), "hbd": Lipinski.NumHDonors(mol),
        "hba": Lipinski.NumHAcceptors(mol), "tpsa": Descriptors.TPSA(mol), "rotb": Lipinski.NumRotatableBonds(mol),
    }  # fmt: skip


def run_gates(
    smiles: str,
    *,
    seen_inchikeys: set[str] | None = None,
    known_inchikeys: set[str] | None = None,
    windows: dict[str, tuple[float, float]] | None = None,
    sa_max: float = SA_MAX,
    project_alerts: dict[str, str] | None = None,
) -> GateReport:
    """`seen_inchikeys`: structures already generated in this project (uniqueness). `known_inchikeys`:
    structures already in the corpus or ChEMBL (novelty); pass None to skip novelty rather than guess."""
    mol = Chem.MolFromSmiles(smiles) if smiles and smiles.strip() else None
    report = GateReport(smiles, None, None)
    out = report.results
    if mol is None:
        out.append(GateResult("validity", True, False, {"reason": "not a valid structure"}))
        return report
    heavy, fragments = mol.GetNumHeavyAtoms(), len(Chem.GetMolFrags(mol))
    valid = heavy >= MIN_HEAVY_ATOMS and fragments == 1
    out.append(
        GateResult(
            "validity",
            True,
            valid,
            {"heavy_atoms": heavy, "fragments": fragments}
            | ({} if valid else {"reason": "too small or not a single connected molecule"}),
        )
    )
    report.canonical, report.inchikey = Chem.MolToSmiles(mol), inchi.MolToInchiKey(mol)
    if not valid:
        return report

    if seen_inchikeys is not None:
        dup = report.inchikey in seen_inchikeys
        out.append(GateResult("uniqueness", True, not dup, {"duplicate_of_earlier_candidate": dup}))
    if known_inchikeys is not None:
        known = report.inchikey in known_inchikeys
        out.append(GateResult("novelty", True, not known, {"already_known": known}))

    for gate, name, hard in (("pains", "PAINS", True), ("brenk", "BRENK", False)):
        hits = sorted({e.GetDescription() for e in _catalog(name).GetMatches(mol)})
        out.append(GateResult(gate, hard, not hits, {"alerts": hits}))
    if project_alerts:
        hits = sorted(
            n
            for n, smarts in project_alerts.items()
            if (p := Chem.MolFromSmarts(smarts)) is not None and mol.HasSubstructMatch(p)
        )
        out.append(GateResult("project_alerts", True, not hits, {"alerts": hits}))

    props, win = properties(mol), windows or DEFAULT_WINDOWS
    bad = {
        k: {"value": round(props[k], 2), "window": list(win[k])}
        for k in win
        if not (win[k][0] <= props[k] <= win[k][1])
    }
    out.append(
        GateResult(
            "property_windows",
            True,
            not bad,
            {"properties": {k: round(v, 2) for k, v in props.items()}, "violations": bad},
        )
    )
    score = float(sascorer.calculateScore(mol))
    out.append(
        GateResult(
            "synthetic_accessibility",
            True,
            score <= sa_max,
            {"sa_score": round(score, 2), "max": sa_max},
        )
    )
    return report
