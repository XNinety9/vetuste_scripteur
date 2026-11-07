# Intégrer Vetuste Scripteur à Printr

Vetuste Scripteur se livre en un seul fichier, `vetuste-scripteur.pyz` : le moteur et la gothique, sans dépendance. Printr l'appelle en sous-processus, comme Barnum, et récupère un PNG noir et blanc qu'il sait déjà imprimer.

Python 3.11 ou plus suffit, et il est déjà présent dans l'image Raspberry Pi et dans le conteneur (Debian bookworm).

## Le contrat

```bash
python3 vetuste-scripteur.pyz --png --largeur=512 --seed=42 --niveau=2 -- "Je mange une pomme"
```

| Élément | Comportement |
| --- | --- |
| `--png` | Écrit un PNG sur la sortie standard, et rien d'autre |
| `--largeur=N` | Obligatoire, de 200 à 4000. L'image fait exactement N pixels de large. Pour Printr : **512** |
| `--seed=N` | Facultatif. Même texte, même seed, même niveau et même largeur donnent la même image |
| `--niveau=N` | Facultatif, de 0 à 3 : vocabulaire seul, léger accent, Les Visiteurs (par défaut), grimoire illisible |
| `-- texte` | Le texte, placé après `--` pour qu'il ne soit jamais lu comme une option |
| Code de sortie | 0 si tout va bien, 2 pour un mauvais usage (message sur la sortie d'erreur) |
| Image | PNG 1 bit, 10 000 px de haut au maximum. Le texte rétrécit si besoin |
| Locale | Fonctionne aussi en locale `C`, donc sous systemd |

Pour le texte seul, sans image, `--json` renvoie `{"original", "result", "seed", "level", "version"}`.

Limites :

- Les caractères absents de la fonte (emojis, idéogrammes) laissent un blanc.
- Le texte passé est exactement `-` : il est lu sur l'entrée standard, donc vide si celle-ci est fermée.

## Côté Rust

[`vetuste.rs`](vetuste.rs) est prêt à copier dans `src/blocks/`. Il suit le modèle de `src/blocks/barnum.rs` et utilise `$PRINTR_VETUSTE` pour trouver la commande.

```rust
let png = vetuste::engrave("Je mange une pomme", raster::PRINT_WIDTH, Some(seed), None)?;
let image = raster::prepare(&raster::decode(&png)?, raster::Dither::None);
```

Il lit la sortie dans un fil à part. C'est nécessaire : une image dépasse vite les 64 Ko d'un tuyau, et attendre la fin du programme avant de lire le bloquerait.

Il reste à écrire le bloc lui-même dans `src/blocks/mod.rs` : variante de `Block`, libellés, et formulaire de l'interface web.

## Côté déploiement

Fige la version et vérifie la somme de contrôle publiée avec la release (`vetuste-scripteur.pyz.sha256`) :

**`deploy/Dockerfile`**

```dockerfile
ARG VETUSTE_VERSION=1.1.1
ADD https://github.com/XNinety9/vetuste_scripteur/releases/download/v${VETUSTE_VERSION}/vetuste-scripteur.pyz /opt/vetuste/vetuste-scripteur.pyz
```

Ajoute aussi `RUN chmod 644 /opt/vetuste/vetuste-scripteur.pyz` et, dans le bloc `ENV`, `PRINTR_VETUSTE="python3 /opt/vetuste/vetuste-scripteur.pyz"`.

**`image/build.sh`, `image/stage-printr/00-printr/01-run.sh` et `deploy/install.sh`** : télécharger le fichier dans `/opt/vetuste/`, là où ils installent `/opt/barnum`.

**`image/printr.env` et `deploy/printr.env.example`**

```bash
PRINTR_VETUSTE="python3 /opt/vetuste/vetuste-scripteur.pyz"
```

## Côté licences

Vetuste Scripteur est sous licence Apache 2.0, comme Printr. Son [`NOTICE`](../../NOTICE), également présent dans le `.pyz`, est à reporter dans celui de Printr, à la suite de celui de CrossWords, comme l'exige la section 4 (d) de la licence.
