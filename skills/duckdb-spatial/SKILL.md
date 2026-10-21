---
name: duckdb-spatial
description: >
  Answer location questions with the DuckDB 2.0 spatial extension: distances,
  containment, GeoJSON and Shapefile, and Overture Maps. Use when the user
  mentions maps, lat/lng, GeoJSON, Shapefile, GeoPackage, Overture, or
  /duckdb-spatial.
---

# Spatial queries

```sql
INSTALL spatial;
LOAD spatial;
SET geometry_always_xy = true;
```

`geometry_always_xy` makes functions treat coordinates as longitude, then latitude. Leave it on for GeoJSON, Overture, and CSV files of lon/lat.

Build a point from a CSV as `ST_Point(longitude, latitude)`. Longitude is first.

Real-world distance and area use the spheroid functions, and those functions want `POINT_2D`. Overture's geometry column is a generic geometry. Extract coordinates, then cast:

```sql
ST_Distance_Spheroid(
    ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D,
    ST_Point(-73.985, 40.748)::POINT_2D
)
```

`ST_Distance` on lon/lat is a planar number, not meters.

Filter with `bbox.xmin` and `bbox.ymin` before any `ST_*` call. For point data the partition column is the min corner. A predicate on `xmax` and `ymax` drops edge partitions.

```sql
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
```

User files: `ST_Read('file.geojson')` after `LOAD spatial`. Shapefile, GeoPackage, and GPX use the same function. Export one result when the user wants a map file:

```sql
COPY (SELECT * FROM result) TO 'out.geojson' (FORMAT GDAL, DRIVER 'GeoJSON');
```

H3 hexes need `INSTALL h3 FROM community`. Install rules are in `duckdb-extensions`.

Function signatures that are not in this file belong in `duckdb-docs`, then a one-row test. Do not paste a function catalog into the answer.

## Overture, when the user has no file

Overture publishes GeoParquet on a public bucket and deletes old releases. Resolve the release from the catalog on every run. Do not hardcode a release id.

```sql
LOAD httpfs;
LOAD spatial;
SET geometry_always_xy = true;
CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');
SET VARIABLE latest = (
    SELECT latest FROM 'https://stac.overturemaps.org/catalog.json'
);
```

Places:

```sql
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=places/type=place/*'
)
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
  AND taxonomy.primary = 'coffee_shop'
LIMIT 20;
```

`categories.primary` was removed in the 2026-09-23 Overture schema. The category column is `taxonomy.primary`. If `DESCRIBE` does not show it, stop and check the Overture schema page instead of guessing another name.

Other themes use the same release prefix and `theme=<name>/type=<type>/*`. Buildings are `theme=buildings/type=building`. Roads are `theme=transportation/type=segment`. Run `DESCRIBE` on a `LIMIT` subquery before you depend on a column.

The keyless S3 secret only sets the region. It was accepted by DuckDB 2.0.0. Do not put keys in the URL.

## References

- https://duckdb.org/docs/2.0/core_extensions/spatial/overview.html
- https://docs.overturemaps.org/getting-data/duckdb/
- https://docs.overturemaps.org/release-calendar/
- https://stac.overturemaps.org/catalog.json
- Bbox-first filtering and the `POINT_2D` cast are adapted from the `spatial` skill in https://github.com/duckdb/duckdb-skills (MIT). The release id and `taxonomy.primary` replace that skill's 2026-03-18 paths and `categories.primary` column. `SELECT latest FROM` the STAC catalog returned `2026-10-21.0` on 2026-10-22. The skill still reads the catalog rather than baking that id in.
