# copied from https://github.com/vrothberg/tabwriter

"""
Python module to write data in a pretty tabular form (e.g., as easy to read csv
files).
"""

# (c) 2015 Valentin Rothberg <valentinrothberg@gmail.com>
#
# Licensed under the terms of the GNU GPL License version 3


import sys


def cast_to_str(data):
    """
    Cast all list elements of double list %data to 'str'.
    """
    cpy = []
    for date in data:
        date = [str(x) for x in date]
        cpy.append(date)
    return cpy


def write(data, fdc=sys.stdout, sep=", "):
    """
    Write all list elements of double list %data in a pretty right-justified
    table separated by %sep (default=", ").
    """
    if len(data) == 0:
        return

    tabmax = [0] * len(data[0])

    data = cast_to_str(data)
    for date in data:
        for i in range(0, len(date)):
            if len(date[i]) > tabmax[i]:
                tabmax[i] = len(date[i])

    for i in range(0, len(data)):
        date = data[i]
        for j in range(0, len(date)):
            fdc.write('{0:>{1}}'.format(date[j], tabmax[j]))
            if j != len(date)-1:
                fdc.write(sep)
        if i != len(data)-1:
            fdc.write('\n')
