/**
 * Real-World UB Case #5: Shift Overflow & Mixed UB in Parsers
 * Reference: CVE-2016-10190 (FFmpeg URL parser), CVE-2021-3506,
 *            CVE-2022-32250 (nftables), CWE-190/CWE-194
 *
 * Pattern: Left-shifting a signed integer by ≥ bit-width, or shifting
 *          into/past the sign bit. Also: mixing UB in data parsers
 *          (URL, image, network packet decoders).
 *
 * At -O0: x86 hardware masks shift amount to 5 bits — appears to produce 0.
 * At -O2: LLVM marks the result as 'poison', which propagates through
 *         dependent operations, allowing branch elimination.
 *
 * Impact: Buffer overflows in media libraries, privilege escalation.
 */
#include <stdio.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>

/* ── FFmpeg-style chunk-size parser (CVE-2016-10190 pattern) ─────────────── */
int parse_chunk_length(unsigned char hi, unsigned char lo) {
    /* UB: 1 << 31 shifts into the sign bit of a 32-bit signed int.
     * At -O0: produces expected value on x86 (hardware silently wraps).
     * At -O2: LLVM marks as poison; guard below may be eliminated. */
    int len = (hi << 8) | lo;
    if (len < 0 || len > 0xFFFF) {   /* guard against overflow — removed at O2 */
        return -1;
    }
    return len;
}

/* ── Image decoder width * height with overflow check ────────────────────── */
int check_image_dimensions(int w, int h) {
    /* Signed multiplication overflow is UB.
     * At -O2: InstCombine adds nsw; overflow check eliminated. */
    int pixels = w * h;
    if (pixels / w != h || pixels < 0) {   /* overflow check: REMOVED at O2 */
        return -1;
    }
    return pixels;
}

/* ── Bit-field extraction with large shift ───────────────────────────────── */
int extract_signed_field(int word, int shift_amount) {
    /* UB if shift_amount >= 32 or shift_amount < 0.
     * At -O0: x86 masks to 5 bits (acts as shift % 32).
     * At -O2: undefined → optimizer assumes shift is valid → may eliminate
     *         the guard checking shift_amount range. */
    if (shift_amount >= 32) {        /* guard that looks safe but isn't */
        return 0;
    }
    return (word << shift_amount) >> shift_amount;
}

/* ── nftables-style bitmask with shift UB (CVE-2022-32250 pattern) ────────── */
uint64_t build_mask(int bit_pos) {
    /* 1ULL << bit_pos is UB when bit_pos >= 64.
     * The guard 'bit_pos < 64' should protect it, but if bit_pos arrived
     * through a signed path with earlier UB, the guard may be eliminated. */
    int safe_pos = bit_pos & 63;   /* looks safe... */
    /* But if bit_pos was derived from signed overflow above, safe_pos
     * inherits poison and the mask becomes non-deterministic at O2. */
    return (uint64_t)1 << safe_pos;
}

/* ── Safe addition with broken overflow check ────────────────────────────── */
int add_with_overflow_check(int a, int b) {
    int result = a + b;           /* UB if overflow */
    if (result < a && b > 0) {   /* check: eliminated at O2 (nsw) */
        return INT_MAX;           /* never reached at O2 */
    }
    if (result > a && b < 0) {
        return INT_MIN;
    }
    return result;
}

/* ── URL length accumulator with signed overflow ─────────────────────────── */
int compute_url_length(const char *scheme, const char *host, int port) {
    int len = strlen(scheme);         /* could be large */
    len += strlen(host);              /* UB if len overflows */
    len += 10;                        /* for "://", ":", port digits, null */
    if (port > 0 && port < 65536) {
        len += (port > 9999) ? 5 : 4; /* port digits */
    }
    if (len < 0) {                    /* overflow guard: REMOVED at O2 */
        return -1;
    }
    return len;
}

int main(void) {
    printf("chunk(0x00, 0xFF):    %d\n", parse_chunk_length(0x00, 0xFF));
    printf("chunk(0xFF, 0xFF):    %d\n", parse_chunk_length(0xFF, 0xFF));
    printf("dimensions(100,100): %d\n", check_image_dimensions(100, 100));
    printf("dimensions(46341,46342): %d\n", check_image_dimensions(46341, 46342));
    printf("extract(0xFF, 4):    %d\n", extract_signed_field(0xFF, 4));
    printf("mask(63):            0x%llX\n", (unsigned long long)build_mask(63));
    printf("safe_add(INT_MAX,1): %d\n", add_with_overflow_check(INT_MAX, 1));
    return 0;
}
