"""STEP → STL 转换 —— 使用 OCP (OpenCASCADE Python 绑定)"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone

step_path = 'E:/Works/Claude_Code/PowerSkivingToolGenerator/assets/hob.stp'
stl_path = 'E:/Works/Claude_Code/PowerSkivingToolGenerator/assets/hob.stl'

print(f'读取 STEP: {step_path}')
reader = STEPControl_Reader()
status = reader.ReadFile(step_path)
if status != IFSelect_RetDone:
    raise RuntimeError(f'STEP 读取失败, status={status}')

reader.TransferRoots()
shape = reader.OneShape()
print(f'模型加载成功, 类型: {shape.ShapeType()}')

# 三角剖分（线性偏转 0.1mm）
print('三角剖分...')
mesh = BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)
mesh.Perform()
print('剖分完成')

# 导出 STL
print(f'导出 STL: {stl_path}')
writer = StlAPI_Writer()
writer.Write(shape, stl_path)

import os
size_mb = os.path.getsize(stl_path) / 1024 / 1024
print(f'完成! 文件大小: {size_mb:.1f} MB')
