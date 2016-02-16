CFLAGS = -O3
CXX = g++

all: pmc

clean:
	rm -f *.o pmc

IO_SRC = pmc_utils.cpp \
	     pmc_graph.cpp \
	     pmc_clique_utils.cpp

PMC_SRC = pmc_heu.cpp \
		  pmc_maxclique.cpp \
		  pmcx_maxclique.cpp \
		  pmcx_maxclique_basic.cpp

BOUND_LIB_SRC = pmc_cores.cpp

PMC_MAIN = pmc_driver.cpp

OBJ_PMC	= $(PMC_MAIN:%.cpp=%.o) $(IO_SRC) $(PMC_SRC) $(BOUND_LIB_SRC)

pmc: $(OBJ_PMC)
	$(CXX) $(CFLAGS) -o pmc $(OBJ_PMC) -fopenmp

.PHONY: all clean
