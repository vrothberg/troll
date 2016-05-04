#!/bin/bash -e
#
# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3

usage () {
    echo "Use this script to collect CPP warnings."
    echo ""
    echo "1st parameter:  path to directory containing configuration files"
    echo "2nd parameter:  path to directory to be compiled (e.g., drivers/usb/) (default: \"./\")"
}

if ["$1" == ""]; then
    echo "Please specify a directory containing configurations."
    echo ""
    usage
    exit 1
fi

DIR="./"

if ["$2" != ""]; then
    DIR="$2"
fi

for config in "$1"/*
do
    echo "Analyzing config $config"

    echo "Cleaning directory"
    make mrproper > /dev/null

    echo "Expanding config"
    KCONFIG_ALLCONFIG=$config make allyesconfig > /dev/null

    echo "Building kernel.  All CPP warnings will be copied to $config.warnings"
    time nice -n10 make C=0 -j8 $2/ 2>&1 > /dev/null | coverage-analyzer --parse-gcc > $config.warnings
done
