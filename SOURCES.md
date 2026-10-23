# Sources and attribution

## Inspiration

| Work | Link | Licence | Note |
|---|---|---|---|
| HistorianRCA (Scott Duncan) | https://github.com/ScottDuncanAI/HistorianRCA | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Inspired the heated-tank challenge idea and published design-basis numbers; **not** our runtime data source |
| claude-manufacturing-skills | https://github.com/ScottDuncanAI/claude-manufacturing-skills | MIT | Related manufacturing tooling (not vendored) |

## How this project works

- The **real_plant simulator** builds the historian in this repo (`challenge/plant`, `scripts/run_pilot.py`).
- **DWSIM** is the **digital twin** for rate / optimize / fouling detection.
- Upstream projects are cited by URL only; they are not cloned into this tree.
