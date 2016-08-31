#!/usr/bin/env python3

"""Pairwise sampling on the Linux kernel.  Note that a big part of this script
is copied from checkconfigsymbols.py."""

# (c) 2016 Valentin Rothberg <valentinrothberg@gmail.com>
#
# Licensed under the terms of the GNU GPL License version 3


import argparse
import itertools
import os
import re
import signal
import sys

from multiprocessing import Pool, cpu_count
from subprocess import Popen, PIPE, STDOUT


# regex expressions
OPERATORS = r"&|\(|\)|\||\!"
SYMBOL = r"(?:\w*[A-Z0-9]\w*){2,}"
DEF = r"^\s*(?:menu){,1}config\s+(" + SYMBOL + r")\s*"
EXPR = r"(?:" + OPERATORS + r"|\s|" + SYMBOL + r")+"
DEFAULT = r"default\s+.*?(?:if\s.+){,1}"
STMT = r"^\s*(?:if|select|depends\s+on|(?:" + DEFAULT + r"))\s+" + EXPR
SOURCE_SYMBOL = r"(?:\W|\b)+[D]{,1}CONFIG_(" + SYMBOL + r")"

# regex objects
REGEX_FILE_KCONFIG = re.compile(r".*Kconfig[\.\w+\-]*$")
REGEX_SYMBOL = re.compile(r'(?!\B)' + SYMBOL + r'(?!\B)')
REGEX_SOURCE_SYMBOL = re.compile(SOURCE_SYMBOL)
REGEX_KCONFIG_DEF = re.compile(DEF)
REGEX_KCONFIG_EXPR = re.compile(EXPR)
REGEX_KCONFIG_STMT = re.compile(STMT)
REGEX_KCONFIG_HELP = re.compile(r"^\s+(help|---help---)\s*$")
REGEX_FILTER_SYMBOLS = re.compile(r"[A-Za-z0-9]$")
REGEX_NUMERIC = re.compile(r"0[xX][0-9a-fA-F]+|[0-9]+")
REGEX_QUOTES = re.compile("(\"(.*?)\")")


def parse_options():
    """The user interface of this module."""

    parser = argparse.ArgumentParser()

    parser.add_argument('-m', '--model', dest='model', action='store',
                        required=True,
                        help="undertaker .model file to check against")


    parser.add_argument('-l', '--local', dest='local', action='store',
                        default="",
                        help="apply local instead of global sampling with "\
                             "the specified batch file")


    args = parser.parse_args()

    return args


def main():
    """Main function of this module."""

    args = parse_options()

    if args.local:
        local_sampling(args.model, args.local)
    else:
        global_sampling(args.model)

    print("Generated %s configurations of %s initial pairs" % (NVAL, NVAL+NINVAL))


def read_file(path):
    """ Return lines of @path. """
    lines = []
    with open(path, "r") as fdc:
        for line in fdc.readlines():
            lines.append(line.strip())
    return lines


def build_pairs(symbols):
    if len(symbols) == 1:
        return (symbols[0], None)

    return itertools.combinations(symbols, 2)


def local_sampling(model, batch):
    """Apply local sampling in current directory."""
    source_files = read_file(batch)

    syms = []
    for sfile in source_files:
        symbols = parse_source_file(sfile)
        for i in range(len(symbols)):
            symbols[i] = "CONFIG_" + symbols[i]

        print(sfile + " " + str(len(set(symbols))))
        if not symbols:
            print("...skipping")
            continue
        syms.extend(symbols)
        pairs = build_pairs(symbols)
        pairwise(pairs, model)

    print("Found %s distinct symbols" % len(set(syms)))


def global_sampling(model):
    """Apply global sampling in current directory."""
    undefined, defined = check_symbols("")

    undefined = set(undefined)
    defined = set(defined)

    symbols = sorted(list(undefined.union(defined)))
    for i in range(len(symbols)):
        symbols[i] = "CONFIG_" + symbols[i]

    print("Detected %s distinct symbols in all files." % (len(symbols)))
    pairs = build_pairs(symbols)
    pairwise(pairs, model)


def check_expr(expr, model):
    """Check %exp against the %model."""

    cmd = ["undertaker", "-m", model, "-j", "checkexpr", expr]
    stdout = execute(cmd, fail=False)
    return stdout


NINVAL = 0
NVAL = 0

def pairwise(pairs, model):
    """Apply pairwise sampling."""

    global NINVAL
    global NVAL

    for pair in pairs:

        if pair[1] is None:
            expr = "\"%s\"" % (pair[0])
            stdout = check_expr(expr, model)
            if stdout:
                with open("config_%s.pair" % NVAL, "w") as fdc:
                    fdc.write(stdout)
                NVAL += 1
            else:
                NINVAL += 1

            expr = "\"!%s\"" % (pair[0])
            stdout = check_expr(expr, model)
            if stdout:
                with open("config_%s.pair" % NVAL, "w") as fdc:
                    fdc.write(stdout)
                NVAL += 1
            else:
                NINVAL += 1

            continue

        # A && B
        expr = "\"%s && %s\"" % (pair[0], pair[1])
        stdout = check_expr(expr, model)
        if stdout:
            with open("config_%s.pair" % NVAL, "w") as fdc:
                fdc.write(stdout)
            NVAL += 1
        else:
            NINVAL += 1

        # !A && !B
        expr = "\"!%s && !%s\"" % (pair[0], pair[1])
        stdout = check_expr(expr, model)
        if stdout:
            with open("config_%s.pair" % NVAL, "w") as fdc:
                fdc.write(stdout)
            NVAL += 1
        else:
            NINVAL += 1

        # A && !B
        expr = "\"%s && !%s\"" % (pair[0], pair[1])
        stdout = check_expr(expr, model)
        if stdout:
            with open("config_%s.pair" % NVAL, "w") as fdc:
                fdc.write(stdout)
            NVAL += 1
        else:
            NINVAL += 1

        # !A && B
        expr = "\"!%s && %s\"" % (pair[0], pair[1])
        stdout = check_expr(expr, model)
        if stdout:
            with open("config_%s.pair" % NVAL, "w") as fdc:
                fdc.write(stdout)
            NVAL += 1
        else:
            NINVAL += 1


def execute(cmd, fail=True):
    """ Execute %cmd and return stdout.  Exit in case of error.  """

    cmd = " ".join(cmd)

    pop = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    (stdout, _) = pop.communicate()  # wait until finished
    if pop.returncode != 0:
        if fail:
            sys.exit(-1)
        return None

    stdout = stdout.decode(errors='replace')
    return stdout


def partition(lst, size):
    """Partition list @lst into eveni-sized lists of size @size."""

    return [lst[i::size] for i in range(size)]


def init_worker():
    """Set signal handler to ignore SIGINT."""

    signal.signal(signal.SIGINT, signal.SIG_IGN)


def get_files():
    """Return a list of all files in the current git directory."""

    # use 'git ls-files' to get the worklist
    stdout = execute(["git", "ls-files"])
    if len(stdout) > 0 and stdout[-1] == "\n":
        stdout = stdout[:-1]

    files = []
    for gitfile in stdout.rsplit("\n"):
        if ".git" in gitfile or "ChangeLog" in gitfile or      \
                ".log" in gitfile or os.path.isdir(gitfile) or \
                gitfile.startswith("tools/"):
            continue
        files.append(gitfile)
    return files


def check_symbols(ignore):
    """Find undefined Kconfig symbols and return a dict with the symbol as key
    and a list of referencing files as value.  Files matching %ignore are not
    checked for undefined symbols."""

    pool = Pool(cpu_count(), init_worker)
    try:
        return check_symbols_helper(pool, ignore)
    except KeyboardInterrupt:
        pool.terminate()
        pool.join()
        sys.exit(1)


def check_symbols_helper(pool, ignore):
    """Helper method for check_symbols().  Used to catch keyboard interrupts in
    check_symbols() in order to properly terminate running worker processes."""

    source_files = []
    kconfig_files = []
    defined_symbols = []
    referenced_symbols = dict()  # {file: [symbols]}

    for gitfile in get_files():
        if REGEX_FILE_KCONFIG.match(gitfile):
            kconfig_files.append(gitfile)
        else:
            if ignore and not re.match(ignore, gitfile):
                continue
            # add source files that do not match the ignore pattern
            source_files.append(gitfile)

    # parse source files
    arglist = partition(source_files, cpu_count())
    for res in pool.map(parse_source_files, arglist):
        referenced_symbols.update(res)

    # parse kconfig files
    arglist = []
    for part in partition(kconfig_files, cpu_count()):
        arglist.append((part, ignore))
    for res in pool.map(parse_kconfig_files, arglist):
        defined_symbols.extend(res[0])
        referenced_symbols.update(res[1])
    defined_symbols = set(defined_symbols)

    # inverse mapping of referenced_symbols to dict(symbol: [files])
    inv_map = dict()
    for _file, symbols in referenced_symbols.items():
        for symbol in symbols:
            inv_map[symbol] = inv_map.get(symbol, set())
            inv_map[symbol].add(_file)
    referenced_symbols = inv_map

    undefined = {}  # {symbol: [files]}
    for symbol in sorted(referenced_symbols):
        # filter some false positives
        if symbol == "FOO" or symbol == "BAR" or \
                symbol == "FOO_BAR" or symbol == "XXX":
            continue
        if symbol not in defined_symbols:
            if symbol.endswith("_MODULE"):
                # avoid false positives for kernel modules
                if symbol[:-len("_MODULE")] in defined_symbols:
                    continue
            undefined[symbol] = referenced_symbols.get(symbol)
    return undefined, defined_symbols


def parse_source_files(source_files):
    """Parse each source file in @source_files and return dictionary with source
    files as keys and lists of references Kconfig symbols as values."""

    referenced_symbols = dict()
    for sfile in source_files:
        referenced_symbols[sfile] = parse_source_file(sfile)
    return referenced_symbols


def parse_source_file(sfile):
    """Parse @sfile and return a list of referenced Kconfig symbols."""

    lines = []
    references = []

    if not os.path.exists(sfile):
        return references

    with open(sfile, "r", encoding='utf-8', errors='replace') as stream:
        lines = stream.readlines()

    for line in lines:
        if "CONFIG_" not in line:
            continue
        symbols = REGEX_SOURCE_SYMBOL.findall(line)
        for symbol in symbols:
            if not REGEX_FILTER_SYMBOLS.search(symbol):
                continue
            references.append(symbol)

    return references


def get_symbols_in_line(line):
    """Return mentioned Kconfig symbols in @line."""

    return REGEX_SYMBOL.findall(line)


def parse_kconfig_files(args):
    """Parse kconfig files and return tuple of defined and references Kconfig
    symbols.  Note, @args is a tuple of a list of files and the @ignore
    pattern."""

    kconfig_files = args[0]
    ignore = args[1]
    defined_symbols = []
    referenced_symbols = dict()

    for kfile in kconfig_files:
        defined, references = parse_kconfig_file(kfile)
        defined_symbols.extend(defined)
        if ignore and re.match(ignore, kfile):
            # do not collect references for files that match the ignore pattern
            continue
        referenced_symbols[kfile] = references
    return (defined_symbols, referenced_symbols)


def parse_kconfig_file(kfile):
    """Parse @kfile and update symbol definitions and references."""

    lines = []
    defined = []
    references = []
    skip = False

    if not os.path.exists(kfile):
        return defined, references

    with open(kfile, "r", encoding='utf-8', errors='replace') as stream:
        lines = stream.readlines()

    for i in range(len(lines)):
        line = lines[i]
        line = line.strip('\n')
        line = line.split("#")[0]  # ignore comments

        if REGEX_KCONFIG_DEF.match(line):
            symbol_def = REGEX_KCONFIG_DEF.findall(line)
            defined.append(symbol_def[0])
            skip = False
        elif REGEX_KCONFIG_HELP.match(line):
            skip = True
        elif skip:
            # ignore content of help messages
            pass
        elif REGEX_KCONFIG_STMT.match(line):
            line = REGEX_QUOTES.sub("", line)
            symbols = get_symbols_in_line(line)
            # multi-line statements
            while line.endswith("\\"):
                i += 1
                line = lines[i]
                line = line.strip('\n')
                symbols.extend(get_symbols_in_line(line))
            for symbol in set(symbols):
                if REGEX_NUMERIC.match(symbol):
                    # ignore numeric values
                    continue
                references.append(symbol)

    return defined, references


if __name__ == "__main__":
    main()
