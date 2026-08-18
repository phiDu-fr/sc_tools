Déporter tes données lourdes sur le SSD de ton Raspberry Pi pour préserver ta carte SD et améliorer les performances.

Cependant, Docker et les liens symboliques (symlinks) ont une relation un peu compliquée.

Voici pourquoi :

* **Si ton `docker-compose.yml` monte le dossier *parent* (`/home/pi/sc_tools/rf/`) :** Le conteneur verra le lien symbolique qui pointe vers `/media/ssd/Podcast`. Mais comme le conteneur n'a pas accès au dossier `/media/ssd/` de ton Raspberry, le lien sera "cassé" à l'intérieur du conteneur.
* **Si ton `docker-compose.yml` monte *exactement* le dossier `Podcast` :** Docker résoudra le lien sur l'hôte au démarrage, et cela fonctionnera.

Pour éviter tout problème sans **absolument rien modifier** à ton `docker-compose.yml`, la méthode la plus simple et la plus robuste n'est pas le lien symbolique, mais le **Bind Mount Linux**. C'est totalement transparent pour Docker : il croira que le dossier est toujours au même endroit.

Voici comment faire, étape par étape.

---

### La solution recommandée : Le Bind Mount

Un "bind mount" au niveau du système d'exploitation permet de monter un dossier existant à un autre endroit de l'arborescence.

**1. Arrête ton conteneur Docker**
Pour éviter de corrompre des fichiers en cours d'écriture :

```bash
cd /chemin/vers/ton/dossier/compose
docker compose down

```

**2. Déplace tes données vers le SSD**
Déplace le dossier lourd vers son nouvel emplacement.

```bash
mv /home/pi/sc_tools/Podcasts /media/ssd/Podcasts
```

**3. Recrée un dossier vide à l'emplacement d'origine**
Ce dossier vide servira de "point d'accroche" (point de montage) pour le SSD.

```bash
mkdir /home/pi/sc_tools/Podcasts
```

**4. Crée le "Bind Mount"**
On va dire à Linux d'afficher le contenu du SSD dans ce dossier vide.

```bash
sudo mount --bind /media/ssd/Podcasts /home/pi/sc_tools/Podcasts
```

**5. Relance Docker**
Ton conteneur y verra que du feu.

```bash
docker compose up -d

```

---

### Rendre la modification permanente (Important)

La commande `mount` au-dessus sera perdue au prochain redémarrage de ton Raspberry Pi. Pour que ce soit permanent, il faut l'ajouter au fichier `/etc/fstab`.

1. Édite le fichier `fstab` :

```bash
sudo nano /etc/fstab

```

2. Ajoute cette ligne tout à la fin du fichier :

```text
/media/ssd/Podcasts    /home/pi/sc_tools/Podcasts    none    bind    0    0

```

3. Sauvegarde et quitte (`Ctrl+O`, `Entrée`, puis `Ctrl+X`).

*(Optionnel)* Pour vérifier que tu n'as pas fait d'erreur de frappe dans le `fstab` (très important pour que le Pi redémarre bien), tape :

```bash
sudo mount -a

```

Si cette commande ne retourne aucune erreur, c'est parfait !
