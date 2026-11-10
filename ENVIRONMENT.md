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
& .\.venv\Scripts\uv.exe run --quiet --offline --no-project --python .\.venv\Scripts\python.exe python evals/candidate/experiment.py --verify-final
```

命令执行原契约及自建测试，从 `take-home-base` 加载原策略，生成公开及定向场景的baseline、A、B和最终方案。`runs/selection.json` 保存门槛、选择、测试日志位置、数据哈希和最终策略一致性核验。`runs/before/`、`runs/candidate_a/`、`runs/candidate_b/`、`runs/after/` 保存summary、quality和完整traces。候选目录的diffs逐条记录质量与成本时延变化；`runs/custom/` 单独保存定向反例。

`--skip-tests` 仅供探索，输出会标记tests_unverified并选择baseline。最终验收使用上述完整命令。
