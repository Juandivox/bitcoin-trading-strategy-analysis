"""
scripts/md_to_pdf_v3.py

Convierte docs/tesis_resultados_v3/CAPITULO_RESULTADOS_v3.md a PDF academico
en el Escritorio, reutilizando el motor de scripts/md_to_pdf_v2.py.

Uso:
    python scripts/md_to_pdf_v3.py
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

# Sobrescribe las rutas del motor base (las funciones leen estos globales).
_base.SRC = ROOT / "docs" / "tesis_resultados_v3" / "CAPITULO_RESULTADOS_v3.md"
_base.FIGDIR = ROOT / "docs" / "tesis_resultados_v3"
_base.OUT = Path(r"C:\Users\jugev\Desktop") / "CAPITULO_RESULTADOS_V3_BTC_Trading.pdf"


def main() -> None:
    if not _base.SRC.exists():
        raise SystemExit(f"[ERROR] No existe {_base.SRC}")
    _base.main()


if __name__ == "__main__":
    main()
