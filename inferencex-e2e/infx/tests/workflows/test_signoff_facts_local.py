"""Exercise the verifier's facts for native images and this repository's master configs."""

import io
import urllib.error

import pytest

from infx.workflows import signoff_facts

ARCHIVE = "https://example.invalid/llama.tar.gz"


@pytest.mark.parametrize(
    ("response", "resolves"),
    [
        (None, True),
        (urllib.error.HTTPError(ARCHIVE, 404, "Not Found", None, None), False),
        (urllib.error.URLError("no route"), None),
    ],
    ids=["answers", "gone", "unreachable"],
)
def test_a_native_archive_image_resolves_by_its_url_not_docker(monkeypatch, response, resolves):
    asked = []

    def answer(request, timeout):  # noqa: ARG001
        asked.append((request.get_method(), request.full_url))
        if response is not None:
            raise response
        return io.BytesIO()

    monkeypatch.setattr(signoff_facts.urllib.request, "urlopen", answer)
    monkeypatch.setattr(signoff_facts, "_inspect", lambda reference: pytest.fail(reference))

    report = signoff_facts.inspect_image(f"{ARCHIVE}@sha256:ab")

    assert asked == [("HEAD", ARCHIVE)]
    assert (report["image"], report["inspected"]) == (f"{ARCHIVE}@sha256:ab", ARCHIVE)
    assert report["resolves"] is resolves


def test_the_matrix_of_a_revision_reads_the_master_configs_at_that_revision(monkeypatch, tmp_path):
    project = tmp_path / "inferencex-e2e"
    (project / "configs").mkdir(parents=True)
    (project / "configs/fixture-master.yaml").write_text("fixture-key: {}\n")
    (project / "configs/runners.yaml").write_text("{}\n")
    monkeypatch.setattr(signoff_facts, "_extract", lambda _rev, _target: project)
    monkeypatch.setattr(signoff_facts, "MASTER_CONFIGS", ["configs/fixture-master.yaml"])

    _, errors = signoff_facts.matrix_at("HEAD", tmp_path)

    assert "fixture-key" in errors
