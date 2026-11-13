"""Supplement Maker — desktop app entry point.

    Supplement Maker            opens the form
    Supplement Maker --selftest out.pdf
                                renders the built-in example to out.pdf and exits
                                (used by the build pipeline to check the packaged app)
"""
import sys


def selftest(out: str) -> int:
    from supplement_maker.model import sample_job
    from supplement_maker.pdf_render import render_pdf
    from supplement_maker.latex_export import build_tex
    render_pdf(sample_job(), out)
    assert "\\begin{lineitems}" in build_tex(sample_job())
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    from supplement_maker.gui import main
    main()
