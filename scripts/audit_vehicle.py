#!/usr/bin/env python3
"""Read-only checks for legacy cube/bone .bbmodels; not a renderer or physics test."""
import argparse
import base64
from collections import Counter
import json
import math
from pathlib import Path
import struct


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def graph(model):
    groups = {g["uuid"]: g for g in model.get("groups", [])}
    parents, refs = {}, []

    def walk(items, parent=None):
        for item in items:
            uid = item if isinstance(item, str) else item["uuid"]
            refs.append(uid)
            parents[uid] = parent
            if isinstance(item, dict):
                if uid not in groups and "name" in item:
                    groups[uid] = item
                walk(item.get("children", []), uid)
    walk(model.get("outliner", []))
    return groups, parents, refs


def rotate(point, angles):
    """ZYX Euler composition: apply X, then Y, then Z (radians internally)."""
    x, y, z = point
    a, b, c = map(math.radians, angles)
    y, z = y*math.cos(a)-z*math.sin(a), y*math.sin(a)+z*math.cos(a)
    x, z = x*math.cos(b)+z*math.sin(b), -x*math.sin(b)+z*math.cos(b)
    x, y = x*math.cos(c)-y*math.sin(c), x*math.sin(c)+y*math.cos(c)
    return [x, y, z]


def world_point(model, bone, point):
    groups, parents, _ = graph(model)
    if bone not in groups:
        matches = [g["uuid"] for g in groups.values() if g.get("name") == bone]
        if len(matches) != 1:
            raise ValueError("bone must be a UUID or unique name: " + str(bone))
        bone = matches[0]
    point, seen = list(point), set()
    if len(point) != 3 or not all(math.isfinite(v) for v in point):
        raise ValueError("point must have three finite coordinates")
    while bone is not None:
        if bone in seen:
            raise ValueError("cycle in bone chain")
        seen.add(bone)
        if bone not in groups:
            raise ValueError("missing parent bone: " + str(bone))
        g = groups[bone]
        if g.get("scale", [1, 1, 1]) != [1, 1, 1]:
            raise ValueError("scaled bones are unsupported by endpoint checks")
        pivot = g.get("origin", [0, 0, 0])
        point = rotate([point[i]-pivot[i] for i in range(3)], g.get("rotation", [0, 0, 0]))
        point = [point[i]+pivot[i] for i in range(3)]
        bone = parents.get(bone)
    return point


def embedded_png(texture):
    src = texture.get("source", "")
    if not src.startswith("data:image/png;base64,"):
        raise ValueError("embedded PNG data is required for this audit")
    data = base64.b64decode(src.split(",", 1)[1], validate=True)
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    return data, struct.unpack(">II", data[16:24])


def audit(model, joints=None, external_png=None):
    errors, warnings, checked_joints, sizes = [], [], [], []
    if model.get("meta", {}).get("model_format") != "bedrock_old":
        errors.append("format is not bedrock_old; review target instead of converting silently")
    elements = model.get("elements", [])
    groups, parents, refs = graph(model)
    ids = [e.get("uuid") for e in elements] + list(groups)
    # Flat groups can have duplicate IDs even though graph lookup normalizes them.
    raw_group_ids = [g.get("uuid") for g in model.get("groups", [])]
    for uid, count in Counter(ids + raw_group_ids).items():
        expected = 2 if uid in groups and uid in raw_group_ids else 1
        if count > expected or uid is None:
            errors.append("duplicate or missing UUID: " + str(uid))
    names = Counter(g.get("name") for g in groups.values())
    for name, count in names.items():
        if count > 1 or not name:
            errors.append("duplicate or missing bone name: " + str(name))
    known = set(ids)
    for uid in refs:
        if uid not in known:
            errors.append("missing outliner reference: " + str(uid))
    for uid, count in Counter(refs).items():
        if count > 1:
            errors.append("duplicate outliner reference: " + str(uid))
    for uid in known - set(refs):
        errors.append("unparented element/group: " + str(uid))
    for uid in groups:
        try:
            world_point(model, uid, groups[uid].get("origin", [0, 0, 0]))
        except ValueError as exc:
            errors.append(str(exc))
    textures = model.get("textures", [])
    if len(textures) != 1:
        errors.append("expected one vehicle atlas, found " + str(len(textures)))
    for t in textures:
        try:
            raw, (w, h) = embedded_png(t)
            sizes.append([w, h])
            if min(w, h) <= 0 or max(w, h) > 128:
                errors.append("PNG exceeds 128x128 or has zero dimensions")
            if (t.get("width", w), t.get("height", h)) != (w, h):
                errors.append("PNG size differs from texture metadata")
            if external_png is not None and raw != Path(external_png).read_bytes():
                errors.append("embedded/external PNG bytes differ")
        except (ValueError, OSError) as exc:
            errors.append("PNG: " + str(exc))
    res = model.get("resolution", {})
    for e in elements:
        kind = e.get("type", "cube")
        if kind not in ("cube", "locator"):
            errors.append("non-Cube geometry: " + str(e.get("name", kind)))
        if kind != "cube":
            continue
        if any(abs(v) > 1e-8 for v in e.get("rotation", [0, 0, 0])):
            errors.append("Cube rotation must be on a bone: " + str(e.get("name")))
        for key in ("from", "to"):
            if len(e.get(key, [])) != 3 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in e.get(key, [])):
                errors.append("invalid Cube coordinates: " + str(e.get("name")))
        if not e.get("faces"):
            errors.append("UV unavailable; Box UV must be evaluated in Blockbench: " + str(e.get("name")))
        for face in e.get("faces", {}).values():
            if face.get("texture") is None:
                continue
            ref = face["texture"]
            if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
                index = int(ref)
                t = textures[index] if 0 <= index < len(textures) else None
            else:
                t = next((t for t in textures if t.get("uuid") == ref), None)
            if t is None:
                errors.append("missing face texture: " + str(e.get("name")))
                continue
            uw, uh = t.get("uv_width", res.get("width")), t.get("uv_height", res.get("height"))
            uv = face.get("uv", [])
            if not uw or not uh or len(uv) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in uv):
                errors.append("UV cannot be checked: " + str(e.get("name")))
            elif not all(-1e-6 <= v <= (uw if i % 2 == 0 else uh)+1e-6 for i, v in enumerate(uv)):
                errors.append("UV out of range: " + str(e.get("name")))
    for joint in joints or []:
        name = joint.get("name", "joint")
        try:
            tolerance = joint.get("tolerance", 1e-4)
            if not math.isfinite(tolerance) or tolerance < 0:
                raise ValueError("invalid joint tolerance")
            a = world_point(model, joint["a"]["bone"], joint["a"]["point"])
            b = world_point(model, joint["b"]["bone"], joint["b"]["point"])
            gap = math.dist(a, b)
            checked_joints.append({"name": name, "gap": gap, "tolerance": tolerance, "a": a, "b": b})
            if gap > tolerance:
                errors.append("joint " + name + " gap exceeds tolerance")
        except (KeyError, ValueError, TypeError) as exc:
            errors.append("joint " + name + ": " + str(exc))
    if any(t.get("layers_enabled") for t in textures):
        warnings.append("active layers: final painted composite needs native verification")
    return {"format": model.get("meta", {}).get("model_format"),
            "cubes": sum(e.get("type", "cube") == "cube" for e in elements),
            "bones": len(groups), "png_sizes": sizes, "joints": checked_joints,
            "errors": sorted(set(errors)), "warnings": warnings,
            "scope": "static file checks only; no visual, animation, physics or game validation"}


EDITOR_FIELDS = {"selected", "primary_selected", "isOpen", "_static"}


def compare_skins(a, b):
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in EDITOR_FIELDS}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    def structure(m):
        groups, _, _ = graph(m)
        def outline(items):
            return [n if isinstance(n, str) else {"uuid": n["uuid"], "children": outline(n.get("children", []))} for n in items]
        return {"format": m.get("meta", {}).get("model_format"), "resolution": m.get("resolution"),
                "elements": {e["uuid"]: clean(e) for e in m.get("elements", [])},
                "groups": {uid: clean({k: v for k, v in g.items() if k != "children"}) for uid, g in groups.items()},
                "outliner": outline(m.get("outliner", [])), "animations": clean(m.get("animations", []))}
    left, right = structure(a), structure(b)
    return ["skin structure differs: " + key for key in left if left[key] != right[key]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--png", type=Path, help="compare exact embedded/external PNG bytes")
    parser.add_argument("--joints", type=Path, help="explicit rest-model endpoint constraints")
    parser.add_argument("--compare", type=Path, help="another skin with identical geometry/UV/rig/animation")
    parser.add_argument("--out", type=Path, help="optional JSON report; no file written by default")
    args = parser.parse_args()
    try:
        model = read(args.model)
        report = audit(model, read(args.joints) if args.joints else None, args.png)
        if args.compare:
            other = read(args.compare)
            report["comparison_audit"] = audit(other)
            report["errors"] += compare_skins(model, other)
            report["errors"] += ["comparison: " + e for e in report["comparison_audit"]["errors"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"errors": [str(exc)]}
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output+"\n", encoding="utf-8")
    print(output)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
