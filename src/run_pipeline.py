#!/usr/bin/env python3
"""
run_pipeline.py
===============
Lance le pipeline complet dans l'ordre avec :
  - Logs horodatés dans logs/pipeline_YYYYMMDD_HHMMSS.log
  - Rapport final dans logs/pipeline_report.txt
  - Reprise possible depuis une étape (--from-step)
  - Gestion des erreurs : continue ou s'arrête selon --strict

Usage :
    python run_pipeline.py                     # tout lancer
    python run_pipeline.py --from-step 3       # reprendre depuis 03_match_ids
    python run_pipeline.py --skip-avg-positions  # plus rapide (sans positions moyennes SS)
    python run_pipeline.py --dry-run           # afficher les commandes sans les exécuter
"""



import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE    = LOGS_DIR / f"pipeline_{TIMESTAMP}.log"
REPORT_FILE = LOGS_DIR / "pipeline_report.txt"

PYTHON  = sys.executable  # même interpréteur que celui qui lance ce script
SRC_DIR = Path(__file__).parent  # répertoire src/ — indépendant du cwd

# Définition du pipeline
# (step_num, script, args_base, label, estimée_durée_min)
PIPELINE_STEPS = [
    (1, "01_extract_v2.py",  [],                  "Extraction données (SS + Understat)",       55),
    (2, "02_validate.py",    [],                  "Validation périmètre et cohérence",          2),
    (3, "03_match_ids.py",   ["--export-unmatched"], "Matching identités inter-sources",        3),
    (4, "04_merge.py",       [],                  "Construction table maître",                  2),
    (5, "05_features_v2.py", [],                  "Feature engineering (per90 + z-scores)",     5),
    (6, "06_scoring.py",     [],                  "Scoring par rôle FM",                        1),
]


# ──────────────────────────────────────────────────────────────────
# LOGGER
# ──────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(log_path, "w", encoding="utf-8", buffering=1)

    def _write(self, msg: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self.fh.write(line + "\n")

    def info(self,    msg): self._write(f"      {msg}")
    def success(self, msg): self._write(f"  ✅  {msg}")
    def warn(self,    msg): self._write(f"  ⚠   {msg}")
    def error(self,   msg): self._write(f"  ❌  {msg}")
    def section(self, msg): self._write(f"\n{'═'*60}\n  {msg}\n{'═'*60}")
    def step(self,    msg): self._write(f"\n  ── {msg}")

    def close(self):
        self.fh.close()

    def stream_process(self, proc: subprocess.Popen):
        """Stream stdout/stderr du process en temps réel."""
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.info(f"  │  {line}")


# ──────────────────────────────────────────────────────────────────
# EXÉCUTION D'UNE ÉTAPE
# ──────────────────────────────────────────────────────────────────

def run_step(step_num: int, script: str, args: list,
             label: str, estimated_min: int,
             log: Logger, dry_run: bool = False) -> dict:
    """Lance une étape du pipeline et retourne les stats."""

    cmd = [PYTHON, script] + args
    log.step(f"ÉTAPE {step_num} — {label}")
    log.info(f"Commande : {' '.join(cmd)}")
    log.info(f"Durée estimée : ~{estimated_min} min")

    result = {
        "step":       step_num,
        "label":      label,
        "script":     script,
        "status":     "skipped",
        "duration_s": 0,
        "error":      None,
    }

    if dry_run:
        log.info("  [DRY RUN — pas d'exécution]")
        result["status"] = "dry_run"
        return result

    script_path = SRC_DIR / script
    if not script_path.exists():
        log.error(f"Script introuvable : {script_path}")
        result["status"] = "error"
        result["error"]  = "Script introuvable"
        return result

    t_start = time.time()
    try:
        import os
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            [PYTHON, str(script_path)] + (args if args else []),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        log.stream_process(proc)
        proc.wait()

        duration = round(time.time() - t_start)
        result["duration_s"] = duration

        if proc.returncode == 0:
            log.success(f"Étape {step_num} terminée en {duration//60}m{duration%60:02d}s")
            result["status"] = "ok"
        else:
            log.error(f"Étape {step_num} échouée (code {proc.returncode}) après {duration//60}m{duration%60:02d}s")
            result["status"] = "error"
            result["error"]  = f"Return code {proc.returncode}"

    except Exception as e:
        duration = round(time.time() - t_start)
        result["duration_s"] = duration
        result["status"]     = "error"
        result["error"]      = str(e)
        log.error(f"Exception : {e}")

    return result


# ──────────────────────────────────────────────────────────────────
# RAPPORT FINAL
# ──────────────────────────────────────────────────────────────────

def write_report(results: list, total_duration: int, log: Logger):
    lines = [
        "=" * 60,
        "  RAPPORT PIPELINE — Football Scoring Project",
        f"  Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
        "=" * 60,
        "",
        f"  Durée totale : {total_duration // 60}m {total_duration % 60:02d}s",
        "",
        "  Résultats par étape :",
        "",
    ]

    icons = {"ok": "✅", "error": "❌", "dry_run": "🔵", "skipped": "⏭ ", "warning": "⚠ "}
    all_ok = True

    for r in results:
        icon = icons.get(r["status"], "?")
        dur  = f"{r['duration_s']//60}m{r['duration_s']%60:02d}s"
        line = f"  {icon}  Étape {r['step']} — {r['label']:<45} {dur}"
        if r.get("error"):
            line += f"\n       Erreur : {r['error']}"
            all_ok = False
        lines.append(line)

    lines += [
        "",
        "=" * 60,
        "  " + ("SUCCÈS — pipeline complet" if all_ok else "ÉCHEC — voir les erreurs ci-dessus"),
        "",
        "  Fichiers produits :",
        "    data/master/players_scores.csv    ← scores finaux",
        "    data/master/players_features_v2.csv",
        "    data/processed/unmatched_players.csv",
        "",
        "  Exploration des scores :",
        "    python src/06_scoring.py --role CM",
        '    python src/06_scoring.py --player "Mbappé"',
        "    python src/06_scoring.py --role GK --top 10",
        "=" * 60,
    ]

    report = "\n".join(lines)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    log.section("RAPPORT FINAL")
    for line in lines:
        log.info(line)

    print(f"\n  Log complet  : {LOG_FILE}")
    print(f"  Rapport      : {REPORT_FILE}\n")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    # Forcer UTF-8 sur Windows (PowerShell utilise CP1252 par défaut)
    import sys, io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Lance le pipeline Football Scoring de bout en bout",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python run_pipeline.py                      # tout lancer
  python run_pipeline.py --from-step 3        # reprendre depuis match_ids
  python run_pipeline.py --from-step 4        # reprendre depuis le merge (données déjà scrapées)
  python run_pipeline.py --only-step 6        # scoring seul
  python run_pipeline.py --skip-avg-positions  # sans positions moyennes SS (~1.5× plus rapide)
  python run_pipeline.py --dry-run            # voir les commandes sans exécuter
        """
    )
    parser.add_argument("--from-step",        type=int, default=1,
                        help="Reprendre depuis cette étape (1-6, défaut: 1)")
    parser.add_argument("--only-step",        type=int, default=None,
                        help="Exécuter uniquement cette étape")
    parser.add_argument("--skip-avg-positions", action="store_true",
                        help="Passer les positions moyennes SofaScore (plus rapide)")
    parser.add_argument("--strict",           action="store_true",
                        help="Arrêter au premier échec (défaut: continuer)")
    parser.add_argument("--dry-run",          action="store_true",
                        help="Afficher les commandes sans les exécuter")
    parser.add_argument("--season",           default="25/26",
                        help="Saison cible (défaut: 25/26)")
    args = parser.parse_args()

    log = Logger(LOG_FILE)

    log.section(f"PIPELINE FOOTBALL SCORING — {TIMESTAMP}")
    log.info(f"Python     : {PYTHON}")
    log.info(f"Répertoire : {Path.cwd()}")
    log.info(f"From step  : {args.from_step}")
    log.info(f"Saison     : {args.season}")
    log.info(f"Avg positions: {'non' if args.skip_avg_positions else 'oui'}")
    log.info(f"Log          : {LOG_FILE}")

    # Injecter les args dynamiques selon les flags
    step_args_override = {}

    # Étape 1 : ajouter --no-avg-positions si demandé
    if args.skip_avg_positions:
        step_args_override[1] = ["--no-avg-positions", "--season", args.season]
    else:
        step_args_override[1] = ["--season", args.season]

    # Durée totale estimée
    total_est = sum(s[4] for s in PIPELINE_STEPS)
    skip_est  = 15 if args.skip_avg_positions else 0
    log.info(f"Durée estimée : ~{total_est - skip_est} minutes")

    t_global_start = time.time()
    results = []

    for step_num, script, base_args, label, est_min in PIPELINE_STEPS:

        # Filtrage des étapes
        if args.only_step is not None and step_num != args.only_step:
            continue
        if step_num < args.from_step:
            log.info(f"  Étape {step_num} ignorée (from-step={args.from_step})")
            results.append({"step": step_num, "label": label, "script": script,
                            "status": "skipped", "duration_s": 0, "error": None})
            continue

        # Args finaux
        final_args = step_args_override.get(step_num, base_args)

        result = run_step(
            step_num, script, final_args, label, est_min,
            log, dry_run=args.dry_run
        )
        results.append(result)

        if result["status"] == "error" and args.strict:
            log.error("Mode --strict : arrêt du pipeline après erreur")
            break

    total_duration = round(time.time() - t_global_start)
    write_report(results, total_duration, log)
    log.close()


if __name__ == "__main__":
    main()
