# Releasing

A merge does not publish a package or deploy the service.

1. **[HUMAN]** Configure PyPI and TestPyPI Trusted Publishers for this repository,
   `release.yml`, and the respective `pypi`/`testpypi` environments. No API tokens are used.
2. **[HUMAN]** Create GitHub environments `pypi` and `testpypi`. Require human reviewers
   on `pypi`, prevent self-approval, and restrict deployments to release tags.
3. Run a dry run without publishing:

   ```bash
   gh workflow run release.yml -f dry_run=true --ref main
   ```

   Inspect the selected run: check-tag, build and both wheel-install jobs must pass;
   both publication jobs must be skipped. Also require the product acceptance report.
4. Update the version and changelog in a reviewed PR, merge it, then **[HUMAN]**:

   ```bash
   git tag -s vX.Y.Z
   git push origin vX.Y.Z
   ```

   Replace `X.Y.Z` with the actual version; prereleases are valid PEP 440 versions.
   Copy the release changelog into the tag annotation. The tag must equal
   `glyphlab.__version__`; CI refuses a mismatch.
5. **[HUMAN]** Check the TestPyPI artifact and approve the PyPI environment only when
   the intended package/version and acceptance evidence have been reviewed.

The first publication and name availability remain operator decisions. The service
package is private and is never published to PyPI. Do not push all local tags.
