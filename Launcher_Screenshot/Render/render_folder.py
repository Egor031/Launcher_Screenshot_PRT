import argparse
import time
import traceback
from pathlib import Path

import numpy as np
import trimesh
import pyrender
from PIL import Image


# ---------------- ARGPARSE ----------------

def parse_args():
    ap = argparse.ArgumentParser(
        description="Batch render OBJ -> PNG views (orthographic like NX) with logging."
    )

    ap.add_argument("--input", required=True,
                    help="Input folder with .obj files (searched recursively).")

    ap.add_argument("--output", required=True,
                    help="Output folder for PNGs.")

    ap.add_argument("--log", default=None,
                    help="Log file path (default: output/render_log.txt)")

    ap.add_argument("--w", type=int, default=1280,
                    help="Output image width (default: 1280).")

    ap.add_argument("--h", type=int, default=720,
                    help="Output image height (default: 720).")

    ap.add_argument("--margin", type=float, default=1.20,
                    help="Extra margin around object (>=1.0). Default: 1.20")

    ap.add_argument(
        "--views",
        default="Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric",
        help="Comma-separated views. Allowed: "
             "Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric"
    )

    ap.add_argument("--overwrite", action="store_true",
                    help="Overwrite existing PNG files.")

    ap.add_argument("--bg", type=float, default=0.95,
                    help="Background gray level in [0..1]. Default: 0.95")

    ap.add_argument("--edges", action="store_true",
                    help="Overlay triangle wireframe (DEBUG only). "
                         "Shows mesh triangles, NOT CAD feature edges.")

    return ap.parse_args()


# ---------------- LOGGING ----------------

def log_line(f, msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    f.write(line + "\n")
    f.flush()


# ---------------- GEOMETRY ----------------

def normalize_mesh(mesh: trimesh.Trimesh) -> None:
    """Center mesh and scale so max extent = 1.0"""
    center = mesh.bounds.mean(axis=0)
    max_extent = float(mesh.extents.max())
    mesh.apply_translation(-center)
    mesh.apply_scale(1.0 / (max_extent + 1e-9))


def camera_pose(view: str) -> np.ndarray:
    target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    D = 10.0

    if view == "Front":        eye = np.array([0.0, 0.0, +D])
    elif view == "Back":       eye = np.array([0.0, 0.0, -D])
    elif view == "Right":      eye = np.array([+D, 0.0, 0.0])
    elif view == "Left":       eye = np.array([-D, 0.0, 0.0])
    elif view == "Top":        eye = np.array([0.0, +D, 0.0])
    elif view == "Bottom":     eye = np.array([0.0, -D, 0.0])
    elif view == "Isometric":  eye = np.array([+D, +D, +D])
    elif view == "Trimetric":  eye = np.array([+D, 0.65 * D, 1.05 * D])
    else:
        raise ValueError(f"Unknown view: {view}")

    up = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    forward = (target - eye)
    forward /= (np.linalg.norm(forward) + 1e-12)

    if abs(np.dot(forward, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    right = np.cross(forward, up)
    right /= (np.linalg.norm(right) + 1e-12)

    true_up = np.cross(right, forward)
    true_up /= (np.linalg.norm(true_up) + 1e-12)

    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = true_up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye

    return pose


def compute_ortho_mag_for_view(mesh: trimesh.Trimesh,
                               view: str,
                               aspect: float,
                               margin: float) -> tuple[float, float]:

    corners = trimesh.bounds.corners(mesh.bounds)
    T_cw = camera_pose(view)
    T_wc = np.linalg.inv(T_cw)

    corners_h = np.hstack([corners, np.ones((8, 1))])
    cam_pts = (T_wc @ corners_h.T).T[:, :3]

    xs = cam_pts[:, 0]
    ys = cam_pts[:, 1]

    half_w = max(0.5 * (xs.max() - xs.min()), 1e-6)
    half_h = max(0.5 * (ys.max() - ys.min()), 1e-6)

    half_w *= margin
    half_h *= margin

    obj_aspect = half_w / half_h

    if obj_aspect >= aspect:
        xmag = half_w
        ymag = half_w / aspect
    else:
        ymag = half_h
        xmag = half_h * aspect

    return xmag, ymag


# ---------------- SCENE ----------------

def build_scene(bg_gray: float):
    bg = float(np.clip(bg_gray, 0.0, 1.0))

    scene = pyrender.Scene(
        bg_color=[bg, bg, bg],
        ambient_light=[0.12, 0.12, 0.12]
    )

    camera = pyrender.OrthographicCamera(xmag=1.0, ymag=1.0)
    cam_node = scene.add(camera, pose=np.eye(4))

    key_pose = np.eye(4);  key_pose[:3, 3] = [2, 2, 3]
    fill_pose = np.eye(4); fill_pose[:3, 3] = [-3, 0, 2]
    back_pose = np.eye(4); back_pose[2, 3] = -3

    scene.add(pyrender.DirectionalLight(color=[1,1,1], intensity=6.5), pose=key_pose)
    scene.add(pyrender.DirectionalLight(color=[1,1,1], intensity=1.2), pose=fill_pose)
    scene.add(pyrender.DirectionalLight(color=[1,1,1], intensity=0.8), pose=back_pose)

    return scene, cam_node, camera


# ---------------- MAIN ----------------

def main():
    args = parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = Path(args.log) if args.log else output_dir / "render_log.txt"

    allowed = {"Front","Back","Right","Left","Top","Bottom","Isometric","Trimetric"}
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    for v in views:
        if v not in allowed:
            raise ValueError(f"Unknown view '{v}'")

    with open(log_path, "a", encoding="utf-8") as logf:

        log_line(logf, "=== START OBJ -> PNG RENDER ===")
        log_line(logf, f"INPUT_DIR = {input_dir}")
        log_line(logf, f"OUTPUT_DIR = {output_dir}")
        log_line(logf, f"EDGES (triangle debug) = {args.edges}")

        obj_files = sorted(input_dir.rglob("*.obj"))
        log_line(logf, f"Found {len(obj_files)} OBJ files")

        if not obj_files:
            log_line(logf, "No OBJ files found.")
            return

        renderer = pyrender.OffscreenRenderer(args.w, args.h)
        scene, cam_node, camera = build_scene(args.bg)

        aspect = args.w / args.h

        base_mat = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.6,0.6,0.6,1],
            metallicFactor=0,
            roughnessFactor=0.9,
            doubleSided=True
        )

        edge_mat = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.05,0.05,0.05,1],
            metallicFactor=0,
            roughnessFactor=1.0,
            doubleSided=True
        )
        ok = 0
        fail = 0
        skipped_total = 0
        start_all = time.time()

        for idx, obj_path in enumerate(obj_files, start=1):

            try:
                part_id = obj_path.stem

                try:
                    rel_dir = obj_path.parent.relative_to(input_dir)
                except ValueError:
                    rel_dir = Path()

                part_dir = output_dir / rel_dir / part_id
                part_dir.mkdir(parents=True, exist_ok=True)

                mesh = trimesh.load(str(obj_path), force="mesh")
                if mesh.is_empty:
                    raise RuntimeError("Empty mesh")

                normalize_mesh(mesh)

                mesh_node = scene.add(
                    pyrender.Mesh.from_trimesh(mesh, material=base_mat, smooth=True)
                )

                wire_node = None
                if args.edges:
                    wire_node = scene.add(
                        pyrender.Mesh.from_trimesh(
                            mesh,
                            material=edge_mat,
                            smooth=False,
                            wireframe=True
                        )
                    )

                saved_here = 0
                skipped_here = 0
                t0 = time.time()

                for v in views:

                    out_png = part_dir / f"{part_id}_{v}.png"
                    if out_png.exists() and not args.overwrite:
                        skipped_here += 1
                        continue



                    xmag, ymag = compute_ortho_mag_for_view(mesh, v, aspect, args.margin)
                    camera.xmag = xmag
                    camera.ymag = ymag

                    scene.set_pose(cam_node, pose=camera_pose(v))

                    color, _ = renderer.render(
                        scene,
                        flags=pyrender.RenderFlags.SKIP_CULL_FACES
                    )

                    Image.fromarray(color).save(out_png)
                    saved_here += 1

                scene.remove_node(mesh_node)
                if wire_node:
                    scene.remove_node(wire_node)
                dt = time.time() - t0
                ok += 1
                skipped_total += skipped_here

                log_line(
                    logf,
                    f"[{idx}/{len(obj_files)}] OK {obj_path.name} "
                    f"({dt:.2f}s) saved={saved_here} skipped={skipped_here}"
                )


            except Exception as e:
                log_line(logf, f"[{idx}/{len(obj_files)}] FAIL {obj_path.name}")
                logf.write(traceback.format_exc() + "\n")
                fail += 1
        
        total = time.time() - start_all
        log_line(logf, "=== FINISH ===")
        log_line(logf, f"OK files: {ok}")
        log_line(logf, f"FAIL files: {fail}")
        log_line(logf, f"SKIPPED PNG total: {skipped_total}")
        log_line(logf, f"Total time: {total:.2f}s")

        renderer.delete()
        log_line(logf, "=== END ===")


if __name__ == "__main__":
    main()
