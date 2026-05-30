/**
 * Real-World UB Case #3: Strict Aliasing Violation
 * Reference: OpenSSL (multiple), glibc, Quake III fast-inverse-sqrt,
 *            GCC bug PR44. C99 §6.5 / C++17 [basic.lval]
 *
 * Pattern: Accessing memory through a pointer of a different type.
 * LLVM TBAA (Type-Based Alias Analysis) considers differently-typed
 * loads/stores as non-aliasing → may reorder, cache, or eliminate them.
 *
 * Impact: Stale values read; cryptographic keys corrupted; protocol parsing
 *         produces wrong results.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* ── Quake III fast inverse square root (famous aliasing bug) ─────────────── */
float fast_inv_sqrt(float number) {
    long i;
    float x2, y;
    x2 = number * 0.5f;
    y  = number;
    /* UB: float* and long* are incompatible types under C99 aliasing rules.
     * At -O0: reads raw IEEE 754 bits correctly.
     * At -O2: TBAA may cache 'y' in float register and not re-read as long. */
    i  = *(long *)&y;
    i  = 0x5f3759df - (i >> 1);
    y  = *(float *)&i;
    y  = y * (1.5f - (x2 * y * y));
    return y;
}

/* ── Network/protocol parser aliasing ─────────────────────────────────────── */
uint32_t parse_u32_be_unsafe(const unsigned char *buf) {
    /* Common pattern in network code — violates strict aliasing.
     * At -O0: reads correct value from buf.
     * At -O2: optimizer may reorder this load relative to adjacent stores
     *         to char* of the same memory. */
    return *(const uint32_t *)buf;
}

uint32_t parse_u32_be_safe(const unsigned char *buf) {
    /* Correct: memcpy is the blessed way to type-pun under strict aliasing. */
    uint32_t v;
    memcpy(&v, buf, sizeof(v));
    return v;
}

/* ── Crypto key schedule aliasing ─────────────────────────────────────────── */
void xor_block_unsafe(uint32_t *block, const unsigned char *key) {
    /* Assumes block (uint32_t*) and key (unsigned char*) don't alias.
     * C allows char* to alias anything, but not the reverse.
     * At -O2: TBAA may reorder the uint32_t stores assuming no char* observer. */
    for (int i = 0; i < 4; i++) {
        uint32_t k;
        k = *(const uint32_t *)(key + i * 4);  /* aliasing violation */
        block[i] ^= k;
    }
}

/* ── Double-precision punning ─────────────────────────────────────────────── */
uint64_t double_to_bits(double d) {
    /* UB type-pun: double* and uint64_t* are incompatible.
     * Safe way: memcpy(&result, &d, 8). */
    return *(uint64_t *)&d;
}

int main(void) {
    printf("fast_inv_sqrt(4.0): %f\n", fast_inv_sqrt(4.0f));

    unsigned char buf[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    printf("unsafe parse: 0x%08X\n", parse_u32_be_unsafe(buf));
    printf("safe parse:   0x%08X\n", parse_u32_be_safe(buf));

    printf("pi bits: 0x%llX\n", (unsigned long long)double_to_bits(3.14159));
    return 0;
}
