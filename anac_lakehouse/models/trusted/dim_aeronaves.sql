
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
    materialized='incremental',
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

{% if is_incremental() %}

-- Implement SCD Type 2 logic using MERGE statement
MERGE INTO {{ this }} AS target
USING (
    -- New and changed records from the source
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
    WHERE NOT EXISTS (
        SELECT 1
        FROM {{ this }} AS current_target
        WHERE current_target.marca_aeronave = source_data_with_hash.marca_aeronave
          AND current_target.is_atual = TRUE
          AND current_target.change_hash = source_data_with_hash.change_hash
    )
) AS source
ON target.marca_aeronave = source.marca_aeronave AND target.is_atual = TRUE

-- When a record in the target matches an existing record in the source (by marca_aeronave)
-- AND the hash has changed, then update the target record to close it out.
WHEN MATCHED AND target.change_hash != source.change_hash THEN
    UPDATE SET
        dt_vigencia_fim = CURRENT_DATE - INTERVAL '1 day',
        is_atual = FALSE

-- When a record in the source does not exist in the target (by marca_aeronave, is_atual = TRUE)
-- OR the hash has changed, then insert a new record.
WHEN NOT MATCHED THEN
    INSERT (
        sk_aeronave,
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
        dt_vigencia_inicio,
        dt_vigencia_fim,
        is_atual,
        change_hash
    )
    VALUES (
        source.sk_aeronave,
        source.marca_aeronave,
        source.nr_certificado_matricula,
        source.nr_serie,
        source.nm_fabricante,
        source.ds_modelo,
        source.cd_tipo_icao,
        source.cd_tipo_aeronave,
        source.cd_classe,
        source.tp_motor,
        source.qtd_motores,
        source.tp_pouso,
        source.pmd_kg,
        source.ano_fabricacao,
        source.idade_aeronave_anos,
        source.qtd_tripulacao_min,
        source.qtd_passageiros_max,
        source.qtd_assentos_total,
        source.classificacao_operacional,
        source.categoria_homologacao,
        source.tp_operacao,
        source.is_interditada,
        source.is_matricula_cancelada,
        source.has_gravame,
        source.is_cva_valido,
        source.is_ca_valido,
        source.is_apta_para_voo,
        source.dt_matricula,
        source.dt_validade_cva,
        source.dias_ate_vencimento_cva,
        source.dt_validade_ca,
        source.dias_ate_vencimento_ca,
        source.dt_cancelamento,
        source.ds_motivo_cancelamento,
        source.ds_gravame,
        source.dt_venda,
        source.cd_moeda_venda,
        source.vl_preco_venda,
        source.proprietarios_json,
        source.operadores_json,
        source.row_hash,
        source.snapshot_date,
        source.last_updated_at,
        source.dt_vigencia_inicio,
        source.dt_vigencia_fim,
        source.is_atual,
        source.change_hash
    )

{% else %}

-- Full refresh logic (initial build)
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

{% endif %}
