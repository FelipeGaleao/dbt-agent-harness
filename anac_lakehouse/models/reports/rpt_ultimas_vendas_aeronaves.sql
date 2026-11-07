{{ config(
    materialized='table',
    schema='reports'
) }}

WITH dim_aeronaves_current AS (
    SELECT
        sk_aeronave,
        marca_aeronave,
        proprietarios_json,
        dt_venda,
        vl_preco_venda,
        cd_moeda_venda,
        ds_modelo AS ds_modelo_aeronave,
        nm_fabricante AS nm_fabricante_aeronave,
        ano_fabricacao AS ano_fabricacao_aeronave,
        idade_aeronave_anos,
        is_matricula_cancelada,
        is_apta_para_voo
    FROM {{ ref('dim_aeronaves') }}
    WHERE is_atual = TRUE
      AND dt_venda IS NOT NULL -- Only consider records with a sale date
),

proprietarios_expanded AS (
    SELECT
        a.marca_aeronave,
        json_extract(prop.value, '$.DOCUMENTO') AS nr_cpf_cnpj_proprietario,
        json_extract(prop.value, '$.NOME') AS nm_proprietario_raw,
        json_extract(prop.value, '$.UF') AS cd_uf_proprietario_raw,
        a.dt_venda,
        a.vl_preco_venda,
        a.cd_moeda_venda,
        a.ds_modelo_aeronave,
        a.nm_fabricante_aeronave,
        a.ano_fabricacao_aeronave,
        a.idade_aeronave_anos,
        a.is_matricula_cancelada,
        a.is_apta_para_voo
    FROM
        dim_aeronaves_current a,
        json_each(a.proprietarios_json) AS prop
),

cleaned_and_joined AS (
    SELECT
        pe.marca_aeronave,
        REPLACE(REGEXP_REPLACE(pe.nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '') AS sk_proprietario,
        REPLACE(pe.nm_proprietario_raw, '"', '') AS nm_proprietario_temp,
        REPLACE(pe.cd_uf_proprietario_raw, '"', '') AS cd_uf_proprietario_temp,
        pe.dt_venda,
        pe.vl_preco_venda,
        pe.cd_moeda_venda,
        pe.ds_modelo_aeronave,
        pe.nm_fabricante_aeronave,
        pe.ano_fabricacao_aeronave,
        pe.idade_aeronave_anos,
        pe.is_matricula_cancelada,
        pe.is_apta_para_voo,
        dp.nm_proprietario, -- From dim_proprietarios
        dp.cd_uf_proprietario -- From dim_proprietarios
    FROM proprietarios_expanded pe
    LEFT JOIN {{ ref('dim_proprietarios') }} dp
        ON REPLACE(REGEXP_REPLACE(pe.nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '') = dp.sk_proprietario
    WHERE REPLACE(REGEXP_REPLACE(pe.nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '') IS NOT NULL
      AND (LENGTH(REPLACE(REGEXP_REPLACE(pe.nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '')) = 11 OR LENGTH(REPLACE(REGEXP_REPLACE(pe.nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '')) = 14) -- Filter valid CPF/CNPJ
)

SELECT
    marca_aeronave,
    sk_proprietario,
    COALESCE(nm_proprietario, nm_proprietario_temp) AS nm_proprietario, -- Prefer joined name, fallback to raw if not found
    COALESCE(cd_uf_proprietario, cd_uf_proprietario_temp) AS cd_uf_proprietario, -- Prefer joined UF, fallback to raw if not found
    dt_venda,
    vl_preco_venda,
    cd_moeda_venda,
    ds_modelo_aeronave,
    nm_fabricante_aeronave,
    ano_fabricacao_aeronave,
    idade_aeronave_anos,
    is_matricula_cancelada,
    is_apta_para_voo,
    TRUE AS is_ultima_venda -- Always TRUE since we filter dim_aeronaves by is_atual
FROM cleaned_and_joined
WHERE sk_proprietario IS NOT NULL -- Ensure a valid proprietor is present
