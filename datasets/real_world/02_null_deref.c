/**
 * Real-World UB Case #2: Null Check After Dereference
 * Reference: Linux kernel CVE-2011-1078, CERT C EXP34-C,
 *            GCC bug reports, multiple Android kernel CVEs
 *
 * Pattern: Pointer dereferenced BEFORE null check.
 * GVN/MemorySSA records the dereference → marks pointer non-null →
 * SimplifyCFG removes the subsequent null guard.
 *
 * Impact: Null pointer crashes / arbitrary code execution in kernel context.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    int id;
    int value;
    char name[64];
    struct Node *next;
} Node;

/* ── Classic: deref before null check ────────────────────────────────────── */
int get_node_value(Node *node) {
    int val = node->value;    /* DEREFERENCE HAPPENS HERE — UB if node==NULL */
    if (node == NULL) {       /* GUARD: optimizer removes this at -O2         */
        return -1;
    }
    return val;
}

/* ── Variant: null check in called function, deref in caller ─────────────── */
static int read_id(Node *n) {
    return n->id;             /* implicit non-null assumption through inlining */
}

int process_node(Node *n) {
    int id = read_id(n);      /* inlined dereference propagates non-null info */
    if (!n) {                 /* dead at -O2: GVN sees prior deref             */
        fprintf(stderr, "null node\n");
        return -1;
    }
    return id * 2;
}

/* ── Refactoring anti-pattern: guard added after the fact ────────────────── */
void update_node(Node *node, int new_val) {
    /* Developer originally had no null check.
     * Security review said "add null check" — but added it AFTER the deref. */
    node->value = new_val;    /* dereference — GVN marks node non-null */
    if (node == NULL) {       /* too late: removed at -O2               */
        return;
    }
    strncpy(node->name, "updated", sizeof(node->name) - 1);
}

/* ── Struct member pointer deref then null check ─────────────────────────── */
typedef struct {
    Node *head;
    int   size;
} List;

int list_front(List *list) {
    int val = list->head->value;     /* two-level deref: list and list->head */
    if (list->head == NULL) {        /* eliminated: head was just deref'd     */
        return 0;
    }
    return val;
}

int main(void) {
    Node n = {.id = 1, .value = 42};
    printf("get_node_value: %d\n", get_node_value(&n));
    printf("process_node:   %d\n", process_node(&n));
    update_node(&n, 100);
    printf("after update: value=%d\n", n.value);

    List list = {.head = &n, .size = 1};
    printf("list_front: %d\n", list_front(&list));
    return 0;
}
