"""Deliberately failing probe for #125: proves branch protection blocks a red PR.

This file is expected to be deleted without merging.
"""


def test_deliberate_red_probe() -> None:
    assert False, "deliberately red: proving the CI check is required on main (#125)"
