---
name: duckdb-spatial
description: >
  Answer location questions with the DuckDB 2.0 spatial extension. Covers
  distance, containment, GeoJSON, Shapefile, GeoPackage, Overture Maps, H3,
  and R-tree indexes. Use when the user mentions maps, lat/lng, a bounding
  box, a geospatial file, or Overture.
---

# Spatial queries

```sql
INSTALL spatial;
LOAD spatial;
SET geometry_always_xy = true;
```

The spatial extension is not autoloadable. `geometry_always_xy` has no default in 2.0. `ST_Transform`, `ST_Distance_Spheroid`, `ST_Area_Spheroid`, and `ST_Length_Spheroid` raise an `Invalid Configuration Error` until it is set. Set it to `true` for longitude, latitude. Setting it to `false` is not a safe default: for EPSG:4326 it reads the coordinates as latitude, longitude and returns wrong numbers. Read it from `duckdb_settings()`; `current_setting('geometry_always_xy')` fails even after `LOAD spatial`.

## Coordinates and distance

Build a point as `ST_Point(longitude, latitude)`. Longitude is first.

```sql
SELECT ST_Point(-73.985, 40.748) AS p;
```

`ST_Distance` on lon/lat is a planar number, not meters. `ST_Distance_Spheroid` wants two `POINT_2D` values:

```sql
SELECT ST_Distance_Spheroid(
    ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D,
    ST_Point(-73.985, 40.748)::POINT_2D
) AS meters;
```

`ST_Area_Spheroid` takes `GEOMETRY` or `POLYGON_2D`; `ST_Length_Spheroid` takes `GEOMETRY` or `LINESTRING_2D`. They return square meters and meters. They do not take `POINT_2D`.

For a CRS change, set `geometry_always_xy` or pass the optional `always_xy` argument. A CRS-typed geometry cannot cast straight to `POINT_2D`; strip the CRS with `::GEOMETRY::POINT_2D` or rebuild the point:

```sql
SELECT ST_AsText(ST_Transform(ST_Point(-73.985, 40.748), 'EPSG:4326', 'EPSG:3857'));
```

## Filter before geometry

Filter with `bbox.xmin` and `bbox.ymin` before any `ST_*` call. `bbox` is a per-row struct, not a partition column. For point data the min corner equals the point, so the min-corner predicate is exact. For polygons it is only a coarse prefilter, and a predicate on `xmax` or `ymax` can drop a feature that starts outside the box but intersects it. Follow the bbox filter with `ST_Intersects`.

```sql
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
```

For a local table with a `GEOMETRY` column, an R-tree index turns those predicates into an index scan:

```sql
CREATE INDEX my_idx ON places USING RTREE (geom);
EXPLAIN SELECT count(*) FROM places
WHERE ST_Within(geom, ST_MakeEnvelope(-74.01, 40.72, -73.96, 40.77));
```

The plan shows `Rtree Index Scan`. The index works for `ST_Equals`, `ST_Intersects`, `ST_Touches`, `ST_Crosses`, `ST_Within`, `ST_Contains`, `ST_Overlaps`, `ST_Covers`, `ST_CoveredBy`, `ST_ContainsProperly`, and `ST_DWithin`, when one argument is constant at planning time. `ST_Distance(geom, point) < d` does not use the index; rewrite it as `ST_DWithin`. Build the index after the table is loaded; bulk loading is faster than incremental inserts.

## Read and write

`ST_Read` reads GeoJSON, Shapefile, GeoPackage, FlatGeobuf, and GPX after `LOAD spatial`.

```sql
SELECT * FROM ST_Read('file.geojson') LIMIT 20;
SELECT * FROM ST_Read('file.gpkg') LIMIT 20;
SELECT * FROM ST_Drivers();
```

GeoJSON can also go through the JSON reader, which is faster for large files:

```sql
SELECT * FROM read_json('features.geojson', geojson := true);
```

Export one result. Native GeoJSON is the simplest path in 2.0:

```sql
COPY (SELECT * FROM result) TO 'out.geojson' (FORMAT GEOJSON);
COPY (SELECT * FROM result) TO 'out.geojsonl' (FORMAT GEOJSONL);
```

For GeoPackage, FlatGeobuf, or Shapefile, use GDAL:

```sql
COPY (SELECT * FROM result) TO 'out.gpkg'
WITH (FORMAT GDAL, DRIVER 'GPKG', SRS 'EPSG:4326');
```

There is no `ST_Write` function in the 2.0 spatial extension. `COPY ... FORMAT GDAL` writes a table; native `FORMAT GEOJSON` writes a FeatureCollection. Only vector drivers are supported; rasters are not.

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

Places near a point:

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

`taxonomy` is `STRUCT(primary VARCHAR, hierarchy VARCHAR[], alternates VARCHAR[])`. `basic_category` is a separate flattened `VARCHAR`. There is no `categories` column. If `DESCRIBE` does not show `taxonomy`, stop and check the Overture schema page instead of guessing another name. Overture geometry is typed `GEOMETRY('OGC:CRS84')`; rebuild a `POINT_2D` with `ST_Point(ST_X(geometry), ST_Y(geometry))` rather than casting it directly.

Other themes use the same release prefix and `theme=<name>/type=<type>/*`:

| Theme | Type |
| --- | --- |
| `places` | `place` |
| `buildings` | `building` |
| `transportation` | `segment`, `connector` |
| `divisions` | `division`, `division_area`, `division_boundary` |
| `base` | `land`, `water`, `infrastructure` |
| `addresses` | `address` |

Run `DESCRIBE` on a `LIMIT` subquery before you depend on a column. The full schema notes and three worked queries are in [references/overture.md](references/overture.md).

The keyless S3 secret only sets the region. Do not put keys in the URL. Overture data has its own licenses per theme; check the Overture attribution page before publishing a derived dataset.

## H3

H3 is a community extension. Install rules are in `duckdb-extensions`.

```sql
INSTALL h3 FROM community;
LOAD h3;

SELECT h3_latlng_to_cell(40.748, -73.985, 9) AS cell,
       h3_get_resolution(h3_latlng_to_cell(40.748, -73.985, 9)) AS res,
       h3_cell_area(h3_latlng_to_cell(40.748, -73.985, 9), 'km^2') AS area;
```

`h3_latlng_to_cell(latitude, longitude, resolution)` is latitude first. Useful functions: `h3_cell_to_latlng` (returns `[lat, lng]`), `h3_cell_to_boundary_wkt`, `h3_get_resolution`, `h3_cell_area`, `h3_grid_disk`, `h3_cell_to_parent`, `h3_cell_to_children`. Resolutions run 0 to 15; 9 is roughly a neighborhood, and 16 returns `NULL`. Area units are `'m^2'` and `'km^2'`; `'m2'` and `'km2'` are rejected. `h3_grid_disk(cell, 1)` returns seven cells, including the center.

## Verify

```bash
duckdb -no-agent -c "
INSTALL spatial; LOAD spatial;
SET geometry_always_xy = true;
SELECT ST_AsGeoJSON(ST_Point(-73.985, 40.748)) AS point,
       ST_Distance_Spheroid(
           ST_Point(-73.985, 40.748)::POINT_2D,
           ST_Point(-73.97, 40.76)::POINT_2D
       ) AS meters;
"
```

The point must be a GeoJSON `Point` with `[-73.985, 40.748]`. The distance must be a positive number near 1,800 meters.

## References

- [Spatial overview](https://duckdb.org/docs/2.0/core_extensions/spatial/overview.html) owns install and the type surface.
- [Spatial functions](https://duckdb.org/docs/2.0/core_extensions/spatial/functions.html) owns the signatures.
- [GDAL integration](https://duckdb.org/docs/2.0/core_extensions/spatial/gdal.html) owns `ST_Read`, `ST_Drivers`, and `COPY ... FORMAT GDAL`.
- [R-tree indexes](https://duckdb.org/docs/2.0/core_extensions/spatial/r-tree_indexes.html) owns the index rules.
- [Overture DuckDB guide](https://docs.overturemaps.org/getting-data/duckdb/) owns the release lookup and examples.
- [Overture schema](https://docs.overturemaps.org/schema/) owns the current columns.
- [Overture release calendar](https://docs.overturemaps.org/release-calendar/) owns the release cadence.
- Bbox-first filtering and the `POINT_2D` cast are adapted from the `spatial` skill in https://github.com/duckdb/duckdb-skills (MIT). The release id and `taxonomy.primary` replace that skill's 2026-03-18 paths and `categories.primary` column. The STAC catalog returned `2026-10-21.0` on 2026-10-22. The skill reads the catalog rather than baking that id in.
