"""macmeta.help — Topic-based help text for the meta CLI."""

REFERENCE = """\
meta — macOS file metadata tool.

Usage:
    meta <verb> <noun> [args...] [options]

Verbs:  get, set, add, remove, clear, delete, search, backup, restore

    meta get all <file>                          Full JSON metadata dump
    meta get tags <file>                         Tags with colour info
    meta get label <file>                        Current label colour
    meta get comment <file>                      Finder comment
    meta get xattr <file> <key>                  Custom xattr value
    meta get xattrs <file>                       All xattr keys and values

    meta set tags <file> <tag>...                Replace all tags
    meta set label <file> <colour>               Set exclusive label colour
    meta set comment <file> <text>               Set Finder comment
    meta set xattr <file> <key> <value>          Write custom xattr

    meta add tags <file|dir> <tag>...            Append tags
                              [--pattern <glob>]

    meta remove tags <file> <tag>...             Remove specific tags

    meta clear tags <file>                       Remove all tags
    meta clear label <file>                      Remove label (keeps text tags)
    meta clear comment <file>                    Clear Finder comment

    meta delete xattr <file> <key>               Delete xattr key

    meta search tag <tag> [--dir <path>]         Search by tag
    meta search label <colour> [--dir <path>]    Search by label colour
    meta search xattr <key> [--dir <path>]       Search custom xattr key
    meta search text <terms> [--dir <path>]      Spotlight text search
    meta search query <predicate> [--dir <path>] Raw mdfind query

    meta backup <file>                           Snapshot metadata
    meta restore <file>                          Restore from backup

Colours: none, gray/grey, green, purple, blue, yellow, red, orange (or 0-7)
Tags:    'name' for text, 'name,colour' for colour (e.g. 'review,red')

Any set/add command accepts --dir <path> [--pattern <glob>]
to apply to all matching files in a directory instead of a single file.

Topics: meta help <topic>   where <topic> is one of:
        concepts, search, xattrs, examples
"""

CONCEPTS = """\
Tags vs Labels — the critical distinction
==========================================

macOS stores two related but distinct kinds of colour metadata. You MUST
understand the difference to use this tool correctly.

TAGS (multi-valued, no exclusivity)
------------------------------------
A file can have any number of tags: "project-x", "urgent", "draft".
Tags optionally carry a colour: "review,red", "final,green".
Multiple colour tags CAN coexist on the same file.
Tags are visible in Finder sidebar, Get Info, and Spotlight.

LABELS (exclusive colour — one at a time)
------------------------------------------
A file has EXACTLY ONE label colour at a time.
Setting a label via "meta set label" REPLACES the previous colour while
PRESERVING all text tags.
This is custom logic — no standard macOS tool handles this correctly.
The colour appears as a dot in Finder list view and as a tint in icon view.

Rule of thumb
-------------
Use "meta set label" for colour status (red=needs attention, green=done).
Use "meta add tags" or "meta set tags" for text organisation.
The label and tags are independent — you can have a red label AND text tags
on the same file.

Colour palette
--------------
  none (0)  gray/grey (1)  green (2)  purple (3)
  blue (4)  yellow (5)     red (6)    orange (7)

You can use names or numbers.

Verb semantics
--------------
  set     — Replace the entire value with what you provide
  add     — Append to existing values without replacing
  remove  — Remove specific items from a multi-valued attribute
  clear   — Empty the value (attribute still conceptually exists)
  delete  — Remove the attribute key entirely (it ceases to exist)

  "clear" vs "delete": clear tags empties the tag list; delete xattr removes
  the xattr key from the file. Tags, labels, and comments are standard macOS
  attributes — you clear them. Custom xattrs are user-defined keys — you
  delete them.

Persistence
-----------
Metadata survives: file content changes, same-volume moves (mv), copy (cp),
Finder duplication (Cmd+D), Time Machine backups.
Metadata is lost by: rsync without -X, standard zip (use ditto instead),
cross-volume moves in some cases.

Symlinks and folders
--------------------
All operations follow symlinks to the target — this is correct behaviour for
metadata. Labels and tags work on directories identically to files.
"""

SEARCH = """\
Search — finding files by metadata
====================================

Fast: Spotlight (tags, labels, text content)
---------------------------------------------
  meta search tag "project-x" --dir ~/Documents
  meta search label red --dir ~/Documents
  meta search text "invoice Q3" --dir ~/Documents

Spotlight queries are fast — they use a pre-built index, O(log n) regardless
of directory size. Results may lag 1–2 seconds for recently-written metadata
(the tool runs mdimport automatically after writes to minimise this).

Tag and label searches find files anywhere under the directory tree.
Text search matches against file content AND metadata.

Slow but comprehensive: Custom xattr scan
-------------------------------------------
  meta search xattr com.agent.status --dir ~/Documents

Custom xattrs are INVISIBLE to Spotlight. This command scans the filesystem
directly using os.scandir — slower than Spotlight but finds everything.

It only searches one directory level (non-recursive). For deep scans,
combine with find:
  find ~/Documents -type f -exec meta get xattr {} com.agent.status \\;

Complex queries: Raw mdfind predicates
----------------------------------------
  meta search query "kMDItemContentType == 'com.adobe.pdf'" --dir .

Uses Apple's Spotlight query language. Useful predicates:

  kMDItemUserTags == 'tagname'              Tag match (exact)
  kMDItemFSLabel == 6                       Label colour index
  kMDItemContentModificationDate > $time.today(-7)  Modified in last 7 days
  kMDItemContentType == 'public.plain-text'        By UTI type
  kMDItemFSName == 'filename.txt'                   By exact filename

Boolean operators:
  (kMDItemUserTags == 'inbox') && (kMDItemFSLabel == 6)
  (kMDItemContentType == 'public.image') || (kMDItemContentType == 'com.adobe.pdf')

The --dir flag restricts results to a directory tree. Without it, Spotlight
searches the entire filesystem.
"""

XATTRS = """\
Custom Xattrs — arbitrary key-value metadata on files
======================================================

Custom xattrs let you attach any key-value pair to a file. The namespace is
yours to define — by convention, use reverse-DNS format:

  meta set xattr <file> com.agent.status "processed"
  meta set xattr <file> com.agent.notes "Reviewed on Friday"
  meta get xattr <file> com.agent.status
  meta delete xattr <file> com.agent.status

Reading all xattrs:
  meta get xattrs <file>

This shows every xattr on the file, including Apple system ones.

Limitations — READ THESE
-------------------------

1. INVISIBLE TO SPOTLIGHT
   mdfind cannot find files by custom xattr. Use "meta search xattr" instead
   (filesystem scan, slower).

2. STRIPPED BY ICLOUD DRIVE
   If the file syncs via iCloud, custom xattrs will be lost on other machines.
   Only Finder Tags (_kMDItemUserTags) survive iCloud sync. If a file lives
   in iCloud Drive, store important metadata in tags, not custom xattrs.

3. SIZE
   Keep values under ~3 KB for best performance. APFS stores small xattrs
   inline (single I/O, atomic write). Larger values use a data stream tier
   (still fast, but one extra indirection). No practical maximum on APFS.

4. PERSISTENCE
   Survive: content changes, same-volume mv, cp, Finder duplication,
   Time Machine.
   Lost by: rsync without -X, standard zip (use ditto or tar --xattr).

Atomicity
---------
For values under 3.8 KB, writes are atomic at the kernel level. Another
process sees either the old value or the new value, never a partial write.
No file locking is needed for single-agent use.
"""

EXAMPLES = """\
Examples — common workflows
============================

Tag files for a project
------------------------
  meta add tags report.pdf "quarterly-review"
  meta add tags ~/Documents/project/ "project-phoenix" --pattern '*.md'

Set a colour label for status
------------------------------
  meta set label invoice.pdf red         # Needs attention
  meta set label draft.docx orange       # In progress
  meta set label final.pdf green         # Done
  meta set label on-hold.txt blue        # On hold

Find all files needing attention
---------------------------------
  meta search label red --dir ~/Documents

Combine tags and labels
------------------------
  meta add tags proposal.pdf "client-acme" "urgent"
  meta set label proposal.pdf red
  # Result: red label + "client-acme" and "urgent" text tags

  meta get tags proposal.pdf
  # Shows: Red (colour 6), client-acme (colour 0), urgent (colour 0)

Change label without losing tags
---------------------------------
  meta set label proposal.pdf green      # Red → green, tags preserved
  meta get tags proposal.pdf
  # Shows: Green (colour 2), client-acme, urgent

Remove label but keep tags
---------------------------
  meta clear label proposal.pdf
  meta get tags proposal.pdf
  # Shows: client-acme, urgent (no colour)

Full metadata audit of a file
-------------------------------
  meta get all invoice.pdf

Write and read custom metadata
-------------------------------
  meta set xattr notes.txt com.agent.summary "Key decisions from meeting"
  meta get xattr notes.txt com.agent.summary

Find files with custom metadata
---------------------------------
  meta search xattr com.agent.summary --dir ~/Documents

Snapshot metadata before risky changes
----------------------------------------
  meta backup important.pdf
  # ... make changes ...
  meta restore important.pdf    # if something went wrong

Bulk operations on a directory
-------------------------------
  meta add tags ~/Downloads/ "to-sort" --pattern '*.pdf'
  meta set label ~/Downloads/ orange --pattern '*.pdf'

Check current state
--------------------
  meta get tags <file>       # What tags does this file have?
  meta get label <file>      # What colour label?
  meta get comment <file>    # Any Finder comment?
  meta get xattrs <file>     # Show all extended attributes
"""

TOPICS = {
    "concepts": CONCEPTS,
    "search": SEARCH,
    "xattrs": XATTRS,
    "examples": EXAMPLES,
}
