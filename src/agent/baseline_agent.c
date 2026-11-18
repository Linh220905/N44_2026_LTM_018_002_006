#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include "../common/cli.h"
#include "../common/stream.h"
#include <arpa/inet.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define RECORD_SIZE 25

static int64_t true_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (int64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}


int main(int argc, char **argv) {
    long id = -1;
    long port = 8080;
    double loss_percent = 0.0;
    double delay_ms = 0.0;
    double jitter_ms = 0.0;

    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--id")) id = cli_long(argv[i + 1], 0, 99);
        else if (!strcmp(argv[i], "--port")) port = cli_long(argv[i + 1], 1, 65535);
        else if (!strcmp(argv[i], "--loss")) loss_percent = cli_double(argv[i + 1], 0, 100);
        else if (!strcmp(argv[i], "--delay")) delay_ms = cli_double(argv[i + 1], 0, 1000);
        else if (!strcmp(argv[i], "--jitter-ms")) jitter_ms = cli_double(argv[i + 1], 0, 1000);
        else return 2;
    }

    if (id < 0 || id > 99) {
        fprintf(stderr, "Invalid or missing --id\n");
        return 2;
    }

    /* Seed PRNG for repeatable or stochastic packet loss */
    srand((unsigned int)(id * 10007 + (unsigned int)time(NULL)));

    int tcp = socket(AF_INET, SOCK_STREAM, 0);
    if (tcp < 0) { perror("socket"); return 1; }

    struct sockaddr_in server_addr = {
        .sin_family = AF_INET,
        .sin_port = htons((uint16_t)port),
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK)
    };

    if (connect(tcp, (struct sockaddr *)&server_addr, sizeof server_addr) != 0) {
        perror("connect");
        close(tcp);
        return 1;
    }

    struct timeval timeout = {.tv_sec = 10};
    if (setsockopt(tcp, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout)) { perror("timeout"); return 1; }

    /* Handshake */
    uint8_t req_frame[HEADER_SIZE + 2];
    uint8_t req_payload[2];
    put16(req_payload, (uint16_t)id);
    size_t req_len = 0;
    encode(req_frame, sizeof req_frame, MSG_HELLO_REQ, 1, req_payload, 2, &req_len);
    if (send_all_bytes(tcp, req_frame, req_len)) {
        perror("send HELLO_REQ");
        close(tcp);
        return 1;
    }

    uint8_t frame[HEADER_SIZE + PAYLOAD_MAX];
    struct packet pkt;
    if (read_frame(tcp, frame, sizeof frame, &pkt) != 0 ||
        pkt.type != MSG_HELLO_ACK || pkt.len != 2 || get16(pkt.payload) != id) {
        fprintf(stderr, "Handshake failed for drone %ld\n", id);
        close(tcp);
        return 1;
    }

    int64_t t_first_start = -1;
    int received_count = 0;
    int dropped_count = 0;
    int total_samples = 0;
    double sum_sq_error = 0.0;
    double max_error_m = 0.0;

    float held_x = 0.0f;
    int has_held = 0;

    for (;;) {
        if (read_frame(tcp, frame, sizeof frame, &pkt) != 0) {
            fprintf(stderr, "stream ended before STOP\n"); close(tcp); return 1;
        }

        if (pkt.type == MSG_EMERGENCY_STOP && pkt.len == 0) {
            break;
        }

        if (pkt.type == MSG_SETPOINT && pkt.len == RECORD_SIZE && get16(pkt.payload) == id) {
            if (t_first_start < 0) {
                /* Same per-link queueing model as the proposed agent: exponential one-way delay. */
                if (jitter_ms > 0) {
                    double u = (rand() + 1.0) / ((double)RAND_MAX + 2.0);
                    usleep((useconds_t)(-log(u) * jitter_ms * 1000.0));
                }
                t_first_start = true_us();
                printf("drone=%ld start_us=%lld\n", id, (long long)t_first_start);
                fflush(stdout);
            }

            /* Read true setpoint position from packet */
            uint32_t x_bits = get32(pkt.payload + 6);
            float target_x;
            memcpy(&target_x, &x_bits, 4);

            if (!has_held) {
                held_x = target_x;
                has_held = 1;
            }

            /* Simulate packet loss */
            double r = (double)rand() / (double)RAND_MAX * 100.0;
            if (r < loss_percent) {
                /* Packet is lost! Drone retains old setpoint */
                dropped_count++;
            } else {
                /* Packet received successfully */
                received_count++;
                held_x = target_x;
            }

            /* Calculate tracking error e = |held_x - target_x| */
            double err = fabs((double)(held_x - target_x));
            sum_sq_error += err * err;
            if (err > max_error_m) max_error_m = err;
            total_samples++;

            if (delay_ms > 0) {
                usleep((useconds_t)(delay_ms * 1000));
            }
        }
    }

    close(tcp);

    double e_rms_m = (total_samples > 0) ? sqrt(sum_sq_error / total_samples) : 0.0;
    double e_rms_cm = e_rms_m * 100.0;
    double max_e_cm = max_error_m * 100.0;
    double actual_loss_rate = (received_count + dropped_count > 0) ?
        ((double)dropped_count / (double)(received_count + dropped_count) * 100.0) : 0.0;

    printf("BASELINE_AGENT_SUMMARY: id=%ld start_us=%lld received=%d dropped=%d loss_rate=%.2f%% E_RMS_cm=%.4f max_e_cm=%.4f\n",
           id, (long long)t_first_start, received_count, dropped_count, actual_loss_rate, e_rms_cm, max_e_cm);
    fflush(stdout);

    return 0;
}
