#ifndef DRONE_CLI_H
#define DRONE_CLI_H
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static inline long cli_long(const char *text, long minimum, long maximum) {
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno || end == text || *end || value < minimum || value > maximum) {
        fprintf(stderr, "Invalid integer: %s (expected %ld..%ld)\n", text, minimum, maximum);
        exit(2);
    }
    return value;
}

static inline double cli_double(const char *text, double minimum, double maximum) {
    char *end;
    errno = 0;
    double value = strtod(text, &end);
    if (errno || end == text || *end || !isfinite(value) || value < minimum || value > maximum) {
        fprintf(stderr, "Invalid number: %s (expected %g..%g)\n", text, minimum, maximum);
        exit(2);
    }
    return value;
}
#endif
