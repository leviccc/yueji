# 本地启动（Windows）
# 用法：.\start.ps1   （首次运行前先建好虚拟环境并安装依赖）

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path ".env") {
    Get-Content ".env" -Encoding UTF8 | Where-Object { $_ -match "^\s*[^#][^=]*=" } | ForEach-Object {
        $name, $value = $_ -split "=", 2
        $name = $name.Trim()
        # 调用者已在终端配置的值优先，避免示例中的空密钥覆盖现有配置。
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value.Trim(), "Process")
        }
    }
}

$provider = if ($env:YUEJI_MODEL_PROVIDER) { $env:YUEJI_MODEL_PROVIDER.ToLowerInvariant() } else { "qwen" }
if (($provider -eq "deepseek" -and -not $env:DEEPSEEK_API_KEY) -or ($provider -eq "qwen" -and -not $env:DASHSCOPE_API_KEY)) {
    Write-Warning "未检测到模型密钥；界面可正常浏览，但抽取会返回 503。"
}

$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
Write-Host "启动 http://127.0.0.1:8000 （Ctrl+C 停止）"
& $python -m uvicorn app:app --host 127.0.0.1 --port 8000
