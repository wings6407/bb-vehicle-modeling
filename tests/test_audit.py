import base64, copy, importlib.util, math, struct, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location("audit", Path(__file__).resolve().parents[1]/"scripts"/"audit_vehicle.py")
audit = importlib.util.module_from_spec(spec)
if spec.loader: spec.loader.exec_module(audit)

def model():
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I",13) + b"IHDR" + struct.pack(">II",128,128)
    return {"meta":{"model_format":"bedrock_old"},"resolution":{"width":128,"height":128},
      "groups":[{"uuid":"g","name":"root","origin":[0,0,0],"rotation":[0,0,0]}],
      "elements":[{"uuid":"c","type":"cube","from":[0,0,0],"to":[1,1,1],"faces":{"north":{"uv":[0,0,1,1],"texture":0}}}],
      "outliner":[{"uuid":"g","children":["c"]}],
      "textures":[{"uuid":"t","width":128,"height":128,"uv_width":128,"uv_height":128,"source":"data:image/png;base64,"+base64.b64encode(png).decode()}]}

class AuditTests(unittest.TestCase):
    def test_valid_single_atlas(self):
        self.assertEqual(audit.audit(model())["errors"],[])
    def test_actual_png_not_metadata(self):
        m=model(); raw=base64.b64decode(m["textures"][0]["source"].split(",")[1]);raw=raw[:16]+struct.pack(">II",256,128)
        m["textures"][0]["source"]="data:image/png;base64,"+base64.b64encode(raw).decode()
        self.assertTrue(any("PNG" in x for x in audit.audit(m)["errors"]))
    def test_uv_overflow_and_cube_rotation(self):
        m=model();m["elements"][0]["faces"]["north"]["uv"]=[0,0,129,1];m["elements"][0]["rotation"]=[0,10,0]
        e=audit.audit(m)["errors"];self.assertTrue(any("UV" in x for x in e));self.assertTrue(any("rotation" in x for x in e))
    def test_missing_bone_and_duplicate_uuid(self):
        m=model();m["outliner"][0]["children"].append("missing");m["elements"].append(copy.deepcopy(m["elements"][0]))
        e=audit.audit(m)["errors"];self.assertTrue(any("missing" in x for x in e));self.assertTrue(any("duplicate" in x for x in e))
    def test_joint_world_rotation_and_gap(self):
        m=model();m["groups"][0]["rotation"]=[0,0,90]
        m["groups"].append({"uuid":"h","name":"fixed","origin":[0,0,0]});m["outliner"].append({"uuid":"h","children":[]})
        joins=[{"name":"seam","a":{"bone":"g","point":[1,0,0]},"b":{"bone":"h","point":[0,1,0]},"tolerance":1e-4}]
        report=audit.audit(m,joins);self.assertEqual(report["errors"],[]);self.assertLess(report["joints"][0]["gap"],1e-8)
        joins[0]["b"]["point"]=[0,1.1,0];self.assertTrue(any("seam" in x for x in audit.audit(m,joins)["errors"]))
    def test_parent_rotation_and_zyx_order(self):
        m=model();m["groups"][0]["rotation"]=[0,0,90]
        m["groups"].append({"uuid":"h","name":"child","origin":[1,0,0],"rotation":[90,90,0]})
        m["outliner"][0]["children"].append({"uuid":"h","children":[]})
        p=audit.world_point(m,"h",[1,1,0]);self.assertAlmostEqual(p[0],0);self.assertAlmostEqual(p[1],2);self.assertAlmostEqual(p[2],0)
    def test_multiple_atlases(self):
        m=model();m["textures"].append(copy.deepcopy(m["textures"][0]));self.assertTrue(audit.audit(m)["errors"])
    def test_skin_comparison_detects_uv_and_animation_changes(self):
        a=model();b=copy.deepcopy(a);b["textures"][0]["name"]="flame.png"
        self.assertEqual(audit.compare_skins(a,b),[])
        b["elements"][0]["faces"]["north"]["uv"][2]=2;self.assertTrue(audit.compare_skins(a,b))
        b=copy.deepcopy(a);b["animations"]=[{"name":"different"}];self.assertTrue(audit.compare_skins(a,b))

    def test_external_atlas_mismatch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"atlas.png";p.write_bytes(b"different")
            self.assertTrue(any("bytes differ" in e for e in audit.audit(model(), external_png=p)["errors"]))
    def test_mirrored_y_rotation_and_pivot(self):
        m=model();m["groups"][0].update(origin=[3,7,2], rotation=[0,180,0])
        p=audit.world_point(m,"g",[4,8,5])
        for actual, expected in zip(p,[2,8,-1]): self.assertAlmostEqual(actual,expected)
    def test_dangling_texture_and_invalid_joint(self):
        m=model();m["elements"][0]["faces"]["north"]["texture"]=9
        self.assertTrue(any("texture" in e for e in audit.audit(m)["errors"]))
        j=[{"name":"bad", "a":{"bone":"absent","point":[0,0,0]},"b":{"bone":"g","point":[0,0,0]}}]
        self.assertTrue(any("bad" in e for e in audit.audit(model(),j)["errors"]))

if __name__ == "__main__": unittest.main()
