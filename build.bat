@echo off
echo ============================================
echo  Vex - Build do executavel
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

echo Instalando dependencias de build...
pip install pyinstaller imageio-ffmpeg customtkinter yt-dlp >nul 2>&1

echo.
echo Garantindo ffmpeg em bin\...
if not exist "bin\ffmpeg.exe" (
    python -c "import imageio_ffmpeg, shutil, os; os.makedirs('bin', exist_ok=True); shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), os.path.join('bin', 'ffmpeg.exe')); print('  ffmpeg copiado.')"
) else (
    echo   bin\ffmpeg.exe ja existe.
)

echo.
echo Obtendo caminho do customtkinter...
for /f "delims=" %%i in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
echo   %CTK_PATH%

echo.
echo Iniciando build...
python -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "Vex" ^
  --add-data "%CTK_PATH%;customtkinter" ^
  --add-data "bin\ffmpeg.exe;bin" ^
  --collect-data yt_dlp ^
  app.py

echo.
if exist "dist\Vex.exe" (
    echo ============================================
    echo  BUILD CONCLUIDO COM SUCESSO!
    echo  Arquivo: dist\Vex.exe
    echo.
    echo  Envie esse unico arquivo para seu amigo.
    echo  Ele so precisa abrir - sem instalar nada.
    echo ============================================
) else (
    echo ERRO: Build falhou. Verifique as mensagens acima.
)

echo.
pause
