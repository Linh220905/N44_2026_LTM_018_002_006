#include "protocol.h"
#include <string.h>

uint16_t get16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }
uint32_t get32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
void put32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

static uint16_t crc(const uint8_t *data, size_t size) {
    uint16_t value = 0xffff;
    for (size_t i = 0; i < size; ++i) {
        uint8_t byte = (i == 12 || i == 13) ? 0 : data[i];
        value ^= (uint16_t)byte << 8;
        for (unsigned j = 0; j < 8; ++j)
            value = (uint16_t)((value & 0x8000) ? (value << 1) ^ 0x1021 : value << 1);
    }
    return value;
}

int encode(uint8_t *out, size_t capacity, uint8_t type, uint32_t seq,
           const uint8_t *payload, uint32_t len, size_t *size) {
    if (!out || !size || (len && !payload) || len > PAYLOAD_MAX ||
        capacity < HEADER_SIZE + (size_t)len || type < MSG_HELLO_REQ || type > MSG_EMERGENCY_STOP)
        return -1;
    put16(out, 0x5058);
    out[2] = 1;
    out[3] = type;
    put32(out + 4, seq);
    put32(out + 8, len);
    put16(out + 12, 0);
    put16(out + 14, 0);
    if (len) memcpy(out + HEADER_SIZE, payload, len);
    *size = HEADER_SIZE + (size_t)len;
    put16(out + 12, crc(out, *size));
    return 0;
}

int decode(const uint8_t *frame, size_t size, struct packet *out) {
    if (!frame || !out || size < HEADER_SIZE || size > FRAME_MAX ||
        get16(frame) != 0x5058 || frame[2] != 1 ||
        frame[3] < MSG_HELLO_REQ || frame[3] > MSG_EMERGENCY_STOP ||
        get16(frame + 14) != 0 || get32(frame + 8) > PAYLOAD_MAX ||
        size != HEADER_SIZE + (size_t)get32(frame + 8) ||
        get16(frame + 12) != crc(frame, size)) return -1;
    *out = (struct packet){.type = frame[3], .seq = get32(frame + 4),
                           .len = get32(frame + 8), .payload = frame + HEADER_SIZE};
    return 0;
}
