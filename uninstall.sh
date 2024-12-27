#!/bin/sh

if [ $UID == 0 ]; then
	rm "/usr/bin/constrict"
else
	echo "Please run this uninstaller as root."
fi