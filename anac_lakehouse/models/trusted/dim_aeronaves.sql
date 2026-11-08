
/*
    Model: dim_aeronaves
    Pattern: Entity-Centric Data Modeling (ECM)
    Granularidade: 1 linha por aeronave registrada (Chave natural: marca_aeronave)
    Origem: stg_anac__rab_aeronaves
*/

{%- set scd_columns = [
    'nr_certificado_matricula', 'nr_serie', 'nm_fabricante', 'ds_modelo', 'cd_tipo_icao',
    'cd_tipo_aeronave', 'cd_classe', 'tp_motor', 'qtd_motores', 'tp_pouso', 'pmd_kg',
    'ano_fabricacao', 'idade_aeronave_anos', 'qtd_tripulacao_min', 'qtd_passageiros_max',
    'qtd_assentos_total', 'classificacao_operacional', 'categoria_homologacao', 'tp_operacao',
    'is_interditada', 'is_matricula_cancelada', 'has_gravame', 'is_cva_valido', 'is_ca_valido',
    'dt_matricula', 'dt_validade_cva', 'dt_validade_ca', 'dt_cancelamento',
    'ds_motivo_cancelamento', 'ds_gravame', 'dt_venda', 'cd_moeda_venda', 'vl_preco_venda',
    'proprietarios_json', 'operadores_json'
] -%}

{{ config(
    materialized='table',
    schema='trusted'
) }}

WITH stg_aeronaves AS (
    SELECT * FROM {{ ref('stg_anac__rab_aeronaves') }}
),

enriched_entity AS (
    SELECT
        -- All existing columns and calculated features
        cd_marca_aeronave AS marca_aeronave,
        nr_certificado_matricula,
        nr_serie,
        nm_fabricante,
        ds_modelo,
        cd_tipo_icao,
        cd_tipo_aeronave,
        cd_classe,
        tp_motor,
        qt_motores AS qtd_motores,
        tp_pouso,
        nr_pmd_kg AS pmd_kg,
        nr_ano_fabricacao AS ano_fabricacao,
        CASE
            WHEN nr_ano_fabricacao IS NOT NULL AND nr_ano_fabricacao > 1900
            THEN DATE_PART('year', CURRENT_DATE) - nr_ano_fabricacao
            ELSE NULL
        END AS idade_aeronave_anos,
        qt_tripulacao_min AS qtd_tripulacao_min,
        qt_passageiros_max AS qtd_passageiros_max,
        qt_assentos_total AS qtd_assentos_total,
        ds_classificacao_operacional AS classificacao_operacional,
        ds_categoria_homologacao AS categoria_homologacao,
        tp_operacao,
        COALESCE(cd_interdicao = 'S', FALSE) AS is_interditada,
        COALESCE(dt_cancelamento IS NOT NULL OR cd_interdicao = 'M', FALSE) AS is_matricula_cancelada,
        COALESCE(ds_gravame IS NOT NULL AND TRIM(ds_gravame) != '' AND TRIM(ds_gravame) != 'NENHUM GRAVAME REGISTRADO', FALSE) AS has_gravame,
        CASE
            WHEN dt_validade_cva IS NOT NULL AND dt_validade_cva >= CURRENT_DATE THEN TRUE
            ELSE FALSE
        END AS is_cva_valido,
        CASE
            WHEN dt_validade_ca IS NOT NULL AND dt_validade_ca >= CURRENT_DATE THEN TRUE
            ELSE FALSE
        END AS is_ca_valido,
        (NOT COALESCE(cd_interdicao = 'S', FALSE) AND NOT COALESCE(dt_cancelamento IS NOT NULL OR cd_interdicao = 'M', FALSE) AND (CASE WHEN dt_validade_cva IS NOT NULL AND dt_validade_cva >= CURRENT_DATE THEN TRUE ELSE FALSE END)) AS is_apta_para_voo,
        dt_matricula,
        dt_validade_cva,
        CASE
            WHEN dt_validade_cva IS NOT NULL
            THEN DATE_DIFF('day', CURRENT_DATE, dt_validade_cva)
            ELSE NULL
        END AS dias_ate_vencimento_cva,
        dt_validade_ca,
        CASE
            WHEN dt_validade_ca IS NOT NULL
            THEN DATE_DIFF('day', CURRENT_DATE, dt_validade_ca)
            ELSE NULL
        END AS dias_ate_vencimento_ca,
        dt_cancelamento,
        ds_motivo_cancelamento,
        ds_gravame,
        dt_venda,
        cd_moeda_venda,
        vl_preco_venda,
        proprietarios_json,
        operadores_json,
        row_hash,
        snapshot_date,
        last_updated_at
    FROM stg_aeronaves
),

-- Create a hash for all relevant SCD columns to detect changes
source_data_with_hash AS (
    SELECT
        *,
        MD5(
            {% for column in scd_columns %}
            COALESCE(CAST({{ column }} AS VARCHAR), '') {{ '||' if not loop.last }}
            {% endfor %}
        ) AS change_hash
    FROM enriched_entity
)

-- Final Entity Table
SELECT
    UUID() AS sk_aeronave,
    marca_aeronave,
    nr_certificado_matricula,
    nr_serie,
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
    qtd_tripulacao_min,
    qtd_passageiros_max,
    qtd_assentos_total,
    classificacao_operacional,
    categoria_homologacao,
    tp_operacao,
    is_interditada,
    is_matricula_cancelada,
    has_gravame,
    is_cva_valido,
    is_ca_valido,
    is_apta_para_voo,
    dt_matricula,
    dt_validade_cva,
    dias_ate_vencimento_cva,
    dt_validade_ca,
    dias_ate_vencimento_ca,
    dt_cancelamento,
    ds_motivo_cancelamento,
    ds_gravame,
    dt_venda,
    cd_moeda_venda,
    vl_preco_venda,
    proprietarios_json,
    operadores_json,
    row_hash,
    snapshot_date,
    last_updated_at,
    CURRENT_DATE AS dt_vigencia_inicio,
    NULL AS dt_vigencia_fim,
    TRUE AS is_atual,
    change_hash
FROM source_data_with_hash
