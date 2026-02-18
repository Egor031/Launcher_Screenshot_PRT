# NX 1899
# Batch export PRT -> OBJ (no UI) + logging
# v0.1.0-alpha

import os
import time
import traceback
import NXOpen


def _script_dir() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name, None)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name, None)
    if val is None:
        return default
    try:
        return float(val.replace(",", "."))
    except Exception:
        return default


# ---------------- DEFAULT PATHS (portable) ----------------

BASE_DIR = _script_dir()

DEFAULT_INPUT_DIR = os.path.join(BASE_DIR, "PRT")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "OBJ")

INPUT_DIR = os.environ.get("PRT_DIR", DEFAULT_INPUT_DIR)
OUTPUT_DIR = os.environ.get("OBJ_DIR", DEFAULT_OUTPUT_DIR)

DEFAULT_LOG_FILE = os.path.join(OUTPUT_DIR, "export_log.txt")
LOG_FILE = os.environ.get("LOG_FILE", DEFAULT_LOG_FILE)

# Options via env
OVERWRITE = _env_bool("OVERWRITE", False)
RECURSIVE = _env_bool("RECURSIVE", True)
ANGULAR_TOL = _env_float("ANGULAR_TOL", 44.0)


def log_line(f, msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    f.write(line + "\n")
    f.flush()


def iter_prt_files(root_dir: str, recursive: bool):
    """
    Yield (absolute_path, relative_path_from_root) for .prt files.
    """
    root_dir = os.path.abspath(root_dir)

    if not recursive:
        for fn in sorted(os.listdir(root_dir)):
            if fn.lower().endswith(".prt"):
                abs_path = os.path.join(root_dir, fn)
                if os.path.isfile(abs_path):
                    yield abs_path, fn
        return

    # recursive
    for cur_root, dirs, files in os.walk(root_dir):
        dirs.sort()
        files.sort()
        for fn in files:
            if not fn.lower().endswith(".prt"):
                continue
            abs_path = os.path.join(cur_root, fn)
            if not os.path.isfile(abs_path):
                continue
            rel_path = os.path.relpath(abs_path, root_dir)
            yield abs_path, rel_path


def main():
    start_all = time.time()

    # Ensure output/log dirs exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        log_line(logf, "=== START EXPORT PRT -> OBJ ===")
        log_line(logf, f"SCRIPT_DIR   = {BASE_DIR}")
        log_line(logf, f"INPUT_DIR    = {INPUT_DIR}")
        log_line(logf, f"OUTPUT_DIR   = {OUTPUT_DIR}")
        log_line(logf, f"LOG_FILE     = {LOG_FILE}")
        log_line(logf, f"RECURSIVE    = {RECURSIVE}")
        log_line(logf, f"OVERWRITE    = {OVERWRITE}")
        log_line(logf, f"ANGULAR_TOL  = {ANGULAR_TOL}")

        if not os.path.isdir(INPUT_DIR):
            log_line(logf, f"ERROR: INPUT_DIR does not exist: {INPUT_DIR}")
            log_line(logf, "TIP: set env var PRT_DIR to a folder with .prt files.")
            return

        # Collect files first (so we can log counts)
        prt_list = list(iter_prt_files(INPUT_DIR, RECURSIVE))
        log_line(logf, f"Found {len(prt_list)} .prt files")

        if not prt_list:
            log_line(logf, "No .prt files found. Nothing to do.")
            log_line(logf, "=== END EXPORT ===")
            return

        # NX Session
        theSession = NXOpen.Session.GetSession()

        # Create creator once
        objCreator = theSession.DexManager.CreateWavefrontObjCreator()
        objCreator.ExportFrom = NXOpen.WavefrontObjCreator.ExportFromOption.ExistingPart
        objCreator.AngularTolerance = ANGULAR_TOL
        objCreator.FlattenAssemblyStructure = True
        objCreator.FileSaveFlag = False

        count_ok = 0
        count_fail = 0
        count_skip = 0
        failed = []

        for i, (prt_abs, prt_rel) in enumerate(prt_list, start=1):
            base = os.path.splitext(prt_rel)[0]  # keeps subfolders in name
            # Keep folder structure for outputs:
            obj_abs = os.path.join(OUTPUT_DIR, base + ".obj")

            out_dir = os.path.dirname(obj_abs)
            os.makedirs(out_dir, exist_ok=True)

            if os.path.exists(obj_abs) and not OVERWRITE:
                count_skip += 1
                log_line(logf, f"[{i}/{len(prt_list)}] SKIP exists: {prt_rel}")
                continue

            t0 = time.time()
            try:
                objCreator.InputFile = prt_abs
                objCreator.OutputFile = obj_abs
                objCreator.Commit()

                dt = time.time() - t0
                count_ok += 1
                log_line(logf, f"[{i}/{len(prt_list)}] OK  {prt_rel} -> {os.path.relpath(obj_abs, OUTPUT_DIR)}  ({dt:.2f}s)")

            except Exception as e:
                dt = time.time() - t0
                count_fail += 1
                failed.append(prt_rel)

                log_line(logf, f"[{i}/{len(prt_list)}] FAIL {prt_rel} ({dt:.2f}s)  err={repr(e)}")
                logf.write(traceback.format_exc() + "\n")
                logf.flush()

        objCreator.Destroy()

        total_dt = time.time() - start_all
        log_line(logf, "=== FINISH ===")
        log_line(logf, f"OK:   {count_ok}")
        log_line(logf, f"SKIP: {count_skip}")
        log_line(logf, f"FAIL: {count_fail}")
        log_line(logf, f"Total time: {total_dt:.2f}s")

        if failed:
            log_line(logf, "Failed files list:")
            for fn in failed:
                log_line(logf, f"  - {fn}")

        log_line(logf, "=== END EXPORT ===")


if __name__ == "__main__":
    main()
