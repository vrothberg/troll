#!/usr/bin/env python2

"""
Script to analyze trolled configurations.

Visit https://gitlab.cs.fau.de/vrothberg/troll for more information.
"""

# (c) 2016 Valentin Rothberg <rothberg@cs.fau.de>
#
# Licensed under the terms of the GNU GPL License version 3


import argparse
import logging
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
    parser.add_argument('-i', '--insert', dest='insert', action='store_true',
                        default=False,
                        help="insert CPP warnings")
    parser.add_argument('-f', '--file', dest='file', action='store',
                        default=None,
                        help="file")
    parser.add_argument('-t', '--threads', dest='threads', action='store',
                        default=None,
                        help="specify number of threads")
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
    parser.add_argument('--syntax-only', dest='syntax', action='store_true',
                        default=False,
                        help="call 'gcc -fsyntax-only' on each file")
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


def execute(cmd):
    """
    Execute %cmd and return stdout.  Exit in case of error.
    """
    logging.info(" executing '%s'" % cmd)
    pop = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    (stdout, _) = pop.communicate()  # wait until finished
    if pop.returncode != 0:
        sys.exit(stdout)
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


def file_syntax_analysis(path):
    """
    Run gcc syntax analysis (i.e., parse but don't compile) on @path, parse the
    CPP warnings and return a dictionary of the following format
    {file : list of tuples(block, start line)}.
    """
    cmd = "gcc -fsyntax-only %s" % path
    stdout = execute(cmd)
    return parse_coverage_data(stdout.split("\n"))


def make_syntax_analysis(num_threads, config):
    """
    Analyze coverage in current Linux tree.  Return a dictionary of the
    following format {file : list of tuples(block, start line)}.
    """
    stdout = execute("KCONFIG_ALLCONFIG=%s make -j%s -m kernel/sched/ " % (config, num_threads))
    return parse_coverage_data(stdout.split("\n"))


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


def coverage_analysis(data):
    """
    Analyze coverage @data and print results on stdout.
    """
    all_blocks = 0
    enabled_blocks = 0

    if not data:
        logging.info("Coverage analysis: no data to analyze")
        return

    for file in sorted(data.keys()):
        all = count_blocks(file)
        enabled = len(data[file])
        perc = percentage(enabled, all)

        assert(perc <= float(100))

        print("%s: %.2f%% coverage: %s of %s blocks enabled" % (file, perc, enabled, all))

        all_blocks += all
        enabled_blocks += enabled

    perc = percentage(enabled_blocks, all_blocks)
    print("%.2f%% total coverage: %s of %s blocks enabled" % (perc, enabled_blocks, all_blocks))



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
    lines.insert(0, "#warning COVERAGE FILE:%s LINE:%s BLOCK:%s\n" % (path, '1', '00'))

    count = 1
    for i in indexes:
        logging.debug(" % s : Inserting #warning at line %s" % (path, i+count))
        lines.insert(i + count, "#warning COVERAGE FILE:%s LINE:%s BLOCK:%s\n" % (path, i, count))
        count += 1

    with open("%s" % path, "w") as fdc:
        for line in lines:
            fdc.write(line)


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


def main():
    args = parse_options()

    files = []
    data = {}
    num_threads = cpu_count()

    if args.batch:
        files = parse_batch_file(args.batch)

    if args.file:
        files.append(args.file)

    if args.threads:
        num_threads = int(args.threads)

    if args.insert:
        pool = Pool(num_threads, init_worker)
        arglist = partition(files, num_threads)
        pool.map(insert_worker, arglist)

    if args.load:
        data = load_data(args.load)
        print(data)
        coverage_analysis(data)
        sys.exit()

    if args.analyze:
        if args.syntax:
            data = file_syntax_analysis(args.file)
        else:
            data = make_syntax_analysis(num_threads, args.config)
        coverage_analysis(data)

    if args.dump:
        dump_data(data, args.dump)


if __name__ == "__main__":
    main()
