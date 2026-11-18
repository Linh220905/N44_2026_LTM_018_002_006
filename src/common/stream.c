#include "stream.h"
#include <errno.h>
#include <poll.h>
#include <sys/socket.h>

int send_all_bytes(int fd, const uint8_t *buffer, size_t length) {
    size_t sent = 0;
    while (sent < length) {
        ssize_t n = send(fd, buffer + sent, length - sent, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (n > 0) { sent += (size_t)n; continue; }
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            struct pollfd event = {.fd = fd, .events = POLLOUT};
            int result;
            do { result = poll(&event, 1, 2000); } while (result < 0 && errno == EINTR);
            if (result > 0 && (event.revents & POLLOUT)) continue;
        }
        return -1;
    }
    return 0;
}

int read_frame(int fd, uint8_t *frame, size_t capacity, struct packet *packet) {
    if (capacity < HEADER_SIZE) return -1;
    size_t used = 0, needed = HEADER_SIZE;
    while (used < needed) {
        ssize_t n = recv(fd, frame + used, needed - used, 0);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        used += (size_t)n;
        if (used == HEADER_SIZE) {
            uint32_t length = get32(frame + 8);
            if (length > PAYLOAD_MAX || HEADER_SIZE + (size_t)length > capacity) return -1;
            needed = HEADER_SIZE + (size_t)length;
        }
    }
    return decode(frame, used, packet);
}
