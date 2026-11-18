#include "../src/common/protocol.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

int main(void) {
    uint8_t frame[FRAME_MAX], payload[] = {0, 42};
    size_t size = 0;
    struct packet packet;
    assert(HEADER_SIZE == 16);
    assert(encode(frame, sizeof frame, MSG_HELLO_REQ, 0x01020304, payload, 2, &size) == 0);
    assert(size == 18 && frame[0] == 0x50 && frame[1] == 0x58);
    assert(frame[4] == 1 && frame[5] == 2 && frame[6] == 3 && frame[7] == 4);
    assert(frame[14] == 0 && frame[15] == 0);
    assert(decode(frame, size, &packet) == 0);
    assert(packet.type == MSG_HELLO_REQ && packet.seq == 0x01020304 && packet.len == 2);
    assert(memcmp(packet.payload, payload, 2) == 0);
    assert(decode(frame, size - 1, &packet) != 0);
    frame[16] ^= 1;
    assert(decode(frame, size, &packet) != 0);
    frame[16] ^= 1;
    frame[8] = 0xff;
    assert(decode(frame, size, &packet) != 0);
    frame[8] = 0;
    frame[2] = 2;
    assert(decode(frame, size, &packet) != 0);
    assert(encode(frame, HEADER_SIZE, MSG_HELLO_REQ, 1, payload, 2, &size) != 0);
    assert(encode(frame, sizeof frame, MSG_SETPOINT, 42, payload, 2, &size) == 0);
    assert(decode(frame, size, &packet) == 0 && packet.type == MSG_SETPOINT);
    uint8_t wide[8];
    put64(wide, 0x0102030405060708ULL);
    assert(wide[0] == 1 && wide[7] == 8 && get64(wide) == 0x0102030405060708ULL);
    assert(encode(frame, sizeof frame, MSG_SHOW_WAYPOINT_DATA, 7, payload, 2, &size) == 0);
    assert(decode(frame, size, &packet) == 0 && packet.type == MSG_SHOW_WAYPOINT_DATA);
    assert(encode(frame, sizeof frame, MSG_SHOW_WAYPOINT_DATA + 1, 7, payload, 2, &size) != 0);
    frame[3] = MSG_SHOW_WAYPOINT_DATA + 1;
    assert(decode(frame, size, &packet) != 0);
    puts("protocol tests passed");
    return 0;
}
