# Tableau de vérification de conformité FLAC — RFC 9639

> Source de référence : [RFC 9639 – Free Lossless Audio Codec (FLAC)](https://www.rfc-editor.org/rfc/rfc9639.txt), IETF, décembre 2024.
>
> **Niveaux de gravité :**
> - 🔴 **ERREUR** — violation d'un MUST / MUST NOT → le flux est non conforme
> - 🟡 **AVERTISSEMENT** — violation d'un SHOULD / SHOULD NOT → non conforme mais pas interdit
> - 🔵 **INFO** — comportement optionnel ou réservé méritant attention

---

## 1. Structure générale du fichier

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| G-01 | Le fichier commence par la signature ASCII `fLaC` (0x664C6143) | 🔴 ERREUR | §6 |
| G-02 | Le premier bloc de métadonnées est obligatoirement un STREAMINFO (type 0) | 🔴 ERREUR | §8, §8.2 |
| G-03 | Les blocs de métadonnées précèdent tous les frames audio | 🔴 ERREUR | §6 |
| G-04 | Un et un seul bloc porte le flag `is_last = 1` (dernier bloc de métadonnées) | 🔴 ERREUR | §8.1 |
| G-05 | Aucun frame audio ne précède le dernier bloc de métadonnées | 🔴 ERREUR | §6 |
| G-06 | Toutes les valeurs numériques fixes sont codées en big-endian (sauf les Vorbis comment) | 🔴 ERREUR | §5 |
| G-07 | Toutes les valeurs numériques sont des entiers (aucun flottant) | 🔴 ERREUR | §5 |
| G-08 | Les échantillons sont représentés en signé (two's complement) | 🔴 ERREUR | §5 |

---

## 2. En-tête de bloc de métadonnées (§8.1)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| MH-01 | Le type de bloc est compris entre 0 et 126 | 🔴 ERREUR | §8.1 |
| MH-02 | Le type 127 (0b1111111) est interdit | 🔴 ERREUR | §5, §8.1 |
| MH-03 | Les types 7–126 sont réservés ; un décodeur peut les ignorer mais ne doit pas échouer | 🔵 INFO | §8.1 |
| MH-04 | La taille du bloc (24 bits, big-endian) est cohérente avec la taille réelle des données suivantes | 🔴 ERREUR | §8.1 |
| MH-05 | Un seul bloc porte le flag `last-metadata-block = 1` | 🔴 ERREUR | §8.1 |

---

## 3. STREAMINFO (§8.2)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| SI-01 | Il existe exactement un seul bloc STREAMINFO dans le flux | 🔴 ERREUR | §8.2 |
| SI-02 | STREAMINFO est le premier bloc de métadonnées | 🔴 ERREUR | §8.2 |
| SI-03 | La taille minimale de bloc (`min_block_size`) est ≥ 16 et ≤ 65535 | 🔴 ERREUR | §8.2 |
| SI-04 | La taille maximale de bloc (`max_block_size`) est ≥ 16 et ≤ 65535 | 🔴 ERREUR | §8.2 |
| SI-05 | `min_block_size` ≤ `max_block_size` | 🔴 ERREUR | §8.2 |
| SI-06 | Si `min_block_size == max_block_size`, le fichier est à block size constant | 🔵 INFO | §8.2 |
| SI-07 | Le sample rate est ≥ 1 Hz si le fichier contient de l'audio (0 autorisé pour non-audio) | 🔴 ERREUR | §8.2 |
| SI-08 | Le sample rate ≤ 1 048 575 Hz (20 bits) | 🔴 ERREUR | §8.2 |
| SI-09 | Le nombre de canaux est compris entre 1 et 8 (champ = canaux − 1, codé sur 3 bits) | 🔴 ERREUR | §8.2 |
| SI-10 | La profondeur de bit est comprise entre 4 et 32 (champ = bits − 1, codé sur 5 bits) | 🔴 ERREUR | §8.2 |
| SI-11 | Le nombre total d'interchannel samples (36 bits) est cohérent avec la somme des frames (0 = inconnu) | 🟡 AVERT. | §8.2 |
| SI-12 | Le checksum MD5 est cohérent avec les données audio décodées (0x00…00 = non renseigné) | 🟡 AVERT. | §8.2 |
| SI-13 | `min_frame_size` et `max_frame_size` sont cohérents avec les frames réels (0 = non renseigné) | 🟡 AVERT. | §8.2 |
| SI-14 | Tous les frames (sauf le dernier) ont une taille de bloc ≥ `min_block_size` et ≤ `max_block_size` | 🔴 ERREUR | §8.2 |
| SI-15 | Le dernier frame a une taille de bloc ≤ `max_block_size` (peut être < 16) | 🔴 ERREUR | §8.2 |

---

## 4. PADDING (§8.3)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| PA-01 | La taille du bloc padding est un multiple de 8 bits (= nombre entier d'octets, peut être zéro) | 🔴 ERREUR | §8.3 |
| PA-02 | Tous les octets du padding sont à 0x00 | 🟡 AVERT. | §8.3 (SHOULD implicite) |
| PA-03 | La présence de plusieurs blocs PADDING est légale mais inhabituellement à surveiller | 🔵 INFO | §8.3 |

---

## 5. APPLICATION (§8.4)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| AP-01 | Le bloc contient un Application ID de 32 bits (obligatoire) | 🔴 ERREUR | §8.4 |
| AP-02 | La taille des données applicatives est un multiple de 8 bits | 🔴 ERREUR | §8.4 |
| AP-03 | L'Application ID est enregistré dans le registre IANA "FLAC Application Metadata Block IDs" | 🔵 INFO | §8.4, §12.2 |

---

## 6. SEEK TABLE (§8.5)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| ST-01 | Il existe au plus un seul bloc SEEK TABLE dans le flux | 🔴 ERREUR | §8.5 |
| ST-02 | La taille du bloc est un multiple exact de 18 octets | 🔴 ERREUR | §8.5 |
| ST-03 | Les seek points sont triés par ordre croissant de `sample_number` | 🔴 ERREUR | §8.5.1 |
| ST-04 | Les `sample_number` sont uniques (sauf pour les placeholders 0xFFFFFFFFFFFFFFFF) | 🔴 ERREUR | §8.5.1 |
| ST-05 | Tous les placeholders (0xFFFFFFFFFFFFFFFF) sont regroupés à la fin de la table | 🔴 ERREUR | §8.5.1 |
| ST-06 | Pour les seek points non-placeholder, le `stream_offset` pointe vers le début d'un frame audio valide | 🟡 AVERT. | §8.5.1 |
| ST-07 | Pour les seek points non-placeholder, le `sample_number` correspond au sample number déclaré dans le frame ciblé | 🟡 AVERT. | §8.5.1 |
| ST-08 | Pour les seek points non-placeholder, `frame_samples` correspond au block size réel du frame ciblé | 🟡 AVERT. | §8.5.1 |
| ST-09 | Les `sample_number` des seek points ne dépassent pas le total d'échantillons déclaré dans STREAMINFO (si non nul) | 🟡 AVERT. | §8.5.1 |
| ST-10 | Les `stream_offset` sont strictement croissants en parallèle des `sample_number` | 🟡 AVERT. | §8.5.1 |
| ST-11 | La seek table n'est pas utilisée pour le seeking dans un fichier FLAC encapsulé dans un conteneur | 🔵 INFO | §8.5 |

---

## 7. VORBIS COMMENT (§8.6)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| VC-01 | Il existe au plus un seul bloc VORBIS COMMENT dans le flux | 🔴 ERREUR | §8.6 |
| VC-02 | La longueur du vendor string et des champs sont codées en little-endian (exception à la règle big-endian) | 🔴 ERREUR | §8.6 |
| VC-03 | Le vendor string et les champs sont en UTF-8 | 🔴 ERREUR | §8.6 |
| VC-04 | Le nom de chaque field ne contient que des caractères ASCII imprimables U+0020–U+007E, hors U+003D (=) | 🔴 ERREUR | §8.6 |
| VC-05 | Chaque field contient un séparateur `=` | 🔴 ERREUR | §8.6 |
| VC-06 | La comparaison des noms de champ est insensible à la casse | 🔵 INFO | §8.6 |
| VC-07 | Si présent, le champ `WAVEFORMATEXTENSIBLE_CHANNEL_MASK` est parsé de façon insensible à la casse | 🔴 ERREUR | §8.6.2 |
| VC-08 | La valeur de `WAVEFORMATEXTENSIBLE_CHANNEL_MASK` commence par `0x` | 🟡 AVERT. | §8.6.2 |
| VC-09 | Un fichier utilisant `WAVEFORMATEXTENSIBLE_CHANNEL_MASK` n'est pas "streamable" (au sens §7) | 🔵 INFO | §8.6.2 |

---

## 8. CUESHEET (§8.7)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| CS-01 | Le media catalog number ne contient que des caractères ASCII imprimables 0x20–0x7E, paddé avec 0x00 | 🔴 ERREUR | §8.7 |
| CS-02 | Les bits réservés (7 + 258×8 bits) sont tous à zéro | 🔴 ERREUR | §8.7 |
| CS-03 | Le nombre de pistes est ≥ 1 (la piste lead-out est obligatoire) | 🔴 ERREUR | §8.7 |
| CS-04 | Pour un CD-DA, le nombre de pistes est ≤ 100 (99 pistes + lead-out) | 🔴 ERREUR | §8.7 |
| CS-05 | La dernière piste est toujours la lead-out | 🔴 ERREUR | §8.7 |
| CS-06 | Pour CD-DA, le numéro de lead-out est 170 ; pour les autres, 255 | 🔴 ERREUR | §8.7 |
| CS-07 | Aucun numéro de piste n'est 0 (réservé pour le lead-in CD) | 🔴 ERREUR | §8.7.1 |
| CS-08 | Pour CD-DA, les numéros de piste sont dans la plage 1–99 (sauf lead-out) | 🔴 ERREUR | §8.7.1 |
| CS-09 | Les numéros de piste sont uniques dans le cuesheet | 🔴 ERREUR | §8.7.1 |
| CS-10 | Pour CD-DA, le track offset est divisible par 588 | 🔴 ERREUR | §8.7.1 |
| CS-11 | Les bits réservés de chaque piste (6 + 13×8 bits) sont tous à zéro | 🔴 ERREUR | §8.7.1 |
| CS-12 | Chaque piste (sauf lead-out) a au moins un index point | 🔴 ERREUR | §8.7.1 |
| CS-13 | La lead-out a exactement zéro index point | 🔴 ERREUR | §8.7.1 |
| CS-14 | Pour CD-DA, le nombre d'index points par piste est ≤ 100 | 🔴 ERREUR | §8.7.1 |
| CS-15 | Le premier index point d'une piste a un numéro de 0 ou 1 | 🔴 ERREUR | §8.7.1.1 |
| CS-16 | Les numéros d'index points sont consécutifs et uniques dans la piste | 🔴 ERREUR | §8.7.1.1 |
| CS-17 | Pour CD-DA, l'offset d'index est divisible par 588 | 🔴 ERREUR | §8.7.1.1 |
| CS-18 | Les bits réservés de chaque index point (3×8 bits) sont tous à zéro | 🔴 ERREUR | §8.7.1.1 |

---

## 9. PICTURE (§8.8)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| PI-01 | Le type de picture est compris entre 0 et 20 (les autres valeurs sont réservées) | 🔴 ERREUR | §8.8 |
| PI-02 | Il existe au plus un bloc de type 1 (PNG 32×32) et au plus un de type 2 (General file icon) | 🔴 ERREUR | §8.8 |
| PI-03 | Le media type string ne contient que des caractères ASCII imprimables 0x20–0x7E | 🔴 ERREUR | §8.8 |
| PI-04 | La longueur déclarée du media type string correspond à la longueur réelle | 🔴 ERREUR | §8.8 |
| PI-05 | La longueur déclarée du description string correspond à la longueur réelle | 🔴 ERREUR | §8.8 |
| PI-06 | La longueur déclarée des données image correspond à la longueur réelle | 🔴 ERREUR | §8.8 |
| PI-07 | Si la valeur est un URI (media type = `-->`), l'URI est conforme à RFC 3986 | 🟡 AVERT. | §8.8 |
| PI-08 | Pour le type 1 (PNG icon), les dimensions déclarées sont 32×32 pixels | 🟡 AVERT. | §8.8 |
| PI-09 | Les champs width/height/color_depth/colors sont à 0 si non applicables | 🟡 AVERT. | §8.8 |
| PI-10 | La taille totale du bloc ne dépasse pas 16 MiB (limite du champ de taille de l'en-tête) | 🔴 ERREUR | §8.8 |

---

## 10. En-tête de frame audio (§9.1)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| FH-01 | Chaque frame commence sur un octet aligné | 🔴 ERREUR | §9.1 |
| FH-02 | Le sync code est 0b111111111111100 (15 bits) | 🔴 ERREUR | §9.1 |
| FH-03 | Les 2 premiers octets de chaque frame sont 0xFFF8 (fixed block size) ou 0xFFF9 (variable) | 🟡 AVERT. | §9.1 |
| FH-04 | Le bit de blocking strategy (0=fixed, 1=variable) ne change pas au cours du flux | 🔴 ERREUR | §9.1 |
| FH-05 | Les block size bits ne sont pas 0b0000 (réservé) | 🔴 ERREUR | §9.1.1 |
| FH-06 | Si block size bits = 0b0110 ou 0b0111, l'uncommon block size est présent | 🔴 ERREUR | §9.1.1, §9.1.6 |
| FH-07 | Les sample rate bits ne sont pas 0b1111 (interdit) | 🔴 ERREUR | §5, §9.1.2 |
| FH-08 | Les sample rate bits 0b0000 ne sont autorisés que pour les flux non-streamable | 🔵 INFO | §7, §9.1.2 |
| FH-09 | Les channels bits ne sont pas dans la plage 0b1011–0b1111 (réservés) | 🔴 ERREUR | §9.1.3 |
| FH-10 | Les non-stéréo ne peuvent PAS utiliser les modes left-side (0b1000), side-right (0b1001), mid-side (0b1010) | 🔴 ERREUR | §4.2 |
| FH-11 | Les bit depth bits ne sont pas 0b011 (réservé) | 🔴 ERREUR | §9.1.4 |
| FH-12 | Le bit réservé suivant les bit depth bits est à 0 | 🔴 ERREUR | §9.1.4 |
| FH-13 | Le coded number (sample number ou frame number) est codé en UTF-8 étendu valide | 🔴 ERREUR | §9.1.5 |
| FH-14 | Pour un flux fixed block size, le frame number = nombre de frames précédant le frame courant | 🔴 ERREUR | §9.1.5 |
| FH-15 | Pour un flux variable block size, le sample number = nombre d'échantillons précédant le frame courant | 🔴 ERREUR | §9.1.5 |
| FH-16 | Un frame number ne dépasse pas 31 bits (6 octets encodés) | 🔴 ERREUR | §9.1.5 |
| FH-17 | L'uncommon block size ne vaut pas 65535 (interdit, car block size 65536 impossible dans STREAMINFO) | 🔴 ERREUR | §5, §9.1.6 |
| FH-18 | Les valeurs 0–14 pour uncommon block size (block sizes 1–15) ne sont autorisées que pour le dernier frame | 🔴 ERREUR | §9.1.6 |
| FH-19 | Le sample rate de l'uncommon sample rate n'est pas 0 pour un frame audio | 🔴 ERREUR | §9.1.7 |
| FH-20 | Le CRC-8 de l'en-tête de frame est valide (poly x^8 + x^2 + x + 1, init=0) | 🔴 ERREUR | §9.1.8 |
| FH-21 | Le sample rate déclaré dans le frame est cohérent avec STREAMINFO (si non 0b0000) | 🟡 AVERT. | §9.1.2 |
| FH-22 | La profondeur de bit déclarée dans le frame est cohérente avec STREAMINFO (si non 0b000) | 🟡 AVERT. | §9.1.4 |

---

## 11. Subframes (§9.2)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| SF-01 | Le premier bit de chaque en-tête de subframe est 0 | 🔴 ERREUR | §9.2.1 |
| SF-02 | Les subframe type bits ne sont pas dans les plages réservées 0b000010–0b000111 et 0b001101–0b011111 | 🔴 ERREUR | §9.2.1 |
| SF-03 | Le nombre de subframes par frame est égal au nombre de canaux audio | 🔴 ERREUR | §9 |
| SF-04 | Si le flag wasted bits est 1, le nombre de wasted bits (k) en unaire suit immédiatement | 🔴 ERREUR | §9.2.2 |
| SF-05 | Le nombre de wasted bits est tel que la profondeur de bit effective du subframe est > 0 | 🔴 ERREUR | §9.2.2 |
| SF-06 | Le padding de wasted bits est effectué avant la restauration des canaux stéréo | 🔴 ERREUR | §9.2.2 |
| SF-07 | Un subframe constant ne peut être utilisé que si tous les échantillons du subblock ont la même valeur | 🔴 ERREUR | §4.3, §9.2.3 |
| SF-08 | La profondeur d'un subframe side (mid-side, left-side, side-right) est augmentée de 1 bit | 🔴 ERREUR | §9.2.3 |
| SF-09 | L'ordre du fixed predictor est compris entre 0 et 4 | 🔴 ERREUR | §9.2.5 |
| SF-10 | Les warm-up samples d'un fixed predictor subframe sont au nombre de `predictor_order` | 🔴 ERREUR | §9.2.5 |
| SF-11 | Les warm-up samples d'un LPC subframe sont au nombre de `lpc_order` | 🔴 ERREUR | §9.2.6 |
| SF-12 | La précision des coefficients LPC ne vaut pas 0b1111 (interdit) | 🔴 ERREUR | §5, §9.2.6 |
| SF-13 | Le prediction right shift LPC n'est pas négatif (interdit) | 🔴 ERREUR | §5, §9.2.6 |
| SF-14 | L'ordre LPC est compris entre 1 et 32 | 🔴 ERREUR | §9.2.1 |
| SF-15 | Les valeurs décodées de tous les échantillons sont dans la plage offerte par la bit depth du frame | 🔴 ERREUR | §5 |

---

## 12. Résiduel codé (§9.2.7)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| RC-01 | Les 2 premiers bits du résiduel ne sont pas 0b10 ou 0b11 (réservés) | 🔴 ERREUR | §9.2.7 |
| RC-02 | L'ordre de partition est tel que `block_size % (2^partition_order) == 0` | 🔴 ERREUR | §9.2.7 |
| RC-03 | L'ordre de partition est tel que `(block_size >> partition_order) > predictor_order` | 🔴 ERREUR | §9.2.7 |
| RC-04 | Pour les 4-bit Rice params, le code d'échappement est 0b1111 ; pour les 5-bit, 0b11111 | 🔴 ERREUR | §9.2.7 |
| RC-05 | Toutes les valeurs de résiduel sont dans la plage ±(2^31 − 1) (signed 32-bit, excl. valeur la plus négative) | 🔴 ERREUR | §9.2.7.3 |
| RC-06 | Les valeurs de résiduel utilisent le zigzag encoding (folded residual) | 🔴 ERREUR | §9.2.7.2 |
| RC-07 | Le décodage unaire utilise des bits à 0 terminés par un bit à 1 | 🔴 ERREUR | §5 |

---

## 13. Footer de frame (§9.3)

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| FF-01 | Après le dernier subframe, des bits 0 sont ajoutés jusqu'à l'alignement octet | 🔴 ERREUR | §9.3 |
| FF-02 | Le CRC-16 de fin de frame est valide (poly x^16 + x^15 + x^2 + 1, init=0, couvre tout le frame sauf le CRC) | 🔴 ERREUR | §9.3 |

---

## 14. Contraintes du Streamable Subset (§7)

*(Ces vérifications s'appliquent uniquement si le fichier est censé être "streamable".)*

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| SS-01 | Les sample rate bits sont dans la plage 0b0001–0b1110 (pas de référence au STREAMINFO) | 🔴 ERREUR | §7 |
| SS-02 | Les bit depth bits sont dans la plage 0b001–0b111 (pas de référence au STREAMINFO) | 🔴 ERREUR | §7 |
| SS-03 | Aucun frame ne dépasse 16 384 interchannel samples | 🔴 ERREUR | §7 |
| SS-04 | Pour sample rate ≤ 48 000 Hz, aucun frame ne dépasse 4 608 interchannel samples | 🔴 ERREUR | §7 |
| SS-05 | Pour sample rate ≤ 48 000 Hz, les subframes LPC ont un predictor order ≤ 12 | 🔴 ERREUR | §7 |
| SS-06 | L'ordre de partition Rice est ≤ 8 | 🔴 ERREUR | §7 |
| SS-07 | Le channel ordering correspond à l'un des layouts définis en §9.1.3 (pas de WAVEFORMATEXTENSIBLE) | 🔴 ERREUR | §7 |

---

## 15. Patterns interdits — récapitulatif (§5, Table 1)

| # | Pattern interdit | Niveau | Référence RFC 9639 |
|---|---|---|---|
| FP-01 | Metadata block type = 127 | 🔴 ERREUR | §8.1 |
| FP-02 | min_block_size ou max_block_size < 16 dans STREAMINFO | 🔴 ERREUR | §8.2 |
| FP-03 | Sample rate bits = 0b1111 dans un frame header | 🔴 ERREUR | §9.1.2 |
| FP-04 | Uncommon block size = 65535 (→ block size 65536) | 🔴 ERREUR | §9.1.6 |
| FP-05 | Predictor coefficient precision bits = 0b1111 dans un subframe LPC | 🔴 ERREUR | §9.2.6 |
| FP-06 | Prediction right shift négatif dans un subframe LPC | 🔴 ERREUR | §9.2.6 |

---

## 16. Unicité des blocs de métadonnées

| # | Vérification | Niveau | Référence RFC 9639 |
|---|---|---|---|
| UN-01 | Exactement 1 bloc STREAMINFO | 🔴 ERREUR | §8.2 |
| UN-02 | Au plus 1 bloc SEEK TABLE | 🔴 ERREUR | §8.5 |
| UN-03 | Au plus 1 bloc VORBIS COMMENT | 🔴 ERREUR | §8.6 |
| UN-04 | Au plus 1 image de type 1 (PNG 32×32 icon) | 🔴 ERREUR | §8.8 |
| UN-05 | Au plus 1 image de type 2 (General file icon) | 🔴 ERREUR | §8.8 |
| UN-06 | Plusieurs blocs PADDING sont légaux | 🔵 INFO | §8.3 |
| UN-07 | Plusieurs blocs PICTURE (type ≠ 1 et ≠ 2) sont légaux | 🔵 INFO | §8.8 |

---

## Résumé des comptages

| Catégorie | 🔴 ERREURS | 🟡 AVERTISSEMENTS | 🔵 INFOS |
|---|---|---|---|
| Structure générale | 8 | 0 | 0 |
| En-tête bloc métadonnées | 4 | 0 | 1 |
| STREAMINFO | 10 | 5 | 1 |
| PADDING | 1 | 1 | 1 |
| APPLICATION | 2 | 0 | 1 |
| SEEK TABLE | 5 | 5 | 1 |
| VORBIS COMMENT | 6 | 1 | 3 |
| CUESHEET | 18 | 0 | 0 |
| PICTURE | 7 | 3 | 0 |
| Frame header | 18 | 2 | 2 |
| Subframes | 14 | 0 | 0 |
| Résiduel codé | 7 | 0 | 0 |
| Frame footer | 2 | 0 | 0 |
| Streamable subset | 7 | 0 | 0 |
| Patterns interdits | 6 | 0 | 0 |
| Unicité des blocs | 5 | 0 | 2 |
| **TOTAL** | **120** | **17** | **12** |
