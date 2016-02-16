---
title: "A Fast Parallel Maximum Clique Algorithm for Large Sparse Graphs and Temporal Strong Components"
layout: project
---

A Fast Parallel Maximum Clique Algorithm for Large Sparse Graphs and Temporal Strong Components
==================================

### Ryan A. Rossi
### David F. Gleich
### Assefaw H. Gebremedhin
### Md. Mostofa Ali Patwary

_These codes are research prototypes and may not work for you. No promises. But do email if you run into problems._


Download
--------

* [parallel-maxclique.tar.gz](parallel-maxclique.tar.gz) ___warning, will unzip into the current directory___

Prereqs
-------
* A working C/C++ compiler


Setup
-----

First, you'll need to compile the parallel maximum clique library.
In bash, change to the directory where you unzipped the parallel-maxclique.tar.gz file, and type `make`:

    $ cd path/to/pmc/
    $ make

Afterwards, the following should work:

	%% compute maximum clique using the full algorithm `-a 0`
	./pmc -f data/socfb-Texas84.mtx -a 0

Please let me know if you run into any issues.


 
Overview
--------

The parallel maximum clique library is organized by directory

`/`  
: C++ codes for max clique algorithms

`/data/`  
: A few sample graphs

`/experiments/`  
: Codes for preprocessing graphs for maximum clique, exporting graphs, computing bounds & network stats

`/experiments/tscc/codes/`  
: Codes used for computing the reachability graph



Figures
-----------
    
|Experiment|Description|Figure|
|:------------------|:------------------------------------|:------------------|
|`exp/pmc_runner.py` | Performance of the max clique algorithm  | Tab. 1 |
|`exp/plots/pmc_linear_perf.m` | Runtime of PMC scales linearly with the network dimension  | Fig. 1 |
|`exp/plots/speedup_social.m` | Speedup of PMC for social networks | Fig. 4 |
|`exp/plots/speedup_dimacs.m` | Speedup of PMC for DIMACs benchmark graphs | Fig. 5 |
|`exp/plots/pp_social_serial.m` | Performance profile of benchmark solvers for social networks | Fig. 6a |
|`exp/plots/pp_dimacs.m` | Performance profile of benchmark solvers for DIMACS | Fig. 6b-c |
|`exp/pmc_runner.py` | Performance of PMC for computing Temporal SCC's | Tab. 2 |
