# Framework-Agnostic Agentic dbt Development Harness

Um **Harness de Desenvolvimento Agêntico para dbt Core e DuckDB**, agnóstico de frameworks de IA e voltado para ambientes de produção.

## Visão Geral da Arquitetura

O princípio arquitetural central deste harness é a **separação entre o raciocínio do agente e as capacidades de engenharia**. Os serviços de domínio, operações do dbt, limites de segurança, inspeção no DuckDB, persistência de sessões e relatórios de validação são completamente desacoplados de qualquer runtime ou framework de agente.

```text
Usuário / CLI (comando `harness`)
    │
    ▼
Runtime do Agente (Google ADK / Agente Customizado / Outros Adaptadores)
    │
    ▼
Adaptador do Agente (`harness.adapters.google_adk`)
    │ (Converte o ToolRegistry do Harness em ferramentas nativas, ex.: FunctionTool)
    ▼
Tool Registry Agnóstico e Interfaces de Protocolo (`harness.core.registry`, `contracts.py`)
    │
    ├── Descoberta de Projeto (`harness.services.discovery`)
    │   └── Parser do manifest.json com fallback para AST/sistema de arquivos (modelos, colunas, linhagem, entidades)
    │
    ├── Diretrizes e Políticas (`harness.services.guidelines`)
    │   └── Regras de Entity-Centric Data Modeling (ECM) e validador determinístico de conformidade
    │
    ├── Gestão do Workspace (`harness.services.workspace`)
    │   └── Confinamento estrito de caminhos, revisão de diff, modificação atômica e rollback por sessão
    │
    ├── Motor de Execução dbt (`harness.services.dbt_runner`)
    │   └── Execução em subprocessos controlados (parse, compile, run, test, build) e análise de artefatos
    │
    ├── Inspeção do DuckDB (`harness.services.duckdb_inspector`)
    │   └── Consultas analíticas somente leitura e limitadas, checagem de PK, taxas de nulos e modo snapshot resiliente a locks
    │
    ├── Persistência de Sessões Multi-Turn (`harness.sessions.store`)
    │   └── Estado durável em SQLite (objetivo, requisitos, modelos modificados, histórico de validação)
    │
    └── Avaliação e Evidências (`harness.evals.evaluators`, `reports`)
        └── Suíte de validação determinística multidimensional (compilação, build, testes, diretrizes e evidências)
    │
    ▼
Projeto dbt Existente (`anac_lakehouse`) + DuckDB (`databases/anac_lakehouse.db`)
```

---

## Principais Funcionalidades

1. **Descoberta de Projeto e Linhagem**:
   - Descobre modelos, colunas, descrições, tipos de dados e testes diretamente do `target/manifest.json`, com fallback resiliente para análise do sistema de arquivos e AST.
   - Mapeia o grafo de dependências upstream e downstream.
   - Identifica automaticamente entidades de negócio e definições de granularidade (grain) a partir da camada `trusted`.

2. **Diretrizes de Modelagem Centrada em Entidades (ECM)**:
   - Encapsula as regras de `guidelines/entity_centric_modeling_guideline.md`.
   - Valida programaticamente a nomenclatura de tabelas (`dim_`, `fct_`, `stg_`), testes de unicidade e nulidade da chave primária (`unique`, `not_null`), nomenclatura de flags booleanas (`is_`, `has_`, valores aceitos) e parsing resiliente (`try_cast`).

3. **Confinamento e Segurança no Workspace**:
   - Restringe operações de leitura, escrita e modificação estritamente ao diretório `models/`.
   - Gera prévias com diffs unificados (`propose_diff`) antes da aplicação das alterações.
   - Mantém histórico de modificações e oferece suporte a reversões imediatas (`revert_file`).

4. **Resiliência a Concorrência e Locks no DuckDB**:
   - Utiliza conexões estritamente somente leitura com consultas limitadas (`SELECT`, `SHOW`, `DESCRIBE`).
   - Rejeita comandos DDL e destrutivos (`DROP`, `DELETE`, `UPDATE`, `TRUNCATE`).
   - Se um processo externo mantiver um lock exclusivo no arquivo DuckDB (como uma interface gráfica ou terminal interativo do DuckDB aberto), o inspetor recorre automaticamente a um snapshot temporário, garantindo que consultas analíticas nunca travem ou falhem.

5. **Sessões Persistentes Multi-Turn**:
   - Salva o estado da sessão (objetivo, requisitos, entidades-alvo, arquivos alterados, revisões, relatórios de validação e feedbacks) em SQLite local (`.harness/sessions.db`).
   - Independente do histórico de conversas do agente, permitindo troca de runtime ou continuação do trabalho entre reinicializações.

6. **Adaptador de Referência para Google ADK**:
   - Converte todas as ferramentas do harness em objetos nativos `google.adk.tools.FunctionTool`.
   - Pré-configura um agente autônomo de engenharia (`google.adk.agents.Agent`) com instruções contextuais e amarração de ferramentas.

---

## Instalação e Configuração

Requisitos:
- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (recomendado) ou ambiente virtual padrão

Instalação das dependências e registro da CLI:
```bash
uv pip install -e .
```

---

## Uso da Linha de Comando (CLI)

O harness disponibiliza uma interface CLI voltada tanto para desenvolvedores humanos quanto para automações:

### Inspecionar Arquitetura do Projeto
```bash
harness inspect
```
Exibe o total de modelos, camadas arquiteturais (`landing`, `raw`, `staging`, `trusted`), localização do DuckDB e entidades de negócio descobertas.

### Listar Modelos por Camada
```bash
harness models
harness models --layer trusted
harness models --layer staging
```

### Inspecionar Detalhes e Linhagem de um Modelo
```bash
harness model dim_aeronaves
```

### Validar e Avaliar um Modelo
```bash
harness validate dim_aeronaves --layer trusted --pk marca_aeronave
```

### Iniciar Sessão com o Runtime do Google ADK

Você pode executar o agente via linha de comando ou via interface gráfica web oficial do ADK:

#### 1. Via Interface Web Oficial do Google ADK
O Google ADK fornece uma interface web com chat interativo, visualização das chamadas de ferramentas e logs.

Para iniciar o servidor web:
```bash
uv run adk web agents
# ou especificando a porta:
uv run adk web agents --port 8000
```
Após executar, acesse no navegador: `http://localhost:8000` (ou a porta informada no terminal). Na interface web, selecione o agente `dbt_developer`.

#### 2. Via Linha de Comando (CLI)
```bash
# Modo interativo no terminal
harness agent --session minha-sessao-001

# Execução de instrução pontual
harness agent --session minha-sessao-001 --message "Descubra os modelos existentes e verifique a conformidade de dim_aeronaves"
```

### Deletar um Modelo
Remova os arquivos SQL e YAML de um modelo com suporte a histórico e rollback:
```bash
harness delete dim_fabricantes_aeronaves --layer trusted
```

### Consultar o Banco com Segurança (Somente Leitura)
```bash
harness query "SELECT marca_aeronave, nm_fabricante, ds_modelo, is_apta_para_voo FROM trusted.dim_aeronaves LIMIT 5"
```

### Visualizar Diretrizes de Modelagem
```bash
harness guidelines
```

### Listar Sessões Persistentes
```bash
harness sessions
```

---

## Integração com Agentes de IA

Exemplo de instanciação do harness com o Google ADK:

```python
from harness.adapters.google_adk import create_adk_agent

# Inicializa o agente com sessão persistente
agent, registry, services = create_adk_agent(
    session_id="tarefa-aeronaves-001",
    model="gemini-2.5-flash",
)

print(f"Agente pronto: {agent.name} com {len(agent.tools)} ferramentas registradas.")
```

Ferramentas disponíveis expostas ao agente:
- `discover_project()`
- `list_models(layer=None)`
- `get_model_details(model_name)`
- `get_model_lineage(model_name)`
- `get_entity_definitions()`
- `get_guidelines()`
- `check_guidelines_compliance(model_name, sql_content, yaml_content, layer)`
- `read_model_file(relative_path)`
- `propose_model_diff(relative_path, new_content)`
- `write_model_file(relative_path, content)`
- `revert_model_file(relative_path)`
- `execute_dbt(command, select, timeout_seconds)`
- `query_database(sql, limit)`
- `inspect_table_profile(table_name, schema_name)`
- `check_pk_uniqueness(table_name, pk_column, schema_name)`
- `validate_and_evaluate_model(model_name, layer, primary_key)`

---

## Execução dos Testes Automatizados

Execute a suíte completa de testes com o `pytest`:

```bash
uv run pytest tests/ -v
```

Cobertura dos testes:
- `test_discovery.py`: Parser de manifest, fallback AST, extração de colunas e linhagem.
- `test_guidelines.py`: Validação de regras ECM, convenções de nomes, constraints de chave primária e testes booleanos.
- `test_workspace.py`: Segurança de limites de diretório, geração de diffs, gravação de arquivos e rollback.
- `test_dbt_runner.py`: Whitelist de comandos permitidos, timeouts e classificação de erros (locks vs compilação vs testes).
- `test_duckdb.py`: Imposição de leitura exclusiva, rejeição de DDL, listagem de esquemas/tabelas, contagem de linhas e checagem de unicidade de PK.
- `test_sessions.py`: Criação, leitura, atualização, revisões e histórico de validações no SQLite.
- `test_evals.py`: Avaliação determinística e formatação de relatórios em Markdown.
- `test_adk_adapter.py`: Conversão para `FunctionTool` e `Agent` do Google ADK.
- `test_end_to_end.py`: Cenário completo multi-turn (descoberta -> checagem de diretrizes -> revisão de diff -> gravação segura -> avaliação mockada -> rollback -> conclusão de sessão).

---

## Considerações e Limitações Conhecidas

1. **Locks de Escrita no DuckDB**:
   - O DuckDB permite apenas um processo gravador por vez no arquivo do banco de dados.
   - Para operações de leitura, o harness utiliza snapshot transparente para evitar bloqueios.
   - Para comandos dbt de gravação (`run`, `build`), caso um processo externo retenha o lock de escrita, o dbt retorna um erro classificado (`lock_error`) com o PID conflitante para que o usuário possa fechar a conexão.
2. **Outros Adaptadores**:
   - O Google ADK é o adaptador de referência implementado. Adaptadores adicionais (como Claude Agent SDK ou OpenAI Assistants) podem ser adicionados simplesmente consumindo `ToolRegistry.list_tools()`, sem necessidade de alterar as regras de negócio centrais.

Um **Harness de Desenvolvimento Agêntico para dbt Core e DuckDB**, agnóstico de frameworks de IA e voltado para ambientes de produção.

## Visão Geral da Arquitetura

O princípio arquitetural central deste harness é a **separação entre o raciocínio do agente e as capacidades de engenharia**. Os serviços de domínio, operações do dbt, limites de segurança, inspeção no DuckDB, persistência de sessões e relatórios de validação são completamente desacoplados de qualquer runtime ou framework de agente.

```text
Usuário / CLI (comando `harness`)
    │
    ▼
Runtime do Agente (Google ADK / Agente Customizado / Outros Adaptadores)
    │
    ▼
Adaptador do Agente (`harness.adapters.google_adk`)
    │ (Converte o ToolRegistry do Harness em ferramentas nativas, ex.: FunctionTool)
    ▼
Tool Registry Agnóstico e Interfaces de Protocolo (`harness.core.registry`, `contracts.py`)
    │
    ├── Descoberta de Projeto (`harness.services.discovery`)
    │   └── Parser do manifest.json com fallback para AST/sistema de arquivos (modelos, colunas, linhagem, entidades)
    │
    ├── Diretrizes e Políticas (`harness.services.guidelines`)
    │   └── Regras de Entity-Centric Data Modeling (ECM) e validador determinístico de conformidade
    │
    ├── Gestão do Workspace (`harness.services.workspace`)
    │   └── Confinamento estrito de caminhos, revisão de diff, modificação atômica e rollback por sessão
    │
    ├── Motor de Execução dbt (`harness.services.dbt_runner`)
    │   └── Execução em subprocessos controlados (parse, compile, run, test, build) e análise de artefatos
    │
    ├── Inspeção do DuckDB (`harness.services.duckdb_inspector`)
    │   └── Consultas analíticas somente leitura e limitadas, checagem de PK, taxas de nulos e modo snapshot resiliente a locks
    │
    ├── Persistência de Sessões Multi-Turn (`harness.sessions.store`)
    │   └── Estado durável em SQLite (objetivo, requisitos, modelos modificados, histórico de validação)
    │
    └── Avaliação e Evidências (`harness.evals.evaluators`, `reports`)
        └── Suíte de validação determinística multidimensional (compilação, build, testes, diretrizes e evidências)
    │
    ▼
Projeto dbt Existente (`anac_lakehouse`) + DuckDB (`databases/anac_lakehouse.db`)
```

---

## Principais Funcionalidades

1. **Descoberta de Projeto e Linhagem**:
   - Descobre modelos, colunas, descrições, tipos de dados e testes diretamente do `target/manifest.json`, com fallback resiliente para análise do sistema de arquivos e AST.
   - Mapeia o grafo de dependências upstream e downstream.
   - Identifica automaticamente entidades de negócio e definições de granularidade (grain) a partir da camada `trusted`.

2. **Diretrizes de Modelagem Centrada em Entidades (ECM)**:
   - Encapsula as regras de `guidelines/entity_centric_modeling_guideline.md`.
   - Valida programaticamente a nomenclatura de tabelas (`dim_`, `fct_`, `stg_`), testes de unicidade e nulidade da chave primária (`unique`, `not_null`), nomenclatura de flags booleanas (`is_`, `has_`, valores aceitos) e parsing resiliente (`try_cast`).

3. **Confinamento e Segurança no Workspace**:
   - Restringe operações de leitura, escrita e modificação estritamente ao diretório `models/`.
   - Gera prévias com diffs unificados (`propose_diff`) antes da aplicação das alterações.
   - Mantém histórico de modificações e oferece suporte a reversões imediatas (`revert_file`).

4. **Resiliência a Concorrência e Locks no DuckDB**:
   - Utiliza conexões estritamente somente leitura com consultas limitadas (`SELECT`, `SHOW`, `DESCRIBE`).
   - Rejeita comandos DDL e destrutivos (`DROP`, `DELETE`, `UPDATE`, `TRUNCATE`).
   - Se um processo externo mantiver um lock exclusivo no arquivo DuckDB (como uma interface gráfica ou terminal interativo do DuckDB aberto), o inspetor recorre automaticamente a um snapshot temporário, garantindo que consultas analíticas nunca travem ou falhem.

5. **Sessões Persistentes Multi-Turn**:
   - Salva o estado da sessão (objetivo, requisitos, entidades-alvo, arquivos alterados, revisões, relatórios de validação e feedbacks) em SQLite local (`.harness/sessions.db`).
   - Independente do histórico de conversas do agente, permitindo troca de runtime ou continuação do trabalho entre reinicializações.

6. **Adaptador de Referência para Google ADK**:
   - Converte todas as ferramentas do harness em objetos nativos `google.adk.tools.FunctionTool`.
   - Pré-configura um agente autônomo de engenharia (`google.adk.agents.Agent`) com instruções contextuais e amarração de ferramentas.

---

## Instalação e Configuração

Requisitos:
- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (recomendado) ou ambiente virtual padrão

Instalação das dependências e registro da CLI:
```bash
uv pip install -e .
```

---

## Uso da Linha de Comando (CLI)

O harness disponibiliza uma interface CLI voltada tanto para desenvolvedores humanos quanto para automações:

### Inspecionar Arquitetura do Projeto
```bash
harness inspect
```
Exibe o total de modelos, camadas arquiteturais (`landing`, `raw`, `staging`, `trusted`), localização do DuckDB e entidades de negócio descobertas.

### Listar Modelos por Camada
```bash
harness models
harness models --layer trusted
harness models --layer staging
```

### Inspecionar Detalhes e Linhagem de um Modelo
```bash
harness model dim_aeronaves
```

### Validar e Avaliar um Modelo
```bash
harness validate dim_aeronaves --layer trusted --pk marca_aeronave
```

### Iniciar Sessão com o Runtime do Google ADK

Você pode executar o agente via linha de comando ou via interface gráfica web oficial do ADK:

#### 1. Via Interface Web Oficial do Google ADK
O Google ADK fornece uma interface web com chat interativo, visualização das chamadas de ferramentas e logs.

Para iniciar o servidor web:
```bash
uv run adk web agents
# ou especificando a porta:
uv run adk web agents --port 8000
```
Após executar, acesse no navegador: `http://localhost:8000` (ou a porta informada no terminal). Na interface web, selecione o agente `dbt_developer`.

#### 2. Via Linha de Comando (CLI)
```bash
# Modo interativo no terminal
harness agent --session minha-sessao-001

# Execução de instrução pontual
harness agent --session minha-sessao-001 --message "Descubra os modelos existentes e verifique a conformidade de dim_aeronaves"
```

### Deletar um Modelo
Remova os arquivos SQL e YAML de um modelo com suporte a histórico e rollback:
```bash
harness delete dim_fabricantes_aeronaves --layer trusted
```

### Consultar o Banco com Segurança (Somente Leitura)
```bash
harness query "SELECT marca_aeronave, nm_fabricante, ds_modelo, is_apta_para_voo FROM trusted.dim_aeronaves LIMIT 5"
```

### Visualizar Diretrizes de Modelagem
```bash
harness guidelines
```

### Listar Sessões Persistentes
```bash
harness sessions
```

---

## Integração com Agentes de IA

Exemplo de instanciação do harness com o Google ADK:

```python
from harness.adapters.google_adk import create_adk_agent

# Inicializa o agente com sessão persistente
agent, registry, services = create_adk_agent(
    session_id="tarefa-aeronaves-001",
    model="gemini-2.5-flash",
)

print(f"Agente pronto: {agent.name} com {len(agent.tools)} ferramentas registradas.")
```

Ferramentas disponíveis expostas ao agente:
- `discover_project()`
- `list_models(layer=None)`
- `get_model_details(model_name)`
- `get_model_lineage(model_name)`
- `get_entity_definitions()`
- `get_guidelines()`
- `check_guidelines_compliance(model_name, sql_content, yaml_content, layer)`
- `read_model_file(relative_path)`
- `propose_model_diff(relative_path, new_content)`
- `write_model_file(relative_path, content)`
- `revert_model_file(relative_path)`
- `execute_dbt(command, select, timeout_seconds)`
- `query_database(sql, limit)`
- `inspect_table_profile(table_name, schema_name)`
- `check_pk_uniqueness(table_name, pk_column, schema_name)`
- `validate_and_evaluate_model(model_name, layer, primary_key)`

---

## Execução dos Testes Automatizados

Execute a suíte completa de testes com o `pytest`:

```bash
uv run pytest tests/ -v
```

Cobertura dos testes:
- `test_discovery.py`: Parser de manifest, fallback AST, extração de colunas e linhagem.
- `test_guidelines.py`: Validação de regras ECM, convenções de nomes, constraints de chave primária e testes booleanos.
- `test_workspace.py`: Segurança de limites de diretório, geração de diffs, gravação de arquivos e rollback.
- `test_dbt_runner.py`: Whitelist de comandos permitidos, timeouts e classificação de erros (locks vs compilação vs testes).
- `test_duckdb.py`: Imposição de leitura exclusiva, rejeição de DDL, listagem de esquemas/tabelas, contagem de linhas e checagem de unicidade de PK.
- `test_sessions.py`: Criação, leitura, atualização, revisões e histórico de validações no SQLite.
- `test_evals.py`: Avaliação determinística e formatação de relatórios em Markdown.
- `test_adk_adapter.py`: Conversão para `FunctionTool` e `Agent` do Google ADK.
- `test_end_to_end.py`: Cenário completo multi-turn (descoberta -> checagem de diretrizes -> revisão de diff -> gravação segura -> avaliação mockada -> rollback -> conclusão de sessão).

---

## Considerações e Limitações Conhecidas

1. **Locks de Escrita no DuckDB**:
   - O DuckDB permite apenas um processo gravador por vez no arquivo do banco de dados.
   - Para operações de leitura, o harness utiliza snapshot transparente para evitar bloqueios.
   - Para comandos dbt de gravação (`run`, `build`), caso um processo externo retenha o lock de escrita, o dbt retorna um erro classificado (`lock_error`) com o PID conflitante para que o usuário possa fechar a conexão.
2. **Outros Adaptadores**:
   - O Google ADK é o adaptador de referência implementado. Adaptadores adicionais (como Claude Agent SDK ou OpenAI Assistants) podem ser adicionados simplesmente consumindo `ToolRegistry.list_tools()`, sem necessidade de alterar as regras de negócio centrais.
