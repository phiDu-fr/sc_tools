# Réinitialiser une enceinte

## Configuration usine : 
```bash
echo "sys factorydefault" | nc -w {IP} 17000
```
ou 
```navigateur
http://{IP}:8090/factoryDefault
```

## L'enceinte redémarre en mode serveur (voyant Wifi orange)
Se connecter sur l'enceinte et entrer les codes Wifi

## Changer le compte installation 
```bash
echo "envswitch AccountId set {1234567}" | timeout 2 nc {IP} 17000
```
ou
```bash
~/sc_tools/tools/change_accountID {IP} {1234567}
```
## Finalisation
* Depuis l'appli Bose soundTouch
- Changer le nom
- Changer la langue
- Changer quelques config (horloge, paramètres)

##SoundCork 
http://{IPsoundcork}:8000/admin

```




