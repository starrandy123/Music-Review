#ifndef COP4530_HASHTABLE_H
#define COP4530_HASHTABLE_H

#include <vector>
#include <list>
#include <utility>  // For std::pair
#include <string>
#include <algorithm>
#include <functional>  // For std::hash
#include <fstream>
#include <iostream>

using namespace std;

namespace cop4530 {

template <typename K, typename V>
class HashTable {
public:
    HashTable(size_t size = 101);
    ~HashTable();

    bool contains(const K& k) const;
    bool match(const std::pair<K, V>& kv) const;
    bool insert(const std::pair<K, V>& kv);
    bool insert(std::pair<K, V>&& kv);
    bool remove(const K& k);
    void clear();
    bool load(const char* filename);
    void dump() const;
    size_t size() const;
    //bool write_to_file(const char* filename);
    bool write_to_file(const char* filename) const;


private:
    vector<list<pair<K, V>>> theLists;
    size_t currentSize; 
    void makeEmpty();
    void rehash();
    size_t myhash(const K& k) const;
    unsigned long prime_below(unsigned long n) const;
    void setPrimes(vector<unsigned long>& vprimes) const;

    

    static const unsigned long max_prime = 1301081;
    static const unsigned long default_capacity = 11;
};

#include "hashtable.hpp"

} // namespace cop4530

#endif // COP4530_HASHTABLE_H
