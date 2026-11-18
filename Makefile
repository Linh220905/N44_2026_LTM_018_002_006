CC = gcc
PYTHON ?= python3
PX4_PYTHON ?= $(PYTHON)
CFLAGS = -std=c11 -D_DEFAULT_SOURCE -O2 -Wall -Wextra -Werror
COMMON = src/common/protocol.c src/common/stream.c
HEADERS = $(wildcard src/common/*.h src/agent/*.h)
PROGRAMS = bin/gcs_server bin/drone_agent bin/baseline_server bin/baseline_agent

all: $(PROGRAMS)

bin:
	mkdir -p $@

bin/gcs_server: src/server/gcs_server.c $(COMMON) $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

bin/drone_agent: src/agent/drone_agent.c src/agent/failsafe.c src/common/geofence.c $(COMMON) $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

bin/baseline_server: src/server/baseline_server.c $(COMMON) $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

bin/baseline_agent: src/agent/baseline_agent.c $(COMMON) $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

bin/test_protocol: tests/test_protocol.c src/common/protocol.c $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@

bin/test_failsafe: tests/test_failsafe.c src/agent/failsafe.c src/common/geofence.c $(HEADERS) | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

bin/test_spline: tests/test_spline.c src/common/spline.c src/common/spline.h | bin
	$(CC) $(CFLAGS) $(filter %.c,$^) -o $@ -lm

test: all bin/test_protocol bin/test_failsafe bin/test_spline
	./bin/test_protocol
	./bin/test_failsafe
	./bin/test_spline
	$(PYTHON) -I tests/test_pattern_generator.py
	$(PYTHON) -I tests/test_network.py
	$(PYTHON) -I tests/test_swarm.py
	$(PYTHON) -I tests/test_baseline.py

test-sitl: all
	$(PX4_PYTHON) -I tests/test_sitl_flight.py
	$(PX4_PYTHON) -I tests/test_mavlink_measure.py

clean:
	rm -rf bin

.PHONY: all test test-sitl clean
