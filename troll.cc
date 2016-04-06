/*
 * Copyright (C) 2015-2016 Valentin Rothberg <rothberg@cs.fau.de>
 *
 * Licensed under the terms of the GNU GPL License version 3
 *
 * Credits to Christian Dietrich <dietrich@cs.fau.de> for providing the
 * underlying algorithm for vector-compatibility testing described here:
 *      https://www4.cs.fau.de/~stettberger/blog/2015/Vector-Compatibility/
 *
 */

#include <algorithm>
#include <cassert>
#include <iostream>
#include <fstream>
#include <list>
#include <map>
#include <mutex>
#include <pstreams/pstream.h>
#include <pthread.h>
#include <regex>
#include <unordered_map>
#include <vector>


using namespace std;


#define DEBUG cout << "DEBUG: "


mutex mtx;
volatile long conflicts;
volatile long compatibles;
unordered_map<int, string> translate;
int MAXTHREADS = 1;
int SYM_COUNT = 0;
int SYM_ENTRIES = 100;

class Config;
Config* configs;

inline char str_to_val(string);
inline string val_to_str(char);


class Config {
public:
    unsigned long long *symbols;
    long max_index = 0;
    long min_index = 0;

    Config(){
        symbols = (unsigned long long*) calloc(SYM_ENTRIES, sizeof(unsigned long long));
        if (symbols == NULL) {
            cout << "Could not allocate enough memory :(" << endl;
            exit(-1);
        }
    };

    ~Config(){};

    void add_symbol(int symbol, char value)
    {
        int index = symbol / 21;
        int pos = (symbol % 21) * 3;

        symbols[index] |= (unsigned long long) value << pos;

        if (index > max_index)
            max_index = index;
        else if (index < min_index)
            min_index = index;
    }

    unordered_map<int, int>* get_set_symbols()
    {
        unordered_map<int, int> *syms = new unordered_map<int, int>();
        unordered_map<int, int>::iterator it = syms->begin();
        for (int i = min_index; i <= max_index; i++) {
            if (symbols[i] == 0) continue;

            unsigned int sym, val;
            for (int j = 0; j < 21; j++) {
                val = symbols[i] >> (j * 3);
                val &= 0x7;

                if (val == 0) continue; // if not set continue

                assert(val <= 3);
                sym = (i * 21) + j;
                syms->insert(it, pair<int,int>(sym, val));
            }
        }
        return syms;
    }

    bool conflict(Config* other)
    {
        bool compatible;

        long max_index = max(this->max_index, other->max_index);
        long min_index = max(this->min_index, other->min_index);
        long long a, b;

        for (int i = min_index; i <= max_index; i++) {
            a = this->symbols[i];
            b = other->symbols[i];
            compatible = (((a << 1) & b) ^ ((b << 1) & a)) == 0;
            if (!compatible)
                return true;
        }
        return false;
    }
};


inline char str_to_val(string value)
{
    if (!value.compare("n"))
        return 1; //b001
    if (!value.compare("m"))
        return 2; //b010
    if (!value.compare("y"))
        return 3; //b011

    cout << "UNKOWN VALUE: " << value << endl;

    assert(false);
}


inline string val_to_str(char value)
{
    if (value == 1)
        return string("n");
    if (value == 2)
        return string("m");
    if (value == 3)
        return string("y");

    assert(false);
}


inline string val_to_sym(int value)
{
    if (translate.count(value) != 1) {
        cout << "Could not translate value '" << value << "' to symbol" << endl;
        exit(-1);
    }
    return translate[value];
}


void resize_configs(Config *configs, int nr_configs)
{
    DEBUG << "...resizing configs" << endl;

    SYM_ENTRIES += 100;
    for (int i = 0; i < nr_configs; i++) {
        configs[i].symbols = (unsigned long long*) realloc(configs[i].symbols, SYM_ENTRIES * sizeof(unsigned long long));
        if (configs[i].symbols == NULL) {
            cout << "Could not allocate enough memory :(" << endl;
            exit(-1);
        }
        for (int j = SYM_ENTRIES-100; j < SYM_ENTRIES; j++)
            configs[i].symbols[j] = 0;
    }

}


int parse_configs(vector<string>* paths)
{
    DEBUG << "... parsing configurations" << endl;

    long counter = 0;
    int nr_configs = paths->size();

    configs = new Config[nr_configs];

    unordered_map<string, int> symbols;
    vector<string>::iterator it;
    for (it = paths->begin(); it != paths->end(); ++it) {
        string line, symbol;
        size_t pos;
        char value;

        ifstream file((const char*)(*it).c_str());

        while (getline(file, line)) {
            if (line.compare(0, 1, "#") == 0) continue;

            pos = line.find_first_of('=');
            symbol = line.substr(0, pos);
            value = str_to_val(line.substr(pos + 1));

            if (symbols.count(symbol) == 1) {
                configs[counter].add_symbol(symbols[symbol], value);
            }
            else {
                configs[counter].add_symbol(SYM_COUNT, value);
                translate[SYM_COUNT] = symbol;
                symbols[symbol] = SYM_COUNT++;
                if ((SYM_COUNT / 21) + 1 > SYM_ENTRIES) {
                    resize_configs(configs, nr_configs);
                }
            }
        }
        counter++;
    }

    cout << "Parsed " << paths->size() << " configurations including ";
    cout << SYM_COUNT << " symbols" << endl;

    return nr_configs;
}


struct build_graph_data {
    char** graph;
    int gsize;
    int from;
    int to;
};


void* task_build_graph(void* args)
{
    struct build_graph_data* data = (struct build_graph_data*)args;
    long _conflicts = 0;
    long _compatibles = 0;

    for (int i = data->from; i < data->to; i++) {
        for (int j = 0; j < data->gsize; j++) {
            if (j == i) {
                data->graph[i][j] = 1;
                continue;
            }

            if (configs[i].conflict(&configs[j])) {
                _conflicts++;
            }
            else {
                data->graph[i][j] = 1;
                data->graph[j][i] = 1;
                _compatibles++;
            }
        }
    }

    mtx.lock();
    conflicts += _conflicts;
    compatibles += _compatibles;
    DEBUG << "FINISHED " << data->from << ":" << data->to << endl;
    mtx.unlock();

    return 0x0;
}


char** build_graph(int gsize)
{
    DEBUG << "... building graph" << endl;

    char** graph = (char**)calloc(gsize, sizeof(char*));
    if (graph == NULL) {
        cout << "Could not allocate enough memory :(" << endl;
        exit(-1);
    }
    for (int i = 0; i < gsize; i++) {
        graph[i] = (char*)calloc(gsize, sizeof(char));
        if (graph[i] == NULL) {
            cout << "Could not allocate enough memory :(" << endl;
            exit(-1);
        }
    }

    struct build_graph_data args[MAXTHREADS];
    pthread_t threads[MAXTHREADS];
    pthread_attr_t attr;
    int rc;
    // initialize and set thread joinable
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    // initialize task data
    int chunk = gsize / MAXTHREADS + 1;
    int steps = 0;
    for (int i = 0; i < MAXTHREADS; i++) {
        steps++;
        args[i].graph = graph;
        args[i].from = i * chunk;
        args[i].to = (i + 1) * chunk;
        if (args[i].to > gsize)
            args[i].to = gsize;
        args[i].gsize = gsize;
    }

    // start threads
    for (int i = 0; i < steps; i++) {
        rc = pthread_create(&threads[i], &attr, task_build_graph, &args[i]);
        if (rc) {
            cout << "Error: unable to creat thread," << rc << endl;
            exit(-1);
        }
    }

    // free attribute and wait for running threads to complete
    pthread_attr_destroy(&attr);
    for (int i = 0; i < steps; i++) {
        rc = pthread_join(threads[i], NULL);
        if (rc) {
            cout << "Error: unable to join thread," << rc << endl;
            exit(-1);
        }
    }

    cout << "Build graph with " << gsize << " nodes" << endl;
    cout << "Number of edges: " << compatibles << endl;
    cout << "Number of conflicts: " << conflicts << endl;

    return graph;
}


struct task_update_data {
    char** graph;
    int gsize;
    vector<int> nodes;
};


void* task_update_graph(void* args)
{
    struct task_update_data* data = (struct task_update_data*)args;
    // zero column and row for each node in data->nodes
    vector<int>::iterator it;
    for (it = data->nodes.begin(); it != data->nodes.end(); ++it) {
        int node = *it;
        for (int i = 0; i < data->gsize; i++) {
            data->graph[node][i] = 0;
        }
        for (int i = 0; i < data->gsize; i++) {
            data->graph[i][node] = 0;
        }
    }
    return 0x0;
}


void update_graph(char** graph, vector<int>* clique, int gsize)
{
    DEBUG << "... updating graph" << endl;

    struct task_update_data *args;
    pthread_t *threads;
    pthread_attr_t attr;
    int rc;

    args = (struct task_update_data *) calloc(MAXTHREADS, sizeof(struct task_update_data));
    if (!args) {
        cout << "Error: allocation failed\n";
        exit(-1);
    }

    threads = (pthread_t *) calloc(MAXTHREADS, sizeof(pthread_t));
    if (!args) {
        cout << "Error: allocation failed\n";
        exit(-1);
    }

    vector<int> nodes(*clique);
    assert(!nodes.empty());

    // initialize and set thread joinable
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

    // initialize task data
    int chunk = nodes.size() / MAXTHREADS + 1;
    int steps = 0;

    for (int i = 0; i < MAXTHREADS; i++) {
        steps++;
        args[i].graph = graph;
        args[i].gsize = gsize;
        for (int j = 0; j < chunk; j++) {
            args[i].nodes.push_back(nodes.back());
            nodes.pop_back();
            if (nodes.empty())
                break;
        }
        if (nodes.empty())
            break;
    }

    assert(nodes.empty());

    // start threads
    for (int i = 0; i < steps; i++) {
        rc = pthread_create(&threads[i], &attr, task_update_graph, &args[i]);
        if (rc) {
            cout << "Error: unable to creat thread," << rc << endl;
            exit(-1);
        }
    }

    // free attribute and wait for running threads to complete
    pthread_attr_destroy(&attr);
    for (int i = 0; i < steps; i++) {
        rc = pthread_join(threads[i], NULL);
        if (rc) {
            cout << "Error: unable to join thread," << rc << endl;
            exit(-1);
        }
    }
}


void dump_graph(char** graph, int gsize)
{
    DEBUG << "... dumping graph" << endl;

    stringstream body, header;

    // write edges to file as "j i" with j > i
    int edges = 0;
    for (int i = 0; i < gsize; i++) {
        for (int j = i + 1; j < gsize; j++) {
            if (graph[i][j]) {
                body << j+1 << " " << i+1 << endl;
                edges++;
            }
        }
    }

    header << "%%MatrixMarket matrix coordinate real symmetric" << endl;
    header << gsize << " " << gsize << " " << edges << endl;

    fstream myfile;
    myfile.open("graph.mtx", ios::out);
    myfile << header.str();
    myfile << body.str();
    myfile.close();
}


vector<int>* find_clique()
{
    DEBUG << "... finding clique" << endl;

    vector<int>* clique = new vector<int>();
    stringstream cmd;
    cmd << "pmc -a0 -f graph.mtx "; // single-threaded for patched version

    redi::ipstream proc(cmd.str(), redi::pstreams::pstdout);
    string line;

    size_t pos;
    int node;
    while (getline(proc.out(), line)) {
        // find max. clique line
        pos = line.find("Maximum clique: ");

        if (pos == string::npos)
            continue;

        // parse result
        pos += string("Maximum clique: ").length();

        stringstream stream(line.substr(pos));
        while (stream >> node)
            clique->push_back(node-1);

        break;
    }

    DEBUG << "...found max. clique of size " << clique->size() << endl;

    return clique;
}


vector<string>* parse_batch_file(char* path)
{
    vector<string>* paths = new vector<string>();
    string line;

    ifstream file(path);
    while (getline(file, line))
        paths->push_back(line);

    return paths;
}


void merge_and_dump_configs(vector<vector<int>*> *cliques)
{
    DEBUG << "... dumping configurations" << endl;

    // iterate over all cliques
    vector<vector<int>*>::iterator it;
    int nr_clique = 0;
    for (it = cliques->begin(); it != cliques->end(); ++it) {
        unordered_map<int, int> config;
        unordered_map<int, int> *cur_syms;

        // merge all configs of this clique
        vector<int> *clique = *it;
        vector<int>::iterator cur;
        for (cur = clique->begin(); cur != clique->end(); ++cur) {
            // add all symbols of cur to config
            cur_syms = configs[*cur].get_set_symbols();
            unordered_map<int, int>::iterator pit;
            int sym, val;
            for (pit = cur_syms->begin(); pit != cur_syms->end(); ++pit) {
                sym = pit->first;
                val = pit->second;

                // if symbol is already set, assert equal value
                if (config.count(sym)) {
                    if (config[sym] != val) {
                        cout << "cur val '" << val << "': symbol " << sym;
                        cout << " already in config with value " << config[sym] << endl;
                    }
                } else {
                    config[sym] = val;
                }
            }
        }

        // dump config
        stringstream path;
        fstream myfile;
        path << "troll.config." << (int) nr_clique++ << "." << (int) clique->size();
        myfile.open(path.str(), ios::out);

        unordered_map<int, int>::iterator con_it;
        string sym, val;
        for (con_it = config.begin(); con_it != config.end(); con_it++) {
            sym = val_to_sym(con_it->first);
            val = val_to_str(con_it->second);
            myfile << sym << "=" << val << endl;
        }

        myfile.close();
    }

    cout << "Generated " << cliques->size() << " configurations" << endl;
}


vector<vector<int>*>* empty_graph(char **graph, int gsize)
{
    DEBUG << "... emptying graph" << endl;

    vector<vector<int>*> *remains = new vector<vector<int>*>();
    for (int i = 0; i < gsize; i++) {
        if (graph[i][i]) {
            vector<int> *clique = new vector<int>();
            clique->push_back(i);
            remains->push_back(clique);
        }
    }
    return remains;
}


void print_help()
{
    cout << "troll -- merge (partial) Kconfig configuration files\n\n";
    cout << "usage: troll -b batch [-t [threads]]\n";
    cout << "the (batch) file must contain paths to configuration files\n\n";
    cout << "optional arguments:\n";
    cout << "    -b    " << " path to batch file (mandatory option)\n";
    cout << "    -d    " << " build and dump graph\n";
    cout << "    -h    " << " print this help message\n";
    cout << "    -t    " << " define number of threads (default: 1)\n";
}


int main(int argc, char** argv)
{
    // parse batch file, configurations and build the graph
    vector<string>* paths;
    char** graph;
    char *path_batch = 0;
    int gsize;
    bool dump = false;

    int opt = 0;
    while ((opt = getopt(argc, argv, "b:c:t:dh")) != -1) {
        switch (opt) {
        case 'b':
            path_batch = optarg;
            break;
        case 'd':
            dump = true;
            break;
        case 'h':
            print_help();
            exit(0);
        case 't':
            MAXTHREADS = std::stoi(optarg);
            if (MAXTHREADS < 1) {
                std::cout << "Invalid number of threads, defaulting to 1.\n";
                MAXTHREADS = 1;
            }
            break;
        }
    }

    if (!path_batch) {
        std::cout << "Please specify the mandatory batch file.\n";
        exit(1);
    }

    paths= parse_batch_file(path_batch);
    gsize = parse_configs(paths);
    graph = build_graph(gsize);

    if (dump) {
        dump_graph(graph, gsize);
        exit(0);
    }

    // iteratively find and select cliques in the graph
    vector<vector<int>*> cliques;
    vector<int>* clique;

    while (true) {
        // dump graph and find current max. clique
        dump_graph(graph, gsize);
        clique = find_clique();

        if (clique->empty())
            break;

        // save clique and remove it from the graph
        cliques.push_back(clique);
        update_graph(graph, clique, gsize);
    }

    // remove potentially remaining nodes from the graph
    vector<vector<int>*> *remains = empty_graph(graph, gsize);
    if (!remains->empty()) {
        vector<vector<int>*>::iterator it;
        for (it = remains->begin(); it != remains->end(); it++)
            cliques.push_back(*it);
    }

    // merge all cliques and dump them to new configuration files
    merge_and_dump_configs(&cliques);

    cout << "Reduced " << paths->size() << " configurations to ";
    cout << cliques.size() << endl;

    return 0;
}
