CC = gcc
PX4_PYTHON = $(HOME)/px4-venv/bin/python
CFLAGS = -std=c11 -D_DEFAULT_SOURCE -O2 -Wall -Wextra -Werror

all: bin/gcs_server bin/drone_agent

bin:
	mkdir -p bin

bin/gcs_server: server/gcs_server.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) server/gcs_server.c common/protocol.c -o $@

bin/drone_agent: agent/drone_agent.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) agent/drone_agent.c common/protocol.c -o $@

bin/test_protocol: tests/test_protocol.c common/protocol.c common/protocol.h | bin
	$(CC) $(CFLAGS) --coverage tests/test_protocol.c common/protocol.c -o $@

test: all bin/test_protocol
	./bin/test_protocol
	python3 -I tests/test_swarm.py
	$(PX4_PYTHON) -I tests/test_sitl_flight.py
	$(PX4_PYTHON) -I tests/test_mavlink_measure.py

clean:
	rm -rf bin *.gcda *.gcno

.PHONY: all test clean
