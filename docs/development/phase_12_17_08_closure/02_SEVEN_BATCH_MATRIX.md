# Matrice des sept lots canoniques

Source des titres et scopes : plan canonique 09, sections B01-B07. Les six commits sont successifs dans l'ascendance de la baseline B07.

| Lot | Titre exact | Commit | Résultat / limites |
|---|---|---|---|
| B01 | Consolidation de provenance | d20428d2c3060546a2c40fc59f0e8b7026be707f | PASS — Six minimisations et EOF18 autorisés ; pas de réécriture historique. |
| B02 | Frontière locale fichiers et SQLite | 2a0ec8f6e24d61e05228119869791999277bfef4 | PASS — Aucune migration de la runtime utilisateur. |
| B03 | Observabilité minimale locale | 2650ae7616fc7067e6c6341f854a10efee633d6f | PASS — Signaux de contrat/composition ; ne prouve pas une application lancée. |
| B04 | Contrat HTTP local-browser fail-closed | b63a1463046141512739e4c8f4618ab967002c78 | PASS — Contrat sans serveur ni endpoint. |
| B05 | Dépendances, environnement et alias de configuration | 313d574cc0aca15529978db622939ed648d0c1c7 | PASS — Réseau B05 one-shot non réutilisé ; configuration persistante non corrigée par B07. |
| B06 | `.gitignore`, tests déterministes et rétention locale | 0404852a3be77381bf7b7c903ee6309e2547487e | PASS — 203 ensembles conservés sans certificat de supprimabilité. |
| B07 | Ré-audit transverse et clôture | Correctif `f28b29f0964d2642b74eb7098f90359d15fb4f0c` ; clôture : commit documentaire porteur de ce paquet | PASS après transaction et postcontrôle de 14 ; 12.18 non commencée. |

Les chemins complets et SHA-256 des manifestes, scopes et prérequis sont dans `08_MACHINE_EVIDENCE.json`, clé `batches`. B07 passe sur sa propre suite globale complète et ses contrôles finaux ; voir 13/14. Le correctif n'ajoute pas un huitième lot.

## Compatibilité des preuves réutilisées

Premier passage : 2240 empreintes PRE/POST identiques. Après le correctif autorisé : 2243/2243 empreintes identiques durant la reprise globale. Les sources de preuve ont été vérifiées à leur état courant, avec les rebindings approuvés, et non contre leurs anciens SHA supersédés.

- B01 : 126 preuves historiques et 11 preuves 05C sont des blobs du commit B01 ; aucun diff vers HEAD. Les 209 chemins de l'allowlist B01 restent suivis. L'inventaire 172, puis les couches 7 + 7 + 10 + 13, ne sont pas confondus avec le libellé initial 165.
- B02/B03/B04 : frontières fichiers/SQLite, composition observabilité et contrat HTTP retestés dans les 122 réussites ciblées. La disponibilité d'un serveur n'est pas déduite des contrats.
- B05 : les trois locks et leurs inputs n'ont pas changé. Deux clean installs hash-required par ensemble ont déjà été prouvées ; elles ne sont pas répétées et le réseau B05 n'est pas réactivé.
- B06 : la suite complète hors seed et les 872 guards d'architecture sont réutilisés uniquement pour leurs invariants inchangés. Ils ne remplacent pas la suite globale B07 incluant le seed : celle-ci a désormais été exécutée avec succès sur la baseline corrigée.
