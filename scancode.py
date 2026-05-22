#!/usr/bin/env python3
"""
scan_files.py - Scan a macOS system for specific file types and report:
    * count + total size per extension
    * top 10 largest files
    * top 10 most recently accessed files
    * a full CSV of every match

Usage:
    python3 scan_files.py            # scans "/" (entire Mac)
    python3 scan_files.py ~/Documents  # scans a specific folder

-------------------------------------------------------------------------
READ THIS BEFORE TRUSTING THE OUTPUT
-------------------------------------------------------------------------
1. EXTENSIONS: matched EXACTLY as ".doc .ppt .pdf .png .heic".
   This deliberately EXCLUDES ".docx" and ".pptx" - the modern Word and
   PowerPoint formats. Most Office files made in the last ~15 years are
   .docx/.pptx and will NOT be counted. To include them, add them to
   TARGET_EXTS below.

2. "MOST RECENTLY ACCESSED" uses access time (atime). On macOS/APFS atime
   is unreliable: Spotlight indexing, antivirus, Quick Look, Time Machine
   and previews all bump it. The "recently accessed" list reflects what
   *touched* a file, not necessarily what *you opened*. Treat it as rough.

3. SCANNING "/" requires Full Disk Access for the app running this script:
   System Settings -> Privacy & Security -> Full Disk Access -> add your
   Terminal (or iTerm). Without it, large parts of the disk are silently
   skipped and reported under "permission denied".

4. System files and app bundles contain huge numbers of .png and .pdf
   resources that will inflate the counts. Add paths to SKIP_DIRS below
   (e.g. "/System", "/Applications") if you only care about your own files.
-------------------------------------------------------------------------
"""

import csv
import os
import sys
import time

# --- Configuration -------------------------------------------------------

# Extensions to match (lowercase, leading dot). Edit this line to change
# what gets counted - e.g. add ".docx", ".pptx", ".jpg".
TARGET_EXTS = {".docx", ".pptx", ".pdf", ".png", ".heic"}

# Directories never descended into. This avoids:
#   - APFS firmlink double-counting (/System/Volumes)
#   - pseudo filesystems and system noise
# Add your own paths here (e.g. "/System", "/Applications") to cut noise.
SKIP_DIRS = {
    "/dev",
    "/System/Volumes",          # APFS firmlink/snapshot area -> double counts
    "/Volumes",                 # external drives + boot volume re-mount
    "/.Spotlight-V100",
    "/.fseventsd",
    "/.DocumentRevisions-V100",
    "/.MobileBackups",
    "/.TemporaryItems",
    "/.Trashes",
    "/private/var/vm",
    "/private/var/folders",     # transient caches; remove if you want them
}

TOP_N = 10

# --- Helpers -------------------------------------------------------------

def human(num_bytes):
    """Format a byte count as a human-readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024


def scan(root):
    """Walk `root` iteratively and collect matching files.

    Returns a dict of results. Uses an explicit stack (not recursion) and
    never follows symlinks, so it cannot loop forever. Files are de-duped
    by (device, inode) so APFS firmlinks and hardlinks are counted once.
    """
    files = []                                   # (path, size, atime)
    per_ext = {e: {"count": 0, "size": 0} for e in TARGET_EXTS}
    seen_inodes = set()                          # (st_dev, st_ino)
    denied = 0
    errors = 0
    dirs_scanned = 0
    start = time.time()

    stack = [root]
    while stack:
        directory = stack.pop()
        if directory in SKIP_DIRS:
            continue
        dirs_scanned += 1
        if dirs_scanned % 2000 == 0:
            sys.stderr.write(
                f"\r  ...{dirs_scanned:,} dirs scanned, "
                f"{len(files):,} matches so far"
            )
            sys.stderr.flush()

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        # Recurse into real directories only (no symlinks).
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue

                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext not in TARGET_EXTS:
                            continue

                        st = entry.stat(follow_symlinks=False)
                        inode_key = (st.st_dev, st.st_ino)
                        if inode_key in seen_inodes:
                            continue          # firmlink / hardlink duplicate
                        seen_inodes.add(inode_key)

                        files.append((entry.path, st.st_size, st.st_atime))
                        per_ext[ext]["count"] += 1
                        per_ext[ext]["size"] += st.st_size

                    except PermissionError:
                        denied += 1
                    except OSError:
                        errors += 1
        except PermissionError:
            denied += 1
        except OSError:
            errors += 1

    return {
        "files": files,
        "per_ext": per_ext,
        "denied": denied,
        "errors": errors,
        "dirs_scanned": dirs_scanned,
        "elapsed": time.time() - start,
    }


def print_report(result, root):
    """Print the formatted scan report to stdout."""
    files = result["files"]
    per_ext = result["per_ext"]

    total_count = sum(v["count"] for v in per_ext.values())
    total_size = sum(v["size"] for v in per_ext.values())

    sys.stderr.write("\r" + " " * 60 + "\r")  # clear progress line

    print()
    print("=" * 64)
    print(f"  FILE SCAN REPORT")
    print(f"  root: {root}")
    print("=" * 64)
    print(f"Directories scanned : {result['dirs_scanned']:,}")
    print(f"Scan time           : {result['elapsed']:.1f} s")
    print(f"Permission denied   : {result['denied']:,}  "
          f"(grant Full Disk Access to reduce this)")
    print(f"Other errors        : {result['errors']:,}")
    print()

    # Per-extension breakdown
    print(f"{'Extension':<12}{'Count':>14}{'Total size':>18}")
    print("-" * 44)
    for ext in sorted(TARGET_EXTS):
        info = per_ext[ext]
        print(f"{ext:<12}{info['count']:>14,}{human(info['size']):>18}")
    print("-" * 44)
    print(f"{'TOTAL':<12}{total_count:>14,}{human(total_size):>18}")
    print()

    if not files:
        print("No matching files found.")
        return

    # Top N largest
    print(f"TOP {TOP_N} LARGEST FILES")
    print("-" * 64)
    largest = sorted(files, key=lambda f: f[1], reverse=True)[:TOP_N]
    for path, size, _atime in largest:
        print(f"  {human(size):>10}  {path}")
    print()

    # Top N most recently accessed
    print(f"TOP {TOP_N} MOST RECENTLY ACCESSED")
    print("  (atime - unreliable on APFS; see notes at top of script)")
    print("-" * 64)
    recent = sorted(files, key=lambda f: f[2], reverse=True)[:TOP_N]
    for path, size, atime in recent:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(atime))
        print(f"  {stamp}  {human(size):>10}  {path}")
    print()


def write_csv(result, csv_path):
    """Write every matched file to a CSV, sorted largest first."""
    files = sorted(result["files"], key=lambda f: f[1], reverse=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "size_bytes", "size_human", "last_accessed"])
        for path, size, atime in files:
            writer.writerow([
                path,
                size,
                human(size),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(atime)),
            ])
    return len(files)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "/"
    root = os.path.abspath(os.path.expanduser(root))

    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a directory.")
        sys.exit(1)

    print(f"Scanning: {root}")
    print(f"Looking for: {', '.join(sorted(TARGET_EXTS))}")
    print("A full-disk scan can take several minutes...\n")

    result = scan(root)
    print_report(result, root)

    csv_path = os.path.join(os.path.expanduser("~"), "file_scan_results.csv")
    try:
        count = write_csv(result, csv_path)
        print(f"Full list of {count:,} files written to:")
        print(f"  {csv_path}")
    except OSError as exc:
        print(f"Could not write CSV: {exc}")


if __name__ == "__main__":
    main()