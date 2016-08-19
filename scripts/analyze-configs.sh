#!/bin/bash -e
#
# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3

DIR="./"
CHECK="0"
SUFIX="coverage"
PARSE="--parse-cov"

usage () {
    echo "Use this script to collect CPP warnings."
    echo ""
    echo "1st parameter:  path to directory containing configuration files"
    echo "2nd parameter:  path to directory to be compiled (e.g., drivers/usb/) (default: \"./\")"
    echo "3rd parameter:  syntax or coverage analysis (default: coverage)"
}

if [ "$1" = "" ]; then
    echo "Please specify a directory containing configurations."
    echo ""
    usage
    exit 1
fi

# target directory for compilation
if [ "$2" != "" ]; then
    DIR="$2"
fi

# syntax or coverage analysis?
if [ "$3" = "syntax" ]; then
    CHECK="1"
    SUFIX="syntax"
    PARSE="--parse-gcc"
fi

echo "Doing $SUFIX analysis"

for config in "$1"/*
do
    echo "---------------------------------------------------------------------"
    echo "Analyzing config $config"

    echo "Cleaning directory"
    make mrproper > /dev/null

    echo "Expanding config"
    KCONFIG_ALLCONFIG=$config make allyesconfig > /dev/null

    echo "Building kernel.  All CPP warnings will be copied to $config.$SUFIX"
    C=$CHECK time nice -n10 make -j8 $DIR 2>&1 > /dev/null | coverage-analyzer $PARSE > $config.$SUFIX
done
