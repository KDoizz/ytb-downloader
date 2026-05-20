# Youtube Downloader — CLAUDE.md

## Vault (Cérebro do Projeto)

`K:\Obsidian\ktwo brain\Projects\Youtube Downloader\`

- `Status.md` — estado atual e checklist de features → **leia antes de começar**
- `Session Log.md` — histórico de sessões → consulte as últimas entradas
- `Decisions Log.md` — decisões técnicas → consulte antes de decisões arquiteturais

Ao concluir tarefas relevantes, atualize os arquivos acima. Use `/close-session` para encerrar.

## Visão Geral

Aplicativo desktop para download de vídeos do YouTube e outras plataformas.

## Stack

- **Linguagem:** Python
- **Interface:** GUI (verificar `app.py`)
- **Build:** PyInstaller (`YTB Downloader.spec`)
- **Scripts:** `build.bat`, `run.bat`, `install.bat`

## Estrutura

```
app.py          # entry point
requirements.txt
build.bat       # gera o executável
install.bat     # instalação
run.bat         # execução em dev
bin/            # binários auxiliares
build/          # artefatos de build
dist/           # executável final
```

## Features Planejadas

- [ ] Aplicativo executável e instalável
- [ ] Download de outros sites (Twitter, Instagram, etc.)
- [ ] Galeria de downloads realizados
