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
    ap = argparse.ArgumentParser(description="Batch render OBJ -> PNG views (orthographic like NX) + logging.")
    ap.add_argument("--input", required=True, help="Input folder with .obj files (searched recursively).")
    ap.add_argument("--output", required=True, help="Output folder for PNGs.")
    ap.add_argument("--log", default=None, help="Log file path (default: output/render_log.txt)")
    ap.add_argument("--w", type=int, default=1280, help="Output image width.")
    ap.add_argument("--h", type=int, default=720, help="Output image height.")
    ap.add_argument("--margin", type=float, default=1.20, help="Extra margin around object (>=1.0).")
    ap.add_argument(
        "--views",
        default="Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric",
        help="Comma-separated views. Allowed: Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric"
    )
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing PNGs.")
    ap.add_argument("--bg", type=float, default=0.95, help="Background gray level in [0..1]. (0=black,1=white)")
    ap.add_argument("--edges", action="store_true", help="Overlay edges (wireframe) like NX 'Shaded with Edges'.")
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
    """Center + scale so that max extent becomes 1.0 (stable across parts)."""
    center = mesh.bounds.mean(axis=0)
    max_extent = float(mesh.extents.max())
    mesh.apply_translation(-center)
    mesh.apply_scale(1.0 / (max_extent + 1e-9))


def camera_pose(view: str) -> np.ndarray:
    """
    Camera->world pose for orthographic rendering.
    Distance does not affect scale in orthographic projection, so we use fixed 'eye' distances.
    """
    target = np.array([0.0, 0.0, 0.0], dtype=np.float64)

    # Fixed distance (any "large enough" value is fine for ortho)
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
    forward = forward / (np.linalg.norm(forward) + 1e-12)

    # Avoid degenerate up (parallel to forward)
    if abs(np.dot(forward, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    right = np.cross(forward, up)
    right = right / (np.linalg.norm(right) + 1e-12)

    true_up = np.cross(right, forward)
    true_up = true_up / (np.linalg.norm(true_up) + 1e-12)

    # Camera looks along -Z, so column 2 is -forward
    pose = np.eye(4, dtype=np.float64)
    pose[:3, 0] = right
    pose[:3, 1] = true_up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye
    return pose


def compute_ortho_mag_for_view(mesh: trimesh.Trimesh, view: str, aspect: float, margin: float):
    """
    Fit-to-view для ортографической камеры: подбирает xmag/ymag так,
    чтобы деталь целиком влезла в кадр для данного вида (включая Isometric/Trimetric).
    """
    corners = trimesh.bounds.corners(mesh.bounds)  # (8,3)

    T_cw = camera_pose(view)
    T_wc = np.linalg.inv(T_cw)

    corners_h = np.hstack([corners, np.ones((corners.shape[0], 1))])  # (8,4)
    cam_pts = (T_wc @ corners_h.T).T[:, :3]  # (8,3)

    xs = cam_pts[:, 0]
    ys = cam_pts[:, 1]

    half_w = 0.5 * (xs.max() - xs.min())
    half_h = 0.5 * (ys.max() - ys.min())

    half_w = max(float(half_w), 1e-6)
    half_h = max(float(half_h), 1e-6)

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


# ---------------- RENDER SETUP ----------------

def build_scene(bg_gray: float):
    bg = float(bg_gray)
    bg = 0.0 if bg < 0.0 else (1.0 if bg > 1.0 else bg)

    scene = pyrender.Scene(bg_color=[bg, bg, bg], ambient_light=[0.12, 0.12, 0.12])

    camera = pyrender.OrthographicCamera(xmag=1.0, ymag=1.0)
    cam_node = scene.add(camera, pose=np.eye(4))

    key_pose = np.eye(4);  key_pose[0, 3] = 2.0; key_pose[1, 3] = 2.0; key_pose[2, 3] = 3.0
    fill_pose = np.eye(4); fill_pose[0, 3] = -3.0; fill_pose[2, 3] = 2.0
    back_pose = np.eye(4); back_pose[2, 3] = -3.0

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

    allowed = {"Front", "Back", "Right", "Left", "Top", "Bottom", "Isometric", "Trimetric"}
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    for v in views:
        if v not in allowed:
            raise ValueError(f"Unknown view '{v}'. Allowed: {sorted(allowed)}")

    with open(log_path, "a", encoding="utf-8") as logf:
        start_all = time.time()

        log_line(logf, "=== START OBJ -> PNG RENDER (ORTHO) ===")
        log_line(logf, f"INPUT_DIR = {input_dir}")
        log_line(logf, f"OUTPUT_DIR = {output_dir}")
        log_line(logf, f"VIEWS = {views}")
        log_line(logf, f"RESOLUTION = {args.w}x{args.h}")
        log_line(logf, f"MARGIN = {args.margin}")
        log_line(logf, f"BG_GRAY = {args.bg}")
        log_line(logf, f"OVERWRITE = {args.overwrite}")
        log_line(logf, f"EDGES = {args.edges}")

        obj_files = sorted(input_dir.rglob("*.obj"))
        log_line(logf, f"Found {len(obj_files)} OBJ files")

        if not obj_files:
            log_line(logf, "No OBJ files found. Exit.")
            return

        w, h = args.w, args.h
        aspect = w / h

        renderer = pyrender.OffscreenRenderer(w, h)
        scene, cam_node, camera = build_scene(args.bg)

        ok = 0
        fail = 0
        skipped_total = 0

        # Materials (stable across parts)
        base_mat = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.60, 0.60, 0.60, 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.9,
            doubleSided=True
        )
        edge_mat = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.06, 0.06, 0.06, 1.0],
            metallicFactor=0.0,
            roughnessFactor=1.0,
            doubleSided=True
        )

        for idx, obj_path in enumerate(obj_files, start=1):
            part_id = obj_path.stem
            part_dir = output_dir / part_id
            part_dir.mkdir(parents=True, exist_ok=True)

            t0 = time.time()

            mesh_node = None
            wire_node = None

            try:
                mesh = trimesh.load(str(obj_path), force="mesh")
                if mesh.is_empty:
                    raise RuntimeError("empty mesh")

                normalize_mesh(mesh)

                # Base shaded mesh
                pr_mesh = pyrender.Mesh.from_trimesh(mesh, material=base_mat, smooth=True)
                mesh_node = scene.add(pr_mesh)

                # Optional edges overlay
                if args.edges:
                    pr_wire = pyrender.Mesh.from_trimesh(
                        mesh,
                        material=edge_mat,
                        smooth=False,
                        wireframe=True
                    )
                    wire_node = scene.add(pr_wire)

                skipped_here = 0

                for v in views:
                    out_png = part_dir / f"{part_id}_{v}.png"
                    if out_png.exists() and not args.overwrite:
                        skipped_here += 1
                        continue

                    # Fit per view
                    xmag, ymag = compute_ortho_mag_for_view(mesh, v, aspect, args.margin)
                    camera.xmag = xmag
                    camera.ymag = ymag

                    scene.set_pose(cam_node, pose=camera_pose(v))

                    # Important: disable face culling so inner faces of holes don't disappear
                    flags = pyrender.RenderFlags.SKIP_CULL_FACES
                    color, _ = renderer.render(scene, flags=flags)
                    Image.fromarray(color).save(out_png)

                # Cleanup nodes
                if wire_node is not None:
                    scene.remove_node(wire_node)
                if mesh_node is not None:
                    scene.remove_node(mesh_node)

                dt = time.time() - t0
                ok += 1
                skipped_total += skipped_here

                log_line(
                    logf,
                    f"[{idx}/{len(obj_files)}] OK  {obj_path.name} ({dt:.2f}s) "
                    f"saved={len(views)-skipped_here} skipped={skipped_here}"
                )

            except Exception as e:
                # Best-effort cleanup
                try:
                    if wire_node is not None:
                        scene.remove_node(wire_node)
                except Exception:
                    pass
                try:
                    if mesh_node is not None:
                        scene.remove_node(mesh_node)
                except Exception:
                    pass

                dt = time.time() - t0
                fail += 1
                log_line(logf, f"[{idx}/{len(obj_files)}] FAIL {obj_path.name} ({dt:.2f}s) err={repr(e)}")
                logf.write(traceback.format_exc() + "\n")
                logf.flush()

        renderer.delete()

        total = time.time() - start_all
        log_line(logf, "=== FINISH ===")
        log_line(logf, f"OK: {ok}")
        log_line(logf, f"FAIL: {fail}")
        log_line(logf, f"SKIPPED PNG (already existed): {skipped_total}")
        log_line(logf, f"Total time: {total:.2f}s")
        log_line(logf, "=== END ===")


if __name__ == "__main__":
    main()
