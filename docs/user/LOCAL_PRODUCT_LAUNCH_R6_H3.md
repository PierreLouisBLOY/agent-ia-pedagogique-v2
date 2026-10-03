# Lancement local — R6 / H3

Cette notice décrit le démarrage local hors ligne du produit. Elle ne vaut pas recette navigateur : le runtime SQLite fourni localement doit d’abord être présent et reconnu par son empreinte exacte.

## Préparer la configuration

1. Disposer d’un runtime Projet V2 provisionné localement, hors du dépôt, et de son reçu de provisionnement. Ne pas utiliser la seed canonique comme runtime.
2. Copier `config/local-v2.example.json` vers `%LOCALAPPDATA%\ProjetV2\launcher.json`.
3. Renseigner `runtime_path`, `data_root` et `runtime_sha256` avec les valeurs du reçu local. Le SHA-256 doit être composé de 64 chiffres hexadécimaux minuscules.
4. Si Python 3.12 n’est pas exposé par `py.exe`, ajouter `python_path` au JSON et le faire pointer vers l’interpréteur local Python 3.12.
5. Garder `saved_root` hors du dépôt. `create_saved` reste `false` tant qu’un emplacement d’écriture distinct n’a pas été choisi.

Ne mettez ni base runtime, ni chemin personnel, ni secret dans Git.

## Démarrer et arrêter

Depuis la racine du dépôt, dans PowerShell :

```powershell
.\tools\launch-local.ps1
```

Le serveur écoute uniquement sur `127.0.0.1` et le port indiqué par `launcher.json` (8765 dans l’exemple). Ouvrez ensuite l’adresse locale affichée dans le navigateur. Le lanceur garde le serveur au premier plan ; `Ctrl+C` l’arrête. Pour le redémarrer, relancez le script.

Le lanceur refuse une configuration incomplète, une empreinte invalide, un port déjà occupé ou un runtime absent/différent. Ne contournez pas ces refus en désactivant les contrôles.

## Portée et limites de qualification

La validation automatisée du lanceur couvre la configuration absente/invalide, le port occupé et le rejet fermé du runtime absent ou à empreinte différente. La campagne R6 « toutes notions » est une qualification Application hors ligne sur 628 identités ; elle ne prouve pas à elle seule le parcours visuel du navigateur.

À la date de cette livraison, le runtime est présent sur l’hôte, mais son identité SHA-256 ne correspond pas à celle attendue par le reçu de provisionnement Boréal (`RUNTIME_IDENTITY_MISMATCH`). Le contrôle Application a refusé le démarrage. Le lancement réel et la vérification visuelle navigateur restent donc en attente du runtime exact. Aucune base métier n’est modifiée par cette notice ou par les tests R6 hors ligne.
