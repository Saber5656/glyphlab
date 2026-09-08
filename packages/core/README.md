# glyphlab

Turn paper handwriting into a TTF and WOFF2 font, locally.

Install `glyphlab[trace,qa]` or install the native `potrace` executable. Run
`glyphlab new MyHand`, then `glyphlab --project myhand template`. Print at 100%,
write, put scans in `myhand/scans/`, and run `ingest`, `status`, `accept`, and `build`
with `--project myhand`. Generated fonts belong to the handwriting author.

See the [repository](https://github.com/Saber5656/glyphlab) for the full guide,
self-hosted web service, and limitations. This development release is not yet published.
