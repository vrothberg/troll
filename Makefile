CFLAGS = -Wall -O3
CXXFLAGS = $(CFLAGS) -std=gnu++11
CC = g++
LDLIBS = -lpthread
PROGS = troll
OBJS = troll.o

all: $(PROGS)

troll:  $(OBJS)
	$(CC) $(CXXFLAGS) -o troll $(OBJS) $(LDLIBS)

clean:
	rm -rf *.o
	rm -rf $(PROGS)

.PHONY: all clean
