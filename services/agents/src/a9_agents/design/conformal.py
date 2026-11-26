"""Calibrated predictions: split-conformal intervals, and an applicability domain that refuses to predict.

A model is only trustworthy near what it was trained on, so each prediction is paired with the nearest-
neighbour Tanimoto similarity to the training set. Below the threshold there is NO prediction at all (not a
wide one): a number with no support is worse than a blank."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from rdkit import Chem as _Chem
from rdkit import DataStructs as _DS
from rdkit.Chem import rdFingerprintGenerator as _rfg

Chem: Any = _Chem
DataStructs: Any = _DS
_GEN: Any = _rfg.GetMorganGenerator(radius=2, fpSize=2048)


def conformal_quantile(abs_residuals: Sequence[float], alpha: float) -> float:
    """The finite-sample-corrected (1 - alpha) quantile of calibration residuals. With too few calibration
    points for the requested coverage it is infinite: an honest 'no useful interval'."""
    n = len(abs_residuals)
    k = math.ceil((n + 1) * (1 - alpha))
    return (
        float("inf")
        if n == 0 or k > n
        else float(np.sort(np.asarray(abs_residuals, dtype=float))[k - 1])
    )


def fingerprint(smiles: str) -> Any | None:
    mol = Chem.MolFromSmiles(smiles)
    return _GEN.GetFingerprint(mol) if mol is not None else None


class ApplicabilityDomain:
    def __init__(self, train_smiles: Sequence[str], threshold: float = 0.3):
        self.threshold = threshold
        self._fps = [fp for s in train_smiles if (fp := fingerprint(s)) is not None]
        if not self._fps:
            raise ValueError("no valid training structures")

    def nn_similarity(self, smiles: str) -> float:
        fp = fingerprint(smiles)
        return max(DataStructs.BulkTanimotoSimilarity(fp, self._fps)) if fp is not None else 0.0

    def contains(self, smiles: str) -> bool:
        return self.nn_similarity(smiles) >= self.threshold


@dataclass(frozen=True)
class Prediction:
    value: float | None
    lower: float | None
    upper: float | None
    coverage: float | None  # nominal coverage of the interval, e.g. 0.9
    in_domain: bool
    nn_similarity: float
