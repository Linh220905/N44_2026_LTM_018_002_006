#ifndef DRONE_PROTOCOL_H
#define DRONE_PROTOCOL_H
#include <stddef.h>
#include <stdint.h>

#define HEADER_SIZE 16u
#define PAYLOAD_MAX 65536u
#define FRAME_MAX (HEADER_SIZE + PAYLOAD_MAX)
#define MSG_HELLO_REQ 1
#define MSG_HELLO_ACK 2
#define MSG_TRAJECTORY_DATA 3
#define MSG_TIME_SYNC_REQ 4
#define MSG_TIME_SYNC_RESP 5
#define MSG_SWARM_HEARTBEAT 6
#define MSG_SHOW_ARM_TRIGGER 7
#define MSG_EMERGENCY_STOP 8
#define MSG_SETPOINT 9
#define MSG_SHOW_WAYPOINT_DATA 10 /* u16 id, u16 count, count x 31-byte spline knot */

struct packet {
    uint8_t type;
    uint32_t seq;
    uint32_t len;
    const uint8_t *payload; /* Borrows input frame; never outlives it. */
};

uint16_t get16(const uint8_t *p);
uint32_t get32(const uint8_t *p);
void put16(uint8_t *p, uint16_t value);
void put32(uint8_t *p, uint32_t value);
uint64_t get64(const uint8_t *p);
void put64(uint8_t *p, uint64_t value);
int encode(uint8_t *out, size_t capacity, uint8_t type, uint32_t seq,
           const uint8_t *payload, uint32_t len, size_t *size);
int decode(const uint8_t *frame, size_t size, struct packet *out);

#endif
