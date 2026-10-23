# Blind evaluation workspace

Contains **only** participant-facing files. Do not place `private/`, generator code, or answer keys here.

Run diagnostics against `historian.parquet` without importing `challenge.faults` or reading `../private/`.

After you write a submission CSV here, organizers score it against `private/answer_key.csv` (outside this folder). Dev baseline scoring regenerates a local submission via `python scripts/run_diagnostics.py`.
