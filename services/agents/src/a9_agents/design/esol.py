"""A small, fully transparent solubility predictor (log S, mol/L) used to exercise calibration end to end.

It is the classic Delaney/ESOL form: a ridge-regularised linear model on four RDKit descriptors, trained on
the public ESOL measurements. It is NOT a state-of-the-art predictor and is not used for any decision; its
value here is that its calibration and domain behaviour can be MEASURED on real held-out data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import Chem as _Chem
from rdkit.Chem import Crippen as _Crippen
from rdkit.Chem import Descriptors as _Desc
from rdkit.Chem import rdMolDescriptors as _rd

from a9_agents.design.conformal import ApplicabilityDomain, Prediction, conformal_quantile

Chem: Any = _Chem
Crippen: Any = _Crippen
Descriptors: Any = _Desc
rdMolDescriptors: Any = _rd

NAME, VERSION, ENDPOINT = "esol-ridge", "1", "logS"


def features(smiles: str) -> np.ndarray | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    heavy = max(mol.GetNumHeavyAtoms(), 1)
    aromatic = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()) / heavy
    return np.array(
        [
            Crippen.MolLogP(mol),
            Descriptors.MolWt(mol),
            rdMolDescriptors.CalcNumRotatableBonds(mol),
            aromatic,
        ]
    )


def load_esol(path: Path) -> list[tuple[str, float]]:
    import csv

    with path.open(newline="") as f:
        return [
            (r["smiles"].strip(), float(r["measured log solubility in mols per litre"]))
            for r in csv.DictReader(f)
            if r["smiles"].strip()
        ]


@dataclass
class EsolModel:
    mean: np.ndarray
    std: np.ndarray
    weights: np.ndarray  # last entry is the intercept
    train_smiles: list[str]
    abs_residuals: list[float]  # calibration residuals, kept so any coverage level can be requested
    domain: ApplicabilityDomain

    @staticmethod
    def train(
        rows: list[tuple[str, float]],
        *,
        seed: int = 7,
        ridge: float = 1.0,
        domain_threshold: float = 0.3,
    ) -> tuple[EsolModel, list[tuple[str, float]]]:
        """Split 60/20/20 into train / calibration / held-out test. Returns the model and the test rows."""
        usable = [(s, y) for s, y in rows if features(s) is not None]
        order = np.random.default_rng(seed).permutation(len(usable))
        n_train, n_cal = int(0.6 * len(usable)), int(0.2 * len(usable))
        train = [usable[i] for i in order[:n_train]]
        cal = [usable[i] for i in order[n_train : n_train + n_cal]]
        test = [usable[i] for i in order[n_train + n_cal :]]
        X = np.array([features(s) for s, _ in train])
        mean, std = X.mean(0), X.std(0) + 1e-9
        A = np.hstack([(X - mean) / std, np.ones((len(X), 1))])
        reg = ridge * np.eye(A.shape[1])
        reg[-1, -1] = 0  # do not shrink the intercept
        w = np.linalg.solve(A.T @ A + reg, A.T @ np.array([y for _, y in train]))
        model = EsolModel(
            mean,
            std,
            w,
            [s for s, _ in train],
            [],
            ApplicabilityDomain([s for s, _ in train], domain_threshold),
        )
        model.abs_residuals = [abs(model._point(s) - y) for s, y in cal]
        return model, test

    def _point(self, smiles: str) -> float:
        x = features(smiles)
        assert x is not None
        return float(np.append((x - self.mean) / self.std, 1.0) @ self.weights)

    def predict(self, smiles: str, coverage: float = 0.9) -> Prediction:
        sim = self.domain.nn_similarity(smiles)
        if features(smiles) is None or sim < self.domain.threshold:
            return Prediction(
                None, None, None, None, False, sim
            )  # outside the domain: no number at all
        q = conformal_quantile(self.abs_residuals, 1 - coverage)
        v = self._point(smiles)
        return Prediction(v, v - q, v + q, coverage, True, sim)

    def to_json(self) -> str:
        return json.dumps(
            {
                "mean": self.mean.tolist(),
                "std": self.std.tolist(),
                "weights": self.weights.tolist(),
                "train_smiles": self.train_smiles,
                "abs_residuals": self.abs_residuals,
                "threshold": self.domain.threshold,
            }
        )

    @staticmethod
    def from_json(text: str) -> EsolModel:
        d = json.loads(text)
        return EsolModel(
            np.array(d["mean"]),
            np.array(d["std"]),
            np.array(d["weights"]),
            d["train_smiles"],
            d["abs_residuals"],
            ApplicabilityDomain(d["train_smiles"], d["threshold"]),
        )


def evaluate(
    model: EsolModel, test: list[tuple[str, float]], coverage: float = 0.9
) -> dict[str, float]:
    preds = [(model.predict(s, coverage), y) for s, y in test]
    inside = [(p, y) for p, y in preds if p.in_domain]
    covered = sum(
        1
        for p, y in inside
        if p.lower is not None and p.upper is not None and p.lower <= y <= p.upper
    )
    mae = float(np.mean([abs((p.value or 0) - y) for p, y in inside])) if inside else float("nan")
    width = (
        float(np.mean([(p.upper or 0) - (p.lower or 0) for p, _ in inside]))
        if inside
        else float("nan")
    )
    return {
        "n_test": len(test),
        "n_in_domain": len(inside),
        "frac_in_domain": len(inside) / len(test),
        "coverage": covered / len(inside) if inside else float("nan"),
        "nominal": coverage,
        "mae": mae,
        "mean_width": width,
    }
