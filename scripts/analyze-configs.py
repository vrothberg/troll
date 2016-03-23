#!/usr/bin/env python3

"""
Script to analyze trolled configurations.

Visit https://gitlab.cs.fau.de/vrothberg/troll for more information.
"""

# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3


import argparse
import tabwriter


def parse_options():
    """
    User interface of this module.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', dest='configs', action='store',
                        default=False,
                        help="list (batch file) of configs")
    args, _ = parser.parse_known_args()
    return args


def config_count(configs):
    """
    Return a dict of {config size: #configs of this size}.
    """
    data = {}

    with open(configs, "r") as fdc:
        for line in fdc.readlines():
            split = line.split(".")
            size = int(split[-1])

            count = data.get(size, 0) + 1
            data[size] = count

    return data


def main():
    """
    Main routine.
    """
    args = parse_options()

    data = config_count(args.configs)

    out = []
    out.append(["size", "#configs"])
    for size in sorted(data.keys()):
        out.append([size, data[size]])

    tabwriter.write(out)


if __name__ == "__main__":
    main()
