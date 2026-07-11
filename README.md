# Visual PDF Data Extractor

Aplicação desktop open source para mapear visualmente regiões de documentos PDF e, nas próximas etapas, extrair seus dados para planilhas.

> Status: Etapa 11 concluída. A aplicação aplica templates a vários PDFs em lote, com progresso, cancelamento, relatório e exportação consolidada. As etapas de revisão manual e validação de dados foram puladas.

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

Os testes verificam PDF, campos, extração nativa, arquivos CSV/XLSX, templates JSON e processamento em lote.

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
- extração de texto nativo das regiões com PyMuPDF;
- tabela com campo, página, valor extraído e status;
- estados `sucesso`, `vazio` e `erro`, sem interromper os demais campos;
- exportação direta dos valores extraídos para CSV e XLSX;
- uma linha por documento, com nome do arquivo e campos em ordem;
- suporte a caracteres acentuados e campos vazios nos arquivos exportados;
- criação de templates novos pelo menu `Template`;
- salvamento, importação e exportação de templates em JSON;
- schema de template versionado, com datas de criação e modificação em UTC;
- validação de estrutura, tipos, campos duplicados e versão do schema;
- restauração das regiões, nomes e ordem dos campos em outro PDF;
- edição e salvamento de templates importados;
- templates portáteis, sem armazenar o caminho do PDF de origem;
- seleção de vários PDFs para processamento em lote;
- seleção dos PDFs existentes diretamente em uma pasta;
- aplicação de um template JSON a cada documento do lote;
- processamento em worker thread para manter a interface responsiva;
- progresso por arquivo e cancelamento seguro entre documentos;
- falha isolada: um PDF inválido não interrompe os demais;
- relatório com total, processados, sucessos, atenção e falhas;
- detalhe do erro associado a cada arquivo;
- prévia da tabela consolidada antes de salvar, com uma coluna por campo;
- exportação consolidada do lote para CSV ou Excel;
- mensagens amigáveis para PDFs inválidos ou corrompidos;
- configuração básica de logging.

## Roadmap imediato

As etapas 7 e 10, de revisão manual e validação de dados, foram puladas. A Etapa 12 de suporte a ZIP também está fora do escopo. A próxima etapa prevista é o fallback de OCR para PDFs digitalizados.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
