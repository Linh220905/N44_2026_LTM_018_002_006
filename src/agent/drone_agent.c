#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include "../common/cli.h"
#include "../common/stream.h"
#include "failsafe.h"
#include <arpa/inet.h>
#include <errno.h>
#include <math.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

#define RECORD_PAYLOAD 27
#define HEARTBEAT_TIMEOUT_US 2000000ull
static int64_t clock_offset_us; /* emulated error of this agent's oscillator */
static double jitter_ms;        /* emulated one-way queueing delay, exponential mean */
static double loss_percent;     /* emulated multicast loss, Bernoulli */

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
static int64_t local_us(void) { return true_us() + clock_offset_us; }
static void queue_delay(void) {
    if (jitter_ms <= 0) return;
    double u = (rand() + 1.0) / ((double)RAND_MAX + 2.0);
    usleep((useconds_t)(-log(u) * jitter_ms * 1000.0));
}
/* Cristian/NTP four-timestamp exchange; keep the sample with minimum RTT (eq. 4.6). */
static int time_sync(long port, int samples, int64_t *theta, int64_t *rtt_min) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in server = {.sin_family = AF_INET, .sin_port = htons((uint16_t)port),
                                 .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    struct timeval timeout = {.tv_usec = 200000};
    if (fd < 0) return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout)) { close(fd); return -1; }
    if (connect(fd, (struct sockaddr *)&server, sizeof server)) { close(fd); return -1; }
    *rtt_min = INT64_MAX;
    for (int k = 1; k <= samples; ++k) {
        uint8_t request[HEADER_SIZE + 8], reply[HEADER_SIZE + 24], stamp[8];
        size_t size;
        int64_t t1 = local_us();
        put64(stamp, (uint64_t)t1);
        if (encode(request, sizeof request, MSG_TIME_SYNC_REQ, (uint32_t)k, stamp, 8, &size)) break;
        queue_delay();
        if (sendto(fd, request, size, 0, (struct sockaddr *)&server, sizeof server) < 0) break;
        ssize_t n = recv(fd, reply, sizeof reply, MSG_TRUNC);
        queue_delay();
        int64_t t4 = local_us();
        struct packet packet;
        if (n < 0 || (size_t)n > sizeof reply || decode(reply, (size_t)n, &packet) || packet.type != MSG_TIME_SYNC_RESP ||
            packet.len != 24 || packet.seq != (uint32_t)k || (int64_t)get64(packet.payload) != t1) continue;
        int64_t t2 = (int64_t)get64(packet.payload + 8), t3 = (int64_t)get64(packet.payload + 16);
        int64_t rtt = (t4 - t1) - (t3 - t2), offset = ((t2 - t1) + (t3 - t4)) / 2;
        printf("sync k=%d rtt_us=%lld theta_us=%lld\n", k, (long long)rtt, (long long)offset);
        if (rtt >= 0 && rtt < *rtt_min) { *rtt_min = rtt; *theta = offset; }
        usleep(2000);
    }
    close(fd);
    return *rtt_min == INT64_MAX ? -1 : 0;
}
static void on_failsafe(struct failsafe_monitor *mon, const failsafe_mavlink_cmd_t *cmd, void *id) {
    (void)mon;
    printf("drone=%ld FAILSAFE true_us=%lld cmd=%u %s\n", *(long *)id, (long long)true_us(),
           cmd->command, cmd->description);
}
static int setup_multicast(const char *spec) {
    const char *separator = strrchr(spec, ':');
    char address[64];
    if (!separator || separator - spec < 1 || (size_t)(separator - spec) >= sizeof address) return -1;
    memcpy(address, spec, (size_t)(separator - spec));
    address[separator - spec] = 0;
    long port = cli_long(separator + 1, 1, 65535);
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
    long id = -1, port = 8080, sync_port = 9091, samples = 8, show_ms = 0;
    const char *group = "239.255.0.1:9090";
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--id")) id = cli_long(argv[i + 1], 0, 99);
        else if (!strcmp(argv[i], "--port")) port = cli_long(argv[i + 1], 1, 65535);
        else if (!strcmp(argv[i], "--multicast")) group = argv[i + 1];
        else if (!strcmp(argv[i], "--sync-port")) sync_port = cli_long(argv[i + 1], 1, 65535);
        else if (!strcmp(argv[i], "--samples")) samples = cli_long(argv[i + 1], 1, 1000);
        else if (!strcmp(argv[i], "--show-ms")) show_ms = cli_long(argv[i + 1], 1, 600000);
        else if (!strcmp(argv[i], "--clock-offset-ms"))
            clock_offset_us = (int64_t)llround(cli_double(argv[i + 1], -100000, 100000) * 1000.0);
        else if (!strcmp(argv[i], "--jitter-ms")) jitter_ms = cli_double(argv[i + 1], 0, 1000);
        else if (!strcmp(argv[i], "--loss")) loss_percent = cli_double(argv[i + 1], 0, 100);
        else return 2;
    }
    srand((unsigned)(id * 7919 + true_us()));
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
        send_all_bytes(tcp, request, size)) return 1;
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
    float position[3];
    for (int axis = 0; axis < 3; ++axis) {
        uint32_t bits = get32(packet.payload + 8 + 4 * axis);
        memcpy(&position[axis], &bits, sizeof bits);
    }
    int64_t theta = 0, rtt_min = 0;
    if (time_sync(sync_port, (int)samples, &theta, &rtt_min)) { fprintf(stderr, "time sync failed\n"); return 1; }
    printf("drone=%ld SYNCED theta_us=%lld rtt_min_us=%lld epsilon_us=%lld true_offset_us=%lld\n", id,
           (long long)theta, (long long)rtt_min, (long long)(rtt_min / 2), (long long)-clock_offset_us);
    fflush(stdout);
    geofence_box_t fence;
    geofence_box_init(&fence, -50, 50, -50, 50, -50, 0);
    failsafe_monitor_t monitor;
    failsafe_init(&monitor, &fence);
    monitor.timeout_us = HEARTBEAT_TIMEOUT_US;
    failsafe_set_action_callback(&monitor, on_failsafe, &id);
    int timer = timerfd_create(CLOCK_REALTIME, TFD_CLOEXEC);
    if (timer < 0) { perror("timerfd_create"); return 1; }
    int armed = 0;
    int64_t target = 0;
    int64_t last = now_ms(), show_end = 0;
    long lost = 0;
    uint32_t sequence = 0;
    for (;;) {
        struct pollfd events[3] = {{.fd = udp, .events = POLLIN},
                                   {.fd = show_end ? -1 : tcp, .events = POLLIN | POLLHUP},
                                   {.fd = timer, .events = POLLIN}};
        int result = poll(events, 3, 200);
        if (result < 0) { if (errno == EINTR) continue; perror("poll"); return 1; }
        if (events[1].revents) { fprintf(stderr, "GCS disconnected\n"); return 1; }
        if (events[0].revents & POLLIN) {
            uint8_t data[HEADER_SIZE + 8];
            ssize_t n = recv(udp, data, sizeof data, MSG_TRUNC);
            if (n < 0) { perror("recv UDP"); return 1; }
            if ((size_t)n > sizeof data || decode(data, (size_t)n, &packet) || packet.seq <= sequence ||
                !((packet.type == MSG_SWARM_HEARTBEAT && packet.len == 0) ||
                  (packet.type == MSG_SHOW_ARM_TRIGGER && packet.len == 8) ||
                  (packet.type == MSG_EMERGENCY_STOP && packet.len == 0))) continue;
            if (rand() / ((double)RAND_MAX + 1.0) * 100.0 < loss_percent) { ++lost; continue; }
            queue_delay();
            sequence = packet.seq;
            last = now_ms();
            failsafe_update_heartbeat(&monitor, (uint64_t)now_ms() * 1000u);
            if (packet.type == MSG_EMERGENCY_STOP && packet.len == 0) return 2;
            if (packet.type == MSG_SHOW_ARM_TRIGGER && !armed && !show_end) {
                uint64_t raw_target = get64(packet.payload);
                if (raw_target > INT64_MAX - 1000000000ull) return 1;
                target = (int64_t)raw_target;
                int64_t wake = target - theta - clock_offset_us;
                /* Reject stale or implausible targets; never start an unsynchronized late agent. */
                if (wake <= true_us() || wake - true_us() > 120000000) {
                    fprintf(stderr, "invalid or late trigger\n"); return 1;
                }
                struct itimerspec deadline = {.it_value = {
                    .tv_sec = wake / 1000000, .tv_nsec = (wake % 1000000) * 1000}};
                if (timerfd_settime(timer, TFD_TIMER_ABSTIME, &deadline, NULL)) {
                    perror("timerfd_settime"); return 1;
                }
                armed = 1;
            }
        }
        if (events[2].revents & POLLIN) {
            uint64_t expirations;
            if (read(timer, &expirations, sizeof expirations) != sizeof expirations) return 1;
            printf("drone=%ld SHOW started true_us=%lld target_us=%lld (simulation only)\n",
                   id, (long long)true_us(), (long long)target);
            fflush(stdout);
            if (!show_ms) return 0;
            show_end = now_ms() + show_ms;
        }
        if (show_end) {
            if (failsafe_check(&monitor, (uint64_t)now_ms() * 1000u, position[0], position[1], -position[2])) {
                fflush(stdout);
                return 3;
            }
            if (now_ms() >= show_end) { printf("drone=%ld SHOW finished lost=%ld\n", id, lost); return 0; }
        } else if (now_ms() - last > 2000) { fprintf(stderr, "heartbeat timeout\n"); return 1; }
    }
}
