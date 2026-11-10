"""
scripts/md_to_pdf_periodo.py

Convierte docs/PERIODO_2026-09-28_2026-10-28.md a PDF en la carpeta de la
tesis del Escritorio.

Uso:
    python scripts/md_to_pdf_periodo.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "md_to_pdf_v2", ROOT / "scripts" / "md_to_pdf_v2.py"
)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_base.SRC = ROOT / "docs" / "PERIODO_2026-09-28_2026-10-28.md"
_base.FIGDIR = ROOT / "docs" / "tesis_resultados_v3"
_base.OUT = (
    Path(r"C:\Users\jugev\Desktop\Tesis_BTC_USDT_4H")
    / "PERIODO_2026-09-28_2026-10-28.pdf"
)


def main() -> None:
    if not _base.SRC.exists():
        raise SystemExit(f"[ERROR] No existe {_base.SRC}")
    _base.OUT.parent.mkdir(parents=True, exist_ok=True)
    _base.main()


if __name__ == "__main__":
    main()
