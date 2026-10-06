# PDF print preflight sample

A small, read-only diagnostic for a PDF page that prints gray or blurry. It checks the effective resolution of embedded images and samples the rendered page's outer border. It produces JSON and verifies that the source PDF is unchanged.

This independent, AI-assisted demonstration uses synthetic data. It is not a client's completed repair. It does not remove writing, recreate text, or claim to recover missing scan detail.

## Run

Requires Python 3.10+, Poppler's `pdfinfo`, `pdfimages`, `pdftoppm`, and Pillow. ReportLab is used only for synthetic test fixtures.

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest -v
python3 pdf_print_check.py examples/gray-low-resolution.pdf
```

Use `--page 2` to inspect another page. Processing failures exit with status 2; a successfully produced diagnostic exits with 0 even when it contains review flags. The input limit is 32 MiB and each Poppler command has a 20-second timeout.

## What the sample proves

The gray fixture contains a full-page 72 PPI bitmap. The white fixture contains a full-page 300 PPI bitmap. Tests exercise both findings, vector-only PDFs, page selection, invalid inputs, CLI output, and byte-for-byte source preservation.

The gray-background flag is a heuristic based on the outside edge. Borders or artwork may trigger it; interior-only shading may be missed. An embedded image with low resolution may be a small logo. Every result requires human review. The sample does not diagnose printer settings or vector-text blur, and higher export DPI alone cannot recover detail absent from the original scan.

Before a cleanup job, compare the original image and the edited PDF, agree the content that must remain intact, and use an ordinary redacted document to establish whether print cleanup is feasible. A final cleanup needs the actual files and an agreed scope.

Poppler defines x-ppi/y-ppi as the image's resolution when placed on the PDF page: [upstream manual source](https://skia.googlesource.com/third_party/poppler/+/master/utils/pdfimages.1).
