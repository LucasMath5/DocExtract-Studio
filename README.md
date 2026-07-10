# Visual PDF Data Extractor

Aplicação desktop open source para mapear visualmente regiões de documentos PDF e, nas próximas etapas, extrair seus dados para planilhas.

> Status: Etapa 1 concluída. A aplicação possui a estrutura inicial e a janela principal; a abertura de PDFs será implementada na Etapa 2.

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

Os testes desta etapa verificam o estado inicial da janela e as ações do menu.

## Funcionalidades atuais

- janela principal em PySide6;
- menu `Arquivo` com as ações `Abrir PDF...` e `Sair`;
- mensagem de estado quando nenhum documento está carregado;
- configuração básica de logging.

## Roadmap imediato

A Etapa 2 adicionará a seleção, validação e renderização da primeira página de um PDF com PyMuPDF.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
