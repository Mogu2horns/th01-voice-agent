# 运行环境

本次验收使用 Windows、Python 3.12.0、uv 0.13.7。产品和评测仅使用 Python 标准库。

## 首次配置

在本项目目录打开 PowerShell。下面的解释器是本机已有的 Python 3.12.0，其他机器可替换为其 Python 3.12.0 路径。

```powershell
& 'D:\anaconda\envs\agent\python.exe' -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-dev.txt
```

首次安装 uv 需要访问包索引。环境创建后，以下检查和实验均可离线执行。

## 每次运行

```powershell
$env:PYTHONUTF8 = '1'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.cache\uv'
& .\.venv\Scripts\python.exe --version
& .\.venv\Scripts\uv.exe --version
& .\.venv\Scripts\uv.exe run --quiet --offline --no-project --python .\.venv\Scripts\python.exe python task.py check
& .\.venv\Scripts\uv.exe run --quiet --offline --no-project --python .\.venv\Scripts\python.exe python task.py run --out runs/environment-check
```

显式解释器确保使用项目环境。`PYTHONUTF8` 会传递给 `task.py` 启动的子进程，使原工程正确读写中文 JSONL。

项目环境和缓存由 `.gitignore` 排除。Python 版本记录在 `.python-version`，uv 版本锁定在 `requirements-dev.txt`。

## 一键复现实验

先执行“每次运行”中的两个环境变量设置，再运行以下命令。

```powershell
& .\.venv\Scripts\uv.exe run --quiet --offline --no-project --python .\.venv\Scripts\python.exe python evals/candidate/ablation.py --verify-final
```

命令执行原契约及自建测试，从 `take-home-base` 加载原策略，完成路由与动作2×2实验、四项动作组件消融及解析回退消融。每组分别重放公开100条、已看反例18条、首个独立集32条和新确认集24条，先核验独立数据冻结哈希。

`runs/ablation/ablation.json` 保存全部指标、门槛、源码/数据哈希、测试日志位置、效应和最终入口一致性。各集合、各方案的summary、quality、完整traces、diffs和规则解释decisions分别保存。默认命令同步生成 `runs/before/`、`runs/after/` 和 `runs/selection.json`。

`runs/ablation_round1/` 保存未通过首个独立集的规则实验，`runs/ablation_selection_diagnostic/` 保存采用集合澄清前的选择记录。正式主矩阵候选为仅路由、仅动作和完整方案，组件移除仅解释贡献。

## 第一轮实验回放

第一轮历史版本和原有候选可使用以下命令独立复算，结果写入单独目录。

```powershell
& .\.venv\Scripts\uv.exe run --quiet --offline --no-project --python .\.venv\Scripts\python.exe python evals/candidate/experiment.py --out runs/routing_v1_replay
```

`runs/routing_v1/` 保留第一轮原始结果。该轮的 `--skip-tests` 仅供探索，其输出标记tests_unverified并选择baseline。
