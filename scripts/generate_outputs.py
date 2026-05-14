from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_master_lifecycle import run as build_master_lifecycle
from scripts.classify_cancellation_reasons import run as classify_reasons
from scripts.match_reengagements import run as match_reengagements
from scripts.normalize_creators import run as normalize_creators
from scripts.pull_salesforce_reports import run as pull_salesforce
from scripts.pull_slack_data import run as pull_slack
from scripts.pull_zendesk_data import run as pull_zendesk
from scripts.generate_visual_report import run as generate_visual_report
from utils.analysis import (
    build_cancellation_reason_analysis,
    build_cohort_analysis,
    build_creator_growth_analysis,
    build_reengagement_output,
    build_rise_creator_analysis,
    cohort_summary,
    write_executive_summary,
)
from utils.config import ensure_project_dirs, load_settings
from utils.io import read_csv, write_csv


def run(run_pulls: bool = False, force_salesforce_api: bool = False) -> None:
    settings = load_settings(ROOT)
    ensure_project_dirs(settings)

    if run_pulls:
        pull_salesforce(force_api=force_salesforce_api)
        pull_zendesk()
        pull_slack()

    normalize_creators()
    match_reengagements()
    classify_reasons()
    build_master_lifecycle()

    master = read_csv(settings.output_dir / "master_creator_lifecycle.csv")

    reengaged_output = build_reengagement_output(master)
    cohort_analysis = build_cohort_analysis(master)
    cancellation_analysis = build_cancellation_reason_analysis(master)
    creator_growth_analysis = build_creator_growth_analysis(master)
    rise_creator_analysis = build_rise_creator_analysis(master)
    cadence_analysis = cohort_summary(master, "Macro Cadence", "macro_cadence")

    write_csv(master, settings.output_dir / "master_creator_lifecycle.csv")
    write_csv(reengaged_output, settings.output_dir / "reengaged_creators.csv")
    write_csv(cohort_analysis, settings.output_dir / "cohort_analysis.csv")
    write_csv(cadence_analysis, settings.output_dir / "cadence_analysis.csv")
    write_csv(cancellation_analysis, settings.output_dir / "cancellation_reason_analysis.csv")
    write_csv(creator_growth_analysis, settings.output_dir / "creator_growth_analysis.csv")
    write_csv(rise_creator_analysis, settings.output_dir / "rise_creator_analysis.csv")
    write_executive_summary(
        settings.output_dir / "executive_summary.md",
        master,
        cohort_analysis,
        creator_growth_analysis,
        rise_creator_analysis,
    )
    generate_visual_report()

    print(f"Wrote outputs to {settings.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all business-readable outputs.")
    parser.add_argument("--run-pulls", action="store_true", help="Pull source data before analysis.")
    parser.add_argument("--force-salesforce-api", action="store_true", help="Refresh Salesforce even if raw CSVs exist.")
    args = parser.parse_args()
    run(run_pulls=args.run_pulls, force_salesforce_api=args.force_salesforce_api)


if __name__ == "__main__":
    main()
