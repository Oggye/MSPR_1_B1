import csv
import json
import math
import os
import subprocess
import sys
from shutil import which
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from threading import Lock

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from app.database import SessionLocal
from app.models import FactsNightTrains

router = APIRouter(prefix="/api/internal", tags=["internal"])

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parents[2] if len(APP_DIR.parents) > 2 else Path("/app")
IA_MODELS_DIR = PROJECT_ROOT / "ia" / "models"
IA_REPORTS_DIR = PROJECT_ROOT / "ia" / "reports"

IA_MANIFEST = IA_MODELS_DIR / "forecast_manifest.json"
IA_CLASSIFIER = IA_MODELS_DIR / "forecast_classifier.joblib"
IA_REGRESSOR = IA_MODELS_DIR / "forecast_regressor.joblib"

IA_CLASSIFICATION_REPORT = (
    IA_REPORTS_DIR / "comparison_classification.csv"
)
IA_REGRESSION_REPORT = (
    IA_REPORTS_DIR / "comparison_regression.csv"
)

PROMETHEUS_URLS = [
    os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
    "http://localhost:9090",
]
GRAFANA_URLS = [
    os.getenv("GRAFANA_URL", "http://grafana:3000"),
    "http://localhost:3001",
]
GITHUB_ACTIONS_API = "https://api.github.com/repos/Oggye/MSPR_1_B3/actions/runs?per_page=10"
RUNNING_TESTS = set()
RUNNING_TESTS_LOCK = Lock()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
    except Exception as exc:
        return {"error": str(exc), "path": str(path)}
    return None


def _data_report_candidates(*parts):
    return [
        PROJECT_ROOT / "data" / Path(*parts),
        Path("/app/data") / Path(*parts),
    ]


def _first_report(paths):
    for path in paths:
        report = _read_json(path)
        if report is not None:
            return report, path
    return None, None


def _latest_data_mtime_ns():
    data_root = next(
        (path for path in [PROJECT_ROOT / "data", Path("/app/data")] if path.exists()),
        None,
    )
    if not data_root:
        return None

    latest = None
    for directory_name in ("raw", "processed", "warehouse"):
        directory = data_root / directory_name
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            try:
                if path.is_file():
                    mtime = path.stat().st_mtime_ns
                    latest = mtime if latest is None else max(latest, mtime)
            except OSError:
                continue
    return latest


def _report_metadata(path, latest_data_mtime_ns=None):
    if not path or not path.exists():
        return {
            "available": False,
            "stale": True,
            "report_modified_at": None,
            "latest_data_at": None,
        }

    report_mtime_ns = path.stat().st_mtime_ns
    return {
        "available": True,
        "stale": bool(
            latest_data_mtime_ns and report_mtime_ns < latest_data_mtime_ns
        ),
        "report_modified_at": datetime.fromtimestamp(
            report_mtime_ns / 1_000_000_000
        ).isoformat(timespec="seconds"),
        "latest_data_at": (
            datetime.fromtimestamp(
                latest_data_mtime_ns / 1_000_000_000
            ).isoformat(timespec="seconds")
            if latest_data_mtime_ns
            else None
        ),
        "path": str(path),
    }


def _http_json(url, timeout=2):
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc), "url": url}


def _first_ok(urls, path):
    last_error = None
    for base_url in urls:
        result = _http_json(f"{base_url}{path}")
        if "error" not in result:
            return result, base_url
        last_error = result
    return last_error or {"error": "service unavailable"}, None


def _prometheus_query(query):
    encoded = query.replace(" ", "%20").replace("[", "%5B").replace("]", "%5D").replace("{", "%7B").replace("}", "%7D").replace('"', "%22").replace("|", "%7C").replace("=", "%3D").replace("~", "~").replace(",", "%2C").replace("*", "%2A")
    result, _ = _first_ok(PROMETHEUS_URLS, f"/api/v1/query?query={encoded}")
    try:
        values = result["data"]["result"]
        if not values:
            return 0
        return float(values[0]["value"][1])
    except Exception:
        return None


def _prometheus_vector(query):
    encoded = query.replace(" ", "%20").replace("[", "%5B").replace("]", "%5D").replace("{", "%7B").replace("}", "%7D").replace('"', "%22").replace("|", "%7C").replace("=", "%3D").replace("~", "~").replace(",", "%2C").replace("*", "%2A")
    result, _ = _first_ok(PROMETHEUS_URLS, f"/api/v1/query?query={encoded}")
    try:
        return [
            {
                "metric": item.get("metric", {}),
                "value": float(item["value"][1]),
            }
            for item in result["data"]["result"]
        ]
    except Exception:
        return []


def _run_command(command, cwd=None, timeout=20):
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "available": True,
            "success": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-6000:],
            "stderr": completed.stderr[-3000:],
            "ran_at": _now(),
        }
    except FileNotFoundError as exc:
        return {"available": False, "success": False, "error": str(exc), "ran_at": _now()}
    except subprocess.TimeoutExpired as exc:
        return {"available": True, "success": False, "error": f"Timeout apres {exc.timeout}s", "ran_at": _now()}
    except Exception as exc:
        return {"available": False, "success": False, "error": str(exc), "ran_at": _now()}


def _docker_compose_cmd():
    if which("docker"):
        check = _run_command(["docker", "compose", "version"], timeout=5)
        if check.get("success"):
            return ["docker", "compose"], "docker compose"
    if which("docker-compose"):
        check = _run_command(["docker-compose", "version"], timeout=5)
        if check.get("success"):
            return ["docker-compose"], "docker-compose"
    return None, None


def _docker_status():
    base_cmd, detected = _docker_compose_cmd()
    if not base_cmd:
        return {
            "available": False,
            "success": False,
            "error": "Docker Compose introuvable (ni `docker compose` ni `docker-compose`).",
            "detected_command": None,
            "services": [],
            "ran_at": _now(),
        }
    command = [*base_cmd, "ps", "--format", "json"]
    result = _run_command(command, cwd=str(PROJECT_ROOT), timeout=8)
    services = []
    if result.get("success"):
        for line in result.get("stdout", "").splitlines():
            try:
                services.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    result["detected_command"] = detected
    if not result.get("success") and not result.get("error"):
        result["error"] = "Docker Compose detecte mais inaccessible depuis l'API."
    result["services"] = services
    return result


def _safe_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _db_totals():
    db = SessionLocal()
    try:
        total_trains = db.query(func.count(FactsNightTrains.fact_id)).scalar() or 0
        total_night = db.query(func.count(FactsNightTrains.fact_id)).filter(FactsNightTrains.is_night.is_(True)).scalar() or 0
        total_day = db.query(func.count(FactsNightTrains.fact_id)).filter(FactsNightTrains.is_night.is_(False)).scalar() or 0
        return {
            "total_trains": int(total_trains),
            "total_night_trains": int(total_night),
            "total_day_trains": int(total_day),
        }
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        db.close()


def _github_actions_status():
    token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"

    try:
        request = urlopen(GITHUB_ACTIONS_API, timeout=4) if not headers else urlopen(Request(GITHUB_ACTIONS_API, headers=headers), timeout=4)
        payload = json.loads(request.read().decode("utf-8"))
        runs = payload.get("workflow_runs", [])
        return {
            "available": True,
            "source": "github_api",
            "runs": [
                {
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "branch": run.get("head_branch"),
                    "updated_at": run.get("updated_at"),
                    "url": run.get("html_url"),
                }
                for run in runs[:10]
            ],
            "message": "Workflows recuperes depuis GitHub Actions.",
        }
    except Exception as exc:
        return {
            "available": False,
            "source": "fallback",
            "runs": [],
            "message": "Connexion GitHub Actions indisponible depuis l'API interne.",
            "error": str(exc),
            "actions_url": "https://github.com/Oggye/MSPR_1_B3/actions",
            "next_steps": "Fournir GITHUB_TOKEN (scope read:actions) et autoriser l'acces sortant reseau.",
        }


def _line_count(path):
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as file:
            return max(sum(1 for _ in file) - 1, 0)
    except Exception:
        return None


def _scan_csv_dir(path, recursive=False, with_lines=False):
    if not path.exists():
        return {"exists": False, "files": 0, "total_size_kb": 0, "details": []}

    files = sorted(path.rglob("*.csv") if recursive else path.glob("*.csv"))
    details = []
    for file in files:
        details.append(
            {
                "name": file.name,
                "path": str(file),
                "size_kb": round(file.stat().st_size / 1024, 2),
                "lines": _line_count(file) if with_lines else None,
            }
        )

    return {
        "exists": True,
        "files": len(files),
        "total_size_kb": round(sum(item["size_kb"] for item in details), 2),
        "details": details,
    }


def _quick_diagnostic_report(reason=None):
    data_dir = PROJECT_ROOT / "data"
    report = {
        "date_diagnostic": _now(),
        "projet": "ObRail Europe - MSPR E6.1",
        "mode": "quick_fallback",
        "reason": reason,
        "raw": _scan_csv_dir(data_dir / "raw", recursive=True, with_lines=False),
        "processed": _scan_csv_dir(data_dir / "processed", recursive=True, with_lines=False),
        "warehouse": _scan_csv_dir(data_dir / "warehouse", recursive=False, with_lines=True),
        "statut": "A_VERIFIER" if reason else "OK",
    }
    report_path = data_dir / "audit" / "diagnostic_report.json"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)
    except Exception as exc:
        report["write_error"] = str(exc)
    return report


def _reports_summary():
    quality, quality_path = _first_report(
        _data_report_candidates("warehouse", "quality_reports.json")
    )
    diagnostic, diagnostic_path = _first_report(
        _data_report_candidates("audit", "diagnostic_report.json")
    )
    latest_data_mtime_ns = _latest_data_mtime_ns()
    return {
        "quality": quality or {},
        "quality_meta": _report_metadata(quality_path),
        "diagnostic": diagnostic,
        "diagnostic_meta": _report_metadata(
            diagnostic_path, latest_data_mtime_ns
        ),
    }

def _read_benchmark_csv(path):
    """
    Lit un petit rapport CSV IA sans dépendance supplémentaire.

    Les rapports sont générés par le pipeline ML dans ia/reports/.
    Si le fichier n'existe pas, la supervision continue simplement
    sans benchmark.
    """
    if not path.exists():
        return []

    try:
        rows = []

        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                cleaned = {}

                for key, value in row.items():
                    if value is None:
                        cleaned[key] = None
                        continue

                    value = value.strip()

                    if value == "":
                        cleaned[key] = None
                        continue

                    if value.lower() == "true":
                        cleaned[key] = True
                        continue

                    if value.lower() == "false":
                        cleaned[key] = False
                        continue

                    try:
                        number = float(value)

                        cleaned[key] = (
                            int(number)
                            if number.is_integer()
                            else number
                        )
                    except ValueError:
                        cleaned[key] = value

                rows.append(cleaned)

        return rows

    except (OSError, csv.Error):
        return []


def _benchmark_payload(path, metric, lower_is_better=False):
    rows = _read_benchmark_csv(path)

    valid_rows = [
        row
        for row in rows
        if isinstance(row.get(metric), (int, float))
    ]

    best_model = None

    if valid_rows:
        if lower_is_better:
            best = min(
                valid_rows,
                key=lambda row: row[metric],
            )
        else:
            best = max(
                valid_rows,
                key=lambda row: row[metric],
            )

        best_model = best.get("model")

    return {
        "available": bool(rows),
        "best_model": best_model,
        "rows": rows,
    }

def _ia_summary():
    artifacts = {
        "manifest": False,
        "classifier": False,
        "regressor": False,
    }

    try:
        artifacts = {
            "manifest": IA_MANIFEST.exists(),
            "classifier": IA_CLASSIFIER.exists(),
            "regressor": IA_REGRESSOR.exists(),
        }

        if not artifacts["manifest"]:
            return {
                "available": False,
                "status": "unavailable",
                "artifacts": artifacts,
                "error": "Manifest IA introuvable",
            }

        manifest = json.loads(
            IA_MANIFEST.read_text(encoding="utf-8")
        )

        if not isinstance(manifest, dict):
            raise ValueError(
                "Le manifest IA doit etre un objet JSON"
            )

        classification = manifest.get(
            "classification",
            {},
        )
        regression = manifest.get(
            "regression",
            {},
        )
        units = manifest.get(
            "units",
            {},
        )

        classification = (
            classification
            if isinstance(classification, dict)
            else {}
        )
        regression = (
            regression
            if isinstance(regression, dict)
            else {}
        )
        units = (
            units
            if isinstance(units, dict)
            else {}
        )

        classification_holdout = classification.get(
            "final_holdout",
            {},
        )
        regression_holdout = regression.get(
            "final_holdout",
            {},
        )

        classification_selection = classification.get(
            "selection",
            {},
        )
        regression_selection = regression.get(
            "selection",
            {},
        )

        classification_holdout = (
            classification_holdout
            if isinstance(classification_holdout, dict)
            else {}
        )
        regression_holdout = (
            regression_holdout
            if isinstance(regression_holdout, dict)
            else {}
        )

        classification_selection = (
            classification_selection
            if isinstance(classification_selection, dict)
            else {}
        )
        regression_selection = (
            regression_selection
            if isinstance(regression_selection, dict)
            else {}
        )

        classification_benchmark = _benchmark_payload(
            IA_CLASSIFICATION_REPORT,
            metric="f1",
            lower_is_better=False,
        )

        regression_benchmark = _benchmark_payload(
            IA_REGRESSION_REPORT,
            metric="mae",
            lower_is_better=True,
        )

        return {
            "available": True,
            "status": (
                "healthy"
                if all(artifacts.values())
                else "degraded"
            ),
            "version": manifest.get("version"),
            "architecture": manifest.get(
                "architecture"
            ),
            "horizons": manifest.get(
                "forecast_horizons",
                [],
            ),
            "final_test_start_year": manifest.get(
                "final_test_target_start_year"
            ),
            "last_updated": datetime.fromtimestamp(
                IA_MANIFEST.stat().st_mtime
            ).isoformat(timespec="seconds"),
            "artifacts": artifacts,

            "classification": {
                "model": classification.get(
                    "selected_model"
                ),
                "selection": classification_selection,
                "overall": classification_holdout.get(
                    "overall",
                    {},
                ),
                "by_horizon": classification_holdout.get(
                    "by_horizon",
                    {},
                ),
                "benchmark": classification_benchmark,
            },

            "regression": {
                "model": regression.get(
                    "selected_model"
                ),
                "baseline": regression.get(
                    "selected_baseline"
                ),
                "unit": units.get("passengers"),
                "selection": regression_selection,
                "overall": regression_holdout.get(
                    "overall",
                    {},
                ),
                "baseline_metrics": (
                    regression_holdout.get(
                        "baseline_only",
                        {},
                    )
                ),
                "by_horizon": regression_holdout.get(
                    "by_horizon",
                    {},
                ),
                "benchmark": regression_benchmark,
            },
        }

    except Exception:
        return {
            "available": False,
            "status": "error",
            "artifacts": artifacts,
            "error": "Impossible de lire le manifest IA",
        }


def _ia_runtime_summary():
    unavailable = {
        "available": False,
        "status": "unavailable",
        "predictions_success": None,
        "predictions_error": None,
        "latency_p95_seconds": None,
        "classification": {"total": 0, "distribution": {}},
        "regression": {"total": 0, "distribution": {}},
    }

    try:
        predictions_success = _prometheus_query(
            'sum(obrail_ai_predictions_total{status="success"})'
        )
        predictions_error = _prometheus_query(
            'sum(obrail_ai_predictions_total{status="error"})'
        )
        if predictions_success is None or predictions_error is None:
            return unavailable

        latency_p95 = _prometheus_query(
            "histogram_quantile(0.95, "
            "sum(rate(obrail_ai_inference_seconds_bucket[5m])) by (le))"
        )
        if latency_p95 is not None and not math.isfinite(latency_p95):
            latency_p95 = None

        classification_rows = _prometheus_vector(
            "sum(obrail_ai_classification_results_total) by (label)"
        )
        regression_rows = _prometheus_vector(
            "sum(obrail_ai_regression_results_total) by (trend)"
        )
        classification_distribution = {
            row["metric"]["label"]: row["value"]
            for row in classification_rows
            if row.get("metric", {}).get("label")
        }
        regression_distribution = {
            row["metric"]["trend"]: row["value"]
            for row in regression_rows
            if row.get("metric", {}).get("trend")
        }

        recent_errors = _prometheus_query(
            'sum(increase(obrail_ai_predictions_total{status="error"}[5m]))'
        )
        predictions_observed = predictions_success + predictions_error
        if predictions_observed <= 0:
            status = "no_data"
        elif recent_errors is not None and recent_errors > 0:
            status = "incident"
        elif latency_p95 is not None and latency_p95 > 1:
            status = "warning"
        else:
            status = "healthy"

        return {
            "available": True,
            "status": status,
            "predictions_success": predictions_success,
            "predictions_error": predictions_error,
            "latency_p95_seconds": latency_p95,
            "classification": {
                "total": sum(classification_distribution.values()),
                "distribution": classification_distribution,
            },
            "regression": {
                "total": sum(regression_distribution.values()),
                "distribution": regression_distribution,
            },
        }
    except Exception:
        return unavailable


@router.get("/overview")
def get_internal_overview():
    health = {"status": "ok", "checked_at": _now()}
    prometheus_targets, prometheus_url = _first_ok(PROMETHEUS_URLS, "/api/v1/targets")
    grafana_search, grafana_url = _first_ok(GRAFANA_URLS, "/api/search")
    reports = _reports_summary()

    active_targets = prometheus_targets.get("data", {}).get("activeTargets", []) if isinstance(prometheus_targets, dict) else []
    fastapi_target = next((target for target in active_targets if target.get("labels", {}).get("job") == "fastapi"), None)
    ia = _ia_summary()
    ia["runtime"] = _ia_runtime_summary()

    metrics = {
        "api_up": _prometheus_query('up{job="fastapi"}'),
        "requests_per_minute": _prometheus_query("sum(rate(http_requests_total[1m])) * 60"),
        "errors_5xx_per_second": _prometheus_query('sum(rate(http_requests_total{status=~"5..|5xx"}[1m])) or vector(0)'),
        "latency_p95_seconds": _prometheus_query("histogram_quantile(0.95, sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))"),
        "latency_avg_seconds": _prometheus_query("sum(rate(http_request_duration_seconds_sum[1m])) / sum(rate(http_request_duration_seconds_count[1m]))"),
        "endpoints": _prometheus_vector("topk(10, sum(rate(http_requests_total[1m])) by (handler)) * 60"),
    }

    return {
        "generated_at": _now(),
        "health": health,
        "metrics": metrics,
        "prometheus": {
            "url": prometheus_url,
            "available": prometheus_url is not None,
            "target": fastapi_target,
            "targets": active_targets,
        },
        "grafana": {
            "url": grafana_url,
            "available": grafana_url is not None,
            "dashboards": grafana_search if isinstance(grafana_search, list) else [],
            "dashboard_url": "http://localhost:3001/d/obrail-api-monitoring/obrail-api-monitoring",
            "ia_dashboard_url": "http://localhost:3001/d/obrail-ia-monitoring/obrail-ia-monitoring",
        },
        "docker": _docker_status(),
        "ci_cd": _github_actions_status(),
        "db_totals": _db_totals(),
        "reports": reports,
        "ia": ia,
    }


@router.post("/diagnostic/run")
def run_diagnostic():
    candidates = [
        PROJECT_ROOT / "etl" / "audit" / "diagnostic.py",
        Path("/app/etl/audit/diagnostic.py"),
    ]
    script = next((path for path in candidates if path.exists()), None)
    if not script:
        return {
            "success": False,
            "available": False,
            "error": "Script diagnostic.py introuvable depuis l'API",
            "ran_at": _now(),
        }

    report_candidates = _data_report_candidates("audit", "diagnostic_report.json")
    mtimes_before = {
        path: path.stat().st_mtime_ns
        for path in report_candidates
        if path.exists()
    }
    result = _run_command([sys.executable, str(script)], cwd=str(script.parents[2]), timeout=120)
    fresh_path = next(
        (
            path
            for path in report_candidates
            if path.exists()
            and path.stat().st_mtime_ns > mtimes_before.get(path, -1)
        ),
        None,
    )

    if not result.get("success"):
        result["report"] = None
        result["stale_report_ignored"] = any(path.exists() for path in report_candidates)
        return result

    report = _read_json(fresh_path) if fresh_path else None
    if not isinstance(report, dict) or report.get("error"):
        result["success"] = False
        result["error"] = "Le diagnostic n'a pas produit de nouveau rapport JSON valide."
        result["report"] = None
        result["stale_report_ignored"] = any(path.exists() for path in report_candidates)
        return result

    result["report"] = report
    result["report_meta"] = _report_metadata(fresh_path, _latest_data_mtime_ns())
    return result


@router.post("/tests/run")
def run_tests():
    test_dir = PROJECT_ROOT / "platform" / "server" / "test"
    if not test_dir.exists():
        test_dir = Path("/app/test")
    if not test_dir.exists():
        return {
            "success": False,
            "available": False,
            "error": "Dossier de tests introuvable depuis l'API",
            "ran_at": _now(),
        }
    return _run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_dir),
            "-vv",
            "-s",
            "-rA",
        ],
        cwd=str(test_dir.parent),
        timeout=240,
    )


def _sse_line(kind, category, text):
    payload = {"kind": kind, "category": category, "line": text, "time": _now()}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/tests/stream")
def stream_tests():
    test_root = PROJECT_ROOT / "platform" / "server" / "test"
    front_root = PROJECT_ROOT / "platform" / "front" / "app"
    if not test_root.exists():
        test_root = Path("/app/test")

    jobs = [
        ("Unit Tests", [sys.executable, "-m", "pytest", str(test_root / "unit"), "-vv", "-s", "-rA"]),
        ("Integration Tests", [sys.executable, "-m", "pytest", str(test_root / "integration"), "-vv", "-s", "-rA"]),
        ("Backend E2E", [sys.executable, "-m", "pytest", str(test_root / "E2E"), "-vv", "-s", "-rA"]),
    ]
    if front_root.exists():
        jobs.append(("Frontend E2E", ["npm", "run", "e2e"]))

    def event_stream():
        for category, cmd in jobs:
            yield _sse_line("section_start", category, f"=== {category} ===")
            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(front_root if category == "Frontend E2E" else test_root.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                yield _sse_line("error", category, f"Commande indisponible: {exc}")
                continue
            except Exception as exc:
                yield _sse_line("error", category, str(exc))
                continue

            for line in iter(process.stdout.readline, ""):
                if line:
                    yield _sse_line("log", category, line.rstrip("\n"))
            process.wait()
            status = "ok" if process.returncode == 0 else "failed"
            yield _sse_line("section_end", category, f"{category}: {status} (code {process.returncode})")
        yield _sse_line("done", "all", "Execution terminee")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


TEST_JOBS = {
    "unit": ("Unit Tests", lambda test_root, front_root: [sys.executable, "-m", "pytest", str(test_root / "unit"), "-vv", "-s", "-rA"], lambda test_root, front_root: str(test_root.parent)),
    "integration": ("Integration Tests", lambda test_root, front_root: [sys.executable, "-m", "pytest", str(test_root / "integration"), "-vv", "-s", "-rA"], lambda test_root, front_root: str(test_root.parent)),
    "backend-e2e": ("Backend E2E", lambda test_root, front_root: [sys.executable, "-m", "pytest", str(test_root / "E2E"), "-vv", "-s", "-rA"], lambda test_root, front_root: str(test_root.parent)),
    "frontend-e2e": ("Frontend E2E", lambda test_root, front_root: ["npm", "run", "e2e"], lambda test_root, front_root: str(front_root)),
}


@router.get("/tests/stream/{category}")
def stream_tests_category(category: str):
    test_root = PROJECT_ROOT / "platform" / "server" / "test"
    front_root = PROJECT_ROOT / "platform" / "front" / "app"
    if not test_root.exists():
        test_root = Path("/app/test")

    if not front_root.exists():
        front_root = Path("/app/frontend")

    selected = TEST_JOBS.get(category)
    if not selected:
        def invalid_stream():
            yield _sse_line("error", "unknown", f"Categorie inconnue: {category}")
            yield _sse_line("done", "unknown", "Execution terminee")
        return StreamingResponse(invalid_stream(), media_type="text/event-stream")

    display_name, cmd_builder, cwd_builder = selected
    if category == "frontend-e2e" and not front_root.exists():
        def missing_front_stream():
            yield _sse_line("error", display_name, "Dossier frontend introuvable pour Frontend E2E.")
            yield _sse_line("done", display_name, "Execution terminee")
        return StreamingResponse(missing_front_stream(), media_type="text/event-stream")

    command = cmd_builder(test_root, front_root)
    command_cwd = cwd_builder(test_root, front_root)

    def event_stream():
        with RUNNING_TESTS_LOCK:
            if category in RUNNING_TESTS:
                yield _sse_line("error", display_name, f"{display_name} deja en cours.")
                yield _sse_line("done", display_name, "Execution terminee")
                return
            RUNNING_TESTS.add(category)

        try:
            yield _sse_line("section_start", display_name, f"=== {display_name} ===")
            try:
                process = subprocess.Popen(
                    command,
                    cwd=command_cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                yield _sse_line("error", display_name, f"Commande indisponible: {exc}")
                yield _sse_line("done", display_name, "Execution terminee")
                return
            except Exception as exc:
                yield _sse_line("error", display_name, str(exc))
                yield _sse_line("done", display_name, "Execution terminee")
                return

            for line in iter(process.stdout.readline, ""):
                if line:
                    yield _sse_line("log", display_name, line.rstrip("\n"))
            process.wait()
            status = "ok" if process.returncode == 0 else "failed"
            yield _sse_line("section_end", display_name, f"{display_name}: {status} (code {process.returncode})")
            yield _sse_line("done", display_name, "Execution terminee")
        finally:
            with RUNNING_TESTS_LOCK:
                RUNNING_TESTS.discard(category)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
