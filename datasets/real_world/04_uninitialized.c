/**
 * Real-World UB Case #4: Uninitialized Variable Use
 * Reference: CVE-2014-0977 (OpenSSL), CVE-2019-9213 (Linux kernel),
 *            CWE-457, multiple Android/Chrome security bugs
 *
 * Pattern: Variable used before initialization in some code paths.
 * LLVM represents uninitialized values as 'undef' (IR) or 'poison' (new IR).
 * At -O2, CorrelatedValuePropagation + InstSimplify may fold comparisons on
 * undef values, deleting branches or producing non-deterministic behavior.
 *
 * Impact: Authentication bypasses, info leaks, memory corruption.
 */
#include <stdio.h>
#include <string.h>

/* ── Authentication bypass via uninitialized result ─────────────────────── */
int verify_token(const char *input, const char *expected, int len) {
    int result;               /* UNINITIALIZED — UB if comparison fails */
    if (memcmp(input, expected, len) == 0) {
        result = 1;           /* only set on success */
    }
    /* At -O0: result is 0 from zeroed stack — appears to reject bad input.
     * At -O2: undef propagated through return; optimizer may assume result==1
     *         (only assignment was '= 1'), enabling auth bypass. */
    return result;
}

/* ── Uninitialized error code ─────────────────────────────────────────────── */
int process_request(int type, int *out_value) {
    int status;        /* UNINITIALIZED */
    int value;         /* UNINITIALIZED */

    if (type == 1) {
        value  = 100;
        status = 0;
    } else if (type == 2) {
        value  = 200;
        status = 0;
    }
    /* type == 3: status and value are uninitialized.
     * Optimizer may delete the 'if (status == 0)' branch entirely
     * because 'status' only ever got assigned to 0. */
    if (status == 0) {
        *out_value = value;
        return 0;
    }
    return -1;
}

/* ── Uninitialized accumulator ────────────────────────────────────────────── */
int sum_positives(int *arr, int len) {
    int sum;           /* UNINITIALIZED */
    for (int i = 0; i < len; i++) {
        if (arr[i] > 0) {
            sum += arr[i];   /* UB: sum uninitialized on first positive */
        }
    }
    return sum;
}

/* ── Kernel-style uninitialized errno pattern ─────────────────────────────── */
typedef struct { int data; int flags; } Buffer;

int read_buffer(Buffer *buf, int *out) {
    int err;               /* UNINITIALIZED */
    int tmp;

    if (!buf) {
        err = -1;
        goto out;
    }
    if (buf->flags & 0x1) {
        tmp = buf->data;
        *out = tmp;
        err = 0;
    }
    /* flags & 0x1 == 0: err is uninitialized → UB */
out:
    return err;
}

int main(void) {
    char secret[8] = "secret!";
    printf("verify 'secret!': %d\n", verify_token("secret!", secret, 7));
    printf("verify 'hackit!': %d\n", verify_token("hackit!", secret, 7));

    int out = -99;
    process_request(3, &out);
    printf("type=3 output: %d\n", out);

    int arr[] = {-1, 2, -3, 4, 5};
    printf("sum_positives: %d\n", sum_positives(arr, 5));
    return 0;
}
