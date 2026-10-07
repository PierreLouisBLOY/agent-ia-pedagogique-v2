# ADR — Rapport historique et revalidation courante de calibration

## Constat et revue préalable

Le rapport JSON historique conserve l'empreinte
`f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272`.
Son test original passe sur la fabrication publique `5b6f563…`, avec les
321 pièces privées préexistantes copiées et vérifiées. Le même rendu avec les
validateurs actuels diffère sur un seul résultat REVIEW_SOL, PARTIAL devenu
SUCCEEDED, ses compteurs et l'empreinte dérivée. Les données, scores, coûts,
tokens et réponses historiques ne changent pas. Ce rejeu local ne transforme
pas la revue fournisseur historique en une nouvelle acceptation pédagogique.

## Décision limitée

Le contrôle des octets historiques exécute le test original inchangé sur le
code Git historique authentifié. Une preuve privée absente échoue explicitement,
sans skip, substitution ou reconstruction de réponse. Un compagnon courant
vérifie la déterminisation, l'absence de données sensibles et l'empreinte exacte
du rapport revalidé. Il conserve séparément l'empreinte historique et le delta.
Les rapports originaux restent inchangés. Aucune equality historique n'est
supprimée : elle est exécutée avec le code qui a fabriqué le rapport.

La revue locale confirme la séparation des deux garanties et la conservation
des assertions originales. Le successeur de garde protège ce delta. Les
résultats du rejeu courant ne prouvent aucun nouvel appel, tarif, admission,
signature enseignante ou autorisation live. La PR doit relire cette évolution.
