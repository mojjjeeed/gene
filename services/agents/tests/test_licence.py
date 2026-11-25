"""The licence gate: only licences that clearly permit storing and deriving from full text pass."""

from __future__ import annotations

import pytest
from a9_agents.fulltext.licence import evaluate_licence, normalise


@pytest.mark.parametrize(
    ("raw", "norm", "ok"),
    [
        ("https://creativecommons.org/licenses/by/4.0/", "cc-by", True),
        ("http://creativecommons.org/licenses/by-sa/3.0/", "cc-by-sa", True),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "cc0", True),
        ("CC0", "cc0", True), ("cc0 1.0", "cc0", True), ("public domain", "public-domain", True),
        ("cc by", "cc-by", True), ("CC-BY", "cc-by", True), ("cc by 4.0", "cc-by", True), ("cc_by", "cc-by", True),
        ("cc by-sa", "cc-by-sa", True),
        ("https://creativecommons.org/licenses/by-nc-nd/4.0/", "cc-by-nc-nd", False),  # real: PMC8562388
        ("cc by-nc", "cc-by-nc", False), ("cc_by_nc_nd", "cc-by-nc-nd", False), ("cc-by-nd", "cc-by-nd", False),
        ("cc_no", None, False),  # bioRxiv's "no licence": all rights reserved
        ("https://arxiv.org/licenses/nonexclusive-distrib/1.0/", None, False),  # arXiv's default
        ("all-rights-reserved", None, False), ("publisher-specific, author manuscript", None, False),
        ("unknown", None, False), ("", None, False), (None, None, False), ("   ", None, False),
    ],
)  # fmt: skip
def test_licence_matrix(raw: str | None, norm: str | None, ok: bool) -> None:
    d = evaluate_licence(raw)
    assert (d.normalised, d.permitted) == (norm, ok), d.reason


def test_unknown_is_never_read_as_open() -> None:
    assert not evaluate_licence(None).permitted
    assert "metadata only" in evaluate_licence(None).reason
    assert "unrecognised" in evaluate_licence("some bespoke terms").reason


def test_the_allowed_set_can_be_widened_deliberately(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not evaluate_licence("cc by-nc").permitted
    monkeypatch.setenv("A9_ALLOWED_LICENCES", "cc-by,cc-by-nc")
    assert evaluate_licence("cc by-nc").permitted
    assert not evaluate_licence(
        "cc0"
    ).permitted  # an override replaces the default, it does not extend it
    monkeypatch.setenv("A9_ALLOWED_LICENCES", "")
    assert not evaluate_licence("cc by").permitted  # an empty list permits nothing


def test_normalise_is_stable_for_urls_with_odd_forms() -> None:
    assert normalise("HTTPS://CreativeCommons.org/licenses/BY/4.0") == "cc-by"
    assert normalise("see https://creativecommons.org/licenses/by/4.0/legalcode") == "cc-by"
