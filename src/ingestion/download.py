"""
src/ingestion/download.py

Descargador robusto para Binance Data Vision (klines spot BTCUSDT).

Caracteristicas:
- Descarga mensual (2017-08 .. mes anterior) + diaria (mes en curso)
- Usa scripts oficiales? No: implementacion propia con requests + ThreadPool
- Verifica SHA256 via .CHECKSUM cuando existe
- Reintentos con backoff exponencial
- Guarda ZIPs preservando estructura: data/raw/spot/monthly/klines/BTCUSDT/1m/...
- Logging claro + CLI

Uso:
  python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2017-08-17 --workers 8
  python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2017-08-17 --end 2024-12-31 --no-verify

Requiere: requests, tqdm (opcional pero recomendado)
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

from .binance import BASE_URL, build_kline_url, checksum_url

# ---------------------------------------------------------------------------

DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL = "1m"
DEFAULT_START = "2017-08-17"  # listado BTCUSDT en Binance

# Binance publica mensuales al inicio del mes siguiente.
# Si hoy es 2026-09-01, el mensual de 2026-08 aun puede no estar disponible -> usar daily.

def month_range(start: dt.date, end: dt.date):
    """Yield (year, month) desde start hasta end inclusive por mes."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1

def day_range(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)

def download_one(
    url: str,
    dest: Path,
    session: requests.Session,
    retries: int = 5,
    timeout: int = 60,
    verify_checksum: bool = True,
    overwrite: bool = False,
) -> dict:
    """
    Descarga un ZIP individual. Retorna dict con status.
    """
    if dest.exists() and not overwrite and dest.stat().st_size > 0:
        return {"url": url, "dest": str(dest), "status": "skipped_exists", "bytes": dest.stat().st_size}

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # HEAD primero para verificar existencia (404 = aun no publicado)
            head = session.head(url, timeout=timeout)
            if head.status_code == 404:
                return {"url": url, "dest": str(dest), "status": "not_found_404", "bytes": 0}
            if head.status_code not in (200, 302):
                # intentar GET directo igualmente
                pass

            with session.get(url, stream=True, timeout=timeout) as r:
                if r.status_code == 404:
                    return {"url": url, "dest": str(dest), "status": "not_found_404", "bytes": 0}
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                sha = hashlib.sha256()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)
                            sha.update(chunk)
                # Verificar checksum si se solicita
                if verify_checksum:
                    try:
                        c_url = checksum_url(url)
                        cr = session.get(c_url, timeout=timeout)
                        if cr.status_code == 200:
                            expected = cr.text.strip().split()[0].lower()
                            actual = sha.hexdigest().lower()
                            if expected != actual:
                                tmp.unlink(missing_ok=True)
                                raise ValueError(f"CHECKSUM mismatch: expected {expected[:16]}.. got {actual[:16]}..")
                    except ValueError:
                        raise
                    except Exception:
                        # Si no hay CHECKSUM o falla, no bloquea la descarga
                        pass
                tmp.replace(dest)
                return {"url": url, "dest": str(dest), "status": "downloaded", "bytes": dest.stat().st_size}

        except Exception as e:
            last_err = e
            tmp.unlink(missing_ok=True)
            if attempt < retries:
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
            else:
                return {"url": url, "dest": str(dest), "status": f"failed: {e}", "bytes": 0}
    return {"url": url, "dest": str(dest), "status": f"failed: {last_err}", "bytes": 0}


def download_range(
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
    start: str = DEFAULT_START,
    end: Optional[str] = None,
    raw_dir: str | Path = "data/raw",
    workers: int = 8,
    retries: int = 5,
    timeout: int = 60,
    verify_checksum: bool = True,
    overwrite: bool = False,
) -> list[dict]:
    """
    Descarga todo el historico de klines para el rango dado.
    - Mensual para meses completos (start .. mes anterior a hoy)
    - Diario para el mes en curso (para completar hasta 'end' / hoy)
    """
    raw_dir = Path(raw_dir)
    start_d = dt.date.fromisoformat(start)
    end_d = dt.date.fromisoformat(end) if end else dt.date.today()

    # Separar: todos los meses COMPLETOS (excluye mes de end_d), y dias del mes de end_d
    tasks: list[tuple[str, Path]] = []

    # Para simplicidad: si el rango es largo, descargar todo mensual + daily para ultimo mes
    # Determinar ultimo mes completo: mes anterior a end_d si hoy no ha terminado el mes
    last_full_month_end = (end_d.replace(day=1) - dt.timedelta(days=1))

    # Mensuales: start .. last_full_month_end
    if start_d <= last_full_month_end:
        for y, m in month_range(start_d, last_full_month_end):
            # saltar meses previos al listado donde Binance no tiene data
            if (y, m) < (start_d.year, start_d.month):
                continue
            url = build_kline_url(symbol, interval, y, m)
            # data/raw/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-YYYY-MM.zip
            dest = raw_dir / "spot" / "monthly" / "klines" / symbol / interval / f"{symbol}-{interval}-{y:04d}-{m:02d}.zip"
            tasks.append((url, dest))

    # Diarios: desde max(start_d, primer dia del mes de end_d) hasta end_d
    first_day_current_month = end_d.replace(day=1)
    daily_start = max(start_d, first_day_current_month)
    for d in day_range(daily_start, end_d):
        # si el mensual de este mes ya existe en tasks, no duplicar; pero daily es complemento
        # solo generamos daily para mes en curso (o si start ya esta en mes en curso)
        url = build_kline_url(symbol, interval, d.year, d.month, d.day)
        dest = raw_dir / "spot" / "daily" / "klines" / symbol / interval / f"{symbol}-{interval}-{d.isoformat()}.zip"
        tasks.append((url, dest))

    print(f"[download] {symbol} {interval}  {start_d} -> {end_d}  |  {len(tasks)} archivos  |  workers={workers}")

    results: list[dict] = []
    session = requests.Session()
    # Reuso de conexion + header
    session.headers.update({"User-Agent": "bitcoin-trading-research/1.0"})

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(download_one, url, dest, session, retries, timeout, verify_checksum, overwrite): (url, dest)
            for url, dest in tasks
        }
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Descargando", unit="file"):
            res = fut.result()
            results.append(res)
            # log inmediato para fallos/not_found
            if "failed" in res["status"] or "404" in res["status"]:
                tqdm.write(f"  {res['status']:25s} {res['url']}")

    ok = sum(1 for r in results if r["status"] == "downloaded")
    skipped = sum(1 for r in results if r["status"] == "skipped_exists")
    notfound = sum(1 for r in results if "404" in r["status"])
    failed = sum(1 for r in results if "failed" in r["status"])
    print(f"[download] done: downloaded={ok} skipped={skipped} not_found={notfound} failed={failed}")
    return results


def main():
    p = argparse.ArgumentParser(description="Descarga historico Binance Vision (klines spot)")
    p.add_argument("--symbol", default=DEFAULT_SYMBOL)
    p.add_argument("--interval", default=DEFAULT_INTERVAL)
    p.add_argument("--start", default=DEFAULT_START, help="YYYY-MM-DD (default: 2017-08-17)")
    p.add_argument("--end", default=None, help="YYYY-MM-DD (default: hoy)")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--no-verify", action="store_true", help="No verificar CHECKSUM SHA256")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()

    download_range(
        symbol=args.symbol,
        interval=args.interval,
        start=args.start,
        end=args.end,
        raw_dir=args.raw_dir,
        workers=args.workers,
        retries=args.retries,
        timeout=args.timeout,
        verify_checksum=not args.no_verify,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
