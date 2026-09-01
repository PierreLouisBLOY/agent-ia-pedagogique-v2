# Phase 12.16-G2-V4.1 — Modèle de portée des manifests

## Identité d'implémentation approuvée

IMPLEMENTATION_MANIFEST_SHA256 = 79a2a967dca8fdc575e5efcc1138f44d7bfe00e5ac3e4ecf5bbc7478dba3a81d

Cette empreinte identifie le paquet technique présenté à l'approbation propriétaire. Elle reste immuable et n'est pas recalculée à partir des documents de gouvernance ultérieurs.

## Gouvernance post-liaison

GOVERNANCE_MANIFEST_SHA256 = b1beebcf8f009788abf88a34bedab91f1822ca7700450fde357fd0434b651c51

Cette empreinte identifie les preuves documentaires après liaison de l'approbation. Elle ne remplace pas l'identité technique approuvée et ne confère aucune autorisation live.

## Trace de freeze

Le fichier `MANIFEST_SHA256.txt` de ce répertoire couvre les cinq documents de freeze. Le SHA de ce manifest est une trace post-freeze rapportée hors du commit ; il ne devient ni une nouvelle identité technique ni une demande récursive d'approbation.

MANIFEST_SCOPE_MODEL = IMPLEMENTATION_PLUS_GOVERNANCE

MANIFEST_APPROVAL_RECURSION = FORBIDDEN
