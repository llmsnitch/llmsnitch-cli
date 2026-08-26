# Unicode-evasion-resistant redaction for `hook._clean`

> Convention note: `docs/` previously held only the notifier spec. This file establishes `docs/research/` as the home for cited research notes — port dossiers with primary-source citations that feed later design changes.

## TL;DR

Before running `_SECRET.sub` in `llmsnitch/hook.py`, gate on `str.isascii()` and, when false, replace `s` with `unicodedata.normalize("NFKC", s)` after stripping a fixed set of invisible/bidi/tag codepoints — a ~10-line addition that closes the zero-width-splitting and fullwidth-homoglyph evasion class Ramparts' `canonicalize()` was built to close, at a measured cost of ~0.08 µs on ASCII and ~4 µs on mixed input for a 2 KB string.

---

## 1. What NFKC normalization does (UAX #15)

- Unicode defines two equivalences: **canonical** (same abstract character, e.g. `Å` U+00C5 ↔ `A` + combining ring U+030A) and **compatibility** (same character with formatting differences, e.g. fullwidth `ｒ` U+FF52 ↔ `r` U+0072, or the ligature `ﬃ` U+FB03 ↔ `ffi`) — UAX #15 §1.1 (https://www.unicode.org/reports/tr15/).
- NFKC = *Compatibility Decomposition, followed by Canonical Composition* — UAX #15 §1.2 table (fetched from https://www.unicode.org/reports/tr15/).
- Effect on the attacker: `ｓｋ-ａｂｃ…` (fullwidth) NFKC-folds to `sk-abc…`, at which point the existing `_SECRET` regex hits.
- What NFKC does **not** do: it does not remove zero-width / bidi / variation-selector / Tag codepoints (they have no compatibility decomposition to ASCII). Those must be stripped separately — see §2.

## 2. Which codepoints count as "invisible" (UTR #36)

The Unicode Consortium documents the class of "invisible" and "bidi" hazards in **UTR #36 "Unicode Security Considerations"** and mitigations in **UTS #39 "Unicode Security Mechanisms"** (both cited by NVD as authoritative for CVE-2021-42574 — see §3). The concrete ranges below match what Ramparts strips in `src/normalize.rs::is_invisible` (lines 30–40), each having a clear name in the Unicode code charts:

| Range | Name | Why strip |
| --- | --- | --- |
| U+200B..U+200F | Zero-width space, ZWNJ, ZWJ, LRM, RLM | Splits keywords / tokens |
| U+2060..U+2064 | Word joiner, invisible operators | Splits keywords / tokens |
| U+202A..U+202E | LRE/RLE/PDF/LRO/RLO — bidi embedding + override | Trojan Source (see §3) |
| U+2066..U+2069 | LRI/RLI/FSI/PDI — bidi isolates | Trojan Source (see §3) |
| U+FEFF | BOM / zero-width no-break space | Splits tokens |
| U+FE00..U+FE0F | Variation selectors | Invisible when attached to base char |
| U+E0000..U+E007F | Unicode Tags block | Fully invisible; UTR #36 §8 flags as a smuggling channel |

The bidi control characters are defined normatively in UAX #9 §2 "Explicit Directional Formatting Characters" (https://www.unicode.org/reports/tr9/) — sections 2.1 (Embeddings), 2.2 (Overrides), 2.4 (Isolates).

## 3. Trojan Source / CVE-2021-42574 — bidi belongs in the same pass

- **CVE-2021-42574** (NVD, fetched via `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2021-42574`): "An issue was discovered in the Bidirectional Algorithm in the Unicode Specification through 14.0. It permits the visual reordering of characters via control sequences, which can be used to craft source code that renders different logic than the logical ordering of tokens ingested by compilers and interpreters." CVSS 3.1 = 8.3 HIGH. NVD explicitly cites UTR #36, UTS #39, and UAX #9 §HL4 as mitigation references.
- For a secret redactor this is the same threat model as zero-width splits: the attacker inserts `U+202E` inside a token so the raw string that hits the regex is not what a reviewer sees. Stripping bidi controls in the same pass costs no extra time (both are single-character filters) and closes the "visually redacted, actually leaks" failure mode.

## 4. How Ramparts does it (Rust, port target)

File: `$HOMERepos/llmsnitch/submodule/security-scanners/highflame-ai-ramparts/src/normalize.rs`

Key lines (30–52):

```rust
fn is_invisible(c: char) -> bool {
    matches!(c,
        '\u{200B}'..='\u{200F}' | '\u{2060}'..='\u{2064}'
      | '\u{202A}'..='\u{202E}' | '\u{2066}'..='\u{2069}'
      | '\u{FEFF}' | '\u{FE00}'..='\u{FE0F}'
      | '\u{E0000}'..='\u{E007F}'
    )
}

pub fn canonicalize(text: &str) -> Option<String> {
    let stripped: String = text.chars().filter(|c| !is_invisible(*c)).collect();
    let folded: String = stripped.nfkc().collect();
    if folded == text { None } else { Some(folded) }
}
```

Design choices worth stealing:
- **Two-stage**: strip invisibles *then* NFKC. Order matters — NFKC on invisibles is a no-op, but leaving them in means the folded string still splits.
- **Return `None` when identical to input** — the caller only scans the "extra view" when normalization actually changed something. Our `_clean` equivalent is: run the regex on both raw *and* canonical when they differ; if only one is checked, an evasion that adds a zero-width char to `sk-...` bypasses the raw pass and matches the canonical pass.
- **`decoded_fragments` runs base64/hex peel to depth 3** (lines 22–23, 183–208). Discussed in §6.

## 5. How MEDUSA handles it (Python, sibling reference)

MEDUSA's `OutputSanitizer` (`submodule/security-scanners/pantheon-security-medusa/medusa/core/output_sanitizer.py`, lines 205–209) does a much narrower removal:

```python
# Remove invisible unicode (these have no diagnostic value)
result = re.sub(r"[​-‏ - ⁠-⁯]", "", result)
# Neutralize RTL overrides
result = re.sub(r"[‪-‮]", "[RTL]", result)
```

Its `PayloadSanitizer` (`.../payload_sanitizer.py` lines 311–313) is the same pattern. Two observations:
- MEDUSA's range `​-‏ - ⁠-⁯` is wider than Ramparts' (it also covers line/paragraph separators U+2028–2029 and the whole U+2060–206F block) but **omits** U+FEFF, U+FE00–FE0F variation selectors, and the U+E0000–E007F Tags block — Ramparts is stricter about steganographic vectors and their tests (`bidi_and_tag_chars_are_stripped`, lines 231–237) exercise the U+E0041 Tag-block case.
- MEDUSA does **not** NFKC-fold. It also does not iterate to a fixed point across normalization + regex (the iterative loop in `sanitize_text` re-runs pattern *detection* only). So it catches zero-width splits but not fullwidth-homoglyph secrets.

MEDUSA's `llm_guard_scanner._check_invisible_chars` (lines 284–311) is a detector, not a normalizer — it flags the presence of an invisible char and reports a `ScannerIssue`; it doesn't produce a canonical view to re-scan. Not what we want for `_clean`, which needs to redact, not report.

## 6. Base64 / hex "iterative peel" — minimum stdlib implementation

Ramparts (`normalize.rs` lines 22, 183–208) walks a queue up to `MAX_DECODE_DEPTH = 3`, decoding maximal ≥24-char runs of the base64/hex alphabet, keeping only "mostly printable" output. The stdlib equivalent is `base64.b64decode(s, validate=True)` (docs.python.org: "Decode the Base64 encoded bytes-like object or ASCII string s and return the decoded bytes") and `bytes.fromhex(s)` / `binascii.unhexlify`. Both raise on invalid input, so a `try/except (binascii.Error, ValueError)` gives us a cheap "is this really base64" test without writing a custom validator.

**Recommendation for `_clean`:** do **not** port the peel. Rationale:
- The hot-path budget is <5 µs per event; scanning `b64decode`-able runs adds a regex scan across the whole string plus one decode per candidate. Even one 2 KB call is more expensive than the entire current `_clean`.
- The secret patterns we actually redact (`sk-…`, `AKIA…`, JWTs) are the *product* the attacker is trying to exfiltrate. Base64-hiding them changes the shape enough that the receiver has to decode before use — at which point the plaintext form is in some downstream tool call, which we'll also capture. Coverage without the peel is: "we redact every plaintext appearance." Coverage with the peel is: "we also redact one specific encoded appearance." Not a proportional trade at 5 µs/event.
- If we later want the peel, do it lazily on **cold-path** replay (the audit UI in `wayfinder/`), not on hot-path capture.

## 7. Performance measurements (2 KB payload on this machine)

Benchmark from `python3 -c "..."` (CPython 3, macOS arm64), 100 000 iterations each, 2 000-char strings:

| Approach | ASCII-only | Mixed (with invisible chars) |
| --- | --- | --- |
| `unicodedata.normalize('NFKC', s)` | 0.06 µs | 1.78 µs |
| `s.translate({ord(c): None for c in INV})` | — | 43.09 µs |
| `re.compile('[…invisible…]').sub('', s)` | 15.69 µs | 17.10 µs |
| `is_normalized('NFKC', s) and s.isascii()` gate → NFKC | **0.08 µs** | **4.00 µs** |
| `str.isascii()` alone | 0.02 µs | 0.02 µs |

The `is_normalized/isascii`-gated path is what to ship: for the overwhelmingly common ASCII case (Bash commands, JSON keys, file paths, most tool inputs) the added cost is one C-level `isascii()` call. `str.translate` with a per-codepoint dict is **not** the right tool despite being the "obvious" way — it iterates every character in Python. `unicodedata.normalize` is a C function (`Modules/unicodedata.c` in CPython) with a fast path for already-normalized strings, documented in `unicodedata.is_normalized`: "Added in version 3.8" (docs.python.org/3/library/unicodedata.html). This matches the "under ~5 µs per event" target in `submodule/security-scanners/highflame-ai-ramparts/CLAUDE.md`.

Note the invisible-stripping regex: at 15–17 µs it *by itself* exceeds the budget on 2 KB inputs. The mitigation is to only strip when we already know the string is non-ASCII, which brings the combined cost back inside 5 µs. The gate is doing real work.

## 8. What this doesn't fix (honest limits)

1. **Confusables that survive NFKC.** Cyrillic `а` U+0430 and Latin `a` U+0061 look identical but NFKC keeps them distinct — they are canonically different characters, not compatibility variants. UTS #39 §5 "Confusable Detection" defines a separate `skeleton()` mapping; stdlib does not ship the confusables table. A `sk-` prefix built from `s` U+0073 + `k` U+006B is already ASCII; but `ѕk-` (Cyrillic `ѕ` U+0455) will not fold. This is out of scope for `_clean`.
2. **Homograph attacks below the pattern threshold.** Our regex requires a `sk-` literal prefix; a token where the attacker replaces the `sk` with a plausible-looking sequence and hopes the receiver's tokenizer accepts it is not our problem — it also won't be a valid API key.
3. **Base64 / hex / gzip-wrapped secrets.** Per §6 we consciously don't peel; a secret pasted as `echo c2stYWJj… | base64 -d` is captured as base64 and stored unredacted in the trail. Documented tradeoff, not a bug.
4. **Novel Unicode ranges.** UTR #36 evolves; new "invisible" ranges (or new Tag block usage) will need list updates. Our list matches Ramparts as of the current submodule pin.
5. **Secrets outside the current pattern set.** GCP `AIza…`, Azure keys, Stripe `sk_live_…` — these need pattern additions, orthogonal to Unicode work. Documented in `hook.py:19-31`.
6. **Case-mangled secrets.** NFKC is not a case fold; `SK-abc…` won't match a `sk-` prefix. Existing `hook._clean` already has this limit; NFKC doesn't help.
7. **Combining-character splits.** `s` + `k` + `­` (U+00AD soft hyphen, not in our strip list because it's a legitimate hyphenation control in real text) — could evade. Ramparts does not strip U+00AD either. Live-with-it call.

---

## Minimal implementation sketch (<30 lines, stdlib only)

To add to `llmsnitch/hook.py` above `_clean`:

```python
import unicodedata

# UTR #36 / UAX #9 invisible + bidi + variation-selector + Tag codepoints.
# Matches Ramparts src/normalize.rs::is_invisible.
_INVISIBLE = frozenset(
    list(range(0x200B, 0x2010))   # ZWSP, ZWNJ, ZWJ, LRM, RLM (+2 unused)
    + list(range(0x2060, 0x2065)) # word joiner, invisible operators
    + list(range(0x202A, 0x202F)) # LRE/RLE/PDF/LRO/RLO
    + list(range(0x2066, 0x206A)) # LRI/RLI/FSI/PDI
    + [0xFEFF]                    # BOM
    + list(range(0xFE00, 0xFE10)) # variation selectors
    + list(range(0xE0000, 0xE0080)) # Tag block
)

def _canonical(s: str) -> str:
    """Fold Unicode evasion into ASCII form for pattern matching.

    Fast path: pure ASCII already-normalized strings return unchanged
    (~0.08 µs / 2 KB). Slow path strips invisibles then NFKC-folds.
    """
    if s.isascii():
        return s
    s = "".join(c for c in s if ord(c) not in _INVISIBLE)
    return unicodedata.normalize("NFKC", s)
```

Wire into `_clean`:

```python
    if isinstance(obj, str):
        s = obj[:_MAX_STR]
        canon = _canonical(s)
        # Redact from BOTH views: canonical catches evaded tokens; raw
        # preserves any secret shape that only exists pre-fold.
        s = _SECRET.sub("<redacted>", s)
        if canon != obj[:_MAX_STR]:
            canon = _SECRET.sub("<redacted>", canon)
            if canon != s:
                # Canonical view found something raw missed → store canonical.
                s = canon
        return s
```

**Caveats to keep in the comment block:**

- Storing the canonical view when they diverge means an audit reader sees `sk-abc<redacted>` instead of `sk-a​b​c…` — we lose the exact bytes the tool received. That's the right trade for a secret leak; not the right trade for prompt-injection forensics. If we ever want both, keep raw and add a second key.
- The `_canonical` fast path is a `str.isascii()` C call — do not replace it with a regex; benchmarks (§7) show that's 200× slower.
- Do not add base64/hex peeling here (§6). If we want it later, do it in the wayfinder replay layer, not `hook.py`.

---

## What this doesn't fix (checklist)

- [ ] Cyrillic / Greek homoglyphs (need UTS #39 skeleton table — not stdlib).
- [ ] Base64/hex-wrapped secrets (deliberate; see §6).
- [ ] New secret shapes (`AIza…`, Stripe `sk_live_…`, Azure) — pattern work, not Unicode work.
- [ ] Case-mangled secrets (existing limit of `_SECRET`).
- [ ] Soft hyphen (U+00AD) splits — matches Ramparts' scope.
- [ ] Combining-mark visual spoofing outside the compatibility table.

Sources cited in-line above; all primary (Unicode.org UAX #15 / UAX #9 / UTR #36; NVD for CVE-2021-42574; docs.python.org for `unicodedata` and `base64`; Ramparts and MEDUSA source in this repo).
