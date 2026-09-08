"""Tests for client-certificate handling in the Mumble client layer."""

from pathlib import Path

from voxlink.mumble.client import resolve_cert_paths


def test_no_certfile_returns_none():
    assert resolve_cert_paths("", "") == (None, None)
    assert resolve_cert_paths(None, None) == (None, None)


def test_existing_pair_is_expanded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    certdir = tmp_path / "certs"
    certdir.mkdir()
    (certdir / "c.pem").write_text("cert")
    (certdir / "c.key").write_text("key")

    cert, key = resolve_cert_paths("~/certs/c.pem", "~/certs/c.key")
    assert cert == str(certdir / "c.pem")
    assert key == str(certdir / "c.key")


def test_missing_certfile_falls_back_to_no_cert(tmp_path: Path, caplog):
    cert, key = resolve_cert_paths(str(tmp_path / "missing.pem"), str(tmp_path / "missing.key"))
    assert (cert, key) == (None, None)
    assert "Client certificate not found" in caplog.text


def test_missing_keyfile_falls_back_to_no_cert(tmp_path: Path, caplog):
    (tmp_path / "c.pem").write_text("cert")
    cert, key = resolve_cert_paths(str(tmp_path / "c.pem"), str(tmp_path / "missing.key"))
    assert (cert, key) == (None, None)
    assert "Client key not found" in caplog.text


def test_certfile_only_is_allowed(tmp_path: Path):
    """A combined PEM (cert+key in one file) needs no separate keyfile."""
    (tmp_path / "combined.pem").write_text("cert+key")
    cert, key = resolve_cert_paths(str(tmp_path / "combined.pem"), "")
    assert cert == str(tmp_path / "combined.pem")
    assert key is None
