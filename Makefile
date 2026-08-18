SHELL := /bin/bash
PYTHON := .venv/bin/python
CC := clang
CFLAGS := -std=gnu89 -O2 -w

.PHONY: setup fetch oracle discharge test clean

setup:
	uv venv -q -p 3.12 .venv
	uv pip install -q -p .venv/bin/python numpy networkx

fetch:
	python3 tools/fetch_sources.py

build:
	mkdir -p build

build/reduce_rsst: third_party/arxiv-1401.6481/src/anc/reduce.c | build
	$(CC) $(CFLAGS) -o $@ $<

build/reduce_stein: third_party/arxiv-0905.0043/src/anc/reduce.c | build
	$(CC) $(CFLAGS) -o $@ $<

build/discharge_rsst: third_party/arxiv-1401.6485/src/anc/discharge.c | build
	$(CC) $(CFLAGS) -o $@ $<

# Historical oracle: RSST reducibility over all 633 configurations.
oracle: build/reduce_rsst
	mkdir -p results/oracle-rsst-633
	cd third_party/arxiv-1401.6481/src/anc && \
	  $(CURDIR)/build/reduce_rsst unavoidable.conf \
	  > $(CURDIR)/results/oracle-rsst-633/stdout.txt 2>&1
	grep -q 'Reducibility of 633 configurations verified' \
	  results/oracle-rsst-633/stdout.txt && echo "oracle: 633/633 verified"

# Historical oracle: RSST unavoidability replay (hub degrees 7-11).
discharge: build/discharge_rsst
	mkdir -p results/discharge-rsst
	cd third_party/arxiv-1401.6485/src/anc && \
	  for p in present7 present8 present9 present10 present11; do \
	    echo "=== $$p ==="; \
	    $(CURDIR)/build/discharge_rsst $$p 2>&1 | tail -2; \
	  done > $(CURDIR)/results/discharge-rsst/replay.txt 2>&1
	grep -c 'verified' results/discharge-rsst/replay.txt

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

clean:
	rm -rf build
	@echo "results/ and third_party/ are intentionally never removed by make."
