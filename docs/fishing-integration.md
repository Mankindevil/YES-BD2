# 自动钓鱼集成

来源：MadestSamurai / MadSamurai，https://github.com/MadestSamurai/bd2-fishing
版本：0.4.5 / d4821c71192e63ebbb5dcc56644c973470a3d1d8，MIT。
适用 Windows x64 PC 客户端；不支持安卓模拟器。

## 架构与默认值

`FishingPage → FishingTask → FishingRunner → JSON-lines 子进程 → BD2Fishing.Core → 游戏内组件`。
Python 负责界面、任务互斥、时长/鱼数上限和生命周期。C# 保留上游接口适配、
注入、命名管道、状态机、出售保护及短租约。连接必须指定游戏 PID、启动时间；
后端再次核对名称及同一 Windows 会话。普通桌面与分身使用不同诊断/偏好目录。

默认 30 分钟，数量上限 0（仅限时），等待进图 180 秒，自动出售关闭，传说鱼保留。
始终保留锁定及资料不明的鱼，不提供自动解锁。鱼种尺寸编辑暂不开放。
不自动加入一键日常；需玩家手动进入已解锁的钓场并关闭游戏内自动钓鱼。

## 控制与停止

Python 每 0.5 秒发送心跳；C# 检查父进程及 5 秒心跳超时。
失联会撤销控制并退出，上游游戏内控制租约最长续期到 10 秒后。
暂停先发 stop，继续需重新验证新鲜状态并获得控制权。
退出/停止等待游戏状态确认无持有输入或未结算操作；超时会在当前工具内阻止后续任务，
提示重启游戏。停止已经发出的操作不能保证撤回，当前一竿可能正常结算。
仅关闭工具不等同于从游戏中卸载组件；需要完全卸载时重启游戏。

## 构建及更新

需要 Windows x64 和 .NET SDK 8 或更新版本：

```powershell
.\scripts\build_fishing.ps1
```

`tools/fishing/backend/YesBd2.FishingBridge.exe` 为自带运行时的本地生成产物，不提交二进制。
`--identity` 只打印版本/协议，不连接游戏。发布工作流在同步更新仓库前构建后端。
`deploy.txt` 包含后端、桥接源码及上游源码/许可，排除中间 bin/obj。
更新依赖才使用 `-UpdateLock`；平常按已提交锁文件构建。

上游源码改动包括指定进程连接/会话校验、YES-BD2 独立数据目录和新增错误消息翻译，见 UPSTREAM.md。
上游 desktop 源码仅保留供本地化回归读取，不构建或启动其独立窗口。

## 验证边界

离线验证覆盖 Python 生命周期、协议错误、目标进程筛选、暂停恢复、停止确认和界面，
以及上游策略/兼容性回归。协议测试不发 connect，不注入游戏。
仍须在实际客户端验证连续钓鱼、暂停停止、分身、昼夜/到期切图及可选自动出售。
不把离线断言数量当作实机用例数量。

可复现的离线检查：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fishing_runner tests.test_fishing_bridge tests.test_fishing_page -v
dotnet run --project vendor/bd2-fishing/tests/BD2Fishing.Tests.csproj -c Release --property:RestoreLockedMode=true
dotnet run --project vendor/bd2-fishing/compatibility-tests/BD2Fishing.Compatibility.Tests.csproj -c Release --property:RestoreLockedMode=true
```

通信测试要求先构建后端；缺少后端时会跳过，生命周期与界面测试仍可运行。
