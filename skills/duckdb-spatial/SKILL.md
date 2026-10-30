---
name: duckdb-spatial
description: >
  Execute spatial queries using DuckDB 2.0 spatial and H3 extensions. Covers
  distance metrics, containment, GeoJSON, Shapefile, GeoPackage, Overture Maps,
  and R-tree index scans. Use when the user mentions maps, lat/lng, bounding
  boxes, geospatial files, or Overture.
---

# Spatial queries

Before calling spatial functions, install and load `spatial`, then configure coordinate order:

```sql
INSTALL spatial; LOAD spatial;
SET geometry_always_xy = true;
```

DuckDB does not autoload `spatial`. The session setting `geometry_always_xy` starts unset. While unset, CRS-sensitive functions (`ST_Transform`, `ST_Distance_Sphere`, `ST_Distance_Spheroid`, `ST_Area_Spheroid`, `ST_Length_Spheroid`) throw an `Invalid Configuration Error`. Always set `geometry_always_xy = true` to enforce `(longitude, latitude)` coordinate order. If set to `false`, CRS-sensitive operations interpret EPSG:4326 as `(latitude, longitude)`, causing silent calculation errors.
To inspect this setting, query `duckdb_settings()`; calling `current_setting('geometry_always_xy')` throws an error even after `LOAD spatial`.

## Measure

Construct points as `ST_Point(longitude, latitude)`. Longitude always precedes latitude. Select measurement functions by accuracy and cost:

| Goal | Function | Units and cost |
| --- | --- | --- |
| Same-CRS comparison | `ST_Distance` | CRS units (degrees on EPSG:4326); lowest cost |
| Fast meters on lon/lat | `ST_Distance_Sphere` | Meters (spherical approximation); low cost |
| Exact meters on lon/lat | `ST_Distance_Spheroid` | Meters (ellipsoidal calculation); highest cost |
| Radial containment | `ST_DWithin` plus bbox | Boolean; leverages R-tree index |

All spherical and spheroidal calculations rely on session `geometry_always_xy`; only `ST_Transform` accepts a per-call `always_xy` parameter.
For radius searches, write `ST_DWithin(geom, point, d)`. When `point` and `d` are constant at planning time, `ST_DWithin` invokes the R-tree index; `ST_Distance(geom, point) < d` forces a full sequential scan.

When computing ellipsoidal distance between coordinates, cast points to `POINT_2D`:

```sql
SELECT ST_Distance_Spheroid(
    ST_Point(ST_X(geom), ST_Y(geom))::POINT_2D,
    ST_Point(-73.985, 40.748)::POINT_2D
) AS meters;
```

For geodesic area and length, pass polygons or linestrings: `ST_Area_Spheroid` accepts `GEOMETRY` or `POLYGON_2D` (square meters); `ST_Length_Spheroid` accepts `GEOMETRY` or `LINESTRING_2D` (meters). Both accept `POINT_2D` casts but return `0.0`.
To project coordinates between CRS systems, run `ST_Transform(geom, 'EPSG:4326', 'EPSG:3857')`. Direct casts from CRS-typed geometry to `POINT_2D` fail; strip the CRS via `::GEOMETRY::POINT_2D` or rebuild with `ST_Point(ST_X(geom), ST_Y(geom))`.

## Filter before geometry

In Parquet and lake tables, `bbox` is a per-row `STRUCT(xmin, xmax, ymin, ymax)`, not a partition column. Always filter `bbox` before evaluating expensive geometry functions:

```sql
-- Points: min corner equals point coordinates
WHERE bbox.xmin BETWEEN -74.01 AND -73.96 AND bbox.ymin BETWEEN 40.72 AND 40.77

-- Lines and polygons: require two-axis overlap before ST_Intersects
WHERE bbox.xmax >= -74.01 AND bbox.xmin <= -73.96
  AND bbox.ymax >= 40.72  AND bbox.ymin <= 40.77
```

For lines and polygons, min-corner filters drop features originating outside the query box that cross into it. Never filter on `xmax` or `ymax` alone; a max predicate drops features extending beyond the query window.

To accelerate topological queries on local `GEOMETRY` tables, create an R-tree index:

```sql
CREATE INDEX my_idx ON places USING RTREE (geom);
EXPLAIN SELECT count(*) FROM places
WHERE ST_Within(geom, ST_MakeEnvelope(-74.01, 40.72, -73.96, 40.77));
```

The output plan confirms execution via `Rtree Index Scan`. R-tree indexes support `ST_Equals`, `ST_Intersects`, `ST_Touches`, `ST_Crosses`, `ST_Within`, `ST_Contains`, `ST_Overlaps`, `ST_Covers`, `ST_CoveredBy`, `ST_ContainsProperly`, and `ST_DWithin` whenever one argument is constant at planning time. Always populate tables before creating indexes; bulk loading into unindexed tables is significantly faster.

## Spatial joins

When joining spatial tables:
1. Build an R-tree index on the smaller or pre-filtered table.
2. Apply bounding-box overlap predicates on both inputs.
3. Join using `ST_Intersects` or `ST_Within`. The planner evaluates deferred bounds for the unindexed input.

Verify execution plans with `EXPLAIN`. A selective query must show `Rtree Index Scan` or `Spatial Join`. A `Seq Scan` on both sides indicates a missing index, omitted bounding-box predicates, or an unselective filter window.

## Read and write

To ingest spatial data, query `ST_Read` (drivers listed in `ST_Drivers()`). For large GeoJSON files, use `read_json` with `geojson := true` for higher throughput:

```sql
SELECT * FROM ST_Read('places.geojson') LIMIT 20;
SELECT * FROM read_json('places.geojson', geojson := true);
```

To export results, choose native GeoJSON or GDAL drivers:

```sql
COPY (SELECT * FROM result) TO 'out.geojson' (FORMAT GEOJSON); -- or FORMAT GEOJSONL
COPY (SELECT * FROM result) TO 'out.gpkg' WITH (FORMAT GDAL, DRIVER 'GPKG', SRS 'EPSG:4326');
```

DuckDB 2.0 provides no `ST_Write` function. Use `COPY ... FORMAT GDAL` for tables and native `FORMAT GEOJSON` for FeatureCollections. The spatial extension supports vector drivers only; raster formats are unsupported.

## Overture, when the user has no file

Overture publishes GeoParquet on a public S3 bucket and prunes older releases. Always resolve the active release dynamically from the STAC catalog; never hardcode a release identifier:

```sql
LOAD httpfs; LOAD spatial;
SET geometry_always_xy = true;
CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');
SET VARIABLE latest = (SELECT latest FROM 'https://stac.overturemaps.org/catalog.json');
```

To query places within a coordinate bounding box:

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

In places schemas, `taxonomy` is `STRUCT(primary VARCHAR, hierarchy VARCHAR[], alternates VARCHAR[])`, and `basic_category` is a flattened `VARCHAR`. There is no `categories` column. Overture geometry is typed `GEOMETRY('OGC:CRS84')`. To convert it into a `POINT_2D`, rebuild the point with `ST_Point(ST_X(geometry), ST_Y(geometry))` rather than casting directly.

Access other themes with path pattern `theme=<name>/type=<type>/*`:

| Theme | Type |
| --- | --- |
| `places` | `place` |
| `buildings` | `building` |
| `transportation` | `segment`, `connector` |
| `divisions` | `division`, `division_area`, `division_boundary` |
| `base` | `land`, `water`, `infrastructure` |
| `addresses` | `address` |

Before filtering unverified columns, run `DESCRIBE SELECT ... LIMIT 0`. Schema structures and worked queries are documented in [references/overture.md](references/overture.md). The keyless S3 secret sets the region only; do not pass AWS credentials. Verify per-theme data licenses before publishing derived datasets.

## H3

For hexagonal hierarchical indexing, install H3 from the community repository (see `duckdb-extensions`):

```sql
INSTALL h3 FROM community; LOAD h3;

SELECT h3_latlng_to_cell(40.748, -73.985, 9) AS cell,
       h3_get_resolution(h3_latlng_to_cell(40.748, -73.985, 9)) AS res,
       h3_cell_area(h3_latlng_to_cell(40.748, -73.985, 9), 'km^2') AS area;
```

Unlike `ST_Point`, `h3_latlng_to_cell(latitude, longitude, resolution)` requires latitude first. Index resolutions span 0 to 15; resolution 9 covers neighborhood scales, and resolution 16 returns `NULL`. For `h3_cell_area`, supply `'m^2'` or `'km^2'`; `'m2'` and `'km2'` are rejected. Core functions include `h3_cell_to_latlng` (returns `[lat, lng]`), `h3_cell_to_boundary_wkt`, `h3_get_resolution`, `h3_cell_to_parent`, `h3_cell_to_children`, and `h3_grid_disk` (`h3_grid_disk(cell, 1)` returns 7 cells including the center).

## Verify

Run a standalone verification query to confirm geometry generation and spherical measurement:

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

The output point must be a GeoJSON `Point` with coordinates `[-73.985, 40.748]`. The spheroidal distance must return a positive value near 1,813 meters.

## References

- [Spatial overview](https://duckdb.org/docs/2.0/core_extensions/spatial/overview.html) owns install and the type surface.
- [Spatial functions](https://duckdb.org/docs/2.0/core_extensions/spatial/functions.html) owns the signatures.
- [GDAL integration](https://duckdb.org/docs/2.0/core_extensions/spatial/gdal.html) owns `ST_Read`, `ST_Drivers`, and `COPY ... FORMAT GDAL`.
- [R-tree indexes](https://duckdb.org/docs/2.0/core_extensions/spatial/r-tree_indexes.html) owns the index rules.
- [Overture DuckDB guide](https://docs.overturemaps.org/getting-data/duckdb/) owns the release lookup and examples.
- [Overture schema](https://docs.overturemaps.org/schema/) owns the current columns.
- [Overture release calendar](https://docs.overturemaps.org/release-calendar/) owns the release cadence.
- Bbox-first filtering and the `POINT_2D` cast are adapted from the `spatial` skill in https://github.com/duckdb/duckdb-skills (MIT). The release id and `taxonomy.primary` replace that skill's fixed-date release paths and legacy category column. The skill reads the STAC catalog rather than baking a release id in.
