# Visual PDF Data Extractor

Aplicação desktop open source para mapear visualmente regiões de documentos PDF e, nas próximas etapas, extrair seus dados para planilhas.

> Status: Etapa 2 concluída. A aplicação abre documentos PDF e renderiza a primeira página.

## Requisitos

- Python 3.11 ou superior
- Windows, Linux ou macOS com suporte ao PySide6

## Instalação

Crie e ative um ambiente virtual:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

No Linux ou macOS, use `source .venv/bin/activate` no segundo comando.

Instale o projeto em modo editável:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Execução

Com o ambiente virtual ativo:

```powershell
visual-pdf-extractor
```

Também é possível executar diretamente pelo módulo:

```powershell
python -m pdf_extractor.main
```

## Testes

```powershell
pytest
```

Os testes verificam o serviço de PDF, o estado inicial da janela, as ações do menu e o carregamento da primeira página.

## Funcionalidades atuais

- janela principal em PySide6;
- menu `Arquivo` com as ações `Abrir PDF` e `Sair`;
- mensagem de estado quando nenhum documento está carregado;
- abertura e validação de documentos PDF;
- renderização da primeira página com PyMuPDF;
- exibição do nome do arquivo e da quantidade de páginas;
- mensagens amigáveis para PDFs inválidos ou corrompidos;
- configuração básica de logging.

## Roadmap imediato

A Etapa 3 adicionará navegação entre páginas e controles de zoom.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
