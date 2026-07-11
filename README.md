# Visual PDF Data Extractor

Aplicação desktop open source para mapear visualmente regiões de documentos PDF e, nas próximas etapas, extrair seus dados para planilhas.

> Status: Etapa 5 concluída. A aplicação permite criar e gerenciar múltiplos campos nomeados sobre as páginas do PDF.

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

Os testes verificam o serviço de PDF, navegação, zoom, coordenadas, campos nomeados e gerenciamento pelo painel lateral.

## Funcionalidades atuais

- janela principal em PySide6;
- menu `Arquivo` com as ações `Abrir PDF` e `Sair`;
- mensagem de estado quando nenhum documento está carregado;
- abertura e validação de documentos PDF;
- renderização de páginas com PyMuPDF;
- exibição do nome do arquivo e da quantidade de páginas;
- navegação entre páginas com controles habilitados conforme os limites;
- zoom entre 50% e 300%, com redefinição para 100%;
- atalhos `←` e `→` para navegar, `Ctrl++` e `Ctrl+-` para controlar o zoom;
- ícone próprio na janela, no alternador de tarefas e na barra de tarefas;
- criação de múltiplos campos nomeados a partir de seleções retangulares;
- painel lateral para selecionar, renomear e excluir campos;
- nomes únicos, com validação de valores vazios e duplicados;
- destaque visual do campo selecionado e navegação automática até sua página;
- regiões preservadas corretamente durante navegação e zoom;
- exclusão do campo selecionado pelo painel ou pela tecla `Delete`;
- cancelamento de uma seleção em andamento com `Esc`;
- mensagens amigáveis para PDFs inválidos ou corrompidos;
- configuração básica de logging.

## Roadmap imediato

A Etapa 6 adicionará a extração de texto nativo das regiões mapeadas.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
