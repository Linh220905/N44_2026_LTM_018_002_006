#ifndef DRONE_STREAM_H
#define DRONE_STREAM_H
#include "protocol.h"

int send_all_bytes(int fd, const uint8_t *buffer, size_t length);
int read_frame(int fd, uint8_t *frame, size_t capacity, struct packet *packet);
#endif
