# Guideline: Entity-Centric Data Modeling (ECM) para Agentes Autônomos

> **Objetivo:** Estabelecer o padrão arquitetural, regras de decisão e diretrizes de implementação de **Entity-Centric Data Modeling (ECM)** na camada **Trusted / Business / Marts** do Lakehouse dbt. Este documento serve como base de conhecimento executável para agentes de IA tomarem decisões de engenharia de dados autônomas, padronizadas e sem ambiguidade.
>
> **Referências Teóricas:**
> - [Introducing Entity-Centric Data Modeling for Analytics (Maxime Beauchemin / Preset)](https://preset.io/blog/introducing-entity-centric-data-modeling-for-analytics/)
> - [Entity-Centric Data Modeling for Analytics: Optimizing KPIs for Effective Decision-Making (Michaël Scherding)](https://michael-scherding.medium.com/entity-centric-data-modeling-for-analytics-optimizing-kpis-for-effective-decision-making-6f41c36f3df0)

---

## 1. O que é Entity-Centric Data Modeling (ECM)?

Tradicionalmente, a modelagem dimensional (Kimball) fragmenta os dados de negócio em dezenas de tabelas de fatos (transações/eventos) e dimensões. Embora eficiente para armazenamento clássico, exige que analistas e ferramentas de BI realizem múltiplos `JOIN`s, `UNION ALL`s e agregações pesadas em tempo de consulta, gerando lentidão, inconsistência de KPIs e alto risco de multiplicação de métricas (*fan-out traps*).

O **ECM** inverte essa lógica: **as Entidades de Negócio (ex.: Aeronave, Proprietário, Operador, Cliente, Produto, Voo) tornam-se os cidadãos de primeira classe da arquitetura de dados.**

### Os 4 Pilares do ECM:
1. **Grain (Granularidade Estrita):**
   - Cada tabela representa exatamente **uma entidade** por linha (`entity_id` único), ou o histórico de uma entidade por período temporal fixo (`entity_id + snapshot_date / time_grain`).
   - Jamais misture granularidades em uma mesma tabela de entidade.
2. **Entity Spine (Espinha Dorsal):**
   - A espinha mestre de identificadores únicos garante que todas as entidades válidas existam no modelo, mesmo em períodos sem transações ou atividade recente.
3. **Rollup de Atividades (Activity to Feature):**
   - Em vez de forçar o usuário final a consultar tabelas transacionais cruas, os eventos e fatos são agregados previamente em colunas de métricas e estados calculados (ex.: contadores, métricas acumuladas, datas relativas, flags booleanas).
4. **Mentalidade de Feature Engineering (Wide Entity Tables):**
   - Inspirado no ecossistema de Machine Learning / Feature Stores: cria-se uma tabela ampla (*wide table*) contendo atributos estáticos, dados descritivos limpos, métricas agregadas pré-computadas, dimensões temporais e estruturas aninhadas/documentais (JSON/Structs/Lists quando suportado).

---

## 2. Estrutura de Camadas no Lakehouse com ECM

| Camada | Papel e Responsabilidades | Naming Convention dbt | Granularidade |
| :--- | :--- | :--- | :--- |
| **Landing** | Dados brutos ingeridos sem alteração técnica ou lógica (seeds/arquivos externos). | `landing_<fonte>` | Linha do arquivo original. |
| **Raw** | Histórico/Timeline com tipagem básica e controle de auditoria (`row_hash`, `loaded_at`). | `raw.<source>__<resource>_timeline`, `..._current` | Snapshot ou evento bruto. |
| **Staging** | **Sanitização Técnica 1:1:** Limpeza, renomeação de colunas, parsing resiliente (`try_cast`, `try_strptime`), remoção de caracteres de unidade (kg, R$) e normalização de nulos. **Não contém regras de negócio ou métricas agregadas.** | `staging.stg_<source>__<entity>` | 1:1 com a fonte raw limpa. |
| **Trusted (ECM)** | **Modelagem Entity-Centric e Negócio:** Wide tables centradas nas entidades, features pré-calculadas (ex: idade, status consolidado, dias para vencimento), regras de negócio e flags analíticas (`is_apta_para_voo`). Consome estritamente do `staging`. | `trusted.dim_<entity>`, `trusted.fct_<entity>_<event>` | **1 linha = 1 instância da Entidade** (ou `dim_<entity>_daily`). |

---

## 3. Matriz de Decisão para o Agente Autônomo

Ao receber uma solicitação de modelagem ou transformação de dados, o agente deve seguir rigorosamente a árvore de decisões abaixo:

```
[Nova Demanda de Dados]
       │
       ▼
1. Identificar o Core Object do Domínio
   • É um substantivo do negócio? (ex.: Aeronave, Empresa, Piloto) -> É uma ENTIDADE.
   • É um evento pontual no tempo? (ex.: Venda, Inspeção, Cancelamento) -> É uma ATIVIDADE/FATO.
       │
       ▼
2. Determinar a Granularidade (Grain)
   • 1 linha por entidade atual? -> `dim_<entity>` ou `<entity>_profile`
   • 1 linha por entidade ao longo do tempo (SCD / Snapshot)? -> `dim_<entity>_history`
   • 1 linha por evento da entidade? -> `fct_<entity>_<event>`
       │
       ▼
3. Pré-agregar Métricas na Entidade (Feature Mindset)
   • Calcular contadores de vida útil, idade do ativo, status operacional ativo/inativo.
   • Prevenir agregações manuais em BI gerando métricas explícitas e pré-calculadas.
       │
       ▼
4. Tratar Relações 1:N (Hierarquias e Afiliações)
   • A relação é 1:1 ou N:1? -> Desnormalizar diretamente na tabela da entidade (ex.: fabricante, modelo).
   • A relação é 1:N com dados repetidos? -> Usar Struct/JSON ou tabela ponte orientada a entidades subordinadas.
       │
       ▼
5. Implementar Testes dbt Obrigatórios
   • Chave primária: `unique` e `not_null`.
   • Flags booleanas: `accepted_values: [true, false]`.
   • Chaves estrangeiras / Integridade referencial.
```

---

## 4. Padrões de Nomenclatura e Design na Camada Trusted

1. **Prefixos das Tabelas:**
   - `dim_<entity>`: Dimensão ampla da entidade com visão corrente (Wide Table / Master Record). Ex: `dim_aeronaves`.
   - `fct_<entity>_<activity>`: Tabela de fatos com eventos atrelados à entidade. Ex: `fct_aeronave_transacoes`.
   - `bridge_<entity1>_<entity2>`: Tabela de relacionamento n:m se desnormalização não for desejada. Ex: `bridge_aeronave_operadores`.

2. **Parsing Resiliente de Dados Brutos (Lições Aprendidas):**
   - Dados de fontes governamentais ou semiestruturadas frequentemente contêm textos em campos numéricos (ex.: `'585Kg'`, `'2721,5'`, `'450 Kg'`). Nunca use `cast(... as double)` direto; use sempre extração regex limpa e `try_cast`.
   - Valores monetários em moeda local com separador de milhar (ex.: `'200.000,00'`) exigem remoção de ponto e troca de vírgula antes de conversão numérica.
   - Datas com múltiplos formatos e strings anômalas (ex.: `'RESRAB'`, `'ABORDO'`, `'24092027'`, `'12/05/2022'`) devem usar `coalesce` de múltiplos `try_strptime` para não quebrar a ingestão.

3. **Convenção de Nomes de Colunas:**
   - **Chaves de Identificação:** `id`. Deve ter apenas o campo _id. Caso seja uma chave estrangeira, utilize `<entity da chave estrangeira>__id`. 
   - **Atributos Categóricos / Descritivos:** `ds_<atributo>`, `nm_<atributo>`, `cd_<atributo>`, `tp_<atributo>`.
   - **Indicadores / Flags Booleanas:** `is_<condicao>` ou `has_<condicao>` (ex.: `is_operacional`, `is_interditada`, `has_gravame`).
   - **Métricas Agregadas / Features Numéricas:** `total_<metrica>`, `qtd_<metrica>`, `vl_<metrica>`, `idade_<unidade>` (ex.: `idade_aeronave_anos`, `qtd_motores`, `vl_venda_reais`).
   - **Datas e Timestamps:** `dt_<evento>` para datas (ex.: `dt_matricula`), `loaded_at` / `dbt_updated_at` para controle técnico.

3. **Valores Nulos e Strings Vazias:**
   - Normalizar strings vazias ou `""` para `NULL`.
   - Colunas booleanas devem ser estritamente `true` ou `false` (usar `coalesce(..., false)`).

---

## 5. Exemplo de Referência: Domínio Aeronáutico (ANAC RAB)

No caso do Registro Aeronáutico Brasileiro:
- **Entidade Primária:** `aeronave` (identificada exclusivamente pela matrícula `MARCAS`, ex.: `PR-GOL`, `PT-BTX`).
- **Dimensões do Ativo:** Fabricante, Modelo, Ano de Fabricação, Tipo de Pouso, Categoria de Homologação, Quantidade de Motores, PMD (Peso Máximo de Decolagem).
- **Métricas de Atividade / Features Embutidas:**
  - `idade_aeronave_anos`: calculada a partir de `ano_fabricacao`.
  - `dias_ate_vencimento_cva`: dias restantes até a expiração da verificação de aeronavegabilidade.
  - `is_cva_valido`: booleano indicando validade do CVA.
  - `is_interditada`: booleano indicando se possui ordem de interdição.
  - `is_matricula_cancelada`: booleano indicando se o registro foi baixado/cancelado.
  - `is_apta_para_voo`: regra de negócio consolidada (`not is_interditada and not is_matricula_cancelada and is_cva_valido`).
- **Entidades Conexas:** `proprietarios` e `operadores` (podem ser modelados como dimensões derivadas ou mantidos estruturados para auditoria).

---

## 6. Checklist de Validação para Agentes de IA

Antes de finalizar qualquer modelo na camada `trusted`, o agente deve validar:
- [ ] O modelo responde diretamente à pergunta: *"Quero saber tudo sobre esta entidade específica numa única linha"*?
- [ ] O grain está definido e documentado no arquivo `schema.yml`?
- [ ] O teste de unicidade (`unique`) e nulidade (`not_null`) está aplicado à chave da entidade?
- [ ] Todas as flags de status foram convertidas para booleanos nomeados com `is_` ou `has_`?
- [ ] Métricas temporais (idades, dias decorridos, dias até vencimento) foram pré-computadas?
- [ ] A documentação no `schema.yml` descreve as regras de negócio utilizadas nas métricas calculadas?

