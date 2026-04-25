# Lab 8: Bloom Filter

This lab implements a Bloom filter, computes the theoretical optimal number of
hash functions, and compares theoretical and empirical false-positive rates.

## Run

```bash
python main.py
```

## Optional parameters

```bash
python main.py --n 5000 --epsilon 0.01 --queries 20000 --seed 42
```

## Output

The program prints:

- computed filter size `m`
- theoretical and rounded optimal `k`
- a sweep of false-positive rates for different `k`
- a comparison table for several target `epsilon` values

Plots are saved into `data/`.
