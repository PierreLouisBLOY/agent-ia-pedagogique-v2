# Phase 12.17.2A — Recommandation suivante

`NEXT_RECOMMENDED_SUBSTEP = 12.17.3_BUSINESS_RULE_AUDIT`

La remédiation ciblée peut être close avec un defer documenté : 18 diagnostics ont disparu sans régression, et les 15 diagnostics restants sont gelés pour 12.17.4.

La séquence recommandée est :

1. conduire 12.17.3 comme audit indépendant des règles métier, sans corriger la dette résiduelle;
2. en 12.17.4, traiter les six clusters résiduels, y compris la nouvelle contrainte d'identité source de `MYPY-001`;
3. rejouer ensuite le contrôle import-driven et viser `0` erreur sans ignore, exclusion ni affaiblissement de type.

Points de décision requis en 12.17.4 : placement du tooling Anthropic, stratégie de versioning des bundles source, constructeur de cardinalité trois tiers, garde budgétaire commune, propriétaire de `AnchorTier` et contrat commun des specs V5.

Ni 12.17.3 ni 12.17.4 ne sont commencées dans ce lot.
