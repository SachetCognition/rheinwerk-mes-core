# W2-9 — Mehrstufiger Rückverfolgungsnachweis

Erzeugt aus `tools.trace_demo` (URS-W2-028, TC-W2-036); nicht von Hand pflegen.

Gesperrte Charge: `BATCH-A-0002` · Ebenen: 3

## Vorwärts ab `BATCH-A-0002`

| Ebene | Charge | Artikel | Menge | QS-Status | Verfall | Gesperrte Vorgänger |
|---|---|---|---|---|---|---|
| 1 | `BATCH-C-1001` | RW-CHM-0003 | 20.000 Kg | Freigegeben | 30.06.2027 | BATCH-A-0002 |
| 1 | `BATCH-C-1002` | RW-CHM-0003 | 10.000 Kg | Freigegeben | 31.07.2027 | BATCH-A-0002 |

## Rückwärts ab `BATCH-C-1001`

| Ebene | Charge | Artikel | Menge | QS-Status | Verfall | Gesperrte Vorgänger |
|---|---|---|---|---|---|---|
| 1 | `BATCH-A-0001` | RW-CHM-0001 | 480.000 Kg | Freigegeben | 31.12.2026 | — |
| 1 | `BATCH-A-0002` | RW-CHM-0001 | 20.000 Kg | Gesperrt | 30.06.2026 | — |
| 2 | `SUP-K7-0001` | RW-CHM-0002 | 20.000 Kg | Freigegeben | 30.11.2026 | — |
