# Some commands

##NAME

### Get speaker Name
```
curl -s http://192.168.1.65:8090/name | xmllint --xpath 'string(//name)' -
```
### Change speaker Name
```
curl -X POST "http://192.168.1.65:8090/name" -H "Content-Type: application/xml" -d '<name>SoundTouch Living Room</name>'
```

## BATTERY

### Battery capable
```
curl -s http://192.168.1.91:8090/powerManagement | xmllint --xpath 'string(//battery/capable)' -
```
### Get battery % charge
```
curl -s http://192.168.1.91:8090/powerManagement | xmllint --xpath 'string(//battery/percentCharge)' -
```
### Running on battery (false = to the power supply)
```
curl -s http://192.168.1.91:8090/powerManagement | xmllint --xpath 'string(//battery/runningOnBattery)' -
```

## PRESETS

### Get the name of preset 1
```
curl -s http://192.168.1.65:8090/presets | xmllint --xpath 'string(//preset[@id="1"]/ContentItem/itemName)' -
```

### Launch preset 2
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="release" sender="Gabbo">PRESET_2</key>'
```

### Save the current playback to preset 2
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">PRESET_2</key>'
```

### Enable shuffle mode SHUFFLE_ON or disable SHUFFLE_OFF
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">SHUFFLE_ON</key>'
```
### Enable repeat mode or disable REPEAT_ALL REPEAT_OFF REPEAT_ONE
```
curl -X POST "http://192.168.1.65:8090/key"  -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">REPEAT_ALL</key>'
```

##CLOCK

### Possible display clock 
```
curl -s http://192.168.1.91:8090/capabilities | xmllint --xpath 'string(//capabilities/clockDisplay)' -
```
### Clock display and setup
```
curl -X POST \
  -H "Content-Type: application/xml" \
  -d '<clockDisplay> <clockConfig timezoneInfo="Europe/Paris" userEnable="true" timeFormat="TIME_FORMAT_24HOUR_ID" userOffsetMinute="0" brightnessLevel="70" userUtcTime="0"/></clockDisplay>' \
  http://192.168.1.65:8090/clockDisplay
```

## POWER

### Check speaker power source="STANDBY", otherwise POWERED ON, no response POWERED OFF
```
curl -s http://192.168.1.65:8090/nowPlaying | xmllint --xpath 'string(//ContentItem/@source)' -
```
### Toggle speaker power state (On/Standby)
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">POWER</key>'
```

##VOLUME

### Current volume
```
curl -s "http://192.168.1.65:8090/volume" | xmllint --xpath 'string(//actualvolume)' -
```
### Set volume 0-100 (example: 9)
```
curl -X POST "http://192.168.1.65:8090/volume" -H "Content-Type: application/xml" -d '<volume>9</volume>'
```
### Volume down
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="release" sender="Gabbo">VOLUME_DOWN</key>'
```
### Volume up
```
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">VOLUME_UP</key>' && \
sleep 0.1 && \
curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="release" sender="Gabbo">VOLUME_UP</key>'
```

## RADIO BROWSER

### Send radio to speaker API radio-browser.info
```
curl -d '<ContentItem source="RADIO_BROWSER" type="stationurl" location="/stations/byuuid/55bdaccc-a91e-4440-9587-4832a8451745"/>' http://192.168.1.65:8090/select
```

##MULTIROOM

### Multiroom Create
```
curl -X POST "http://192.168.1.65:8090/setZone" -H "Content-Type: text/xml" -d '<zone master="E8EB11B9B723"><member ipaddress="192.168.1.65">E8EB11B9B723</member><member ipaddress="192.168.1.82">F9BC35A6D825</member></zone>'
```
### Multiroom Remove Member 
```
curl -X POST "http://192.168.1.65:8090/removeZoneSlave" -H "Content-Type: text/xml" -d '<zone master="E8EB11B9B723"><member ipaddress="192.168.1.82">F9BC35A6D825</member></zone>'
```
### Multiroom Status 
```
curl -s "http://192.168.1.65:8090/getZone"   ### <zone /> if no multiroom
```

## REBOOT

### Reboot the speaker
```
echo "sys reboot" | timeout 1 nc 192.168.1.65 17000
```
### Factory default
```
echo sys factorydefault | timeout 1 nc 192.168.1.65 17000
```
### Endpoints
```
http://192.168.1.65:8090/supportedURLs
```
### Possibilities
```
curl -s http://192.168.1.91:8090/capabilities
```
### Update firmware
```
http://192.168.1.65:17008/update.html  ### https://archive.org/download/bose-soundtouch-software-and-firmware
```
### Trigger a sources refresh on the speaker and reboot
```
curl -sS -X POST 'http://192.168.1.100:8090/notification' -H 'ContentTrigger a sources refresh on the speaker:-Type: application/xml' -d '<updates deviceID="08DF1F1D0EA5"><sourcesUpdated/></updates>'
echo "sys reboot" | timeout 1 nc 192.168.1.65 17000
```
### Change source (ST 300)
```
curl -X POST \
  -H "Content-Type: application/xml" \
  -d '<ContentItem source="PRODUCT" sourceAccount="HDMI_1"><itemName>HDMI_1</itemName></ContentItem>' \
  http://192.168.1.65:8090/select
```

## CONFIGURATIONS

### Timeout on (false = OFF)
```
curl -X POST \
  -H "Content-Type: application/xml" \
  -d "<systemtimeout><powersaving_enabled>true</powersaving_enabled></systemtimeout>" \
  http://192.168.1.65:8090/systemtimeout
```

### Language (5=FR)
```
curl -X POST \
  -H "Content-Type: application/xml" \
  -d "<sysLanguage>5</sysLanguage>"
  http://192.168.1.65:8090/language
```
