.mode line
.output proof.txt

SELECT 'input_rows' AS metric, count(*) AS value
FROM read_csv('orders.csv', all_varchar = true, header = true)
UNION ALL
SELECT 'clean_rows', count(*) FROM read_parquet('out/**/*.parquet')
UNION ALL
SELECT 'quarantine_rows', count(*) FROM 'quarantine.parquet'
UNION ALL
SELECT 'parquet_footer_rows', sum(num_rows) FROM parquet_file_metadata('out/**/*.parquet')
ORDER BY metric;

.output stdout
