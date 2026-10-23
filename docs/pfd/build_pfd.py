#!/usr/bin/env python3
"""Conceptual PFD SVG for TK-101 (adapted from manufacturing-skills guidance; original drawing)."""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("tk-101-hold-tank.svg")

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="940" viewBox="0 0 1400 940">
  <rect x="20" y="20" width="1360" height="900" fill="none" stroke="#343a46" stroke-width="1"/>
  <text x="40" y="55" font-family="Segoe UI, Arial, sans-serif" font-size="22" fill="#111418" font-weight="700">TK-101 Steam-Heated Hold Tank</text>
  <text x="40" y="80" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="#5a6472">Temperature-to-steam cascade (TIC-101 / FIC-201) + level (LIC-101). Conceptual — NOT FOR CONSTRUCTION.</text>
  <rect x="1050" y="35" width="300" height="36" fill="none" stroke="#b02418" stroke-width="1.4"/>
  <text x="1200" y="58" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#b02418" font-weight="700">NOT FOR CONSTRUCTION</text>

  <!-- Vessel -->
  <rect x="560" y="280" width="220" height="320" rx="20" fill="#f7f8fa" stroke="#343a46" stroke-width="2"/>
  <rect x="560" y="400" width="220" height="200" fill="#dce8f5" stroke="none"/>
  <text x="670" y="270" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#111418" font-weight="700">TK-101</text>
  <text x="670" y="455" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#5a6472">h_SP = 2.0 m</text>

  <!-- Coil -->
  <path d="M590 480 C620 460,660 500,690 480 S740 460,770 480" fill="none" stroke="#a34a28" stroke-width="2.4"/>
  <text x="680" y="515" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#a34a28">E-101 steam coil</text>

  <!-- Feed (line 1001) -->
  <line x1="120" y1="320" x2="560" y2="320" stroke="#1d4e89" stroke-width="2.4"/>
  <polygon points="560,320 545,314 545,326" fill="#1d4e89"/>
  <text x="300" y="305" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#1d4e89">1001 · Feed FI-101 / TI-100</text>
  <circle cx="200" cy="320" r="18" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="200" y="324" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="10">FT</text>

  <!-- Product: vessel out (1002) then after LV (1003) -->
  <line x1="670" y1="600" x2="670" y2="700" stroke="#1d4e89" stroke-width="2.4"/>
  <line x1="670" y1="700" x2="980" y2="700" stroke="#1d4e89" stroke-width="2.4"/>
  <polygon points="980,700 965,694 965,706" fill="#1d4e89"/>
  <text x="640" y="640" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#1d4e89">1002</text>
  <text x="820" y="690" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#1d4e89">1003 · Product FI-102 / TI-102</text>
  <!-- LV -->
  <polygon points="720,688 740,700 720,712 710,700" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="730" y="730" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11">LV-101</text>

  <!-- Steam supply (2001) / coil (2002) -->
  <line x1="120" y1="520" x2="400" y2="520" stroke="#a34a28" stroke-width="2.4"/>
  <line x1="400" y1="520" x2="400" y2="480" stroke="#a34a28" stroke-width="2.4"/>
  <line x1="400" y1="480" x2="590" y2="480" stroke="#a34a28" stroke-width="2.4"/>
  <polygon points="590,480 575,474 575,486" fill="#a34a28"/>
  <text x="160" y="508" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#a34a28">2001 · Steam PI-201 / TI-201</text>
  <text x="450" y="470" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#a34a28">2002</text>
  <polygon points="350,508 370,520 350,532 340,520" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="355" y="550" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11">TV-101</text>
  <!-- FT-201 steam flow element for FIC-201 (on supply upstream of TV) -->
  <circle cx="250" cy="520" r="18" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="250" y="524" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="9">FT</text>
  <text x="250" y="555" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="10">FT-201</text>
  <!-- condensate (2003) -->
  <line x1="770" y1="480" x2="900" y2="480" stroke="#a34a28" stroke-width="2.4"/>
  <line x1="900" y1="480" x2="900" y2="560" stroke="#a34a28" stroke-width="2.4"/>
  <text x="910" y="520" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#a34a28">2003 · Cond. TI-202</text>

  <!-- Controllers -->
  <rect x="480" y="140" width="56" height="56" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <circle cx="508" cy="168" r="22" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="508" y="172" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="10">TIC</text>
  <text x="508" y="215" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11">TIC-101</text>

  <rect x="300" y="140" width="56" height="56" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <circle cx="328" cy="168" r="22" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="328" y="172" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="10">FIC</text>
  <text x="328" y="215" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11">FIC-201</text>

  <rect x="780" y="620" width="56" height="56" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <circle cx="808" cy="648" r="22" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="808" y="652" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="10">LIC</text>
  <text x="808" y="695" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="11">LIC-101</text>

  <!-- TT-101 on tank temperature PV path (historised as TIC-101.PV) -->
  <circle cx="670" cy="240" r="18" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="670" y="244" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="9">TT</text>
  <text x="700" y="245" font-family="Segoe UI, Arial, sans-serif" font-size="10">TT-101</text>

  <!-- LT-101 on level PV path (historised as LIC-101.PV) -->
  <circle cx="720" cy="600" r="18" fill="#fff" stroke="#343a46" stroke-width="1.6"/>
  <text x="720" y="604" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="9">LT</text>
  <text x="745" y="605" font-family="Segoe UI, Arial, sans-serif" font-size="10">LT-101</text>

  <!-- Signal lines -->
  <line x1="670" y1="280" x2="670" y2="258" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="670" y1="222" x2="670" y2="200" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="670" y1="200" x2="536" y2="168" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="480" y1="168" x2="356" y2="168" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="300" y1="168" x2="360" y2="168" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="328" y1="196" x2="328" y2="520" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="328" y1="520" x2="350" y2="520" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <text x="400" y="155" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#50565f">remote SP</text>
  <line x1="670" y1="600" x2="702" y2="600" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="738" y1="600" x2="808" y2="600" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="808" y1="600" x2="808" y2="620" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="808" y1="676" x2="730" y2="700" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <!-- FT-201 to FIC-201 -->
  <line x1="250" y1="502" x2="250" y2="420" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <line x1="250" y1="420" x2="328" y2="196" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>

  <!-- Design basis note -->
  <text x="40" y="820" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#111418" font-weight="700">Design basis (pilot)</text>
  <text x="40" y="840" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#5a6472">15 m3/h feed @ 25 C; T_SP 75 C; level 2.0 m; steam 6.0 barg; duty ~898 kW; valves ~50%.</text>
  <text x="40" y="860" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#5a6472">Omits relief, isolation, drains. TT-101 / LT-101 / FT-201 historised as TIC/LIC/FIC PVs. Inspired by Scott Duncan / HistorianRCA (CC BY 4.0).</text>
  <text x="40" y="890" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="#5a6472">Rev 1 — universal-plant pilot</text>

  <!-- Legend -->
  <line x1="1050" y1="780" x2="1120" y2="780" stroke="#1d4e89" stroke-width="2.4"/>
  <text x="1130" y="784" font-family="Segoe UI, Arial, sans-serif" font-size="11">Process liquid</text>
  <line x1="1050" y1="805" x2="1120" y2="805" stroke="#a34a28" stroke-width="2.4"/>
  <text x="1130" y="809" font-family="Segoe UI, Arial, sans-serif" font-size="11">Steam / condensate</text>
  <line x1="1050" y1="830" x2="1120" y2="830" stroke="#50565f" stroke-width="1.35" stroke-dasharray="7,5.5"/>
  <text x="1130" y="834" font-family="Segoe UI, Arial, sans-serif" font-size="11">Instrument signal</text>
</svg>
"""

OUT.write_text(SVG, encoding="utf-8")
print(f"Wrote {OUT}")
