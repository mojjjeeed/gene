# Evaluation sets

## Triage golden set (`triage_golden.csv`)

100 real records across two topics (`triage_plans.json`), exported with a **blank `label` column**.
The PRD's triage gate is Cohen's kappa >= 0.7 between the model's include/exclude and an expert's.

**Nobody has labelled it yet.** The file is a template; `make eval` reports "NOT MEASURED" until it
is labelled, and never prints a score it did not compute.

### How to label

For each row, read the title and abstract and the topic's plan in `triage_plans.json`, then write
`include` or `exclude` in `label`. Judge only against that plan's criteria, not general interest.
Leave a row blank only if you cannot tell; blank rows are left out of scoring and counted.

Label it yourself or have a domain expert do it. Do not have a model label it: the point is an
independent standard to measure the model against. The model's `unsure` is scored as a disagreement.

### Running

    make eval              # score the current triager; fail if kappa regressed against evals/triage_baseline.json
    make eval-update       # accept the current score as the new baseline (do this on purpose)

### Rebuilding the template

    .venv-a9/bin/python -m a9_agents.evals.export_golden   # needs network; overwrites the CSV and any labels in it
