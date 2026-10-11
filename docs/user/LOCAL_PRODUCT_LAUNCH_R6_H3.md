# Lancement local — R6 / H3

Cette notice décrit le démarrage local hors ligne du produit. Elle ne vaut pas recette navigateur : le runtime SQLite fourni localement doit d’abord être présent et reconnu par son empreinte exacte.

## Préparer la configuration

1. Disposer d’un runtime Projet V2 provisionné localement, hors du dépôt, et de son reçu de provisionnement. Ne pas utiliser la seed canonique comme runtime.
2. Copier `config/local-v2.example.json` dans un fichier prive hors du depot. Les chemins sont des marqueurs a remplacer.
3. Renseigner `runtime_path`, `data_root` et `runtime_sha256` avec les valeurs du reçu local. Le SHA-256 doit être composé de 64 chiffres hexadécimaux minuscules.
4. Si Python 3.12 n’est pas exposé par `py.exe`, ajouter `python_path` au JSON et le faire pointer vers l’interpréteur local Python 3.12.
5. Garder `saved_root` hors du dépôt. `create_saved` reste `false` tant qu’un emplacement d’écriture distinct n’a pas été choisi.

Ne mettez ni base runtime, ni chemin personnel, ni secret dans Git.

## Démarrer et arrêter

Depuis la racine du dépôt, dans PowerShell :

```powershell
.\tools\launch-local.ps1 -ConfigPath 'C:\chemin-prive\launcher.json'
```

Le serveur écoute uniquement sur `127.0.0.1` et le port indiqué par `launcher.json` (8765 dans l’exemple). Ouvrez ensuite l’adresse locale affichée dans le navigateur. Le lanceur garde le serveur au premier plan ; `Ctrl+C` l’arrête. Pour le redémarrer, relancez le script.

Le lanceur refuse une configuration incomplète, une empreinte invalide, un port déjà occupé ou un runtime absent/différent. Ne contournez pas ces refus en désactivant les contrôles.

## Portée et limites de qualification

La reprise du 3 octobre distingue la runtime R5 conforme et la runtime ancienne Boreal. Le refus anterieur venait de la selection du mauvais repertoire avec une ancienne empreinte. Utiliser les trois valeurs du meme recu de provisionnement : runtime_path, data_root, runtime_sha256. Aucun controle d'identite ou ACL n'a ete desactive.

Le lancement normal active uniquement la consultation authentifiee et la bibliotheque de sauvegarde configuree. Aucun generateur synthetique, fournisseur, COUNT, review ou modification n'est active. Les controles correspondants restent inactifs.

Pour rouvrir un document conserve : Retrouver les versions sauvegardees, choisir la version exacte, Rouvrir, puis Sujet eleve et Previsualiser / Telecharger le DOCX editable. Un import Boreal documentaire conserve le sujet historique ; le corrige et le bareme enseignants restent des references separees. Aucun resultat de resolution n'en est deduit.

Les preuves privees de reprise couvrent lancement depuis une extraction propre, recherche/lecture CP645 et reouverture apres arret. Les sept scenarios CP645 sont distingues des mecanismes synthetiques et de la sortie fournisseur historique. La campagne de 628 notions realise la preparation AG03, aucune generation. Les combinaisons non executees restent NOT_PROVEN. Recette et acceptation enseignantes : PENDING.
