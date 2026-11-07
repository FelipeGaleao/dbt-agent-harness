{{ config(
    materialized='table',
    schema='trusted'
) }}

/*
    Model: dim_aeronaves
    Pattern: Entity-Centric Data Modeling (ECM)
    Granularidade: 1 linha por aeronave registrada (Chave natural: marca_aeronave / MARCAS)
    Objetivo: Consolidar todas as características cadastrais, técnicas, operacionais,
              indicadores de conformidade (features) e status de aeronavegabilidade em uma única wide table.
*/

with raw_current as (
    select * from {{ ref('anac__rab_aeronaves_current') }}
),

features as (
    select
        -- 1. Chaves de Identificação da Entidade (Entity Spine / Keys)
        upper(trim(MARCAS)) as marca_aeronave,
        trim(NR_CERT_MATRICULA) as nr_certificado_matricula,
        trim(NR_SERIE) as nr_serie,

        -- 2. Atributos Descritivos e Especificações Técnicas do Ativo
        upper(trim(NM_FABRICANTE)) as nm_fabricante,
        upper(trim(DS_MODELO)) as ds_modelo,
        upper(trim(CD_TIPO_ICAO)) as cd_tipo_icao,
        upper(trim(CD_TIPO)) as cd_tipo_aeronave,
        upper(trim(CD_CLS)) as cd_classe,
        upper(trim(TP_MOTOR)) as tp_motor,
        upper(trim(TP_POUSO)) as tp_pouso,
        upper(trim(CF_OPERACIONAL)) as classificacao_operacional,
        upper(trim(DS_CATEGORIA_HOMOLOGACAO)) as categoria_homologacao,
        upper(trim(TP_OPERACAO)) as tp_operacao,

        -- 3. Métricas Físicas e Capacidades Operacionais
        cast(QT_MOTOR as integer) as qtd_motores,
        cast(NR_PASSAGEIROS_MAX as integer) as qtd_passageiros_max,
        cast(NR_TRIPULACAO_MIN as integer) as qtd_tripulacao_min,
        cast(NR_ASSENTOS as integer) as qtd_assentos_total,
        cast(NR_PMD as double) as pmd_kg,
        cast(NR_ANO_FABRICACAO as integer) as ano_fabricacao,

        -- 4. Marcos Temporais e Datas de Registro
        try_cast(DT_MATRICULA as date) as dt_matricula,
        try_cast(DT_VALIDADE_CA as date) as dt_validade_ca,
        try_cast(DT_VALIDADE_CVA as date) as dt_validade_cva,
        try_cast(DT_CANC as date) as dt_cancelamento,
        try_cast(DT_VENDA as date) as dt_venda,

        -- 5. Informações de Cancelamento e Gravames
        upper(trim(DS_MOTIVO_CANC)) as ds_motivo_cancelamento,
        upper(trim(DS_GRAVAME)) as ds_gravame,
        upper(trim(CD_INTERDICAO)) as cd_interdicao,

        -- 6. Dados Estruturados / Relacionamentos (Documentos JSON)
        PROPRIETARIOS as proprietarios_json,
        OPERADORES as operadores_json,

        -- 7. Dados Comerciais
        trim(DS_MOEDA) as cd_moeda_venda,
        cast(NR_PRECO_VENDA as double) as vl_preco_venda,

        -- 8. Metadados de Ingestão e Linhagem Técnica
        row_hash,
        snapshot_date,
        last_updated_at

    from raw_current
),

enriched_entity as (
    select
        *,
        -- Features Calculadas (ECM Mindset):
        -- Idade do ativo em anos
        case
            when ano_fabricacao is not null and ano_fabricacao > 1900
            then date_part('year', current_date) - ano_fabricacao
            else null
        end as idade_aeronave_anos,

        -- Contadores de dias restantes / expirados para auditoria
        case
            when dt_validade_cva is not null
            then date_diff('day', current_date, dt_validade_cva)
            else null
        end as dias_ate_vencimento_cva,

        case
            when dt_validade_ca is not null
            then date_diff('day', current_date, dt_validade_ca)
            else null
        end as dias_ate_vencimento_ca,

        -- Flags de Status Operacional e Conformidade
        coalesce(cd_interdicao = 'S', false) as is_interditada,
        coalesce(dt_cancelamento is not null or cd_interdicao = 'M', false) as is_matricula_cancelada,
        coalesce(ds_gravame is not null and trim(ds_gravame) != '', false) as has_gravame,

        -- Validade da inspeção técnica (CVA)
        case
            when dt_validade_cva is not null and dt_validade_cva >= current_date then true
            else false
        end as is_cva_valido,

        -- Validade do certificado de aeronavegabilidade (CA)
        case
            when dt_validade_ca is not null and dt_validade_ca >= current_date then true
            else false
        end as is_ca_valido

    from features
)

select
    -- Identificadores da Entidade
    marca_aeronave,
    nr_certificado_matricula,
    nr_serie,

    -- Especificações Técnicas
    nm_fabricante,
    ds_modelo,
    cd_tipo_icao,
    cd_tipo_aeronave,
    cd_classe,
    tp_motor,
    qtd_motores,
    tp_pouso,
    pmd_kg,
    ano_fabricacao,
    idade_aeronave_anos,

    -- Capacidades
    qtd_tripulacao_min,
    qtd_passageiros_max,
    qtd_assentos_total,

    -- Classificação e Uso
    classificacao_operacional,
    categoria_homologacao,
    tp_operacao,

    -- Situação Legal e Conformidade (Features de Decisão Rápida)
    is_interditada,
    is_matricula_cancelada,
    has_gravame,
    is_cva_valido,
    is_ca_valido,

    -- Flag de Conclusão Sintética (Health Status da Entidade):
    -- Aeronave considerada apta a voar se não estiver interditada, com matrícula ativa e CVA válido.
    (
        not is_interditada
        and not is_matricula_cancelada
        and is_cva_valido
    ) as is_apta_para_voo,

    -- Datas Críticas
    dt_matricula,
    dt_validade_cva,
    dias_ate_vencimento_cva,
    dt_validade_ca,
    dias_ate_vencimento_ca,
    dt_cancelamento,
    ds_motivo_cancelamento,
    ds_gravame,

    -- Aspectos Comerciais
    dt_venda,
    cd_moeda_venda,
    vl_preco_venda,

    -- Relacionamentos Mapeados (JSON)
    proprietarios_json,
    operadores_json,

    -- Auditoria
    row_hash,
    snapshot_date,
    last_updated_at

from enriched_entity

