import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function formatDuration(ms: number | null): string {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`
}

export function highlightIR(text: string): string {
  if (!text) return ''
  const esc = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  return esc
    .replace(
      /\b(define|declare|ret|br|call|load|store|alloca|phi|icmp|add|sub|mul|div|shl|lshr|ashr|and|or|xor|getelementptr|trunc|zext|sext|bitcast|select|switch|unreachable|global|constant|private|internal|dso_local|align|attributes)\b/g,
      '<span class="ir-keyword">$1</span>',
    )
    .replace(/\b(i1|i8|i16|i32|i64|i128|float|double|void|ptr)\b/g, '<span class="ir-type">$1</span>')
    .replace(/\b(nsw|nuw|nnan|ninf|exact)\b/g, '<span class="ir-nsw">$1</span>')
    .replace(/\b(undef|poison)\b/g, '<span class="ir-undef">$1</span>')
    .replace(/^([\w.]+:)/gm, '<span class="ir-label">$1</span>')
    .replace(/(;[^\n]*)/g, '<span class="ir-comment">$1</span>')
}

export function highlightDiff(text: string): string {
  if (!text) return ''
  return text
    .split('\n')
    .map(line => {
      const esc = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      if (line.startsWith('+++') || line.startsWith('---')) return `<span class="diff-hdr block">${esc}</span>`
      if (line.startsWith('@@')) return `<span class="diff-hdr block opacity-70">${esc}</span>`
      if (line.startsWith('+')) return `<span class="diff-add block">${esc}</span>`
      if (line.startsWith('-')) return `<span class="diff-rem block">${esc}</span>`
      return `<span class="diff-ctx block">${esc}</span>`
    })
    .join('\n')
}

export const EXAMPLE_SOURCES: Array<{ name: string; lang: string; code: string }> = [
  {
    name: 'Signed Overflow (x+1>x)',
    lang: 'c',
    code: `#include <stdio.h>
#include <limits.h>

// Classic UB time bomb: always true at -O2
int overflow_check(int x) {
    return x + 1 > x;
}

// Broken allocation guard
void *safe_alloc(int count, int size) {
    int total = count * size;        // UB if overflows
    if (total < count || total < 0) // guard removed at -O2
        return NULL;
    return malloc(total);
}

int main(void) {
    printf("check(INT_MAX): %d\\n", overflow_check(INT_MAX));
    printf("check(5):       %d\\n", overflow_check(5));
    return 0;
}`,
  },
  {
    name: 'Null Check After Dereference',
    lang: 'c',
    code: `#include <stdio.h>

typedef struct { int value; int flags; } Node;

// Guard eliminated: dereference happens before null check
int get_value(Node *node) {
    int v = node->value;   // dereference
    if (node == NULL) {    // optimizer removes this!
        return -1;
    }
    return v;
}

int main(void) {
    Node n = {42, 0};
    printf("value: %d\\n", get_value(&n));
    return 0;
}`,
  },
  {
    name: 'Strict Aliasing Type Pun',
    lang: 'c',
    code: `#include <stdio.h>
#include <stdint.h>

// Violates strict aliasing (C99 §6.5)
float bits_to_float(uint32_t x) {
    return *(float *)&x;   // UB: float* and uint32_t* incompatible
}

// Safe version using memcpy
#include <string.h>
float bits_to_float_safe(uint32_t x) {
    float f;
    memcpy(&f, &x, 4);
    return f;
}

int main(void) {
    printf("unsafe: %f\\n", bits_to_float(0x3f800000));
    printf("safe:   %f\\n", bits_to_float_safe(0x3f800000));
    return 0;
}`,
  },
  {
    name: 'Uninitialized Variable',
    lang: 'c',
    code: `#include <stdio.h>

// Result uninitialized if condition is false
int check_positive(int x) {
    int result;          // uninitialized!
    if (x > 0) {
        result = 1;
    }
    return result;       // UB if x <= 0
}

// Authentication bypass via uninit
int verify(int input, int secret) {
    int ok;
    if (input == secret) {
        ok = 1;          // only set on match
    }
    return ok;           // undef otherwise -> optimizer may assume 1
}

int main(void) {
    printf("check(5):  %d\\n", check_positive(5));
    printf("check(-1): %d\\n", check_positive(-1));
    return 0;
}`,
  },
]
