# Editor de Videos em Lote

Software desktop em Python para Windows que edita varios videos usando FFmpeg.

O programa gera videos verticais em 1080x1920, aplica uma imagem de fundo, opcionalmente adiciona logo/marca d'agua, textos superior e inferior, marca em texto translucida no centro, mascara para ocultar @ central, e salva tudo em MP4 com H.264.

## Estrutura

```text
video_editor_lote/
|-- main.py
|-- requirements.txt
|-- README.md
|-- app/
|   |-- __init__.py
|   |-- interface.py
|   |-- video_processor.py
|   `-- utils.py
|-- entrada/
|-- saida/
`-- assets/
    |-- fundo_padrao.jpg
    `-- logo_padrao.png
```

## Como instalar o Python no Windows

1. Acesse https://www.python.org/downloads/windows/
2. Baixe a versao mais recente do Python 3.
3. Durante a instalacao, marque a opcao **Add Python to PATH**.
4. Depois de instalar, abra o Prompt de Comando ou PowerShell e confira:

```powershell
python --version
```

## Como instalar o FFmpeg no Windows

Opcao simples usando Winget:

```powershell
winget install Gyan.FFmpeg
```

Depois feche e abra novamente o terminal. Confirme:

```powershell
ffmpeg -version
```

Se preferir instalar manualmente:

1. Baixe uma build do FFmpeg em https://www.gyan.dev/ffmpeg/builds/
2. Extraia o arquivo ZIP.
3. Adicione a pasta `bin` do FFmpeg ao PATH do Windows.
4. Abra um novo terminal e rode `ffmpeg -version`.

## Como instalar as dependencias

Entre na pasta do projeto:

```powershell
cd "C:\Users\Hugo\Documents\APP CRIAÇÃO VIDEO\video_editor_lote"
```

Crie um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Instale as bibliotecas:

```powershell
pip install -r requirements.txt
```

## Como rodar

Com o ambiente virtual ativo:

```powershell
python main.py
```

Na interface:

1. Selecione a pasta com os videos de entrada.
2. Escolha a imagem de fundo.
3. Escolha a logo, caso queira aplicar marca d'agua.
4. Escolha a pasta de saida.
5. Preencha os textos e a duracao maxima, se quiser.
6. Escolha o template.
7. Marque **Incluir subpastas** se quiser buscar videos dentro das pastas internas.
8. Use **Ajuste do video** para mudar tamanho e posicao do video com barras.
9. Se quiser ocultar um @ no centro, marque **Ocultar @ central** e mova a area com as barras.
10. Se quiser usar seu @ em texto, marque **Aplicar meu @ no centro**, preencha o campo e ajuste posicao/tamanho com as barras.
11. Clique em **Gerar videos**.

Formatos de entrada aceitos: `.mp4`, `.mov`, `.avi` e `.mkv`.

Quando **Incluir subpastas** estiver ativo, o programa procura videos em todos os niveis abaixo da pasta de entrada. Se dois arquivos tiverem o mesmo nome em subpastas diferentes, o programa evita sobrescrever a saida adicionando um numero ao final, como `_2`.

## Configuracoes salvas

O app salva automaticamente as ultimas informacoes usadas, como:

- pasta de entrada e saida;
- imagem de fundo e logo;
- template;
- textos;
- @, tamanho e posicao;
- ajuste de tamanho/posicao do video;
- opcao de incluir subpastas;
- area de ocultar @ central.

Quando usado como `.exe`, essas informacoes ficam em `config/settings.json` ao lado do executavel.

## Templates

**Template 1:** video centralizado sobre fundo, largura maxima de 900 px, logo no canto inferior direito e textos opcionais.

**Template 2:** video maior, largura maxima de 1000 px, com logo e texto inferior opcional.

**Template 3:** video centralizado com faixas escuras semitransparentes no topo e no rodape para textos.

## Configuracoes de exportacao

- Resolucao: 1080x1920
- Video: `libx264`
- Audio: `aac`
- Preset: `veryfast`
- CRF: `23`
- Pixel format: `yuv420p`
- Nome de saida: nome original + `_editado.mp4`

Se o video nao tiver audio, ele sera gerado normalmente.

## Ajuste do video com barras

A area **Ajuste do video** permite melhorar o enquadramento antes de gerar:

- **Tamanho:** aumenta ou diminui o video dentro do layout.
- **Largura:** estica ou comprime o video apenas na horizontal, sem aumentar a altura junto.
- **Horizontal:** move o video para a esquerda ou direita.
- **Vertical:** move o video para cima ou baixo.
- **Centralizar video:** volta para tamanho `100%`, largura `100%` e posicao central.

A previa mostra o enquadramento aproximado conforme as barras sao movidas.

## Ocultar marca central e aplicar seu @

A opcao **Ocultar @ central** usa o filtro `delogo` do FFmpeg para suavizar uma area retangular no video final. A posicao da area e ajustada com barras:

- **Horizontal:** move a area para a esquerda ou direita.
- **Vertical:** move a area para cima ou baixo.
- `Largura`: largura da area.
- `Altura`: altura da area.

O padrao de posicao horizontal/vertical, largura `700` e altura `160` cobre uma faixa central comum. Ajuste pelas barras se o @ estiver mais alto, mais baixo ou maior.

A opcao **Aplicar meu @ no centro** escreve uma marca em texto translucida no centro do video, sem precisar de arquivo de logo.

O campo **Tamanho do @** controla o tamanho da fonte dessa marca central. Use valores menores, como `40` ou `50`, para uma marca mais discreta; o valor padrao e `76`.

As barras **Horizontal @** e **Vertical @** movem a marca em texto para a esquerda, direita, cima ou baixo. Use **Centralizar @** para voltar a marca ao centro.

A area **Previa da marca** mostra uma miniatura vertical do resultado, incluindo:

- o espaco aproximado do video dentro do template;
- a area que sera suavizada quando **Ocultar @ central** estiver ativo;
- a logo no canto inferior direito, quando **Aplicar logo** estiver ativo;
- o seu @ translucido no centro, quando **Aplicar meu @ no centro** estiver ativo.

Use essas opcoes apenas em videos que voce tem direito de editar e republicar.

## Gerar .exe com PyInstaller

Primeiro instale as dependencias:

```powershell
pip install -r requirements.txt
```

Comando simples:

```powershell
pyinstaller --noconfirm --onefile --windowed main.py
```

Comando incluindo os assets padrao:

```powershell
pyinstaller --noconfirm --onefile --windowed --add-data "assets;assets" main.py
```

O executavel ficara dentro da pasta `dist`.

## Observacoes

- O FFmpeg precisa estar instalado e disponivel no PATH.
- Os comandos FFmpeg sao executados de forma local usando `subprocess`.
- Nao ha banco de dados, login, internet ou integracao com redes sociais.
