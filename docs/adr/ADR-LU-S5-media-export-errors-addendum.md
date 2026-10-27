# Addendum ADR LU-S5 — refus précis des exports média

Statut : PROPOSED_FOR_REVIEW. LU-PRODUIT-01. Complément des contrats média et
companion HTTP déjà relus ; le registre d'erreurs historique R4 reste intact.

Un média requis absent bloque Application avec REQUIRED_MISSING:<visual_id>,
mais r4_error ne reconnaît pas ce nouveau code et rend HTTP 500 générique.
Prévoir une projection compagne fermée dans SavedProductionEndpoint, uniquement
pour les refus nouveaux de l'export média. Ne pas ajouter de wildcard global
au vocabulaire _CODES ni exposer str(exception) libre.

Contrat `P0-MEDIA-EXPORT-REFUSAL-1.0`, statut409, enveloppe error/meta existante :

- PRODUCTION_MEDIA_REQUIRED_MISSING:<identifiant visuel> : code fixe
  PRODUCTION_MEDIA_REQUIRED_MISSING et visual_ref strict
  `[A-Z][A-Z0-9_]{0,39}`.
- PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE:<identifiant section/question> :
  code fixe PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE et anchor_ref strict
  `[SQ][A-Z0-9_-]{1,63}`.
- PRODUCTION_WORD_ANCHOR_AMBIGUOUS : code fixe sans détail libre.

La projection ne s'applique qu'aux opérations preview/word. Si le suffixe ou
l'opération n'est pas conforme, suivre le refus R4 générique historique, sans
fuite de chemin ou de texte d'infrastructure. Le détail ne contient ni bytes,
URL, source privée, candidat professeur ni empreinte financière. Le frontend
peut expliquer le blocage à partir du code et d'un identifiant d'asset.

Objets : API saved_production.py et tests du refus via SavedProductionEndpoint
en invoquant le véritable ExportSavedCommand sur une fixture média requise
absente. Aucun store, permission, fournisseur ou génération. Tests de suffixe
injecté et opération étrangère, R4 historique inchangé, refus nominal409 avec
identité exacte ; Ruff/mypy. Retour arrière : retirer seulement la projection
compagne, préserver tous les records et résultats historiques.
