# scripts/archive/

Scripts históricos, **fuera del pipeline**. No se ejecutan ni se mantienen.

- `audit_and_run_atr.py` — auditoría del stop ATR (fijo vs trailing, cierre vs intra-vela).
- `optimize_atr.py` — barrido de `atr_period` / `atr_k` para E2-A.

Se archivaron cuando el stop ATR se eliminó del proyecto (2026-11): nunca se
aplicó en ningún backtest y agregaba parámetros muertos. Se conservan solo como
registro de la exploración. La fuente vigente es `scripts/run_resultados.py`.
