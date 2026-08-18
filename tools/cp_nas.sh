#!/bin/bash

nas="192.168.1.150"
usr="phd"
pwd=""
file="sc_tools.lasted.7z"

smbclient //$nas/web -U $usr%$pwd -c 'lcd  /media/ssd/.sauve; cd sc_tools ; put $file'