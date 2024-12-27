#!/bin/sh

if [ $UID == 0 ]; then
	install -Dm755 constrict.py "/usr/bin/constrict"
else
	echo "Please run this installer as root."
fi