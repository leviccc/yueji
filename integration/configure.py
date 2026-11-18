"""Run on the server: sudo /opt/yueji/venv/bin/python -m integration.configure.

Secrets are entered with getpass and atomically written to a root-only env file.
Nothing entered is sent to a website or printed to the terminal.
"""
import getpass
import os
import tempfile
from pathlib import Path
from dotenv import dotenv_values
from .state import password_hash


def main():
    destination = Path(os.getenv("YUEJI_ENV_FILE", "/etc/yueji.env"))
    values = dict(dotenv_values(destination)) if destination.exists() else {}
    print("直接回车保留原配置；API Key 不回显。输入 - 可清除对应 Key。")
    for key, label in [("DASHSCOPE_API_KEY", "阿里云百炼 API Key（三个功能统一调用 DeepSeek V4.1 Flash）")]:
        value = getpass.getpass(label + ": ").strip()
        if value:
            if value != "-" and (not value.isascii() or any(c.isspace() for c in value) or any(c in value for c in "'\"#\\")):
                raise SystemExit("密钥格式不正确，未保存。")
            values[key] = "" if value == "-" else value
    values["MODEL_PROVIDER"] = "aliyun"
    values["MODEL_NAME"] = "deepseek-v4.1-flash"
    values["MODEL_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    values["MODEL_INPUT_CNY_PER_MILLION"] = "2"
    values["MODEL_OUTPUT_CNY_PER_MILLION"] = "8"
    for obsolete in ["DEEPSEEK_API_KEY", "MODEL_API_KEY", "PLOT_MODEL", "CHARACTER_PROVIDER", "CHARACTER_MODEL", "QA_MODEL", "QA_BASE_URL"]:
        values.pop(obsolete, None)
    password = getpass.getpass("新的工作台访问密码（回车保持现有密码）: ")
    if password:
        if len(password) < 12:
            raise SystemExit("访问密码请至少使用 12 个字符；未保存。")
        if getpass.getpass("再次输入工作台访问密码: ") != password:
            raise SystemExit("两次密码不一致；未保存。")
        values["APP_PASSWORD_HASH"] = password_hash(password)
    budget = input(f"项目 API 预算（元，当前 {values.get('API_BUDGET_CNY', '50')}，回车保持）: ").strip()
    if budget:
        amount = float(budget)
        if not 0 < amount <= 200:
            raise SystemExit("本项目预算应在 0 到 200 元之间；未保存。")
        values["API_BUDGET_CNY"] = str(amount)
        values["API_WARNING_CNY"] = str(amount * .8)
    values.setdefault("YUEJI_DATA_DIR", "/var/lib/yueji")
    values.setdefault("REQUIRE_AUTH", "true")
    if not values.get("APP_PASSWORD_HASH"):
        raise SystemExit("请设置工作台访问密码；未保存。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".yueji-env-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            for key, value in values.items():
                # Single quotes preserve the dollar separators in password hashes
                # for both python-dotenv and systemd EnvironmentFile.
                if value is not None:
                    stream.write(f"{key}='{value}'\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("配置已保存。请执行 systemctl restart yueji 后，在页面刷新服务状态。")


if __name__ == "__main__":
    main()

