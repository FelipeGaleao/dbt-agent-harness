{{ config(
    materialized='table',
    schema='trusted'
) }}

/*
    Model: dim_aeronaves
    Pattern: Entity-Centric Data Modeling (ECM)
    Granularidade: 1 linha por aeronave registrada (Chave natural: marca_aeronave)
    Origem: stg_anac__rab_aeronaves
    Objetivo: Consolidar características de negócio da entidade Aeronave,
              aplicando o Entity-Centric Mindset (features calculadas, conformidade operacional,
              regras de negócio e auditoria analítica).
*/

with stg_aeronaves as (
    select * from {{ ref('stg_anac__rab_aeronaves') }}
),

enriched_entity as (
    select
        -- 1. Identificadores da Entidade
        cd_marca_aeronave as marca_aeronave,
        nr_certificado_matricula,
        nr_serie,

        -- 2. Especificações Técnicas do Ativo
        nm_fabricante,
        ds_modelo,
        cd_tipo_icao,
        cd_tipo_aeronave,
        cd_classe,
        tp_motor,
        qt_motores as qtd_motores,
        tp_pouso,
        nr_pmd_kg as pmd_kg,
        nr_ano_fabricacao as ano_fabricacao,

        -- Feature: Idade do ativo calculada
        case
            when nr_ano_fabricacao is not null and nr_ano_fabricacao > 1900
            then date_part('year', current_date) - nr_ano_fabricacao
            else null
        end as idade_aeronave_anos,

        -- 3. Capacidades
        qt_tripulacao_min as qtd_tripulacao_min,
        qt_passageiros_max as qtd_passageiros_max,
        qt_assentos_total as qtd_assentos_total,

        -- 4. Classificação e Operação
        ds_classificacao_operacional as classificacao_operacional,
        ds_categoria_homologacao as categoria_homologacao,
        tp_operacao,

        -- 5. Flags de Conformidade e Decisão Operacional (Features de Negócio ECM)
        coalesce(cd_interdicao = 'S', false) as is_interditada,
        coalesce(dt_cancelamento is not null or cd_interdicao = 'M', false) as is_matricula_cancelada,
        coalesce(ds_gravame is not null and trim(ds_gravame) != '' and trim(ds_gravame) != 'NENHUM GRAVAME REGISTRADO', false) as has_gravame,

        case
            when dt_validade_cva is not null and dt_validade_cva >= current_date then true
            else false
        end as is_cva_valido,

        case
            when dt_validade_ca is not null and dt_validade_ca >= current_date then true
            else false
        end as is_ca_valido,

        -- 6. Datas e Prazos Regulatórios
        dt_matricula,
        dt_validade_cva,
        case
            when dt_validade_cva is not null
            then date_diff('day', current_date, dt_validade_cva)
            else null
        end as dias_ate_vencimento_cva,

        dt_validade_ca,
        case
            when dt_validade_ca is not null
            then date_diff('day', current_date, dt_validade_ca)
            else null
        end as dias_ate_vencimento_ca,

        dt_cancelamento,
        ds_motivo_cancelamento,
        ds_gravame,

        -- 7. Aspectos Comerciais
        dt_venda,
        cd_moeda_venda,
        vl_preco_venda,

        -- 8. Relacionamentos Documentais
        proprietarios_json,
        operadores_json,

        -- 9. Metadados de Linhagem Técnica
        row_hash,
        snapshot_date,
        last_updated_at

    from stg_aeronaves
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

    -- Health Status Consolidado da Entidade:
    (
        not is_interditada
        and not is_matricula_cancelada
        and is_cva_valido
    ) as is_apta_para_voo,

    -- Datas Críticas e Auditoria de Prazos
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

    -- Linhagem e Auditoria
    row_hash,
    snapshot_date,
    last_updated_at

from enriched_entity
