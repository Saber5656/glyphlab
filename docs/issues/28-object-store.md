# Title

ObjectStore: local-disk + S3-compatible implementations

# Summary

Implement the blob-storage boundary of DESIGN §14.2: a typed `ObjectStore` interface whose
keys are constructed only from server-generated parts, with `LocalDiskStore` (default) and
`S3Store` (Tigris/any S3) implementations and containment guarantees.

# Context

Uploads, glyph SVGs, and font artifacts all live behind this interface; ADR-005 makes it the
portability seam (Fly volume today, S3/Cloud Run tomorrow). T6 (path traversal) is designed
out by the key model.

# Scope

`packages/service/src/glyphlab_service/store/{base.py,local.py,s3.py}` + tests (moto for S3).
Adds service deps: `boto3` (extra `glyphlab-service[s3]`? no — include; small and the compose
story needs it switchable at runtime).

# Detailed Requirements

1. `base.py`:
   ```python
   @dataclass(frozen=True)
   class StoreKey:
       project_id: uuid.UUID
       category: Literal["uploads", "glyphs", "artifacts"]
       name: str  # server-generated; validated against the §14.2 pattern:
                  # ^(?:[0-9a-f]{32}(\.[a-z0-9]{1,8})?|U\+[0-9A-F]{4,6}\.svg)$
                  # (uuid4-hex [+ext] or glyph-SVG name — "." / ".." are unrepresentable)
   class ObjectStore(Protocol):
       def put(self, key: StoreKey, data: bytes, content_type: str) -> None: ...
       def get(self, key: StoreKey) -> bytes: ...
       def stream(self, key: StoreKey) -> Iterator[bytes]: ...      # for artifact downloads
       def delete(self, key: StoreKey) -> None: ...
       def delete_prefix(self, project_id: uuid.UUID) -> int: ...   # purge; returns count
       def exists(self, key: StoreKey) -> bool: ...
   ```
   `KeyError`-equivalent → `E_NOT_FOUND` GlyphlabError. `StoreKey.__post_init__` enforces
   the name regex (defense-in-depth; callers already pass UUIDs/enum names).
2. `local.py`: root `= settings.data_dir / "store"`; path
   `root/projects/<id>/<category>/<name>`; after join, `resolved.is_relative_to(root)`
   asserted (belt-and-braces per §17.3 T6); writes atomic (tmp + rename); `delete_prefix`
   = rmtree of the project dir (guard: path must end with the project UUID).
3. `s3.py`: boto3 client from issue 26's exact settings fields (`s3_endpoint_url` — set
   for Tigris, `s3_bucket`, `s3_region`, `s3_access_key_id`, `s3_secret_access_key`);
   same key layout as string keys `projects/{id}/{category}/{name}`; `delete_prefix` via paginated
   `list_objects_v2` + batched `delete_objects` (1000/batch); streaming get via
   `Body.iter_chunks()`; retries: boto default (documented); no presigned URLs in v1
   (downloads proxy through the app — token check on every byte, §15).
4. Factory `make_store(settings) -> ObjectStore` exported from
   `glyphlab_service/store/__init__.py`.
5. Tests: interface conformance suite run against BOTH implementations (moto for S3):
   put/get/stream/delete/exists round-trips (binary-safe), delete_prefix counts,
   name-regex rejection incl. `"."`, `".."`, `"../../etc/passwd"`, `"a/b"` (all fail the
   §14.2 pattern at `StoreKey`); local containment defense-in-depth test (bypass the
   dataclass via `object.__new__`, feed a traversal name, assert the resolved-path
   assertion still refuses); atomicity failure-injection: monkeypatch `os.replace` to
   raise mid-put → final path absent and no temp residue.

# Acceptance Criteria

- [ ] Conformance suite green on both stores.
- [ ] Containment: crafted names rejected at StoreKey AND at the resolved-path assertion
      (both layers tested).
- [ ] moto-backed S3 delete_prefix handles > 1000 objects (pagination test with 1005 keys).
- [ ] Atomicity failure-injection test proves no partial final file.

# Validation

```bash
uv run pytest packages/service/tests/store -q
```

# Dependencies

26.

# Non-goals

Retention scheduling (36 — calls `delete_prefix`), quotas (31), CDN/presigned URLs (v2).

# Design References

DESIGN §14.2 (key scheme), §17.3 T6, ADR-005, research/03 (Tigris).
