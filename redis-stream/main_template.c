/*
 * main.c - STM32 MEMS to Redis Streamer for QNX
 *
 * Reads CSV sensor data from a serial port (default: /dev/serusb1) and
 * pushes each sample as an XADD entry to the /data/mems Redis stream using
 * raw RESP protocol over a plain TCP socket.  No external libraries required;
 * only standard POSIX sockets and termios are used.
 *
 * CSV format (produced by the STM32 MEMS firmware):
 *   timestamp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,
 *   mag_x,mag_y,mag_z,press,roll,pitch,yaw
 *
 * Redis stream: /data/mems
 *
 * Build on the QNX target (native):
 *   qcc -o mems_stream main.c -lsocket
 *
 * Cross-compile from QNX SDP host (64-bit ARM):
 *   qcc -V gcc_ntoaarch64le -o mems_stream main.c -lsocket
 *
 * Usage:
 *   ./mems_stream [serial_device]
 *
 * Defaults:
 *   serial_device = /dev/serusb1
 *
 * Connection details are configured via compile-time macros below, or
 * overridden at runtime with REDIS_HOST / REDIS_PORT / REDIS_PASS env vars.
 */

/*
 * QNX header compatibility shim.
 * When compiling with plain `cc` (Clang) instead of `qcc`, QNX's
 * sys/compiler_gnu.h references _GCC_ATTR_ALIGN_64t which is only
 * defined by qcc's internal GCC-version machinery.  Defining it here
 * before any system header is pulled in satisfies the typedef.
 */
#ifndef _GCC_ATTR_ALIGN_64t
#define _GCC_ATTR_ALIGN_64t long long
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <time.h>
#include <sys/socket.h>
#include <netdb.h>
#include <signal.h>

/* --- Default Redis endpoint --- */
#define DEFAULT_REDIS_HOST "hospitable-van-guitar-57111.db.redis.io"
#define DEFAULT_REDIS_PORT "17434"
#define DEFAULT_REDIS_PASS 
#define REDIS_USER         "default"
#define REDIS_STREAM       "/data/mems"

/* --- Serial defaults --- */
#define DEFAULT_SERIAL_DEV "/dev/serusb1"
#define DEFAULT_BAUD        B115200

/* --- Tuning --- */
#define BATCH_SIZE          10      /* flush every N samples (~100 ms @100 Hz) */
#define RECV_BUF_SIZE       256     /* small; we only check reply type byte */
#define LINE_BUF_SIZE       512
#define SEND_BUF_SIZE       4096    /* per XADD command */

/* ── Globals ─────────────────────────────────────────────────────────────── */
static volatile int g_running = 1;

static void handle_sigint(int sig) {
    (void)sig;
    g_running = 0;
}

/* ================================================================
 * RESP helpers
 * ================================================================ */

/* Append a RESP bulk string to buf, returning the new write position. */
static char *resp_bulk(char *buf, const char *s) {
    int len = (int)strlen(s);
    buf += sprintf(buf, "$%d\r\n%s\r\n", len, s);
    return buf;
}

/*
 * Build a complete RESP array for:
 *   XADD /data/mems * ts <ts> acc_x <v> ... yaw <v>
 *
 * Fields: 14 key-value pairs → total array elements = 3 + 14*2 = 31
 */
static int build_xadd(char *out, size_t cap,
                       const char *ts,
                       const char *acc_x, const char *acc_y, const char *acc_z,
                       const char *gyr_x, const char *gyr_y, const char *gyr_z,
                       const char *mag_x, const char *mag_y, const char *mag_z,
                       const char *press,
                       const char *roll,  const char *pitch, const char *yaw)
{
    char *p = out;
    /* 3 fixed + 28 field/value tokens = 31 */
    p += snprintf(p, cap - (size_t)(p - out), "*31\r\n");
    p = resp_bulk(p, "XADD");
    p = resp_bulk(p, REDIS_STREAM);
    p = resp_bulk(p, "*");   /* auto-generate stream ID */

    /* field/value pairs */
    p = resp_bulk(p, "ts");    p = resp_bulk(p, ts);
    p = resp_bulk(p, "acc_x"); p = resp_bulk(p, acc_x);
    p = resp_bulk(p, "acc_y"); p = resp_bulk(p, acc_y);
    p = resp_bulk(p, "acc_z"); p = resp_bulk(p, acc_z);
    p = resp_bulk(p, "gyr_x"); p = resp_bulk(p, gyr_x);
    p = resp_bulk(p, "gyr_y"); p = resp_bulk(p, gyr_y);
    p = resp_bulk(p, "gyr_z"); p = resp_bulk(p, gyr_z);
    p = resp_bulk(p, "mag_x"); p = resp_bulk(p, mag_x);
    p = resp_bulk(p, "mag_y"); p = resp_bulk(p, mag_y);
    p = resp_bulk(p, "mag_z"); p = resp_bulk(p, mag_z);
    p = resp_bulk(p, "press"); p = resp_bulk(p, press);
    p = resp_bulk(p, "roll");  p = resp_bulk(p, roll);
    p = resp_bulk(p, "pitch"); p = resp_bulk(p, pitch);
    p = resp_bulk(p, "yaw");   p = resp_bulk(p, yaw);

    return (int)(p - out);
}

/* Build AUTH command */
static int build_auth(char *out, size_t cap, const char *user, const char *pass)
{
    char *p = out;
    p += snprintf(p, cap, "*3\r\n");
    p = resp_bulk(p, "AUTH");
    p = resp_bulk(p, user);
    p = resp_bulk(p, pass);
    return (int)(p - out);
}

/* ================================================================
 * TCP helpers
 * ================================================================ */

static int tcp_connect(const char *host, const char *port) {
    struct addrinfo hints, *res, *rp;
    int fd = -1;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family   = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, port, &hints, &res) != 0) {
        fprintf(stderr, "[redis] getaddrinfo(%s:%s) failed: %s\n",
                host, port, strerror(errno));
        return -1;
    }

    for (rp = res; rp != NULL; rp = rp->ai_next) {
        fd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (fd < 0) continue;
        if (connect(fd, rp->ai_addr, rp->ai_addrlen) == 0) break;
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    return fd;
}

/* Send all bytes; returns 0 on success, -1 on error. */
static int tcp_send_all(int fd, const char *buf, int len) {
    int sent = 0;
    while (sent < len) {
        int n = (int)send(fd, buf + sent, (size_t)(len - sent), 0);
        if (n <= 0) return -1;
        sent += n;
    }
    return 0;
}

/*
 * Read until we see at least `count` RESP responses (each starts with
 * '+', '-', ':', '$', or '*').  We only care about errors here.
 */
static int tcp_drain_replies(int fd, int count) {
    char buf[RECV_BUF_SIZE];
    int seen = 0;
    while (seen < count) {
        int n = (int)recv(fd, buf, sizeof(buf) - 1, 0);
        if (n <= 0) return -1;
        buf[n] = '\0';
        /* Count RESP response lines (starting character of each reply) */
        for (int i = 0; i < n; i++) {
            if (buf[i] == '+' || buf[i] == '-' ||
                buf[i] == ':' || buf[i] == '$' || buf[i] == '*') {
                /* Check for error */
                if (buf[i] == '-') {
                    fprintf(stderr, "[redis] Server error: %s\n", buf + i);
                }
                seen++;
            }
        }
    }
    return 0;
}

/* ================================================================
 * Serial port helpers
 * ================================================================ */

static int serial_open(const char *dev, speed_t baud) {
    int fd = open(dev, O_RDONLY | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        fprintf(stderr, "[serial] open(%s): %s\n", dev, strerror(errno));
        return -1;
    }

    /* Clear O_NONBLOCK so reads block */
    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);

    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd, &tty) != 0) {
        fprintf(stderr, "[serial] tcgetattr: %s\n", strerror(errno));
        close(fd);
        return -1;
    }

    cfsetispeed(&tty, baud);
    cfsetospeed(&tty, baud);

    tty.c_cflag  = (tty.c_cflag & ~CSIZE) | CS8; /* 8-bit chars */
    tty.c_cflag |= CLOCAL | CREAD;               /* enable receiver, local */
    tty.c_cflag &= ~(PARENB | CSTOPB);           /* no parity, 1 stop bit */
#ifdef CRTSCTS
    tty.c_cflag &= ~CRTSCTS;                      /* no HW flow control (if supported) */
#endif

    tty.c_iflag  = IGNBRK | IGNPAR;              /* ignore break & parity errors */
    tty.c_iflag &= ~(IXON | IXOFF | IXANY);     /* no SW flow control */

    tty.c_oflag  = 0;                            /* raw output */
    tty.c_lflag  = 0;                            /* raw input */

    tty.c_cc[VMIN]  = 1;   /* block until at least 1 byte */
    tty.c_cc[VTIME] = 10;  /* 1-second read timeout */

    tcflush(fd, TCIFLUSH);
    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        fprintf(stderr, "[serial] tcsetattr: %s\n", strerror(errno));
        close(fd);
        return -1;
    }

    return fd;
}

/* Read one newline-terminated line; strips \r\n.  Returns 0 on success. */
static int serial_readline(int fd, char *buf, int maxlen) {
    int pos = 0;
    while (pos < maxlen - 1) {
        char c;
        int n = (int)read(fd, &c, 1);
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) continue;
            return -1;
        }
        if (n == 0) return -1; /* timeout / EOF */
        if (c == '\n') break;
        if (c != '\r') buf[pos++] = c;
    }
    buf[pos] = '\0';
    return 0;
}

/* ================================================================
 * CSV parser
 * ================================================================ */

#define NUM_FIELDS 14

/*
 * Split a CSV line into exactly NUM_FIELDS fields.
 * Pointers in `fields[]` point into `line` (modified in-place).
 * Returns 0 on success, -1 if the line has too few fields or is a header.
 */
static int csv_split(char *line, char *fields[NUM_FIELDS]) {
    if (strlen(line) == 0) return -1;
    /* Skip header lines */
    if (strncmp(line, "timestamp", 9) == 0 ||
        strncmp(line, "ts",        2) == 0) return -1;

    int i = 0;
    char *p = line;
    while (i < NUM_FIELDS) {
        fields[i++] = p;
        p = strchr(p, ',');
        if (!p) break;
        *p++ = '\0';
    }
    return (i == NUM_FIELDS) ? 0 : -1;
}

/* ================================================================
 * Main
 * ================================================================ */

int main(int argc, char *argv[]) {
    signal(SIGINT,  handle_sigint);
    signal(SIGTERM, handle_sigint);

    /* ── Config from argv / env ── */
    const char *serial_dev  = (argc > 1) ? argv[1] : DEFAULT_SERIAL_DEV;
    /* baud rate arg currently maps only to the constant; extend as needed */

    const char *redis_host  = getenv("REDIS_HOST") ? getenv("REDIS_HOST") : DEFAULT_REDIS_HOST;
    const char *redis_port  = getenv("REDIS_PORT") ? getenv("REDIS_PORT") : DEFAULT_REDIS_PORT;
    const char *redis_pass  = getenv("REDIS_PASS") ? getenv("REDIS_PASS") : DEFAULT_REDIS_PASS;

    printf("==================================================\n");
    printf(" STM32 MEMS → Redis Streamer  (QNX / C)\n");
    printf("==================================================\n");
    printf("Serial device : %s  @ 115200 baud\n", serial_dev);
    printf("Redis endpoint: %s:%s\n", redis_host, redis_port);
    printf("Redis stream  : %s\n", REDIS_STREAM);
    printf("Batch size    : %d samples\n", BATCH_SIZE);
    printf("--------------------------------------------------\n");

    /* ── Open serial port ── */
    printf("Opening serial port...\n");
    int sfd = serial_open(serial_dev, DEFAULT_BAUD);
    if (sfd < 0) {
        fprintf(stderr, "Failed to open serial port. Aborting.\n");
        return 1;
    }
    printf("Serial port opened.\n");

    /* ── Connect to Redis ── */
    printf("Connecting to Redis...\n");
    int rfd = tcp_connect(redis_host, redis_port);
    if (rfd < 0) {
        fprintf(stderr, "Failed to connect to Redis. Aborting.\n");
        close(sfd);
        return 1;
    }
    printf("TCP connection established.\n");

    /* Authenticate */
    char auth_buf[512];
    int  auth_len = build_auth(auth_buf, sizeof(auth_buf), REDIS_USER, redis_pass);
    if (tcp_send_all(rfd, auth_buf, auth_len) < 0) {
        fprintf(stderr, "Failed to send AUTH command.\n");
        close(rfd); close(sfd);
        return 1;
    }
    if (tcp_drain_replies(rfd, 1) < 0) {
        fprintf(stderr, "AUTH reply not received.\n");
        close(rfd); close(sfd);
        return 1;
    }
    printf("Authenticated to Redis.\n");
    printf("Streaming started. Press Ctrl+C to stop.\n\n");

    /* ── Main loop ── */
    char line[LINE_BUF_SIZE];
    char send_buf[SEND_BUF_SIZE];
    long long total_sent = 0;
    int  batch_count     = 0;
    int  pending_replies = 0;

    while (g_running) {
        if (serial_readline(sfd, line, sizeof(line)) < 0) {
            if (!g_running) break;
            fprintf(stderr, "[serial] read error: %s\n", strerror(errno));
            usleep(100000); /* back-off 100 ms */
            continue;
        }

        char *fields[NUM_FIELDS];
        if (csv_split(line, fields) < 0) continue; /* skip bad / header lines */

        /* Build and send XADD — pipeline: send without waiting for reply */
        int len = build_xadd(send_buf, sizeof(send_buf),
                              fields[0],  /* ts    */
                              fields[1],  /* acc_x */
                              fields[2],  /* acc_y */
                              fields[3],  /* acc_z */
                              fields[4],  /* gyr_x */
                              fields[5],  /* gyr_y */
                              fields[6],  /* gyr_z */
                              fields[7],  /* mag_x */
                              fields[8],  /* mag_y */
                              fields[9],  /* mag_z */
                              fields[10], /* press */
                              fields[11], /* roll  */
                              fields[12], /* pitch */
                              fields[13]  /* yaw   */);

        if (tcp_send_all(rfd, send_buf, len) < 0) {
            fprintf(stderr, "[redis] send failed: %s — attempting reconnect...\n",
                    strerror(errno));
            close(rfd);
            rfd = tcp_connect(redis_host, redis_port);
            if (rfd < 0) { g_running = 0; break; }
            /* Re-authenticate after reconnect */
            auth_len = build_auth(auth_buf, sizeof(auth_buf), REDIS_USER, redis_pass);
            tcp_send_all(rfd, auth_buf, auth_len);
            tcp_drain_replies(rfd, 1);
            pending_replies = 0;
            continue;
        }

        pending_replies++;
        batch_count++;
        total_sent++;

        /* Drain replies in batches to avoid socket buffer buildup */
        if (batch_count >= BATCH_SIZE) {
            if (tcp_drain_replies(rfd, pending_replies) < 0) {
                fprintf(stderr, "[redis] drain error\n");
            }
            printf("[%lld] Pushed %d samples to %s\n",
                   total_sent, batch_count, REDIS_STREAM);
            batch_count     = 0;
            pending_replies = 0;
        }
    }

    /* Drain any remaining pipelined replies */
    if (pending_replies > 0) {
        tcp_drain_replies(rfd, pending_replies);
    }

    printf("\nStopping. Total samples pushed: %lld\n", total_sent);
    close(rfd);
    close(sfd);
    return 0;
}
