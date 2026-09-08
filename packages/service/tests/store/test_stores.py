import os
from uuid import uuid4

import pytest
from moto import mock_aws

from glyphlab_service.settings import Settings
from glyphlab_service.store import LocalDiskStore, StoreKey
from glyphlab_service.store.s3 import S3Store


@pytest.fixture(params=["local", "s3"])
def store(request, tmp_path):
    if request.param == "local":
        yield LocalDiskStore(tmp_path)
    else:
        with mock_aws():
            result = S3Store(
                Settings(
                    s3_bucket="test-bucket",
                    s3_region="us-east-1",
                    s3_access_key_id="testing",
                    s3_secret_access_key="testing",
                )
            )
            result.client.create_bucket(Bucket="test-bucket")
            yield result


def test_conformance(store):
    pid = uuid4()
    key = StoreKey(pid, "glyphs", "U+0041.svg")
    assert not store.exists(key)
    store.put(key, b"\x00hello\xff", "image/svg+xml")
    assert store.exists(key)
    assert store.get(key) == b"\x00hello\xff"
    assert b"".join(store.stream(key)) == b"\x00hello\xff"
    assert store.delete_prefix(pid) == 1
    assert store.delete_prefix(pid) == 0
    store.delete(key)


def test_atomic_failure(tmp_path, monkeypatch):
    store = LocalDiskStore(tmp_path)
    key = StoreKey(uuid4(), "uploads", uuid4().hex)

    def fail(*args):
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        store.put(key, b"bytes", "image/png")
    assert not store.exists(key)
    assert not list(tmp_path.rglob("*.*"))
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_containment_bypass(tmp_path):
    store = LocalDiskStore(tmp_path)
    key = object.__new__(StoreKey)
    object.__setattr__(key, "project_id", uuid4())
    object.__setattr__(key, "category", "uploads")
    object.__setattr__(key, "name", "../../../../outside")
    with pytest.raises(ValueError):
        store.put(key, b"bad", "text/plain")


def test_s3_pagination():
    with mock_aws():
        store = S3Store(
            Settings(
                s3_bucket="test-bucket",
                s3_region="us-east-1",
                s3_access_key_id="testing",
                s3_secret_access_key="testing",
            )
        )
        store.client.create_bucket(Bucket="test-bucket")
        pid = uuid4()
        for _ in range(1005):
            store.put(StoreKey(pid, "uploads", uuid4().hex), b"x", "image/png")
        assert store.delete_prefix(pid) == 1005
