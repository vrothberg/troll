# Troll

**Troll** is a tool written in C++ with the main purpose of merging a specified
set of partial configurations to a smaller set of partial configurations
potentially enabling more options and hence more code for further (static)
analysis.  Such partial configurations can be generated with
[undertaker](https://undertaker.cs.fau.de).  Thanks to the
[PMC](https://www.cs.purdue.edu/homes/dgleich/codes/maxcliques/) maximum-clique
finder, Troll scales surprisingly well (NP completeness) and merges over 30k x86
Linux kernel configurations in around 3 minutes on an average work station with
a core i7 and 16GiB of RAM.


# What is a partial configuration?

Configurations are called *partial* when they only set (or select) a subset of
all configuration options required for compilation (e.g., of the Linux kernel).

Partial configurations are generated, for instance, by undertaker's CPP-block
coverage analysis.  Consider the following CPP block:

``` C
#ifdef CONFIG_X86_DRIVER

#endif
```

To enable this CPP block at least the configuration option CONFIG_X86_DRIVER
must be enabled.  However, a configuration which only enables this driver is not
enough to compile an entire Linux kernel and is hence a *partial configuration*.


# Trolling source code

Here's a rather verbose step-by-step (story telling) guide how to use Troll in
the Linux kernel.  Note that the steps below can be automated.

Let's assume we're a Linux USB maintainer; we integrated a bunch of changes and
now want to do some build tests before issuing run-time tests.  Instead of
using a pre-defined set of configs which are likely not to cover newly
integrated code, we can generate partial configurations for the files of
interest and use them as a base for further analysis.


## Step 1: find a set of files

Let's first get a set of files of our interest, and remember, we're playing USB
maintainer now:

``` Bash
$ find drivers/usb -name "*.[cSsh]" > usb.batch
```


## Step 2: generate partial configurations

Generating partial configurations is the backbone of Troll.  No configurations,
nothing to 'troll'.  As shown by [Medeiros et al](http://arxiv.org/pdf/1602.02052v3.pdf),
there are various (combinations) of so called sampling algorithms (i.e.,
algorithms generating partial configurations).  For our purpose, we use the
statement-coverage algorithm implemented in [undertaker](https://undertaker.cs.fau.de)
entailing several advantages.  First, statement coverage shows good scalability
and since we need to get work done, scaling is a good thing.  Second, undertaker
ships an entire suite of different tools that, among other things, allows us to
extract variability information (i.e., variability models) from the
configuration system Kconfig and also the build system of Linux.  Having
variability information at hand, such as the dependencies among features, is a
prerequisite to merge partial configurations.  Without such information, we
could generate invalid configurations (i.e., invalid combinations of
configuration options) since we would not know the relationships (i.e.,
constraints) among them.

After downloading and installing [undertaker](undertaker.cs.fau.de) (there are
some Debian/Ubuntu packages as well), we can start extracting the variability
models. Let's assume that we only care about the x86 architecture:

``` Bash
$ undertaker-kconfigdump x86
```

Now the more interesting part starts -- generating partial configurations --
which we do by using the previously generated batch file *usb.batch*.  Since
Troll also requires a batch file specifying the partial configs of interested,
we collect them right after generation.

``` Bash
$ undertaker -j coverage -m models/x86.model -t#CPUs -b usb.batch
$ find drivers/usb/ -name "*.config[0-9]*" > usb.configs
```


## Step 3: merging partial configurations

Reaching this step, we 'sampled' all files of our interested and generated a set
of partial configurations.  *Without* Troll, the only thing we can do with those
configs is to use them on their corresponding files in order to do *local*
analysis only.  Such file local analysis are well understood despite the fact
that headers are not included due to the exponential explosion of potential
combinations of configuration options.  Linux files tend to include more than
200 headers on average, which is a serious threat to scalability and feasibility
for sampling algorithms in general, but that's another story.  *With* Troll, we
can elevate the local analysis to a *global* analysis, since we gather the
variability information from source files of our interested, and aggregate
them into a small(er) set of partial configurations.

To merge the previously generated partial configurations, we give Troll the
corresponding batch file:

``` Bash
$ troll -b usb.configs -t#CPUs
```

As soon as Troll has finished, we can find a set of new *partial* configurations
in our working directory in the following format *troll.config.**ID**.**SIZE**.*
Those merged configurations are consecutively numbered (ID) and also indicate
how many previous configurations have been merged (SIZE) -- lower IDs usually
indicate bigger SIZEs.

Now we have a bunch of merged partial configurations that we can use for further
(static) analysis, build tests, boot tests, run-time tests, etc.  In our
experience, Troll generates a small amount of configs with high sizes, and many
configs with small sizes (usually of size 1).


# How can we evaluate 'trolled' configurations?

## Coverage

TODO:  the text here should explain the idea(s) behind scripts/ and wrappers/
