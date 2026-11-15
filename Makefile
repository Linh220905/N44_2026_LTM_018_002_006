CC = gcc
PX4_PYTHON = $(HOME)/px4-venv/bin/python
CFLAGS = -std=c11 -D_DEFAULT_SOURCE -O2 -Wall -Wextra -Werror

all: bin/gcs_server bin/drone_agent bin/baseline_server bin/baseline_agent

bin:
	mkdir -p bin

bin/gcs_server: server/gcs_server.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) server/gcs_server.c common/protocol.c -o $@

bin/drone_agent: agent/drone_agent.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) agent/drone_agent.c common/protocol.c -o $@

bin/baseline_server: server/baseline_server.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) server/baseline_server.c common/protocol.c -o $@ -lm

bin/baseline_agent: agent/baseline_agent.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) agent/baseline_agent.c common/protocol.c -o $@ -lm

bin/test_protocol: tests/test_protocol.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) --coverage tests/test_protocol.c common/protocol.c -o $@

bin/test_failsafe: tests/test_failsafe.c agent/failsafe.c agent/failsafe.h common/geofence.c common/geofence.h | bin
	$(CC) $(CFLAGS) tests/test_failsafe.c agent/failsafe.c common/geofence.c -o $@

test: all bin/test_protocol bin/test_failsafe
	./bin/test_protocol
	./bin/test_failsafe
	python3 -I tests/test_swarm.py
	python3 -I tests/test_baseline.py
	$(PX4_PYTHON) -I tests/test_sitl_flight.py
	$(PX4_PYTHON) -I tests/test_mavlink_measure.py

clean:
	rm -rf bin *.gcda *.gcno

.PHONY: all test clean
