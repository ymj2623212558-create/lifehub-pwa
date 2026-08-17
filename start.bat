@echo off
rem LifeHub 本地启动脚本 (端口 8002, 避开被占用的 8000)
cd /d "%~dp0"
rem 清掉 PYTHONPATH，避免加载 Hermes venv 的旧库（Pillow 等）
set PYTHONPATH=
echo [1/3] 检查依赖...
if not exist .venv\Scripts\python.exe (
    echo   未找到 .venv, 正在创建 (Python 3.12)...
    uv venv --python 3.12 .venv || goto :error
    .venv\Scripts\pip.exe install -r requirements.txt || goto :error
    .venv\Scripts\pip.exe install reportlab python-docx || goto :error
)
echo [2/3] 数据库迁移...
.venv\Scripts\python.exe manage.py migrate || goto :error
echo [3/3] 启动服务器: http://127.0.0.1:8002/
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8002
goto :eof

:error
echo 启动失败, 请检查上方错误信息。
pause
