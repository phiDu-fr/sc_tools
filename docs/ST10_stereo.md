##Connectez ST10 à la paire stéréo

Deux boîtiers ST10 peuvent également être connectés à une paire stéréo sans l'application BOSE et le serveur BOSE.

    Préparer les deux ST10 pour l'accès aux telnets, comme décrit ci-dessus
    Sélectionnez la case à jouer le canal stéréo GAUCHE dans le futur, connectez-vous en tant que root
        Passez au répertoire correct sur cette case

cd /mnt/nv/BoseApp-Persistence/1/

        Voici un fichier GroupService.xml. Dans l'état normal (non apparié), cela a le contenu

<? xml version="1.0" encoding="UTF-8" ? > >
<groupe />

        Remplacez le contenu de ce fichier par

<? xml version="1.0" encoding="UTF-8" ? > >
<groupe id="1234567">
   <name>{NOM DU COUPLE, par ex. "ST10-1 et ST10-2"}</name>
   <masterDeviceId>{BOSE-ID du dispositif maître, par ex. 50338B343905}</masterDieux-devides>
   <roles>
       <groupRole>
           <dieuxId>{BOSE-ID du dispositif maître, par ex. 50338B343905}</appareilId>
           <rôle>LEFT</role>
           <ipAddress>{adresse IP du périphérique maître}</ipAddress>
       </groupRole>
       <groupRole>
           <deviceId>{BOSE-ID du dispositif esclave, par exemple 458790343905}</deviceId>
           <rôle>DROIT</role>
           <ipAddress>{adresse IP de l'appareil esclave}</ipAddress>
       </groupRole>
   </roles>
   <senderIPAddress>{adresse IP du périphérique maître}</senderIPAddress>
</groupe>

        Sauvegarde du fichier et redémarrage de la boîte
    Sélectionnez la boîte à jouer le canal stéréo droit dans le futur, connectez-vous en tant que root
        Passez au répertoire correct sur cette case

cd /mnt/nv/BoseApp-Persistence/1/

        Voici un fichier GroupService.xml. Dans l'état normal (non apparié), cela a le contenu

<? xml version="1.0" encoding="UTF-8" ? > >
<groupe />

        Remplacez le contenu de ce fichier par

<? xml version="1.0" encoding="UTF-8" ? > >
<groupe id="1234567">
   <name>{NOM DU COUPLE, par ex. "ST10-1 et ST10-2"}</name>
   <masterDeviceId>{BOSE-ID du dispositif maître, par ex. 50338B343905}</masterDieux-devides>
   <roles>
       <groupRole>
           <dieuxId>{BOSE-ID du dispositif maître, par ex. 50338B343905}</appareilId>
           <rôle>LEFT</role>
           <ipAddress>{adresse IP du périphérique maître}</ipAddress>
       </groupRole>
       <groupRole>
           <deviceId>{BOSE-ID du dispositif esclave, par exemple 458790343905}</deviceId>
           <rôle>DROIT</role>
           <ipAddress>{adresse IP de l'appareil esclave}</ipAddress>
       </groupRole>
   </roles>
   <senderIPAddress>{adresse IP du périphérique maître}</senderIPAddress>
   <status>GROUP_OK</status>
</groupe>

        Attention: La seule différence avec le fichier sur la boîte de GAUCHE est l'avant-dernière ligne avec l'état
        Sauvegarde du fichier et redémarrage de la boîte

Les commandes de lecture ne sont alors envoyées qu'à la boîte maître, qui se synchronise automatiquement avec l'autre case 