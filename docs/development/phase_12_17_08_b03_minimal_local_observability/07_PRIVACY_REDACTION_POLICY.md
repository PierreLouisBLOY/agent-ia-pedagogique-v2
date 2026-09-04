# Politique de confidentialité et de minimisation

Le schéma est fermé : tout champ non prévu est rejeté. Les noms et valeurs sont bornés et contrôlés avant sérialisation. Sont interdits :

- Authorization header, clés API, tokens, mots de passe, credentials, cookies et secrets de session ;
- prompt complet, réponse fournisseur brute, payload/body/query/headers HTTP et contenu pédagogique ;
- chemin absolu utilisateur, username, valeur d'environnement et donnée SQLite ;
- message d'exception, stack trace, locals, `repr` ou export générique.

Les valeurs qui ressemblent à un bearer token, une clé fournisseur, un chemin Windows/UNC ou un chemin personnel Unix sont rejetées. Les tests utilisent exclusivement des secrets synthétiques et démontrent l'absence de leur texte dans le NDJSON.

```text
SECRET_LEAKAGE = 0
RAW_PAYLOAD_LEAKAGE = 0
PERSONAL_PATH_LEAKAGE = 0
RAW_EXCEPTION_LEAKAGE = 0
NETWORK_EXPORT = 0
```
