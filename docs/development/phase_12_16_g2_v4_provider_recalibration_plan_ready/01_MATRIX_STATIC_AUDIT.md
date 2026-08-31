# Phase 12.16-G2-V4 — Audit statique de la matrice

L'audit a construit et inspecté la matrice en mémoire, sans client réseau.

## Résultat conforme

| Contrôle | Résultat |
|---|---:|
| Version | `12.16-g2-plan-v1` |
| Snapshot déclaré | `official-2026-08-29` |
| SHA-256 | `997e814f65ac7c5fc25da990cf286800fa6ca4edd761d821a6f6f59f5e2550ed` |
| Appels | `96` |
| OpenAI | `20` |
| Anthropic | `76` |
| `call_id` dupliqués | `0` |
| Sorties brutes | `artifacts/calibration/12.16-g2/raw` |
| Marqueurs de secret | `0` |
| Plafond maximal avec marge | `4.096440 USD` |

Répartition des modèles : `gpt-5.6-terra = 10`, `gpt-5.6-sol = 10`, `claude-sonnet-5 = 76`. Répartition des rôles : `PRIMARY = 14`, `FALLBACK = 6`, `JUDGE = 76`.

`MATRIX_STATIC_AUDIT = PASS` signifie uniquement que la matrice courante est déterministe, bornée et conforme à son ancien contrat.

## Écart bloquant : absence de liaison V4

Les 24 références d'anchors utilisées par la matrice sont des identifiants historiques de la forme `cal.scn-*`. Les 24 anchors canoniques V4 utilisent des identifiants `cal.v4.scn-*`.

```text
MATRIX_ANCHOR_REFERENCE_COUNT = 24
V4_ANCHOR_COUNT = 24
INTERSECTION_COUNT = 0
MATRIX_V4_ANCHOR_BINDING = FAIL
```

Le builder importe le catalogue historique et non `anchor_corpus_v4.py`. L'exécution de cette matrice ne mesurerait donc pas la baseline humaine V4 clôturée.

Décision : ne pas modifier automatiquement la matrice dans ce lot documentaire. Une version de matrice explicitement reliée au corpus V4, rehashée et revue est un prérequis live.
