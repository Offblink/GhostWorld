# GhostWorld — 需求对照 (v2)

## 完成

**引擎**: 7 阶段射线投射管线、实体投影、动画、小地图、`.T` 转置全入口统一  
**编辑器**: 传送门全地图扫描下拉框、跨图双向即时配对、墙壁-实体互斥、越界幽灵清理、定时自动保存(3s)、另存为、标题栏地图名、NPC 对话字段  
**服务器**: 同进程架构、全指令支持（16 条）、传送坐标越界保护、set_entity 跨图搜索 + 深拷贝隔离  
**客户端**: WASD/小地图/聊天/暂停/ESC、跨图地图切换 + 深拷贝隔离、NPC 对话检测 + E 键交互 + 3s 提示  
**Agent**: Blinvo（默认名）、对话互动、文件命令、snapshot/post_issue  
**Launcher**: 一键启动、默认读取 `.last_map`、`ghostworld` / `ghostworld-editor` CLI 命令  
**默认地图**: 对称迷宫 + Blinvo NPC（对话"你好，我是Blinvo！欢迎来到GhostWorld！"）+ 传送门跨图往返  
**测试**: 112 项（含编辑器验证、传送门配对、深拷贝隔离回归）  
**分发**: `pip install git+https://github.com/Offblink/GhostWorld.git`
