# Phase 12.16-G2-V4.2 — Redesign du contrat OpenAI Review

## Décision

Le contrat `12.16-g2-v4.2-compact-review-v1` est intrinsèquement compact. Le plafond
n'est pas simplement porté de 2 048 à 4 096 : `max_output_tokens=3072` est lié à une
forme canonique localement bornée.

Le prompt V4.2 :

- envoie la projection V4 strong correcte une seule fois ;
- ne demande aucune citation ni reproduction de la source ;
- contient uniquement le contexte de scénario nécessaire ;
- demande du JSON strict et compact, sans Markdown.

Le schéma de sortie ferme les propriétés supplémentaires et conserve seulement :

- `assessment`, `correction_required`, `coverage`, `confidence` ;
- au plus 4 `findings`, chacun réduit à un id, une dimension, une sévérité, un
  locator court, une note courte et une action courte ;
- au plus 2 notes courtes.

Les contraintes que le schéma fournisseur ne garantit pas sont réappliquées par le
parser local : types exacts, clés exactes, bornes de longueur et de cardinalité,
unicité des ids/dimensions, cohérence entre assessment, sévérité et
`correction_required`.

## Preuve de terminaison hors ligne

- sortie JSON UTF-8 maximale autorisée localement : 1 536 octets ;
- fixture maximale valide : 1 431 octets ;
- marge structurelle observée : 105 octets ;
- output budget proposé : 3 072 tokens ;
- reasoning effort : `low`.

La fixture remplit toutes les cardinalités et longueurs maximales puis passe le parser
local. Une mutation dépassant une borne est rejetée. Le budget de 3 072 tokens est
donc supérieur à la taille maximale du document canonique, même sous la conversion
conservatrice d'un token par octet. L'augmentation est justifiée par le contrat borné,
et non utilisée pour masquer une réponse non bornée.

## Diagnostic ledger obligatoire

Chaque future Review doit conserver :

- `finish_reason` ;
- `incomplete_reason` ;
- `output_tokens` ;
- `parse_error_category` ;
- `structured_output_validation` ;
- `truncation_classification` parmi `CONFIRMED`, `SUSPECTED`, `OTHER`.

La classification locale reconnaît notamment `incomplete/max_output_tokens` comme
troncature confirmée. Le contrat échoue fermé si son hash, sa forme ou ses bornes
changent.

`REVIEW_CONTRACT_SHA256 = 1201a11ddb6b2d57b28a0f8ab20ce58f87a78e02be555c0c5248edbf525f8b1d`
