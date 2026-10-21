# Overture reference

Read this when the skill needs the current Overture release, a theme schema, or a worked query. The driver is `duckdb-spatial/SKILL.md`.

## Release lookup

```sql
SET VARIABLE latest = (
    SELECT latest FROM 'https://stac.overturemaps.org/catalog.json'
);
SELECT getvariable('latest');
```

The STAC catalog returned `2026-10-21.0` on 2026-10-22. Overture publishes monthly and keeps roughly two months of releases in the public bucket. Do not hardcode a release id in saved SQL.

Path layout:

```text
s3://overturemaps-us-west-2/release/<release>/theme=<theme>/type=<type>/*
```

Region: `us-west-2`. A keyless secret pins it:

```sql
LOAD httpfs;
CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');
```

## Themes and types

| Theme | Types | Geometry |
| --- | --- | --- |
| `places` | `place` | Point |
| `buildings` | `building`, `building_part` | Polygon |
| `transportation` | `segment`, `connector` | LineString, Point |
| `divisions` | `division`, `division_area`, `division_boundary` | Point, Polygon, LineString |
| `base` | `land`, `water`, `infrastructure` | Polygon, Point, LineString |
| `addresses` | `address` | Point |

Every feature carries `id`, `geometry`, `bbox`, `version`, and `sources`. `bbox` is a `STRUCT(xmin, xmax, ymin, ymax)`. Overture geometry is typed `GEOMETRY('OGC:CRS84')`; direct casts to `POINT_2D` fail. For points, `xmin = xmax` and `ymin = ymax`.

## Places

Core columns: `id`, `geometry`, `bbox`, `version`, `sources`, `names`, `taxonomy`, `basic_category`, `confidence`, `operating_status`, `websites`, `socials`, `emails`, `phones`, `brand`, `addresses`.

`taxonomy` is `STRUCT(primary VARCHAR, hierarchy VARCHAR[], alternates VARCHAR[])`. `basic_category` is a separate flattened `VARCHAR`. There is no `categories` column. Use `taxonomy.primary` or `basic_category`. `confidence` is a 0-1 existence score; 0 pairs with `operating_status = 'permanently_closed'`.

Coffee shops near Times Square:

```sql
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=places/type=place/*'
)
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
  AND taxonomy.primary = 'coffee_shop'
SELECT names.primary AS name,
       taxonomy.primary AS category,
       confidence,
       ST_X(geometry) AS lon,
       ST_Y(geometry) AS lat
LIMIT 20;
```

Count by basic category:

```sql
SELECT basic_category, count(*) AS places
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=places/type=place/*'
)
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
GROUP BY basic_category
ORDER BY places DESC
LIMIT 20;
```

For point data, the bbox min corner equals the point, so `bbox.xmin` and `bbox.ymin` are exact. `bbox` is a per-row struct, not a Hive partition column. For polygons the bbox is a coarse prefilter; a predicate on `xmax`/`ymax` can drop a feature that starts outside the box but intersects it, so follow the bbox filter with `ST_Intersects`.

## Buildings

Core columns: `id`, `geometry`, `bbox`, `version`, `sources`, `class`, `subtype`, `height`, `num_floors`, `names`, `level`, `has_parts`, `is_underground`.

Polygons need an overlap test against the bbox, not min-corner containment:

```sql
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=buildings/type=building/*'
)
WHERE bbox.xmax >= -74.01 AND bbox.xmin <= -73.96
  AND bbox.ymax >= 40.72  AND bbox.ymin <= 40.77
SELECT id, height, num_floors, ST_Area(geometry) AS area
LIMIT 20;
```

## Divisions

`division` is the point type: `id`, `geometry`, `bbox`, `version`, `sources`, `names`, `subtype`, `country`, `admin_level`, `class`, `population`, `hierarchies`, `parent_division_id`. `division_area` is the polygon type: `division_id`, `is_land`, `is_territorial`, `country`, `region`, `admin_level`, and no `population`. `division_boundary` is the boundary-line type.

`subtype` values include `country`, `region`, `county`, `locality`, `localadmin`, `neighborhood`, and `dependent`. Check the schema before filtering.

```sql
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=divisions/type=division/*'
)
WHERE subtype = 'country'
  AND names.primary = 'France'
SELECT names.primary, subtype, population, geometry
LIMIT 5;
```

For a polygon such as a US state, query `division_area` and filter `country`, `subtype`, and `is_land`. The `division_area` table has no `population` column.

For a point-in-polygon lookup, filter the division bbox first, then use `ST_Intersects`. `ST_Contains` is false for a point on the boundary; `ST_Covers` includes it.

## Transportation

`segment` carries `class`, `subtype`, `names`, `road_surface`, `speed_limits`, `width`, `level_rules`, and connector references. `class` values include `motorway`, `primary`, `secondary`, `residential`, `service`, `footway`, `cycleway`, and `track`.

```sql
FROM read_parquet(
    's3://overturemaps-us-west-2/release/'
    || getvariable('latest')
    || '/theme=transportation/type=segment/*'
)
WHERE bbox.xmin BETWEEN -74.01 AND -73.96
  AND bbox.ymin BETWEEN 40.72 AND 40.77
  AND class = 'primary'
SELECT names.primary, class, ST_Length(geometry) AS length
LIMIT 20;
```

## Performance

- Filter `bbox` before any `ST_*` call. For polygons, follow with `ST_Intersects`.
- Use `LIMIT` and `DESCRIBE SELECT ... LIMIT 0` before selecting many columns. `ST_Read` does not expose the manual's `spatial_filter` parameters in this build; use a `WHERE bbox` filter.
- Parquet predicate pushdown skips row groups, but only when the predicate uses a column with stats. In 2.0, a `GEOMETRY` column has no min/max stats; a separate `bbox` struct does. A `bbox` filter on a 10-row-group file scanned 2 groups and 1.1 MB instead of 10 groups and 11.5 MB.
- Current file counts are places 16, buildings 512, transportation/segment 128, division_area 8, division 1, address 64. A 0.002-degree building bbox took 2:36 only to read footers. For repeated work, make a regional extract.
- Do not download the theme and filter locally. The bucket is large.
- Do not glob `<release>/**` across themes. Pick the theme and type.
- A bbox-filtered places scan followed by `ORDER BY confidence` or a computed distance hit an internal `Vector::Reference` error on 2.0.0. Wrap the filtered scan in `WITH ... AS MATERIALIZED (...)` and sort outside it.

## Licenses

Overture themes carry different licenses. Places is published under CDLA Permissive 2.0 and Apache 2.0. Check the attribution page for the theme you use before publishing a derived dataset.

## Native GeoJSON

```sql
COPY (SELECT * FROM result) TO 'out.geojson' (FORMAT GEOJSON);
COPY (SELECT * FROM result) TO 'out.geojsonl' (FORMAT GEOJSONL);
```

`ID_COLUMN` and `GEOMETRY_COLUMN` choose the feature id and geometry. `ST_AsGeoJSON` returns `JSON`, not `VARCHAR`.

## References

- https://docs.overturemaps.org/getting-data/duckdb/
- https://docs.overturemaps.org/schema/
- https://docs.overturemaps.org/guides/places/
- https://docs.overturemaps.org/guides/buildings/
- https://docs.overturemaps.org/guides/divisions/
- https://docs.overturemaps.org/guides/transportation/
- https://docs.overturemaps.org/release-calendar/
- https://stac.overturemaps.org/catalog.json
