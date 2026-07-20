@echo off
chcp 65001 >nul
cd /d %~dp0

REM ===== 先杀掉旧的 8765 进程（如果存在），确保新代码生效 =====
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R "LISTENING.*:8765 "') do (
    echo [run.bat] 检测到旧进程 PID=%%a，正在结束...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ===== 启动 uvicorn（带 --reload，修改代码会自动热重载）=====
start "AI旅游小助手" cmd /k "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload"

REM ===== 等待服务起来后打开浏览器 =====
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8765/