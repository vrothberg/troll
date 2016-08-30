#!/bin/bash -e
#
# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3

if [ "$1" = "" ]; then
    echo "Please specify a directory containing configurations."
    echo ""
    usage
    exit 1
fi

for config in "$1"/*
do
    echo "---------------------------------------------------------------------"
    echo "Analyzing config $config"

    echo "Cleaning directory"
    make mrproper > /dev/null

    echo "Expanding config"
    KCONFIG_ALLCONFIG=$config make allyesconfig > $config.kconfig
done
