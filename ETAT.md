# État au 2026-08-16 (session « validation »)

**Session close proprement.** Fork commité (`8849389`, arbre propre), Remote
Script déployé et rechargé, documentation à jour. **Rien n'est en suspens côté
outillage** — il est validé et il ne demande plus rien.

> Une seule chose bloque désormais le teaser, et elle ne dépend pas du code :
> **`E:\WORK\VIDEO\teaser88_v2\audio\sources\` est toujours vide.** Sans les
> mp3 du commerce déposés par Ant, aucun extrait ne peut être choisi.
> C'est le chemin critique de la prochaine session.

## Validation terminée : les cinq handlers passent

Tout ce qui restait en attente a **tourné pour de vrai**. Un défaut a été
trouvé sur le cinquième, corrigé, redéployé et **vérifié après redémarrage**.

La session de Live a été rendue dans l'état où elle a été trouvée : 4 pistes,
2 retours, 120 BPM, piste d'essai et fichiers d'essai supprimés.

### Résultat de la validation

| Handler | Résultat |
|---|---|
| `get_clip_notes` | **OK** — relit les 4 notes écrites, au beat près |
| `remove_clip_notes` | **OK** — fenêtre temps × hauteur chirurgicale (4 → 3), avertit à vide |
| `delete_session_clip` | **OK** — vide le slot |
| `set_clip_fade` (session) | **OK** — rampe vers **0,850** et non 1,0 ; `has_envelopes` passe à `true` |
| `create_arrangement_audio_clip(warp=False)` | **défaut trouvé, corrigé, vérifié** — voir ci-dessous |

Contrôle final, après correction, sur un WAV de 6,000 s :

| Posé avec | Annoncé | Étendue relue | Verdict |
|---|---|---|---|
| `warp=False` | 6,000 s, **+0,00 %**, pas de WARNING | 0 → 12 beats = 6,000 s | conforme |
| `warp=True` | 8,000 s, **+33,33 %**, WARNING | 32 → 48 beats = 8,000 s | conforme |

La détection n'a pas été rendue muette : elle discrimine, et dit vrai des deux
côtés.

### Le défaut trouvé : l'outil anti-mensonge mentait

Un WAV de 6,000 s posé avec `warp=False` était annoncé
« clip 8.000s (**+33.33 %**) » avec un WARNING d'étirement. Mesuré sur le clip
lui-même : `warping=false`, `sample_length` 264 600 @ 44 100 Hz = **6,0000 s**,
`end_time − start_time` = 12 beats = **6,0 s**. **Le clip était parfait ; c'est
la mesure qui était fausse.**

**Racine** : écrire `clip.warping = False` ne fait pas recalculer l'étendue du
clip dans le même tick. `clip.warping` se relit bien `False` tout de suite,
mais `length`, `start_time` et `end_time` décrivent encore l'import warpé —
16 beats au lieu de 12, d'où les 8,000 s et les +33,33 %. Vérifié : dans le
même tick **aucune** propriété d'étendue n'est fraîche, et **une seule**
relecture suffit à les stabiliser (mesuré : la première).

Le faux positif était le pire des deux mensonges possibles : il crie à
l'étirement sur un clip juste, et pousserait à « corriger » ce qui va bien.

**Correction** : la mesure se fait maintenant dans un **second aller-retour**.
`create_arrangement_audio_clip` ne rapporte plus d'étirement du tout — il rend
`clip_index` — et le serveur MCP enchaîne sur le nouveau handler
`measure_arrangement_clip`, qui tombe forcément sur un tick ultérieur.

Commité en `8849389` (Remote Script + `server.py`).
> `origin` pointe vers l'**amont** (`uisato/ableton-mcp-extended`), pas vers un
> fork personnel. **Ne jamais `git push`.** Le travail vit en local sur `main`.

**Leçon générale, valable au-delà de ce handler** : ne jamais mesurer une
conséquence dans le tick qui vient de l'écrire. La règle du projet était « ne
pas croire l'accusé de réception, relire la conséquence observable » — elle est
insuffisante. Une relecture faite trop tôt ment tout autant, et de façon plus
convaincante puisqu'elle a la forme d'une mesure. **La relecture doit être un
aller-retour distinct.**

---

# Archive — session « outillage » du 2026-08-16

> Ce qui suit est **historique**. Les rechargements qu'il réclamait ont été
> faits et la validation qu'il attendait est terminée (voir plus haut).
> Conservé pour les mesures et le raisonnement, pas pour les consignes.

Fork commité (`4aaf24a`), Remote Script déployé, documentation à jour.

## Le test qui tranchait, à l'époque

```bash
./check_ableton.sh                       # les 4 étages doivent être OK
python3 ableton_raw.py get_clip_notes track_index=0 clip_index=0
```

`get_clip_notes` n'existait **que** dans la nouvelle version, donc il tranchait
— la même ruse resservira au prochain rechargement, avec un handler plus
récent (aujourd'hui `measure_arrangement_clip`) :

| Réponse | Lecture |
|---|---|
| `Unknown command` | Live tourne encore sur l'**ancien** script — il n'a pas été redémarré |
| `Slot 0 ... is empty` | script **rechargé** (la session a bien été rouverte à neuf) |
| une liste de notes | script rechargé, et le clip de test est encore là |

## Ce qui a été fait cette session

Tout ce qui suit a été **exécuté**, pas seulement écrit.

### Mesures qui changent la méthode du teaser

- **Live warpe tout import** : 15,000 s → 16,000 s, **+6,1 %**. Poser avec
  `warp=False`.
- **Un mp3 ne commence pas au même endroit dans Live et dans ffmpeg** :
  **84,6 ms**, soit 2,5 images à 29,97 fps. En WAV, l'écart tombe à **0
  échantillon** (vérifié en posant le WAV dans Live et en comparant
  `sample_length`). Donc **jamais de mp3 dans Live**.
- **Ni découpe, ni déplacement, ni fondu ne sont scriptables** dans
  l'arrangement — `end_marker` est accepté et sans effet, `start_marker` est
  remis à zéro en silence, `start_time` est en lecture seule, et les clips
  d'arrangement refusent toute enveloppe (« Not a session clip »). L'écriture
  d'automation d'arrangement n'existe pas dans le LOM.

**Conséquence** : Live assemble, il ne monte pas. Les extraits arrivent déjà
coupés et déjà fondus.

### Défauts corrigés (ils mentaient tous en silence)

- `set_clip_fade` cherchait « Volume » là où Live dit « Track Volume », et
  rampait vers `param.max` = +6 dB au lieu du niveau nominal. Il ne pouvait de
  toute façon pas viser un clip d'arrangement : il vise les slots de session.
- `manage_clip_automation` résolvait un clip d'arrangement — **code mort**, il
  ne pouvait jamais aboutir.
- `set_arrangement_clip_property` renvoyait la valeur écrite ; il renvoie
  maintenant les **conséquences observables** et signale les propriétés inertes.
- `create_arrangement_audio_clip` accepte `warp` et **mesure l'étirement**.
  *(La mesure elle-même était fausse — corrigée depuis, voir plus haut.)*
- `load_instrument_or_effect` annonçait « Devices on track: » suivi de rien
  après un chargement réussi.

### Trous comblés pour la composition

L'amont ne savait qu'**ajouter** des notes : ni les relire, ni les supprimer.
Sans cela il n'y a pas de boucle de travail — on ne peut ni vérifier ni
corriger. Ajoutés : `get_clip_notes`, `remove_clip_notes`,
`delete_session_clip`.

### Outils nouveaux

- `preparer_extrait.py` — découpe à l'échantillon près, fondus cuits dans le
  WAV, rend la longueur en beats. **Testé** : 6,0000 s demandés, 6,0000 s
  obtenus, écart +0,00 ms.
- `ableton_raw.py` — parle directement au Remote Script (se rejoue tout seul
  via le Python Windows, que WSL ne peut pas joindre autrement).
- Skill `piloter-ableton-live` — tout le savoir mesuré, pour ne pas le
  redécouvrir.

## Le banc d'essai, à rejouer après tout rechargement

Il a servi une fois et il resservira : créer une piste audio **jetable**, y
poser un WAV produit par `preparer_extrait.py`, mesurer, supprimer la piste.
La session de Live doit être rendue dans l'état où elle a été trouvée.

C'est lui qui a attrapé le faux +33,33 % ; sans lui, le défaut serait passé
pour une propriété de Live.

## Limite connue, non contournable

Live n'expose **aucune** méthode d'export / render / bounce dans son LOM. Le
rendu final se fait à la main (Ctrl + Maj + R).

## Où est le reste

- Infrastructure, chemins, pièges : `CLAUDE.md` (ce dossier)
- Méthode d'usage de Live : skill `piloter-ableton-live`
- Mesure du son et de l'image : skill `mesurer-son-et-image`
- Projet éditorial du teaser : `E:\WORK\VIDEO\teaser88_v2\audio\README.md`
- Montage image, autre session : `E:\WORK\VIDEO\teaser88\`
