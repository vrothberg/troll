#!/usr/bin/env python2

"""
Script to analyze trolled configurations.
"""

# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3


import argparse
import logging
import os
import pickle
import re
import signal
import sys

from multiprocessing import Pool, cpu_count
from subprocess import Popen, PIPE, STDOUT


REGEX_BLOCK = re.compile(r"^\s*#(if|else|elif)")
REGEX_ESC   = re.compile(r".*\\\s*$")
REGEX_WARN  = re.compile(r"\s*#warning COVERAGE FILE:([^\s]*) LINE:([0-9]+) BLOCK:([0-9]+)")


def parse_options():
    """
    User interface of this module.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-a', '--analyze', dest='analyze', action='store_true',
                        default=False,
                        help="analyze coverage (in Linux tree only)")

    parser.add_argument('-b', '--batch', dest='batch', action='store',
                        default=None,
                        help="batchfile")

    parser.add_argument('-c', '--config', dest='config', action='store',
                        default="",
                        help="use this config for analysis (make only)")

    parser.add_argument('--count', dest='count', action='store_true',
                        default=False,
                        help="count number of CPP blocks")

    parser.add_argument('-e', '--expand', dest='expand', action='store_true',
                        default=False,
                        help="expand specified configurations")

    parser.add_argument('-i', '--insert', dest='insert', action='store_true',
                        default=False,
                        help="insert CPP warnings")

    parser.add_argument('-f', '--file', dest='file', action='store',
                        default=None,
                        help="file")

    parser.add_argument('-t', '--threads', dest='threads', action='store',
                        default=None,
                        help="specify number of threads")

    parser.add_argument('-s', '--strategy', dest='strategy', action='store',
                        default="allnoconfig",
                        help="expansion strategy for all unspecified options (-e)")

    parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                        default=0,
                        help="increase verbosity (specify multiple times for more)")

    parser.add_argument('--dump', dest='dump', action='store',
                        default=None,
                        help="dump coverage data to this file (pickle format)")

    parser.add_argument('--load', dest='load', action='store',
                        default=None,
                        help="load (previously dumped) file (pickle format) " \
                             "and do coverage analysis")

    parser.add_argument('--parse-gcc', dest='parse_gcc', action='store_true',
                        default=False,
                        help="parse GCC compiler warnings from stdin, e.g. via 'make 2>&1 > /dev/null | ...'")

    args, _ = parser.parse_known_args()

    # setup logging
    lvl = logging.WARNING # default
    if args.verbose == 1:
        lvl = logging.INFO
    elif args.verbose >= 2:
        lvl = logging.DEBUG

    logging.basicConfig(level=lvl)

    return args


def percentage(part, whole):
    """
    Return percentage of part in whole as float.
    """
    return 100 * float(part)/float(whole)


def execute(cmd, fail=True):
    """
    Execute %cmd and return stdout.  Exit in case of error.
    """
    logging.info(" executing '%s'" % cmd)
    pop = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    (stdout, _) = pop.communicate()  # wait until finished
    if pop.returncode != 0:
        logging.error(stdout)
        if fail:
            sys.exit(-1)
    return stdout


def parse_coverage_data(lines):
    """
    Parse each line in @lines for CPP coverage warnings and return a dictionary
    of the following format {file : list of tuples(block, start line)}.
    """
    data = {}

    for line in lines:
        match = REGEX_WARN.match(line)
        if not match:
            continue

        file = match.group(1)
        line = match.group(2)
        block = match.group(3)

        blocks = data.get(file, set())
        blocks.add(block)
        data[file] = blocks

    return data


def build_config(num_threads, config, dir=""):
    """
    Build config and return stdout.
    """
    stdout = execute("KCONFIG_ALLCONFIG=%s make -j%s %s" % (config, num_threads, dir))
    return stdout


def count_blocks(path):
    """
    Return the number of CPP blocks in the @path.
    """
    lines = []
    with open(path, "r") as fdc:
        lines = fdc.readlines()

    count = 1  # B00 (i.e., the file itself)
    for i in range(0, len(lines)):
        if REGEX_BLOCK.match(lines[i]):
            count += 1
            while REGEX_ESC.match(lines[i]):
                i += 1

    logging.debug("%s contains %s CPP blocks" % (path, count))
    return count


def block_stats(batch):
    """
    Return a dict with the format {path: #ifdef blocks}.
    """
    stats = {}
    total = 0
    for path in batch:
        count = count_blocks(path)
        stats[path] = count
        total += count
    print("%s #CPP blocks detected" % total)
    return stats


def insert_warnings(path):
    """
    Insert CPP warnings in each #ifdef block in @path.
    """
    lines = []
    with open(path, "r") as fdc:
        lines = fdc.readlines()

    indexes = []
    depth = 0
    for i in range(0, len(lines)):
        if REGEX_BLOCK.match(lines[i]):
            while REGEX_ESC.match(lines[i]):
                i += 1
            assert(i < len(lines))
            indexes.append(i+1)

    logging.debug(" %s : Inserting #warning at line %s" % (path, 1))
    lines.insert(0, "#warning COVERAGE %s %s %s\n" % (path, '1', '00'))

    count = 1
    for i in indexes:
        logging.debug(" % s : Inserting #warning at line %s" % (path, i+count))
        lines.insert(i + count, "#warning COVERAGE %s %s %s\n" % (path, i, count))
        count += 1

    with open("%s" % path, "w") as fdc:
        for line in lines:
            fdc.write(line)


def expand_config(config, strategy="allnoconfig"):
    """
    Expand the specified @config.  All unspecified options will be set
    according to the specified @strategy.
    """
    if os.path.exists(".config"):
        cmd = "rm .config"
        execute(cmd, fail=False)

    cmd = "KCONFIG_ALLCONFIG=%s make %s" % (config, strategy)
    out = execute(cmd)
    logging.debug(out)

    cmd = "scripts/diffconfig %s .config > %s.diff" % (config, config)
    execute(cmd)

    cmd = "mv .config %s.expanded" % config
    execute(cmd)


def partition(lst, size):
    """
    Partition list @lst into eveni-sized lists of size @size.
    """
    return [lst[i::size] for i in iter(range(size))]


def insert_worker(files):
    """
    Call insert_warning() for each file in @file.
    """
    for file in files:
        try:
            insert_warnings(file)
        except:
            logging.warning(" could not parse '%s'" % file)
            sys.exit(1)


def init_worker():
    """
    Set signal handler to ignore SIGINT.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def parse_batch_file(path):
    """
    Return lines of @path.
    """
    lines = []
    with open(path, "r") as fdc:
        for line in fdc.readlines():
            lines.append(line.strip())
    return lines


def dump_data(data, path):
    """
    Dump @data to @path in pickle format.
    """
    pickle.dump(data, open(path, "wb"))


def load_data(path):
    """
    Load data from @path.
    """
    try:
        return pickle.load(open(path, "rb"))
    except (IOError, pickle.PickleError, EOFError) as e:
        sys.exit("Could not load data from '%s'\n%s" % (path, e))


def parse_gcc_stdin():
    """
    Parse GCC warnigs from stdin.
    """
    data = dict()
    lines = set()

    coverage = " #warning COVERAGE "
    offset = len(coverage) - 1

    for line in sys.stdin:
        if not line.startswith(coverage):
            continue
        else:
            line = line.strip()[offset:]
            lines.add(line)

    for line in lines:
        print line


if __name__ == "__main__":
    args = parse_options()

    files = []
    data = {}
    num_threads = cpu_count()

    # parse gcc warnings from stdin
    if args.parse_gcc:
        parse_gcc_stdin()

    # parse batch file and add paths to @files list
    if args.batch:
        files = parse_batch_file(args.batch)

    # add specified file to @files list
    if args.file:
        files.append(args.file)

    if args.threads:
        num_threads = int(args.threads)

    # expand the specified @files and suffix them with ".expanded"
    if args.expand:
        for file in files:
            expand_config(file, args.strategy)
        sys.exit()

    # count all CPP blocks in @files
    if args.count:
        block_stats(files)
        sys.exit()

    # insert CPP #warnings in each CPP block of all @files
    if args.insert:
        pool = Pool(num_threads, init_worker)
        arglist = partition(files, num_threads)
        pool.map(insert_worker, arglist)
