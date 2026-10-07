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

## Complément issu de la suite globale

Quatre assertions de plan R3B calculent également leurs empreintes à partir
du statut de revalidation. Leurs rapports ont été fabriqués au commit
`12685070a3c7cccd2c1a6ab0a429d1881ac58465`, identifié dans Git. Elles sont
reproduites sur cette fabrication exacte ; la fabrication R5 ne lui est pas
substituée. Aucun checksum ni texte d'approbation ancien n'est modifié. Un
compagnon courant contrôle les empreintes revalidées séparément. Aucun grant
historique ne devient valide pour le plan recalculé.

Les tests de gardes R5 et de mutation AST R3 qui lisent les octets du source
sont explicitement appariés au source historique public. Leurs assertions et
mutations restent inchangées. La garde active protège leurs propriétaires et
chaque fichier du delta actuel. Les assertions privées non satisfaites restent
FAIL : ce complément ne produit aucune attestation des préparations absentes.
Cette revue locale préalable retient la même séparation des garanties ; aucun
ancien garde n'est assoupli et la revue de PR doit examiner les deux couvertures.

Le mock process global des trois assertions d'index R3 remplaçait également
les lectures binaires `git show` nécessaires aux gardes transitives, provoquant
une erreur de type. Ces trois cas deviennent des substitutions du véritable
index Git dans une copie isolée, avec contrôle positif préalable et source
inchangé : propriétaire connu, préparation privée interdite (contenu négatif
explicitement synthétique, sans document privé) et chemin inconnu. Les
prédicats originaux transitifs restent exécutés et doivent rejeter chaque cas.

Le contrôle historique de fichiers R3B comporte aussi un défaut de banc :
ses renderers terminent déjà le Markdown par LF, mais son assertion ajoute
un second LF, absent des fichiers publiés. Le rejeu original conserve ce FAIL.
Le successeur du banc corrige uniquement ces deux additions de LF dans la
copie de test, sous contrat `R2-HISTORICAL-RENDER-CHECK-1.1`. Les renderers,
rapports, JSON, hashes et contrôles du ledger restent inchangés. Le reçu du
banc inventorie le fichier original et le fichier corrigé ; le résultat est
celui du successeur, jamais un PASS rétroactif de l'assertion originale.

La comparaison du ledger conserve le correctif public déjà versionné au
commit `2b378114…` : identités, politique, absence de retry et paramètres de
chaque appel restent exacts ; états, timestamps, coût et reçus des appels
consommés ne sont pas comparés à un template vierge. Seul le corps de cette
assertion publique est repris dans le banc 12685070 ; les imports et le code
de fabrication du rapport restent ceux de 12685070. Le reçu conserve les
empreintes des deux sources du banc. Aucun ledger n'est remis à zéro.
