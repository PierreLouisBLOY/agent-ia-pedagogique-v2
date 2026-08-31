# 12.16-G2-V4 — Reporting V4 et pairwise implémentés

Le rapport expose désormais la clôture corrective, les checksums du formulaire et du corpus V4, la matrice et le snapshot pricing courants, les cardinalités calculées, le statut humain `PASS_WITH_CORRECTIVE_ATTESTATION`, les canaries persistés et la séparation entre plafond technique proposé et plafond propriétaire approuvé.

Pour chaque score `output:<source_call_id>`, le modèle et le rôle sont ceux de l'appel OpenAI producteur, jamais ceux du scorer Anthropic. Les groupes ayant une paire PRIMARY/FALLBACK produisent une `PairwiseQualityObservation`.

```text
OUTPUT_SCORE_CALLS = 18
PAIRWISE_COMPARISONS = 6
PAIRWISE_SCENARIOS = SCN-03, SCN-06, SCN-07
V4_REPORTING_PAIRWISE = PASS
```

Les compteurs `20/82/102` ne sont pas hardcodés dans le rapport. Le double build reste déterministe et les rapports ne contiennent ni output brut ni secret.
