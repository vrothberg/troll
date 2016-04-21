CFLAGS = -Wall -O3
CXXFLAGS = $(CFLAGS) -std=gnu++11
CC = g++
LDLIBS = -lpthread

OBJS = troll.o

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

all: troll
	$(MAKE) -C pmc/

troll: $(OBJS)
	$(CC) $(CXXFLAGS) -o troll $(OBJS) $(LDLIBS)

clean:
	rm -rf *.o
	rm -rf troll
	$(MAKE) -C pmc/ clean

install: all
	install -D troll $(BINDIR)
	install -D pmc/pmc $(BINDIR)

uninstall:
	-rm -f $(BINDIR)/troll
	-rm -f $(BINDIR)/pmc

.PHONY: all clean install uninstall
