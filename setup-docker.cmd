@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker was not found. Install Docker Desktop and restart CMD.
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo Docker Desktop is not running. Start it and wait for the Linux engine.
    exit /b 1
)

for /f "delims=" %%i in ('docker info --format "{{.OSType}}"') do set "DOCKER_OS=%%i"
if /i not "%DOCKER_OS%"=="linux" (
    echo Docker Desktop must use Linux containers with the WSL 2 engine.
    exit /b 1
)

echo Building the restricted WiFi CodeShare C++ runner...
docker build --pull --tag wifi-codeshare-cpp-runner:1.0 docker\cpp-runner
if errorlevel 1 exit /b 1

echo.
echo Building the restricted WiFi CodeShare Python runner...
docker build --pull --tag wifi-codeshare-python-runner:1.0 docker\python-runner
if errorlevel 1 exit /b 1

echo.
echo Docker execution runners are ready.
docker image inspect wifi-codeshare-cpp-runner:1.0 --format "Image: {{.RepoTags}}"
docker image inspect wifi-codeshare-python-runner:1.0 --format "Image: {{.RepoTags}}"
endlocal
