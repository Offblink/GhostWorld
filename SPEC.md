# GhostEngine Metaverse — 需求对照

## 完成 (v2)

**引擎**: EntityView 字段重整、fallback 纹理、A\* 通用寻路、`.T` 转置一致性  
**编辑器**: 工具栏、右侧属性面板互斥、传送门全地图扫描下拉框、跨图双向即时配对、墙壁-实体互斥、越界幽灵清理、定时自动保存、另存为、标题栏地图名显示  
**服务器**: 同进程、20Hz tick、拾取/传送门/聊天/快照/持久化、传送门坐标越界保护（回退出生点）、portal_target 严格 `{portal_id, map}` 无坐标  
**客户端**: 渲染/WASD/暂停/小地图/ESC不关服/聊天气泡/软碰撞、跨地图 Item 深拷贝隔离  
**Agent**: 文件命令 agent、实时日志、snapshot 本地保存、post_issue 发 GitHub Issue  
**Launcher**: 一键启动、人类退出 server 继续、默认读取 `.last_map`  
**跨地图**: 多地图预加载 + 传送门 + 跨图往返 + 坐标越界安全网  
**物品交换**: give 命令 + capture_for 限制拾取  
**测试**: 112 tests

## 修复的重大 Bug

| Bug | 修复 |
|-----|------|
| 编辑器-预览器 90° 旋转 | `runner.pyw` 补 `.T` 转置 |
| 传送门下拉框闪烁/信号竞态 | `currentIndexChanged` → `activated` |
| 跨图 Item 坐标污染 | `dict()` 浅拷贝 → `type(item)(**item.__dict__)` |
| 传送门越界传送 | 传送前校验坐标 + 回退出生点 |
| 覆盖已有实体 | 改为提示"位置已被占用" |
| 保存后传送门消失 | 移除 `_save_to` 中的实体全量重载 |
| 已删除地图的传送门残留 | 下拉框标注 `[⚠已删除]` |
