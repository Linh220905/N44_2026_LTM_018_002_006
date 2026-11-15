#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include <arpa/inet.h>
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define RECORD_PAYLOAD 27
static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}
static int read_frame(int fd, uint8_t *frame, size_t capacity, struct packet *packet) {
    size_t used = 0, needed = HEADER_SIZE;
    while (used < needed) {
        ssize_t n = recv(fd, frame + used, needed - used, 0);
        if (n <= 0) return -1;
        used += (size_t)n;
        if (used == HEADER_SIZE) {
            uint32_t len = get32(frame + 8);
            if (len > PAYLOAD_MAX || HEADER_SIZE + (size_t)len > capacity) return -1;
            needed = HEADER_SIZE + (size_t)len;
        }
    }
    return decode(frame, used, packet);
}
static int setup_multicast(const char *spec) {
    const char *separator = strrchr(spec, ':');
    char address[64];
    if (!separator || separator - spec < 1 || (size_t)(separator - spec) >= sizeof address) return -1;
    memcpy(address, spec, (size_t)(separator - spec));
    address[separator - spec] = 0;
    char *end;
    long port = strtol(separator + 1, &end, 10);
    if (*end || port < 1 || port > 65535) return -1;
    struct in_addr group;
    if (inet_pton(AF_INET, address, &group) != 1 ||
        (ntohl(group.s_addr) & 0xf0000000u) != 0xe0000000u) return -1;
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;
    int reuse = 1;
    struct sockaddr_in local = {.sin_family = AF_INET, .sin_port = htons((uint16_t)port),
                                .sin_addr.s_addr = htonl(INADDR_ANY)};
    struct ip_mreq membership = {.imr_multiaddr = group,
                                 .imr_interface.s_addr = htonl(INADDR_LOOPBACK)};
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof reuse) ||
        bind(fd, (struct sockaddr *)&local, sizeof local) ||
        setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &membership, sizeof membership)) {
        close(fd);
        return -1;
    }
    return fd;
}
int main(int argc, char **argv) {
    long id = -1, port = 8080;
    const char *group = "239.255.0.1:9090";
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--id")) {
            char *end;
            id = strtol(argv[i + 1], &end, 10);
            if (*end || id < 0 || id > 99) return 2;
        } else if (!strcmp(argv[i], "--port")) {
            char *end;
            port = strtol(argv[i + 1], &end, 10);
            if (*end || port < 1 || port > 65535) return 2;
        } else if (!strcmp(argv[i], "--multicast")) group = argv[i + 1];
        else return 2;
    }
    if (id < 0) return 2;
    int udp = setup_multicast(group);
    if (udp < 0) { perror("multicast"); return 1; }
    int tcp = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in server = {.sin_family = AF_INET, .sin_port = htons((uint16_t)port),
                                 .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    if (tcp < 0 || connect(tcp, (struct sockaddr *)&server, sizeof server)) { perror("connect"); return 1; }
    struct timeval timeout = {.tv_sec = 5};
    setsockopt(tcp, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    uint8_t request[HEADER_SIZE + 2], drone_id[2];
    put16(drone_id, (uint16_t)id);
    size_t size;
    if (encode(request, sizeof request, MSG_HELLO_REQ, 1, drone_id, 2, &size) ||
        send(tcp, request, size, MSG_NOSIGNAL) != (ssize_t)size) return 1;
    uint8_t frame[HEADER_SIZE + RECORD_PAYLOAD];
    struct packet packet;
    if (read_frame(tcp, frame, sizeof frame, &packet) || packet.type != MSG_HELLO_ACK ||
        packet.len != 2 || get16(packet.payload) != id ||
        read_frame(tcp, frame, sizeof frame, &packet) || packet.type != MSG_TRAJECTORY_DATA ||
        packet.len != RECORD_PAYLOAD || get16(packet.payload) != id || get16(packet.payload + 2) != 1) {
        fprintf(stderr, "invalid handshake or trajectory for drone %ld\n", id);
        return 1;
    }
    printf("drone=%ld trajectory loaded\n", id);
    fflush(stdout);
    int64_t last = now_ms();
    uint32_t sequence = 0;
    for (;;) {
        struct pollfd events[2] = {{.fd = udp, .events = POLLIN}, {.fd = tcp, .events = POLLIN | POLLHUP}};
        int result = poll(events, 2, 200);
        if (result < 0) { if (errno == EINTR) continue; perror("poll"); return 1; }
        if (events[1].revents) { fprintf(stderr, "GCS disconnected\n"); return 1; }
        if (events[0].revents & POLLIN) {
            uint8_t data[HEADER_SIZE + 8];
            ssize_t n = recv(udp, data, sizeof data, 0);
            if (n < 0) { perror("recv UDP"); return 1; }
            if (decode(data, (size_t)n, &packet) || packet.seq <= sequence) continue;
            sequence = packet.seq;
            last = now_ms();
            if (packet.type == MSG_EMERGENCY_STOP && packet.len == 0) return 2;
            if (packet.type == MSG_SHOW_ARM_TRIGGER && packet.len == 8) {
                printf("drone=%ld SHOW started (simulation only)\n", id);
                return 0;
            }
        }
        if (now_ms() - last > 2000) { fprintf(stderr, "heartbeat timeout\n"); return 1; }
    }
}
