"""Exercise the verifier's facts for this repository's master configs."""

from infx.workflows import signoff_facts


def test_the_matrix_of_a_revision_reads_the_master_configs_at_that_revision(monkeypatch, tmp_path):
    project = tmp_path / "inferencex-e2e"
    (project / "configs").mkdir(parents=True)
    (project / "configs/fixture-master.yaml").write_text("fixture-key: {}\n")
    (project / "configs/runners.yaml").write_text("{}\n")
    monkeypatch.setattr(signoff_facts, "_extract", lambda _rev, _target: project)
    monkeypatch.setattr(signoff_facts, "MASTER_CONFIGS", ["configs/fixture-master.yaml"])

    _, errors = signoff_facts.matrix_at("HEAD", tmp_path)

    assert "fixture-key" in errors
