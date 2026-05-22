# Mac Metadata Agent Skill — Requirements Document

**Date:** 2026-05-22  
**Status:** Requirements Complete — Ready to Build  
**Based on:** 24 hands-on experiments on macOS (APFS, arm64, Python 3.14) + 3 rounds of Perplexity research  
**Verified:** Finder colour dot confirmed displaying correctly from programmatic writes

---

## 1. Experimental Summary

All findings are from direct experimentation on Bear's system, cross-referenced with Perplexity research and osxmetadata source code analysis. Several claims from initial research were disproven.

### Key Discoveries

| # | Finding | Source |
|---|---------|--------|
| 1 | Finder **does** display colour dots when set programmatically (both xattr stores) | Manual verification |
| 2 | `SetFile` does NOT set labels — only attribute flags | Experiment |
| 3 | `tag` tool does NOT enforce label exclusivity | Experiment |
| 4 | `osxmetadata` CLI works on Python 3.14 via pipx | Install test |
| 5 | `osxmetadata findercolor` reads from xattr directly (not Spotlight) | Source code analysis |
| 6 | Our `0xF1` mask on FinderInfo byte 9 is correct | Verified against `tag` and `osxmetadata` outputs |
| 7 | Perplexity's "bit offset 76" claim maps to the same physical bits as our approach | Bitstring vs x86 notation |
| 8 | `osxmetadata` comment writes use Scripting Bridge → Finder process | Source code |
| 9 | xattr-only comment writes also work with `mdimport` | Experiment |
| 10 | `osxmetadata --mirror` is broken (early-return bug) | Source code analysis |
| 11 | `osxmetadata --copyfrom` does NOT copy custom xattrs | Source code analysis |
| 12 | All tools follow symlinks to the target by default | Experiment |
| 13 | `uv run --with osxmetadata` gives Python API access in ~0.38s | Timing test |
| 14 | Custom xattrs are stripped by iCloud sync (Finder Tags survive) | Perplexity research |
| 15 | `mdfind "tag:Red"` locale warning fixable with `kMDItemUserTags ==` form | Experiment |
| 16 | Folder labels work identically to file labels at the xattr level | Experiment |
| 17 | `mdfind` by `kMDItemFSLabel` may be slower to index folders than files | Experiment |
| 18 | `tag -f` does NOT return identical results to `mdfind` — may not be a pure wrapper | Experiment |
| 19 | xattr writes are atomic for inline tier (≤3,804 bytes) — no locking needed for single agent | Perplexity |
| 20 | Tags persist across file content changes, moves, copies (same volume), and Finder duplication | Perplexity |
| 21 | `kMDItemKeywords` is invisible in Finder; tags are strictly superior for user-facing metadata | Perplexity |
| 22 | `mdfind` queries are O(log n) from the Spotlight index, not O(n) in file count | Perplexity |
| 23 | `FSEvents` with `kFSEventStreamEventFlagItemXattrMod` can detect xattr changes in directory trees | Perplexity |
| 24 | `NSURL.setResourceValues` (used by osxmetadata) ultimately calls atomic `setxattr` syscall | Perplexity + source code |

---

## 2. Tool Inventory (Bear's System)

| Tool | Location | Status | Role |
|------|----------|--------|------|
| `xattr` | `/usr/bin/xattr` | ✅ | Raw xattr read/write/delete |
| `mdls` | `/usr/bin/mdls` | ✅ | Read Spotlight attributes |
| `mdfind` | `/usr/bin/mdfind` | ✅ | Search by Spotlight predicates |
| `mdimport` | `/usr/bin/mdimport` | ✅ | Force re-index of specific files |
| `plutil` | `/usr/bin/plutil` | ✅ | Convert binary plist ↔ XML/JSON |
| `tag` | `/opt/homebrew/bin/tag` | ✅ | Tag add/remove/set/list/find (jdberry) |
| `exiftool` | `/opt/homebrew/bin/exiftool` | ✅ | File-embedded metadata (EXIF, IPTC, XMP) |
| `osxmetadata` | `/Users/bear/.local/bin/osxmetadata` | ✅ | **Primary tool** — comprehensive metadata CLI (v1.4.1, pipx) |
| `uv` | Available | ✅ | Python package runner — gives osxmetadata API access |
| `SetFile` | `/usr/bin/SetFile` | ⚠️ | Attribute flags only, NOT labels |
| `GetFileInfo` | `/usr/bin/GetFileInfo` | ⚠️ | Limited usefulness |
| HoudahSpot | `/Applications/Setapp/HoudahSpot.app` | ⚠️ | GUI only; URL scheme `houdahspot4://` for simple searches |

---

## 3. How macOS Actually Stores Metadata

### 3.1 Tags (Multi-valued Text Labels)
- **xattr:** `com.apple.metadata:_kMDItemUserTags`
- **Format:** Binary plist array of strings
- **Encoding:** Each tag is `"TagName\n<colour_index>"` where `\n` is a literal newline
  - `colour_index = 0` → no colour (plain text tag)
  - `colour_index = 1–7` → Gray, Green, Purple, Blue, Yellow, Red, Orange
- Multiple tags can coexist. Colour tags and text tags are stored in the same array.

### 3.2 Labels (Exclusive Colour)
- **xattr:** `com.apple.FinderInfo` (32-byte struct)
- **Colour encoding:** Byte 9, bits 1–3, stored as `colour_index << 1`
- **Safe mask formula:** `byte_9 = (byte_9 & 0xF1) | (colour_index << 1)`
- **Preserves all non-colour flags** including `kHasBeenInited` (bit 6), alias, stationery, namelock
- FinderInfo is created lazily (first colour write) and may be deleted when no longer needed

| Colour | Index | Byte 9 Value | Binary |
|--------|-------|-------------|--------|
| None | 0 | 0x00 | 00000000 |
| Gray | 1 | 0x02 | 00000010 |
| Green | 2 | 0x04 | 00000100 |
| Purple | 3 | 0x06 | 00000110 |
| Blue | 4 | 0x08 | 00001000 |
| Yellow | 5 | 0x0A | 00001010 |
| Red | 6 | 0x0C | 00001100 |
| Orange | 7 | 0x0E | 00001110 |

**Label exclusivity is NOT enforced by any tool.** Both `tag` and `osxmetadata` will happily write multiple colour tags. Our skill must implement this manually.

### 3.3 Finder Comments
- **Dual storage:** `com.apple.metadata:kMDItemFinderComment` xattr AND `.DS_Store` file
- **osxmetadata uses Scripting Bridge** to Finder process — writes both stores, no `mdimport` needed
- **Direct xattr write + mdimport also works** for Spotlight visibility
- **For maximum reliability:** use `osxmetadata` for comment writes (it uses the proper Finder channel)
- **Headless/fallback:** xattr write + `mdimport` if Finder process is unavailable

### 3.4 Spotlight Index
- **Read via:** `mdls` (per-file), `mdfind` (search)
- **Key attributes:** `kMDItemUserTags`, `kMDItemFSLabel`, `kMDItemFinderComment`, `kMDLabel_<uuid>`
- **Indexing lag:** After xattr writes, Spotlight may be stale until `mdimport <file>`. Brief delay possible even after `mdimport`.
- **Locale-safe search:** Use `mdfind "kMDItemUserTags == 'Tag'"` — never use `tag:Red` shorthand (emits locale warning)

### 3.5 Custom xattrs
- Any namespace writable: `xattr -w com.agent.notes "value" file`
- **Invisible to Spotlight** — no `mdfind` access
- **Stripped by iCloud sync** — Finder Tags survive, custom xattrs do not
- **Search:** `os.scandir()` + `xattr` subprocess per file (fastest tested: ~0.078s for small sets)

---

## 4. osxmetadata Evaluation (Definitive)

### What It Does Well
- **Tags:** add, remove, set, clear — all correct, colour encoding handled (`'TagName,red'` syntax)
- **JSON output:** `osxmetadata -j --list FILE` — comprehensive, structured, agent-parseable
- **Finder comments:** uses Scripting Bridge (reliable), reads work immediately
- **Backup/restore:** `--backup` / `--restore` to `.osxmetadata.json`
- **Directory walk:** `--walk --pattern '*.pdf'` for bulk operations
- **Finder colour read:** reads from xattr directly (not Spotlight), reliable after writes
- **Copy from:** `--copyfrom SOURCE FILE` copies known attributes between files
- **Attribute coverage:** 100+ kMDItem attributes beyond tags/comments

### What It Does NOT Do
- **Label exclusivity** — no enforcement, will write multiple colour tags
- **Custom xattr support** — only known `kMDItem*` attributes
- **Search** — no `mdfind` equivalent, only per-file read/write
- **Mirror** — broken (early-return bug in source code)
- **Copy custom xattrs** — `--copyfrom` only covers its known attribute list

### How to Access
- **CLI:** `/Users/bear/.local/bin/osxmetadata` — always works, pipx-isolated
- **Python API:** `uv run --with osxmetadata python3 -c "..."` — ~0.38s overhead, cached after first run
- **Not importable** from system Python directly (pipx isolation)

---

## 5. Verified Approaches (All Tested)

### 5.1 Read All Metadata as JSON
```bash
osxmetadata -j --list FILE
```
✅ Comprehensive JSON. Foundation of the read path.

### 5.2 Read Specific Attributes
```bash
osxmetadata -j -g tags FILE           # Tags with colour
osxmetadata -j -g findercolor FILE    # Label colour (from xattr)
osxmetadata -j -g findercomment FILE  # Comment
```
✅ All work. `findercolor` reads from xattr, not Spotlight.

### 5.3 Tag Operations
```bash
osxmetadata --append tags 'name' FILE        # Add tag
osxmetadata --append tags 'name,red' FILE     # Add tag with colour
osxmetadata --remove tags 'name' FILE         # Remove tag
osxmetadata --set tags 'name1,name2' FILE     # Replace all tags
osxmetadata --clear tags FILE                 # Remove all tags
```
✅ All verified. Colour syntax `'name,colour'` correctly encoded.

### 5.4 Finder Comments
```bash
osxmetadata --set findercomment 'text' FILE   # Via Scripting Bridge
osxmetadata --clear findercomment FILE
```
✅ Uses Scripting Bridge → Finder process. No `mdimport` needed.

### 5.5 Label Set (Exclusive) — Custom Logic ✅
```python
# The ONE thing we must build ourselves
# 1. Read _kMDItemUserTags, separate colour tags from text tags
# 2. Strip existing colour tags, add new "Colour\n<index>"
# 3. Write updated _kMDItemUserTags as binary plist
# 4. Read FinderInfo, mask byte 9 with 0xF1, set colour << 1
# 5. Write updated FinderInfo
# 6. Run mdimport <file>
```
✅ Proven correct. Finder displays the colour dot.

### 5.6 Label Read — Direct from xattr ✅
```python
# Read FinderInfo byte 9 directly, not via Spotlight
# byte_9 & 0x0E >> 1 = colour_index
# osxmetadata -g findercolor also reads from xattr (verified)
```

### 5.7 Search
```bash
mdfind "kMDItemUserTags == 'tagname'" -onlyin DIR    # By tag
mdfind "kMDItemFSLabel == 6" -onlyin DIR             # By colour
mdfind "(kMDItemUserTags == 'a') && (kMDItemUserTags == 'b')" -onlyin DIR  # Boolean
tag -f 'tagname' DIR                                  # Direct xattr (no Spotlight lag)
```
✅ All work. Always use predicate form, never `tag:` shorthand.

### 5.8 Custom xattr Search (No Spotlight) ✅
```python
# Fastest approach: os.scandir + subprocess xattr
import os, subprocess
for entry in os.scandir(dirpath):
    if entry.is_file():
        result = subprocess.run(['xattr', entry.path], capture_output=True, text=True)
        if target_key in result.stdout:
            # Found
```

### 5.9 Bulk Operations ✅
```bash
osxmetadata --walk --append tags 'project' --pattern '*.pdf' DIR
```

### 5.10 Backup/Restore ✅
```bash
osxmetadata --backup FILE    # Creates .osxmetadata.json
osxmetadata --restore FILE   # Restores from backup
```

---

## 6. Resolved Open Questions

| # | Question | Answer | Confidence |
|---|----------|--------|------------|
| Q1 | Finder displays colour dot from programmatic writes? | **YES** — verified manually | ✅ Certain |
| Q2 | Finder comment .DS_Store trap? | **Mitigated** — `osxmetadata` uses Scripting Bridge (writes both stores). xattr+mdimport also works for Spotlight. | ✅ Certain |
| Q3 | FinderInfo byte 9 bit map? | **Confirmed** — bits 1-3 are colour; `0xF1` mask preserves all other flags | ✅ Certain |
| Q4 | mdfind locale warning? | **Fixed** — use `kMDItemUserTags ==` predicate form exclusively | ✅ Certain |
| Q5 | Fast custom xattr search? | **os.scandir + xattr subprocess** — fastest tested approach | ✅ Certain |
| Q6 | osxmetadata on Python 3.14? | **Works** — installed and fully functional | ✅ Certain |
| Q7 | iCloud sync and tags? | **Tags survive; custom xattrs stripped; Finder comments uncertain** | ⚠️ Partial |
| Q8 | HoudahSpot URL scheme? | **Limited** — simple queries only; better as display tool | ⚠️ Partial |
| Q9 | Symlink xattr behaviour? | **All tools follow symlinks** to target by default | ✅ Certain |
| Q10 | xattr write failure modes? | **EPERM on SIP paths; EACCES on permissions; catch OSError** | ✅ Certain |
| Q11 | osxmetadata findercolor source? | **Reads from xattr directly** — not Spotlight. Bit offset 76 = bits 1-3 (same physical bits) | ✅ Certain |
| Q12 | Python API access method? | **`uv run --with osxmetadata`** — ~0.38s overhead, clean isolation | ✅ Certain |
| Q13 | copyfrom completeness? | **Known attributes only** — no custom xattrs | ✅ Certain |
| Q14 | mirror feature? | **Broken** — early-return bug; do not use | ✅ Certain |
| Q15 | Comment write implementation? | **Scripting Bridge** to Finder — no mdimport needed | ✅ Certain |
| R1 | Labels on folders? | **Identical behaviour** to files at xattr level; Spotlight indexing may be slower for folders | ✅ Certain |
| R2 | Label persistence across operations? | **Preserved** for content rewrite, same-volume mv, cp, Finder duplicate. Lost by rsync without -X, zip. Custom xattrs stripped by iCloud. | ✅ Certain |
| R3 | kMDItemKeywords vs Tags? | **Tags are superior** — visible in Finder, support colour. Keywords are invisible in Finder; only useful for cross-app interoperability (Lightroom, etc.) | ✅ Certain |
| R4 | Spotlight query performance? | **O(log n)** from Spotlight index; -onlyin adds no linear cost. tag -f may not be identical to mdfind. | ✅ Certain |
| R5 | xattr size limits? | **≤3,804 bytes = inline tier** (atomic, fast). Larger values use data stream tier. No practical limit on APFS. | ✅ Certain |
| R6 | Detecting metadata changes? | **FSEvents** with `kFSEventStreamEventFlagItemXattrMod` flag (via `watchdog` in Python). `NSMetadataQuery` for tag-change workflows at scale. `kqueue NOTE_ATTRIB` for specific files. | ✅ Certain |
| R7 | osxmetadata write atomicity? | **Atomic for inline tier** via `NSURL.setResourceValues` → `setxattr`. No locking needed for single agent. TOCTOU risk for concurrent agents (use advisory lock). | ✅ Certain |

---

## 7. Architecture Decision: Two-Tier Approach

### Tier 1: CLI Wrapper (Skill Interface)
A shell/Python script that the agent calls via bash. It presents a unified command interface and delegates to the appropriate backend tool.

### Tier 2: Backend Tools
- **`osxmetadata` CLI** — for tags, comments, metadata reads, backup/restore, bulk operations
- **`xattr` CLI** — for custom xattr read/write/search
- **`mdfind`** — for Spotlight search
- **Custom Python function** — for label-exclusive set/clear (the one gap)
- **`mdimport`** — post-write Spotlight nudge

### Implementation Choice: CLI over Python API
While `uv run --with osxmetadata` gives API access, the CLI approach is preferable for the skill because:
- No dependency on `uv` at runtime (already installed, but principle of minimal coupling)
- `osxmetadata` CLI is already pipx-installed and working
- JSON output from CLI is clean and parseable
- The only custom code (label-exclusive) can use stdlib only
- Simpler error handling and debugging for the agent

### Command Interface

```
# READ
meta read <file>                       → Full JSON metadata dump (osxmetadata -j --list)
meta tags <file>                       → Tags with colour info
meta label <file>                      → Current label colour
meta comment <file>                    → Finder comment
meta xattrs <file>                     → All xattr keys + custom values

# TAGS (multi-valued)
meta tag-add <file> <tag>...           → Add tags (optionally 'name,colour')
meta tag-remove <file> <tag>...        → Remove specific tags
meta tag-set <file> <tag>...           → Replace all tags
meta tag-clear <file>                  → Remove all tags

# LABELS (exclusive colour — custom logic)
meta label-set <file> <colour>         → Set exclusive label (preserves text tags)
meta label-clear <file>                → Remove label only (preserves text tags)

# FINDER COMMENTS
meta comment-set <file> <text>         → Set Finder comment
meta comment-clear <file>              → Clear Finder comment

# CUSTOM XATTRS
meta xattr-get <file> <key>            → Read xattr value
meta xattr-set <file> <key> <val>      → Write custom xattr
meta xattr-delete <file> <key>         → Delete xattr

# SEARCH
meta search --tag <tag> [--dir <path>]       → mdfind by tag
meta search --label <colour> [--dir <path>]  → mdfind by label colour
meta search --query <predicate> [--dir <path>] → raw mdfind query
meta search --xattr <key> [--dir <path>]     → os.scandir + xattr
meta search --text <terms> [--dir <path>]    → Spotlight text search

# BULK
meta bulk-tag-add <tag> --dir <path> [--pattern <glob>]
meta bulk-label-set <colour> --dir <path> [--pattern <glob>]

# SAFETY
meta backup <file>                     → Snapshot metadata
meta restore <file>                    → Restore from backup
```

### Colour Name Mapping
```python
COLOURS = {
    "none": 0, "gray": 1, "grey": 1, "green": 2,
    "purple": 3, "blue": 4, "yellow": 5, "red": 6, "orange": 7
}
COLOUR_NAMES = {v: k for k, v in COLOURS.items() if v > 0}
```

### Post-Write Contract
1. Complete the metadata write(s)
2. Run `mdimport <file>` (except for Finder comments via osxmetadata — Scripting Bridge handles notification)
3. Return JSON: `{"success": true, "file": "<path>", "operation": "<op>"}`

---

## 8. What to Build vs What to Use As-Is

| Component | Decision | Tool |
|-----------|----------|------|
| Metadata read (JSON) | Use `osxmetadata` | `osxmetadata -j --list` |
| Tag add/remove/set/clear | Use `osxmetadata` | `osxmetadata --append/remove/set/clear tags` |
| Label set (exclusive) | **Build custom** | Python + `xattr` + `struct` + `plistlib` |
| Label clear | **Build custom** | Same approach as label-set with colour=0 |
| Label read | Use `osxmetadata` | `osxmetadata -g findercolor` (reads xattr) |
| Finder comment read/write | Use `osxmetadata` | `osxmetadata --set/get findercomment` |
| Custom xattr read/write | Use `xattr` | `xattr -p/-w/-d` |
| Custom xattr search | **Build custom** | `os.scandir` + `xattr` subprocess |
| Tag search | Use `mdfind` | `mdfind "kMDItemUserTags == '...'"` |
| Label search | Use `mdfind` | `mdfind "kMDItemFSLabel == N"` |
| Text search | Use `mdfind` | `mdfind "terms"` |
| Bulk operations | Use `osxmetadata --walk` | `osxmetadata --walk --append tags` |
| Backup/restore | Use `osxmetadata` | `--backup` / `--restore` |
| Spotlight nudge | Use `mdimport` | `mdimport <file>` |
| Error handling | **Build custom** | OSError/EPERM/EACCES catch + SIP detection |

---

## 9. Library Stack

| Layer | Tool/Library | Our Use |
|---|---|---|
| **Primary** | `osxmetadata` CLI (v1.4.1) | Tags, comments, reads, backup, bulk |
| **Label logic** | Python stdlib (`struct`, `plistlib`, `subprocess`) | Exclusive label set/clear |
| **Raw xattr** | `xattr` CLI (built-in) | Custom namespace operations |
| **Search** | `mdfind` (built-in) | Spotlight queries |
| **Direct search** | `tag -f` (Homebrew) | Bypasses Spotlight lag |
| **Indexing** | `mdimport` (built-in) | Post-write nudge |
| **Embedded metadata** | `exiftool` (Homebrew) | Future extension |

### Not Used
| Tool | Reason |
|---|---|
| `pyobjc` / `NSMetadataQuery` | Overkill — CLI tools sufficient |
| `macos-tags` | Less complete than osxmetadata |
| `mac-tag` | Just wraps jdberry `tag` binary |
| `osxmetadata` Python API via `uv` | CLI is sufficient and already installed |
| `--mirror` | Broken in source code |

---

## 10. Edge Cases and Error Handling

### Symlinks
- All tools follow symlinks to target by default — correct for tag/label operations
- No special handling needed

### iCloud Sync
- **Finder Tags survive** iCloud sync (special Apple exemption)
- **Custom xattrs are stripped** — do not rely on them for iCloud-synced files
- Agent should warn or document this limitation

### Permissions and Failures
- **SIP-protected paths** (`/System`, `/sbin`, `/bin`, `/usr`): xattr writes fail with `EPERM`
- **Immutable files** (`uchg` flag): writes fail
- **Read-only volumes**: writes fail
- **Quarantined files**: readable, writable with proper permissions
- **Error pattern:** wrap all writes in try/except for `OSError`, check `errno.EPERM` and `errno.EACCES`

### Finder Process
- Finder comment writes via `osxmetadata` require Finder to be running
- Headless/server fallback: direct xattr write + `mdimport`
- Finder label dots update on folder view refresh (no relaunch needed)

### Folder Labels
- Work identically to file labels at the xattr level (same byte 9 encoding)
- Spotlight may take longer to index folder labels than file labels
- Always use `mdimport` after writing folder labels

### Metadata Persistence
- **Preserved:** content rewrite, same-volume mv, cp (default on macOS), Finder Cmd+D, Time Machine
- **Lost by:** rsync without -X, standard zip (use `ditto` or `tar --xattr` instead)
- **iCloud:** Finder Tags and FinderInfo survive; custom xattrs are stripped

### Atomicity and Concurrency
- `setxattr` is atomic for values ≤ 3,804 bytes (inline tier on APFS)
- Tag arrays (typically < 1 KB) fall within inline tier — no locking needed for single agent
- For concurrent agents: use advisory lock (`flock`) to serialise read-modify-write cycles
- Multi-step operations (tags + colour + custom xattr) are NOT atomic — backup before modify for safety

### xattr Size Guidance
- ≤ 3,804 bytes: inline tier — single I/O, atomic, fastest
- > 3,804 bytes: data stream tier — one extra indirection, still fast
- Store JSON blobs up to ~3 KB in custom xattrs safely
- No practical maximum on APFS for reasonable use cases

### Keywords (kMDItemKeywords)
- Independent from tags, stored in separate xattr
- Invisible in Finder UI — only accessible via Spotlight/mdls
- Written by Lightroom, Capture One, some PDF tools
- For agent skill: **use tags, not keywords** — tags are visible, support colour, and are more ergonomic
- Consider keywords only if cross-app interoperability is required

### Metadata Change Detection
- **FSEvents** (`kFSEventStreamEventFlagItemXattrMod`): detects xattr changes on directory trees; accessible via Python `watchdog` library
- **NSMetadataQuery**: live Spotlight queries that update when tags change (1-5 second lag); best for reactive tag-based workflows
- **kqueue NOTE_ATTRIB**: per-file attribute change notification; limited to watched file descriptors
- For the agent skill: not immediately needed, but available for future reactive workflows

### Spotlight Lag
- After any xattr write, Spotlight may show stale data
- `mdimport <file>` resolves within seconds
- For search of freshly-written metadata: `tag -f` reads xattrs directly (no lag)
- Always use `mdimport` as post-write step (except osxmetadata comment writes)

---

## 11. Non-Goals (For Now)
- File-embedded metadata (EXIF, IPTC) — `exiftool` handles this separately
- GUI automation — HoudahSpot is a display tool, not a programmatic backend
- `pyobjc` native API — CLI tools are sufficient
- File dates/times — standard `touch` covers this
- Permissions/ownership — standard `chmod`/`chown` covers this
- Maintaining a custom xattr search index (SQLite) — revisit if performance is an issue at scale

---

## 12. Dependencies
- **CLI tools:** `osxmetadata` (pipx), `xattr` (built-in), `mdfind` (built-in), `mdimport` (built-in), `tag` (Homebrew)
- **Custom code:** Python 3 with `plistlib`, `struct`, `subprocess`, `json` (all stdlib)
- **No additional pip/brew installs required**

---

## 13. Implementation Plan

### Phase 1: Core Tool
Build the `meta` CLI script (Python) with:
1. `read` — delegate to `osxmetadata -j --list`
2. `tag-add/remove/set/clear` — delegate to `osxmetadata`
3. `label-set/clear` — custom logic (the one hard part, already prototyped)
4. `comment-set/clear` — delegate to `osxmetadata`
5. `search` — delegate to `mdfind` / `tag -f` / custom scan
6. `backup/restore` — delegate to `osxmetadata`

### Phase 2: Agent Skill (SKILL.md)
Write the skill instructions teaching the agent:
1. When and how to use each command
2. The label-exclusivity rule
3. Post-write `mdimport` discipline
4. Error handling patterns
5. iCloud sync caveat
6. Search strategies (Spotlight vs direct xattr)

### Phase 3: Testing and Polish
1. Test with real files across Bear's filesystem
2. Test with folders (labels on directories)
3. Test bulk operations on real directories
4. Performance test custom xattr search on large trees
5. Edge cases: locked files, SIP paths, broken symlinks
