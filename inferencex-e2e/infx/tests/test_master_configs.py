"""Exercise the default master config list against projects that lack some of its files."""

import pytest

from infx.config import LOCAL_MASTER_CONFIG, MASTER_CONFIGS

UPSTREAM = [path for path in MASTER_CONFIGS if path != LOCAL_MASTER_CONFIG]


@pytest.mark.parametrize(
    ("written", "listed"),
    [([LOCAL_MASTER_CONFIG], MASTER_CONFIGS), ([], UPSTREAM)],
    ids=["local-only", "none"],
)
def test_a_missing_upstream_master_config_stays_listed(tmp_path, monkeypatch, written, listed):
    (tmp_path / "configs").mkdir()
    for path in written:
        (tmp_path / path).write_text("{}\n")
    monkeypatch.chdir(tmp_path)

    assert MASTER_CONFIGS.present() == listed
