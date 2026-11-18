#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include "../common/cli.h"
#include "../common/stream.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define MAX_CLIENTS 256
#define RECORD_SIZE 25

struct client {
    int fd;
    int id;
    int active;
    size_t used;
    uint8_t hello[HEADER_SIZE + 2];
};

static struct client clients[MAX_CLIENTS];
static uint8_t base_records[100][RECORD_SIZE];
static int total_drones = 0;
static int connected_count = 0;

static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static int64_t true_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (int64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

static int nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static int load_show(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror("fopen show"); return -1; }
    uint8_t header[6];
    if (fread(header, 1, 6, f) != 6 || memcmp(header, "SHOW", 4) != 0) {
        fclose(f);
        fprintf(stderr, "invalid show magic\n");
        return -1;
    }
    total_drones = get16(header + 4);
    if (total_drones < 1 || total_drones > 100) {
        fclose(f);
        fprintf(stderr, "invalid drone count: %d\n", total_drones);
        return -1;
    }
    for (int i = 0; i < total_drones; ++i) {
        if (fread(base_records[i], 1, RECORD_SIZE, f) != RECORD_SIZE || get16(base_records[i]) != i) {
            fclose(f);
            fprintf(stderr, "invalid record for drone %d\n", i);
            return -1;
        }
    }
    int extra = fgetc(f);
    int invalid = extra != EOF || ferror(f);
    fclose(f);
    return invalid ? -1 : 0;
}


int main(int argc, char **argv) {
    const char *show_path = NULL;
    long port = 8080;
    long rate_hz = 10;
    double duration_sec = 5.0;
    double velocity = 2.0; /* 2.0 m/s default for theoretical alignment */

    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--show")) show_path = argv[i + 1];
        else if (!strcmp(argv[i], "--port")) port = cli_long(argv[i + 1], 1, 65535);
        else if (!strcmp(argv[i], "--rate")) rate_hz = cli_long(argv[i + 1], 1, 100);
        else if (!strcmp(argv[i], "--duration")) duration_sec = cli_double(argv[i + 1], 0.1, 600);
        else if (!strcmp(argv[i], "--velocity")) velocity = cli_double(argv[i + 1], -1000, 1000);
        else return 2;
    }

    if (!show_path || load_show(show_path) != 0) return 2;

    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) { perror("socket"); return 1; }
    int reuse = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof reuse);

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons((uint16_t)port),
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK)
    };
    if (bind(listener, (struct sockaddr *)&addr, sizeof addr) != 0 ||
        listen(listener, 128) != 0) {
        perror("bind/listen");
        close(listener);
        return 1;
    }

    printf("BASELINE_GCS: listening on port %ld for %d drones\n", port, total_drones);
    fflush(stdout);

    for (int i = 0; i < MAX_CLIENTS; ++i) {
        clients[i].fd = -1;
        clients[i].id = -1;
        clients[i].active = 0;
    }

    /* Wait for all drones to connect and perform HELLO */
    int ep = epoll_create1(0);
    if (ep < 0 || nonblock(listener)) { perror("epoll/nonblock"); return 1; }
    struct epoll_event ev = {.events = EPOLLIN, .data.ptr = NULL};
    if (epoll_ctl(ep, EPOLL_CTL_ADD, listener, &ev)) { perror("epoll_ctl"); return 1; }

    int64_t connect_deadline = now_ms() + 15000;
    while (connected_count < total_drones && now_ms() < connect_deadline) {
        struct epoll_event events[16];
        int n = epoll_wait(ep, events, 16, 50);
        if (n < 0) { if (errno == EINTR) continue; perror("epoll_wait"); return 1; }
        for (int i = 0; i < n; ++i) {
            struct client *c = events[i].data.ptr;
            if (!c) {
                int fd = accept(listener, NULL, NULL);
                if (fd < 0) continue;
                int slot = 0;
                while (slot < MAX_CLIENTS && clients[slot].fd >= 0) ++slot;
                if (slot == MAX_CLIENTS || nonblock(fd)) { close(fd); continue; }
                c = &clients[slot];
                *c = (struct client){.fd = fd, .id = -1};
                struct epoll_event cev = {.events = EPOLLIN | EPOLLRDHUP, .data.ptr = c};
                if (!epoll_ctl(ep, EPOLL_CTL_ADD, fd, &cev)) continue;
            } else if (!(events[i].events & (EPOLLERR | EPOLLHUP | EPOLLRDHUP)) && !c->active) {
                ssize_t r = recv(c->fd, c->hello + c->used, sizeof c->hello - c->used, 0);
                if (r < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) continue;
                if (r > 0) {
                    c->used += (size_t)r;
                    if (c->used < sizeof c->hello) continue;
                    struct packet pkt;
                    if (!decode(c->hello, c->used, &pkt) && pkt.type == MSG_HELLO_REQ && pkt.len == 2 &&
                        get16(pkt.payload) < total_drones) {
                        int id = get16(pkt.payload), duplicate = 0;
                        for (int j = 0; j < MAX_CLIENTS; ++j)
                            if (clients[j].active && clients[j].id == id) duplicate = 1;
                        uint8_t ack[HEADER_SIZE + 2];
                        size_t length;
                        if (!duplicate && !encode(ack, sizeof ack, MSG_HELLO_ACK, 1, pkt.payload, 2, &length) &&
                            !send_all_bytes(c->fd, ack, length)) {
                            c->id = id;
                            c->active = 1;
                            ++connected_count;
                            struct epoll_event cev = {.events = EPOLLRDHUP, .data.ptr = c};
                            if (!epoll_ctl(ep, EPOLL_CTL_MOD, c->fd, &cev)) continue;
                        }
                    }
                }
            }
            epoll_ctl(ep, EPOLL_CTL_DEL, c->fd, NULL);
            close(c->fd);
            if (c->active) --connected_count;
            *c = (struct client){.fd = -1, .id = -1};
        }
    }

    if (connected_count < total_drones) {
        fprintf(stderr, "BASELINE_GCS: timed out waiting for all drones (connected %d/%d)\n",
                connected_count, total_drones);
        close(listener);
        close(ep);
        return 1;
    }

    struct client ordered[100];
    for (int i = 0; i < MAX_CLIENTS; ++i)
        if (clients[i].active) ordered[clients[i].id] = clients[i];
    memcpy(clients, ordered, (size_t)total_drones * sizeof *clients);

    printf("BASELINE_GCS: all %d drones connected. Commencing sequential trigger...\n", total_drones);
    fflush(stdout);

    /* Phase 1: Sequential Unicast Startup Trigger */
    int64_t first_send_us = 0;
    int64_t last_send_us = 0;

    for (int i = 0; i < total_drones; ++i) {
        int64_t t_send = true_us();
        if (i == 0) first_send_us = t_send;
        if (i == total_drones - 1) last_send_us = t_send;

        /* Send first setpoint / start trigger sequentially */
        uint8_t payload[RECORD_SIZE];
        memcpy(payload, base_records[i], RECORD_SIZE);
        put32(payload + 2, 0); /* t_ms = 0 */

        uint8_t frame[HEADER_SIZE + RECORD_SIZE];
        size_t frame_len = 0;
        encode(frame, sizeof frame, MSG_SETPOINT, 1, payload, RECORD_SIZE, &frame_len);
        if (send_all_bytes(clients[i].fd, frame, frame_len)) { perror("send setpoint"); return 1; }
    }

    int64_t start_skew_us = last_send_us - first_send_us;
    printf("BASELINE_GCS: sequential trigger done. send_spread_us=%lld\n", (long long)start_skew_us);
    fflush(stdout);

    /* Phase 2: Real-time 10 Hz Unicast Setpoint Streaming (Algorithm 4) */
    int64_t show_start_ms = now_ms();
    int64_t show_end_ms = show_start_ms + (int64_t)(duration_sec * 1000.0);
    int interval_ms = (int)(1000 / rate_hz);
    int64_t next_tick = show_start_ms + interval_ms;
    uint32_t seq = 1;
    size_t total_bytes_sent = 0;

    while (now_ms() < show_end_ms) {
        int64_t now = now_ms();
        if (now >= next_tick) {
            uint32_t t_show_ms = (uint32_t)(now - show_start_ms);
            float dt_sec = (float)t_show_ms / 1000.0f;
            float shift = (float)(velocity * dt_sec);

            for (int i = 0; i < total_drones; ++i) {
                if (clients[i].fd < 0) continue;
                uint8_t payload[RECORD_SIZE];
                memcpy(payload, base_records[i], RECORD_SIZE);
                put32(payload + 2, t_show_ms);

                /* Update x position along trajectory: x(t) = x0 + v * t */
                /* Read base x */
                uint32_t x_bits = get32(payload + 6);
                float x0;
                memcpy(&x0, &x_bits, 4);
                float x_curr = x0 + shift;
                uint32_t x_curr_bits;
                memcpy(&x_curr_bits, &x_curr, 4);
                put32(payload + 6, x_curr_bits);

                uint8_t frame[HEADER_SIZE + RECORD_SIZE];
                size_t frame_len = 0;
                encode(frame, sizeof frame, MSG_SETPOINT, ++seq, payload, RECORD_SIZE, &frame_len);
                if (send_all_bytes(clients[i].fd, frame, frame_len)) { perror("send setpoint"); return 1; }
                total_bytes_sent += frame_len;
            }
            next_tick += interval_ms;
        } else {
            usleep(1000);
        }
    }

    int64_t actual_duration_ms = now_ms() - show_start_ms;
    double actual_sec = (double)actual_duration_ms / 1000.0;
    double bandwidth_kbps = (double)total_bytes_sent / (actual_sec * 1024.0);

    /* Send Emergency Stop to finish */
    for (int i = 0; i < total_drones; ++i) {
        if (clients[i].fd >= 0) {
            uint8_t stop_frame[HEADER_SIZE];
            size_t stop_len = 0;
            encode(stop_frame, sizeof stop_frame, MSG_EMERGENCY_STOP, ++seq, NULL, 0, &stop_len);
            if (send_all_bytes(clients[i].fd, stop_frame, stop_len)) { perror("send stop"); return 1; }
            close(clients[i].fd);
        }
    }

    close(listener);
    close(ep);

    struct rusage usage;
    getrusage(RUSAGE_SELF, &usage);
    double cpu = (double)usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6 +
                 (double)usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1e6;
    printf("BASELINE_GCS_SUMMARY: N=%d duration_sec=%.2f total_bytes=%zu bandwidth_kbps=%.3f send_spread_us=%lld cpu_s=%.4f\n",
           total_drones, actual_sec, total_bytes_sent, bandwidth_kbps, (long long)start_skew_us, cpu);
    fflush(stdout);
    return 0;
}
