@echo off
echo ============================================
echo  YTB Downloader - Instalacao de dependencias
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo Instale o Python em https://python.org e marque "Add to PATH".
    pause
    exit /b 1
)

echo Instalando pacotes Python (inclui ffmpeg via imageio-ffmpeg)...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Copiando ffmpeg para bin\...
python -c "
import imageio_ffmpeg, shutil, os
bin_dir = os.path.join(os.path.dirname(os.path.abspath('.')), 'bin')
bin_dir = 'bin'
os.makedirs(bin_dir, exist_ok=True)
dst = os.path.join(bin_dir, 'ffmpeg.exe')
if not os.path.isfile(dst):
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), dst)
    print('ffmpeg copiado para', dst)
else:
    print('ffmpeg ja existe em', dst)
"
if errorlevel 1 (
    echo AVISO: Nao foi possivel copiar ffmpeg para bin\.
    echo O app tentara configurar automaticamente na primeira execucao.
)

echo.
echo Instalacao concluida! Execute run.bat para iniciar.
pause
