# BB 车辆建模 Skill

把实车照片转为可编辑的 Blockbench Cube/Bone 车辆，整理自车辆风格分析与 DMC 多轮修订。优先解决连续侧线、A/C柱与门窗衔接、母版轮组与立体轮毂、细件尺度和简洁材质。

默认旧版实体，单车单张≤128×128颜色图集；原色、风格、红橙白火焰皮肤共享几何/UV/骨架。附有悬挂反馈、漂移与大量烟雾的制作及验收规范。

**验证边界：** DMC经验中的静态模型/三款贴图曾在原生Blockbench检查；此仓库不含项目模型、用户照片或凭据。动画/粒子章节属于待具体资产执行和验证的制作规范，不是已经完成的DMC动作包。审计脚本只做文件与显式端点检查。

## 安装与使用

将仓库保存为 `bb-vehicle-modeling`，放入技能目录（通常 `$CODEX_HOME/skills`），保留整个目录结构。

```text
使用 $bb-vehicle-modeling 根据这张实车照片制作旧版实体车辆。
侧面轮廓连续，轮毂必须立体，单张贴图不超过128×128；先交原色和风格版供确认。
```

```text
使用 $bb-vehicle-modeling 给这台车制作加速点头、悬挂回弹、漂移反打和后轮大量烟雾，注明烘焙反馈与游戏运行验证状态。
```

[入口](SKILL.md) · [几何](references/geometry.md) · [贴图](references/texture.md) · [动作/特效](references/motion-vfx.md) · [审计工具](references/audit.md)

## 文件检查

Python 3.10+，无第三方依赖：

```bash
python -B scripts/audit_vehicle.py vehicle.bbmodel --png atlas.png --compare flame.bbmodel
python -B -m unittest discover -s tests -v
```

脚本不会生成模型、自动焊接所有接缝、计算完整车辆物理或代替目标环境验收。技能不绑定本机路径、MCP调试端口或特定插件实现。

## 本次验证

- 技能格式检查通过；11项脚本测试覆盖图集尺寸、UV越界、Cube旋转、外图一致性、UUID/层级、父子旋转、镜像枢轴、端点间隙及皮肤结构差异。
- 在已有DMC原色/风格/火焰三个文件上运行审计：各564 Cubes、224 Bones，单张128×128，内外PNG一致，三款几何/UV/骨架相同。本次不是新增游戏内验证。
- 使用场景复核覆盖侧线优先、母版轮组、世界空间烟雾、有限发射器和烘焙/运行时区分；补充单照片尺度标定、版本能力记录及共图透明采样要求。
