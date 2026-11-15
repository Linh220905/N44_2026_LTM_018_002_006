#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define MAX_CLIENTS 256
#define RECORD_SIZE 25
#define TRAJECTORY_SIZE 27
struct client { int fd, id; size_t received, sent, to_send; uint8_t input[18], output[2 * HEADER_SIZE + 2 + TRAJECTORY_SIZE]; int ready; };
static struct client clients[MAX_CLIENTS];
static uint8_t records[100][RECORD_SIZE];
static int claimed[100], count, ready_count;

static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}
static void close_client(int ep, struct client *c) {
    if (c->fd < 0) return;
    epoll_ctl(ep, EPOLL_CTL_DEL, c->fd, NULL);
    close(c->fd);
    c->fd = -1;
    if (c->id >= 0) claimed[c->id] = 0;
    if (c->ready) { c->ready = 0; --ready_count; }
}
static int load_show(const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file) { perror("show"); return -1; }
    uint8_t header[6];
    int result = -1;
    if (fread(header, 1, sizeof header, file) != sizeof header || memcmp(header, "SHOW", 4) ||
        (count = get16(header + 4)) < 1 || count > 100) goto done;
    for (int i = 0; i < count; ++i) {
        if (fread(records[i], 1, RECORD_SIZE, file) != RECORD_SIZE || get16(records[i]) != i) goto done;
    }
    if (fgetc(file) != EOF || ferror(file)) goto done;
    result = 0;
done:
    fclose(file);
    if (result) fprintf(stderr, "invalid show format\n");
    return result;
}
static int nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}
static void handle_client(int ep, struct client *c, uint32_t events) {
    if (events & (EPOLLERR | EPOLLHUP | EPOLLRDHUP)) { close_client(ep, c); return; }
    if (events & EPOLLIN) {
        ssize_t n = recv(c->fd, c->input + c->received, sizeof c->input - c->received, 0);
        if (n <= 0) { if (n == 0 || errno != EAGAIN) close_client(ep, c); return; }
        c->received += (size_t)n;
        if (c->received != sizeof c->input) return;
        struct packet request;
        if (decode(c->input, c->received, &request) || request.type != MSG_HELLO_REQ || request.len != 2 ||
            get16(request.payload) >= count) { close_client(ep, c); return; }
        int id = get16(request.payload);
        if (claimed[id]) { close_client(ep, c); return; }
        claimed[id] = 1;
        c->id = id;
        uint8_t payload[TRAJECTORY_SIZE];
        put16(payload, (uint16_t)id);
        put16(payload + 2, 1);
        memcpy(payload + 4, records[id] + 2, RECORD_SIZE - 2);
        size_t ack_length, trajectory_length;
        if (encode(c->output, sizeof c->output, MSG_HELLO_ACK, 1,
                   request.payload, request.len, &ack_length) ||
            encode(c->output + ack_length, sizeof c->output - ack_length,
                   MSG_TRAJECTORY_DATA, 2, payload, sizeof payload, &trajectory_length)) {
            close_client(ep, c); return;
        }
        c->to_send = ack_length + trajectory_length;
        struct epoll_event ev = {.events = EPOLLOUT | EPOLLRDHUP, .data.ptr = c};
        if (epoll_ctl(ep, EPOLL_CTL_MOD, c->fd, &ev)) close_client(ep, c);
    }
    if (c->fd >= 0 && (events & EPOLLOUT)) {
        ssize_t n = send(c->fd, c->output + c->sent, c->to_send - c->sent, MSG_NOSIGNAL);
        if (n < 0) { if (errno != EAGAIN) close_client(ep, c); return; }
        c->sent += (size_t)n;
        if (c->sent == c->to_send) {
            c->ready = 1;
            ++ready_count;
            struct epoll_event ev = {.events = EPOLLRDHUP, .data.ptr = c};
            if (epoll_ctl(ep, EPOLL_CTL_MOD, c->fd, &ev)) close_client(ep, c);
        }
    }
}
static int multicast_socket(const char *spec, struct sockaddr_in *peer) {
    char address[64];
    const char *separator = strrchr(spec, ':');
    if (!separator || separator - spec < 1 || (size_t)(separator - spec) >= sizeof address) return -1;
    memcpy(address, spec, (size_t)(separator - spec));
    address[separator - spec] = 0;
    char *end;
    long port = strtol(separator + 1, &end, 10);
    if (*end || port < 1 || port > 65535) return -1;
    *peer = (struct sockaddr_in){.sin_family = AF_INET, .sin_port = htons((uint16_t)port)};
    if (inet_pton(AF_INET, address, &peer->sin_addr) != 1 ||
        (ntohl(peer->sin_addr.s_addr) & 0xf0000000u) != 0xe0000000u) return -1;
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct in_addr loop = {.s_addr = htonl(INADDR_LOOPBACK)};
    if (fd < 0) return -1;
    if (setsockopt(fd, IPPROTO_IP, IP_MULTICAST_IF, &loop, sizeof loop) < 0) { close(fd); return -1; }
    return fd;
}
int main(int argc, char **argv) {
    const char *show = NULL, *group = "239.255.0.1:9090";
    long port = 8080;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--show")) show = argv[i + 1];
        else if (!strcmp(argv[i], "--multicast")) group = argv[i + 1];
        else if (!strcmp(argv[i], "--port")) {
            char *end;
            port = strtol(argv[i + 1], &end, 10);
            if (*end || port < 1 || port > 65535) return 2;
        } else return 2;
    }
    if (!show || load_show(show)) return 2;
    struct sockaddr_in peer;
    int udp = multicast_socket(group, &peer);
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (udp < 0 || listener < 0) { perror("socket"); return 1; }
    int reuse = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof reuse);
    struct sockaddr_in local = {.sin_family = AF_INET, .sin_port = htons((uint16_t)port),
                                .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    if (bind(listener, (struct sockaddr *)&local, sizeof local) || listen(listener, 128) || nonblock(listener)) {
        perror("listener"); return 1;
    }
    for (int i = 0; i < MAX_CLIENTS; ++i) { clients[i].fd = -1; clients[i].id = -1; }
    int ep = epoll_create1(0);
    struct epoll_event event = {.events = EPOLLIN, .data.ptr = NULL};
    if (ep < 0 || epoll_ctl(ep, EPOLL_CTL_ADD, listener, &event)) { perror("epoll"); return 1; }
    int64_t next = now_ms(), started = -1;
    uint32_t sequence = 0;
    for (;;) {
        struct epoll_event events[32];
        int n = epoll_wait(ep, events, 32, 50);
        if (n < 0) { if (errno == EINTR) continue; perror("epoll_wait"); return 1; }
        for (int i = 0; i < n; ++i) {
            if (events[i].data.ptr) { handle_client(ep, events[i].data.ptr, events[i].events); continue; }
            for (;;) {
                int fd = accept(listener, NULL, NULL);
                if (fd < 0) { if (errno != EAGAIN) perror("accept"); break; }
                int slot = 0;
                while (slot < MAX_CLIENTS && clients[slot].fd >= 0) ++slot;
                if (slot == MAX_CLIENTS || nonblock(fd)) { close(fd); continue; }
                clients[slot] = (struct client){.fd = fd, .id = -1};
                struct epoll_event ev = {.events = EPOLLIN | EPOLLRDHUP, .data.ptr = &clients[slot]};
                if (epoll_ctl(ep, EPOLL_CTL_ADD, fd, &ev)) close_client(ep, &clients[slot]);
            }
        }
        int64_t now = now_ms();
        if (ready_count == count && started < 0) started = now + 500;
        if (ready_count < count && started > now) started = -1;
        if (now >= next) {
            uint8_t frame[HEADER_SIZE + 8];
            size_t length;
            int trigger = started >= 0 && now >= started;
            uint8_t target[8];
            uint64_t timestamp = (uint64_t)time(NULL) * 1000;
            for (int j = 7; j >= 0; --j) { target[j] = (uint8_t)timestamp; timestamp >>= 8; }
            if (!encode(frame, sizeof frame, trigger ? MSG_SHOW_ARM_TRIGGER : MSG_SWARM_HEARTBEAT,
                        ++sequence, trigger ? target : NULL, trigger ? 8 : 0, &length) &&
                sendto(udp, frame, length, 0, (struct sockaddr *)&peer, sizeof peer) < 0) perror("multicast");
            next = now + 250;
        }
    }
}
