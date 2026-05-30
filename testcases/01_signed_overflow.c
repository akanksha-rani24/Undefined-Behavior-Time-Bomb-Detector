/**
 * Real-World UB Case #1: Signed Integer Overflow
 * Reference: CWE-190, GCC Bug PR#30475, CVE-2009-1897 (Linux kernel)
 *
 * Pattern: Overflow checks written using signed arithmetic are themselves UB.
 * The optimizer (InstCombine + SimplifyCFG) assumes nsw and folds the check.
 *
 * Impact: Security checks silently removed in optimized builds.
 */
#include <stdio.h>
#include <limits.h>
#include <string.h>

/* ── Canonical x+1>x time bomb ───────────────────────────────────────────── */
int overflow_check_broken(int x) {
    /* Tries to detect overflow — but this comparison IS undefined behavior.
     * At -O0: may return 0 (false) when x == INT_MAX (hardware wraps).
     * At -O2: InstCombine adds nsw, folds to 'ret i1 true' always. */
    return x + 1 > x;
}

/* ── Security allocation guard (broken) ──────────────────────────────────── */
void *safe_alloc_broken(int count, int size) {
    /* Intended to detect integer overflow before malloc.
     * At -O2: 'count * size' gets nsw; the overflow check is folded away.
     * Attacker can pass count=65536, size=65537 → allocation too small. */
    int total = count * size;
    if (total < count || total < size) {   /* overflow guard — REMOVED at O2 */
        return NULL;
    }
    return malloc((size_t)total);
}

/* ── Saturating arithmetic (broken) ─────────────────────────────────────── */
int saturate_add(int a, int b) {
    int result = a + b;          /* UB if overflows */
    if (result < a) {            /* guard removed at O2 via nsw */
        return INT_MAX;
    }
    return result;
}

/* ── Loop that optimizer may make infinite ───────────────────────────────── */
void count_down(int n) {
    int total = 0;
    /* If n == INT_MAX, i++ at max value is UB.
     * Optimizer may assume the loop always terminates normally
     * and unroll/vectorize assuming no wrap. */
    for (int i = 0; i <= n; i++) {
        total++;
    }
    printf("total = %d\n", total);
}

int main(void) {
    printf("overflow_check(INT_MAX): %d\n", overflow_check_broken(INT_MAX));
    printf("overflow_check(5):       %d\n", overflow_check_broken(5));
    printf("saturate(INT_MAX, 1):    %d\n", saturate_add(INT_MAX, 1));
    count_down(3);
    return 0;
}
