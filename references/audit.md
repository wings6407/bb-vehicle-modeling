# 只读文件检查器

Python 3.10+，仅标准库。不会连接Blockbench、修改模型或运行插件。支持当前 `.bbmodel` 的Cube/Group结构；主层级读取outliner，兼容group属性单独存在及嵌套保存。用于旧版实体车辆，遇到其他格式报告限制。

```bash
python -B scripts/audit_vehicle.py car.bbmodel --png atlas.png
python -B scripts/audit_vehicle.py car.bbmodel --compare flame.bbmodel
python -B scripts/audit_vehicle.py car.bbmodel --joints seams.json --out report.json
```

正常退出0；发现文件约束问题退出1。`--out` 只写显式指定的报告位置，否则标准输出。PNG仅检查IHDR尺寸，内嵌与外部字节一致性；不是完整图片解码器。

检查单张图、图片实际与声明尺寸、逻辑UV尺寸、逐面UV范围、Cube旋转、重复UUID/Bone名称、层级引用和孤立元素。缺少面的已烘焙Box UV会报告无法核验，不自行猜Auto UV布局。

`--compare` 按UUID比较元素、组、层级、分辨率和动画，忽略编辑器选中/折叠状态。只允许纹理本身及材质/纹理元数据变化；不会证明图案美观或材质设置在游戏中正确。

接缝清单是数组，例如：

```json
[
  {
    "name": "left_waist_01_to_02",
    "a": {"bone": "side_segment_01", "point": [-20, 16, -12]},
    "b": {"bone": "side_segment_02", "point": [-20, 16, -12]},
    "tolerance": 0.0001
  }
]
```

`bone`接受UUID或唯一名称，`point`是**未施加任何Bone旋转的模型坐标**，不是骨骼局部坐标。包括父链的静态ZYX Euler旋转，不包括动画、显示变换、伸缩、约束或Mesh。起点终点须来自真正的可见外侧边，不能为了通过而随意填写相同点。先在原生读取相同端点比对，再使用其批量检查。

它只验证显式列出的连接，不会自动判断车身每个缝隙。输出没有joints时就没有接缝证据。原生动画/视觉/游戏检查必须另做。
