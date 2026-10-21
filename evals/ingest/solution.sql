CREATE TEMP TABLE raw AS
FROM read_csv('orders.csv', all_varchar = true, header = true);

CREATE TEMP TABLE typed AS
SELECT
    TRY_CAST(trim(order_id) AS BIGINT) AS order_id,
    COALESCE(
        TRY_CAST(trim(ordered_at) AS DATE),
        TRY_STRPTIME(trim(ordered_at), '%d/%m/%Y')::DATE
    ) AS ordered_at,
    NULLIF(trim(customer), '') AS customer,
    TRY_CAST(
        replace(replace(replace(trim(amount), '$', ''), '€', ''), ',', '')
        AS DECIMAL(18,2)
    ) AS amount,
    TRY_CAST(trim(payload) AS JSON) AS payload
FROM raw;

CREATE TEMP TABLE flagged AS
SELECT *,
    nullif(concat_ws('; ',
        CASE WHEN order_id IS NULL THEN 'invalid_order_id' END,
        CASE WHEN ordered_at IS NULL THEN 'invalid_date' END,
        CASE WHEN amount IS NULL THEN 'invalid_amount' END,
        CASE WHEN payload IS NULL THEN 'invalid_json' END
    ), '') AS reason
FROM typed;

CREATE TEMP TABLE good AS
FROM flagged
WHERE reason IS NULL;

CREATE TEMP TABLE bad AS
FROM flagged
WHERE reason IS NOT NULL;

COPY (
    SELECT *,
           year(ordered_at) AS year,
           month(ordered_at) AS month
    FROM good
)
TO 'out'
(
    FORMAT parquet,
    PARTITION_BY (year, month),
    OVERWRITE,
    FILENAME_PATTERN 'part_{i}',
    ROW_GROUP_SIZE 122880,
    COMPRESSION zstd,
    RETURN_FILES
);

COPY (SELECT * FROM bad) TO 'quarantine.parquet' (FORMAT parquet);
