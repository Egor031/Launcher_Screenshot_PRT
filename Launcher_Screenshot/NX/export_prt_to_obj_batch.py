# NX 1899
# Batch export PRT -> OBJ (no UI) + logging

import os
import time
import traceback
import NXOpen

# значения по умолчанию
INPUT_DIR  = r"D:\ZherlitsynEE\SaveFormatTest\Test\PRT"
OUTPUT_DIR = r"D:\ZherlitsynEE\SaveFormatTest\Test\OBJ"
LOG_FILE   = r"D:\ZherlitsynEE\SaveFormatTest\Test\export_log.txt"

INPUT_DIR  = os.environ.get("PRT_DIR", INPUT_DIR)
OUTPUT_DIR = os.environ.get("OBJ_DIR", OUTPUT_DIR)
LOG_FILE   = os.environ.get("LOG_FILE", LOG_FILE)


def log_line(f, msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    f.write(line + "\n")
    f.flush()


def main():
    
    start_all = time.time()

    # Открываем лог сразу
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        log_line(logf, "=== START EXPORT PRT -> OBJ ===")
        log_line(logf, f"INPUT_DIR = {INPUT_DIR}")
        log_line(logf, f"OUTPUT_DIR = {OUTPUT_DIR}")

        if not os.path.isdir(INPUT_DIR):
            log_line(logf, f"ERROR: INPUT_DIR does not exist: {INPUT_DIR}")
            return

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # NX Session
        theSession = NXOpen.Session.GetSession()

        # Создаём creator один раз
        objCreator = theSession.DexManager.CreateWavefrontObjCreator()
        objCreator.ExportFrom = NXOpen.WavefrontObjCreator.ExportFromOption.ExistingPart
        objCreator.AngularTolerance = 44.0
        objCreator.FlattenAssemblyStructure = True
        objCreator.FileSaveFlag = False

        count_ok = 0
        count_fail = 0
        failed = []

        files = sorted(os.listdir(INPUT_DIR))
        prt_files = [fn for fn in files if fn.lower().endswith(".prt")]

        log_line(logf, f"Found {len(prt_files)} .prt files")

        for i, fname in enumerate(prt_files, start=1):
            prt_path = os.path.join(INPUT_DIR, fname)
            base = os.path.splitext(fname)[0]
            obj_path = os.path.join(OUTPUT_DIR, base + ".obj")

            # (опционально) пропуск уже существующих
            if os.path.exists(obj_path):
                log_line(logf, f"[{i}/{len(prt_files)}] SKIP exists: {fname}")
                continue

            t0 = time.time()
            try:
                objCreator.InputFile = prt_path
                objCreator.OutputFile = obj_path
                objCreator.Commit()

                dt = time.time() - t0
                count_ok += 1
                log_line(logf, f"[{i}/{len(prt_files)}] OK  {fname} -> {os.path.basename(obj_path)}  ({dt:.2f}s)")

            except Exception as e:
                dt = time.time() - t0
                count_fail += 1
                failed.append(fname)

                log_line(logf, f"[{i}/{len(prt_files)}] FAIL {fname} ({dt:.2f}s)  err={repr(e)}")
                # Полный traceback в лог (очень полезно)
                logf.write(traceback.format_exc() + "\n")
                logf.flush()

        # Чистим creator
        objCreator.Destroy()

        total_dt = time.time() - start_all
        log_line(logf, "=== FINISH ===")
        log_line(logf, f"OK: {count_ok}")
        log_line(logf, f"FAIL: {count_fail}")
        log_line(logf, f"Total time: {total_dt:.2f}s")

        if failed:
            log_line(logf, "Failed files list:")
            for fn in failed:
                log_line(logf, f"  - {fn}")

        log_line(logf, "=== END EXPORT ===")


if __name__ == "__main__":
    main()
