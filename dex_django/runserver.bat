@echo off
setlocal
set API_AUTH_ENABLED=true
set API_KEY=dev-123
set VENV_PY=venv\Scripts\python.exe
set DJANGO_DIR=dex_django
echo Starting server with API_AUTH_ENABLED=%%API_AUTH_ENABLED%%
"%%VENV_PY%%" "%%DJANGO_DIR%%\manage.py" runserver
endlocal
