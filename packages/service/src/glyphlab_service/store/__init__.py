from .base import ObjectStore, StoreKey
from .local import LocalDiskStore


def make_store(settings) -> ObjectStore:
    if settings.object_store == "s3":
        from .s3 import S3Store

        return S3Store(settings)
    return LocalDiskStore(settings.data_dir / "store")


__all__ = ["LocalDiskStore", "ObjectStore", "StoreKey", "make_store"]
