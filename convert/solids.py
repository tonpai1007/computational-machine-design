"""CAD solid conversion.

Two tiers:

* **Mesh formats** (STL, OBJ, 3MF) are converted in pure Python. They are all
  triangle soups, so translating between them is exact and needs no kernel.
* **B-rep formats** (STEP, IGES, IGES) need a real geometry kernel. When
  FreeCAD is installed it is driven headlessly; otherwise the converter raises
  a clear error naming the tool it looked for.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

Triangle = tuple
Vec = tuple

MESH_FORMATS = {"stl", "obj", "3mf"}
BREP_FORMATS = {"step", "iges"}
KERNEL_FORMATS = MESH_FORMATS | BREP_FORMATS | {"scad"}

# Windows: keep the kernel's console window from flashing up.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ConversionError(RuntimeError):
    """Raised when a conversion cannot be performed."""


# ------------------------------------------------------------------- STL I/O


def read_stl(path: Path) -> list[Triangle]:
    """Read binary or ASCII STL into triangles."""
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        expected = 84 + count * 50
        if expected == len(data):
            return _read_binary_stl(data, count)
    return _read_ascii_stl(data)


def _read_binary_stl(data: bytes, count: int) -> list[Triangle]:
    tris: list[Triangle] = []
    for i in range(count):
        off = 84 + i * 50
        vals = struct.unpack_from("<12f", data, off)
        tris.append(
            (
                (vals[3], vals[4], vals[5]),
                (vals[6], vals[7], vals[8]),
                (vals[9], vals[10], vals[11]),
            )
        )
    return tris


def _read_ascii_stl(data: bytes) -> list[Triangle]:
    tris: list[Triangle] = []
    verts: list[Vec] = []
    for raw in data.decode("utf-8", errors="replace").splitlines():
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "vertex":
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            if len(verts) == 3:
                tris.append((verts[0], verts[1], verts[2]))
                verts.clear()
        elif parts[0] == "endloop":
            verts.clear()
    if not tris:
        raise ConversionError("no triangles found in STL")
    return tris


def write_stl(path: Path, tris: list[Triangle], binary: bool = True) -> Path:
    """Write triangles as binary or ASCII STL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        header = b"MDIE STL export".ljust(80, b"\0")
        chunks = [header, struct.pack("<I", len(tris))]
        for tri in tris:
            normal = triangle_normal(tri)
            chunks.append(struct.pack("<3f", *normal))
            for v in tri:
                chunks.append(struct.pack("<3f", *v))
            chunks.append(struct.pack("<H", 0))
        path.write_bytes(b"".join(chunks))
    else:
        lines = ["solid mdie"]
        for tri in tris:
            lines.append(f"  facet normal {tri[0][0]:.6g} {tri[0][1]:.6g} {tri[0][2]:.6g}")
            lines.append("    outer loop")
            for v in tri:
                lines.append(f"      vertex {v[0]:.6g} {v[1]:.6g} {v[2]:.6g}")
            lines.append("    endloop")
            lines.append("  endfacet")
        lines.append("endsolid mdie")
        path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ------------------------------------------------------------------- OBJ I/O


def read_obj(path: Path) -> list[Triangle]:
    verts: list[Vec] = []
    tris: list[Triangle] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "f":
            idx = [int(p.split("/")[0]) for p in parts[1:]]
            for k in range(1, len(idx) - 1):
                tris.append((verts[idx[0] - 1], verts[idx[k] - 1], verts[idx[k + 1] - 1]))
    return tris


def write_obj(path: Path, tris: list[Triangle]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MDIE OBJ export"]
    for tri in tris:
        for v in tri:
            lines.append(f"v {v[0]:.6g} {v[1]:.6g} {v[2]:.6g}")
    for i in range(0, len(tris)):
        b = i * 3 + 1
        lines.append(f"f {b} {b + 1} {b + 2}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ------------------------------------------------------------------- 3MF I/O

_3MF_MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
 xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model">
   <mesh>
    <vertices>
{v}
    </vertices>
    <triangles>
{f}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build>
  <item objectid="1"/>
 </build>
</model>
"""

_3MF_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

_3MF_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0"
  Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def write_3mf(path: Path, tris: list[Triangle]) -> Path:
    verts = [v for tri in tris for v in tri]
    v_xml = "\n".join(
        f'      <vertex x="{v[0]:.6g}" y="{v[1]:.6g}" z="{v[2]:.6g}"/>' for v in verts
    )
    f_xml = "\n".join(
        f'      <triangle v1="{i * 3}" v2="{i * 3 + 1}" v3="{i * 3 + 2}"/>'
        for i in range(len(tris))
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _3MF_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _3MF_RELS)
        zf.writestr("3D/3dmodel.model", _3MF_MODEL.format(v=v_xml, f=f_xml))
    return path


def read_3mf(path: Path) -> list[Triangle]:
    import re

    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".model"))
        xml = zf.read(name).decode("utf-8", errors="replace")

    verts: list[Vec] = [
        (float(x), float(y), float(z))
        for x, y, z in re.findall(
            r'<vertex[^>]*x="([-\d.eE+]+)"[^>]*y="([-\d.eE+]+)"[^>]*z="([-\d.eE+]+)"', xml
        )
    ]
    tris: list[Triangle] = []
    for a, b, c in re.findall(r'<triangle[^>]*v1="(\d+)"[^>]*v2="(\d+)"[^>]*v3="(\d+)"', xml):
        try:
            tris.append((verts[int(a)], verts[int(b)], verts[int(c)]))
        except IndexError:
            continue
    if not tris:
        raise ConversionError("no triangles found in 3MF")
    return tris


# --------------------------------------------------------------- mesh helpers


def triangle_normal(tri: Triangle) -> Vec:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    mag = (nx * nx + ny * ny + nz * nz) ** 0.5
    return (0.0, 0.0, 0.0) if mag == 0 else (nx / mag, ny / mag, nz / mag)


def mesh_bounds(tris: list[Triangle]) -> tuple[Vec, Vec]:
    pts = [v for tri in tris for v in tri]
    if not pts:
        raise ConversionError("empty mesh")
    lo = tuple(min(p[i] for p in pts) for i in range(3))
    hi = tuple(max(p[i] for p in pts) for i in range(3))
    return lo, hi


READERS = {"stl": read_stl, "obj": read_obj, "3mf": read_3mf}
WRITERS = {"stl": write_stl, "obj": write_obj, "3mf": write_3mf}


def convert_mesh(src: Path, src_format: str, dst: Path, dst_format: str) -> Path:
    """Convert between STL/OBJ/3MF in pure Python."""
    if src_format not in READERS:
        raise ConversionError(f"cannot read '{src_format}' meshes")
    if dst_format not in WRITERS:
        raise ConversionError(f"cannot write '{dst_format}' meshes")
    tris = READERS[src_format](src)
    return WRITERS[dst_format](dst, tris)


# ----------------------------------------------------------- kernel-backed path

#: Console-mode binaries only. FreeCAD's GUI executable opens a window and can
#: block forever on a modal dialog, so it must never be driven headlessly.
_KERNEL_BINARIES = ("freecadcmd", "freecadcmd.exe", "FreeCADCmd", "FreeCADCmd.exe")


def find_kernel() -> str | None:
    """Locate FreeCAD's *console* binary, or ``None`` if it is absent.

    Deliberately does not fall back to ``FreeCAD.exe``: launching the GUI
    build from a script pops a window and hangs the caller.
    """
    for name in _KERNEL_BINARIES:
        found = shutil.which(name)
        if found:
            return found

    from cli.viewers import find_cad_tools

    gui = find_cad_tools().get("freecad")
    if gui:
        sibling = Path(gui).parent / "FreeCADCmd.exe"
        if sibling.exists():
            return str(sibling)
    return None


# Paths travel by environment variable, not argv: FreeCADCmd sets sys.argv[0]
# to its own executable, so positional indexes are easy to get wrong.
_KERNEL_SCRIPT = """
import os
import FreeCAD
import Part
import Mesh

src = os.environ["MDIE_SRC"]
dst = os.environ["MDIE_DST"]
shape = Part.Shape()
shape.read(src)
# STEP assemblies arrive as B-rep faces, so tessellate before building a mesh.
verts, facets = shape.tessellate(0.02)
triangles = [[verts[i] for i in facet] for facet in facets]
Mesh.Mesh(triangles).write(dst)
"""


def convert_via_kernel(src: Path, dst: Path, dst_format: str, timeout: int = 300) -> Path:
    """Convert a B-rep or SCAD file to a mesh format.

    SCAD goes through OpenSCAD; STEP/IGES go through FreeCAD's console binary.
    Both calls are bounded by ``timeout`` so a wedged external tool cannot hang
    the CLI.
    """
    if src.suffix.lower() == ".scad":
        return convert_scad(src, dst, dst_format, timeout=timeout)

    kernel = find_kernel()
    if not kernel:
        raise ConversionError(
            f"converting '{src.suffix}' needs a geometry kernel. Install FreeCAD "
            "(its console binary FreeCADCmd.exe) and make sure it is on PATH."
        )
    if dst_format not in MESH_FORMATS:
        raise ConversionError(
            f"FreeCAD cannot export '{dst_format}' here; use one of {sorted(MESH_FORMATS)}"
        )

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "_convert.py"
        staged = Path(tmp) / "out.stl"
        script.write_text(_KERNEL_SCRIPT, encoding="utf-8")
        env = {**os.environ, "MDIE_SRC": str(src.resolve()), "MDIE_DST": str(staged.resolve())}
        try:
            proc = subprocess.run(
                [kernel, str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_NO_WINDOW,
                env=env,
            )
        except subprocess.TimeoutExpired:
            raise ConversionError(
                f"FreeCAD did not finish within {timeout}s; "
                "the kernel hung or the model is too large to tessellate"
            )
        if not staged.exists():
            raise ConversionError(
                "FreeCAD produced no mesh: "
                + (proc.stderr.strip() or proc.stdout.strip() or "no diagnostics")
            )

        # Finish inside the temp directory - it is removed on the way out.
        if dst_format == "stl":
            shutil.copyfile(staged, dst)
            return dst
        return WRITERS[dst_format](dst, read_stl(staged))


def find_openscad() -> str | None:
    """Locate the OpenSCAD command-line binary, or ``None``."""
    for name in ("openscad", "openscad.com", "openscad.exe"):
        found = shutil.which(name)
        if found:
            return found
    from cli.viewers import find_cad_tools

    return find_cad_tools().get("openscad")


def convert_scad(src: Path, dst: Path, dst_format: str, timeout: int = 300) -> Path:
    """Render an OpenSCAD source file with OpenSCAD's CLI.

    OpenSCAD always emits STL; other mesh targets are finished in pure Python.
    """
    if dst_format not in MESH_FORMATS:
        raise ConversionError(
            f"OpenSCAD cannot export '{dst_format}'; use one of {sorted(MESH_FORMATS)}"
        )
    binary = find_openscad()
    if not binary:
        raise ConversionError(
            f"converting '{src.suffix}' needs OpenSCAD. Install it and make sure it is on PATH."
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "out.stl"
        try:
            proc = subprocess.run(
                [binary, "-o", str(staged), str(src)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            raise ConversionError(f"OpenSCAD did not finish within {timeout}s")
        if not staged.exists():
            raise ConversionError(
                "OpenSCAD produced no mesh: "
                + (proc.stderr.strip() or proc.stdout.strip() or "no diagnostics")
            )
        if dst_format == "stl":
            shutil.copyfile(staged, dst)
            return dst
        return WRITERS[dst_format](dst, read_stl(staged))


def describe_mesh(path: Path) -> str:
    """Human-readable summary of a mesh file: bounds, triangle count, extents."""
    from convert.registry import format_for_extension

    fmt = format_for_extension(path)
    if fmt not in READERS:
        raise ConversionError(f"cannot inspect '{path.name}'")
    tris = READERS[fmt](path)
    lo, hi = mesh_bounds(tris)
    size = tuple(hi[i] - lo[i] for i in range(3))
    return (
        f"{path.name}: {len(tris)} triangles, "
        f"bounds {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f} mm "
        f"(origin {lo[0]:.3f}, {lo[1]:.3f}, {lo[2]:.3f})"
    )
