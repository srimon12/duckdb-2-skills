# Slice: spatial, Overture, H3

Status: complete
Scope: `spatial` extension setup, geometry types and casts, CRS, R-tree, file I/O, GeoParquet, Overture Maps, H3. Audits `skills/duckdb-spatial/SKILL.md`.
Sources: `research/sources/duckdb-2.0/core_extensions/spatial/{overview,functions,gdal,r-tree_indexes}.md`; `data/json/{loading_json,writing_json}.md`; `data/partitioning/hive_partitioning.md`; `guides/network_cloud_storage/s3_import.md`; `sql/data_types/geometry.md`; `sql/functions/geometry.md`; `sql/statements/copy.md`; live `docs.overturemaps.org/getting-data/duckdb/`, `release-calendar/`, `schema/reference/{places/place,divisions/division,divisions/division_area,buildings/building,transportation/segment,addresses/address,base/land_use}/`; `stac.overturemaps.org/catalog.json`; `duckdb.org/community_extensions/extensions/h3.html`. Binary: DuckDB 2.0.0 `d54cbbe3df`, spatial `a3dbcd1781`, h3 `v1.5.6` (H3 4.5.0).

## Verified facts

| # | Claim | Evidence | Confidence |
|---|-------|----------|------------|
| 1 | `spatial` is not autoloadable. `INSTALL spatial; LOAD spatial;` is required. | `core_extensions/spatial/overview.md`; P1 | Documented, Probed |
| 2 | `geometry_always_xy` has no default value: `duckdb_settings()` returns `NULL`. v2.0 requires it to be set explicitly before CRS-sensitive calls. | P1; P2 error text | Probed |
| 3 | With `geometry_always_xy` unset, `ST_Transform`, `ST_Distance_Spheroid`, `ST_Area_Spheroid`, and `ST_Length_Spheroid` raise `Invalid Configuration Error`, not a wrong answer. | P2, P3 | Probed |
| 4 | Setting it `true` forces all CRS-aware input/output to `(easting, northing)`. `ST_Point(4.892360,52.373123)` -> `POINT (544615.02 6867874.10)` in 3857; `false` interprets EPSG:4326 as `(lat,lon)` and returns a wrong `POINT (5830149.38 545278.04)`. | P2 | Probed |
| 5 | It does not change `ST_Point(x,y)` argument order, `ST_X`/`ST_Y`, WKT parsing, GeoJSON parsing, or topology predicates such as `ST_Intersects`. `ST_Intersects` works with the setting unset. | P2, P3; `ST_Point` always x,y | Probed |
| 6 | GeoJSON reading is always lon/lat. `ST_Read('pts.geojson')` returns `GEOMETRY('EPSG:4326')` and coordinates `(-73.985, 40.748)`; `read_json(..., geojson := true)` returns untyped `GEOMETRY` with the same coordinates. | P8; `data/json/loading_json.md` | Probed, Documented |
| 7 | `GEOMETRY` is a built-in type since DuckDB 1.5 and can carry a CRS: `GEOMETRY('OGC:CRS84')`, `GEOMETRY('EPSG:4326')`. CRS identifiers are strings; storage v1.5+ is required. | `sql/data_types/geometry.md`; P4 | Documented, Probed |
| 8 | The specialized types are `POINT_2D`, `POINT_3D`, `POINT_4D`, `BOX_2D`, `BOX_2DF`, `LINESTRING_2D`, `POLYGON_2D`. `LINESTRING` and `POLYGON` are not type names in this build. | P4; `Binder Error: Type with name LINESTRING does not exist` | Probed |
| 9 | `ST_AsText(POINT_3D)` is ambiguous between `(POINT_2D)` and `(GEOMETRY)`. Cast `POINT_3D` to `GEOMETRY` before formatting. | P4 | Probed |
| 10 | `ST_X`/`ST_Y` on a generic `GEOMETRY` work only if the runtime subtype is `POINT`; a polygon raises `ST_X only supports POINT geometries`. | P4 | Probed |
| 11 | A CRS-typed geometry cannot cast directly to `POINT_2D`: `GEOMETRY('OGC:CRS84') -> POINT_2D` raises `Unimplemented type for cast`. Strip the CRS first (`::GEOMETRY::POINT_2D`) or rebuild with `ST_Point(ST_X(g), ST_Y(g))::POINT_2D`. | P4; Overture probe P11 | Probed |
| 12 | `ST_Distance_Spheroid` has exactly `(p1 POINT_2D, p2 POINT_2D)`. Untyped `GEOMETRY` implicitly casts; CRS-typed Overture geometry does not. | `functions.md`; P4, P11 | Documented, Probed |
| 13 | `ST_Area_Spheroid` accepts `GEOMETRY` or `POLYGON_2D`; `ST_Length_Spheroid` accepts `GEOMETRY` or `LINESTRING_2D`. A `POINT_2D` cast is accepted and returns `0.0`, so pass a polygon or line for a real measure. | `functions.md`; P3; probe 2026-10-26 | Documented, Probed |
| 14 | `ST_MakeEnvelope(xmin,ymin,xmax,ymax)` returns `GEOMETRY` (a polygon); `ST_MakeBox2D(point,point)` returns `BOX_2D`. | P4 | Probed |
| 15 | `ST_Point` returns `GEOMETRY`; `ST_Point2D` returns `POINT_2D`; `ST_Point3D` returns `POINT_3D`. | P4 | Probed |
| 16 | `ST_GeomFromText(VARCHAR)` and `ST_AsText(GEOMETRY)` are the WKT pair; `ST_GeomFromGeoJSON(JSON or VARCHAR)` and `ST_AsGeoJSON(GEOMETRY)` are the GeoJSON pair. `ST_AsGeoJSON` returns `JSON`, not `VARCHAR`. | `functions.md`; P4 | Documented, Probed |
| 17 | Planar `ST_Area`/`ST_Length` return CRS units. On EPSG:4326 a 1-degree square is `1.0` and a 1-degree diagonal is `1.414`; the spheroid versions return `12,308,778,361 m²` and `156,899 m`. | P3 | Probed |
| 18 | `ST_Contains(poly, point)` is false for a point on the boundary; `ST_Covers` is true. `ST_Touches` and `ST_Intersects` are true for adjacent polygons sharing an edge. | P5 | Probed |
| 19 | `ST_Union(a,b)` is binary; `ST_Union_Agg(geom)` dissolves a column. `ST_Intersection_Agg`, `ST_Envelope_Agg`, and `ST_Extent_Agg` also exist. | P5 | Probed |
| 20 | `ST_ClosestPoint(g1,g2)` returns the point on `g1` closest to `g2`; `ST_ShortestLine(g1,g2)` returns the segment from `g1` to `g2`. | P5 | Probed |
| 21 | `ST_MakeValid` repairs a self-intersecting bowtie into a `MULTIPOLYGON`; `ST_IsValid` flips from false to true. | P5 | Probed |
| 22 | `ST_Buffer` is planar and takes the CRS unit. `ST_Simplify(geom,tolerance)` passes the tolerance to GEOS in the geometry's coordinate units; on lon/lat that means degrees. | `functions.md` ST_Buffer; GEOS semantics for ST_Simplify | Documented; Simplify units not probed |
| 23 | `ST_Transform` overloads include `(geom,target_crs)` which uses the geometry's carried CRS, and `(geom,source_crs,target_crs[,always_xy])`. | P5 signature query; `sql/data_types/geometry.md` | Probed, Documented |
| 24 | With `spatial` loaded, `duckdb_coordinate_systems()` has **7,246** rows; without it, only `OGC:CRS83` and `OGC:CRS84` (2 rows). EPSG:4326 and 3857 have WKT and PROJJSON. | P6 | Probed |
| 25 | There is no `spatial_ref_sys` table. `SELECT * FROM spatial_ref_sys` is a catalog error; use `duckdb_coordinate_systems()`. | P6 | Probed |
| 26 | PROJ is bundled: `duckdb_proj_version()` = `9.1.1`, compiled `Rel. 9.1.1, December 1st, 2022`. Grid files are not bundled; docs show EPSG:27700 can be ~10 m off without an NTv2 grid. | P6; `functions.md` ST_Transform example | Probed, Documented |
| 27 | Probe: NYC `(-73.985,40.748)` EPSG:4326 -> 3857 = `POINT (-8235972.526340345 4975242.477853835)`; UTM 18N = `POINT (585688.0183420986 4511278.727780813)`. | P6 | Probed |
| 28 | GeoParquet carries CRS in the `geo` key. A column typed `GEOMETRY('EPSG:4326')` writes a full PROJJSON `crs`; reading it back preserves `EPSG:4326`. An untyped geometry writes no `crs` and reads back as `OGC:CRS84`. | P9 | Probed |
| 29 | R-tree syntax: `CREATE INDEX name ON tbl USING RTREE (geom);` Options `max_node_capacity` (default 128) and `min_node_capacity` (default 0.4 * max). | `core_extensions/spatial/r-tree_indexes.md`; P7 | Documented, Probed |
| 30 | R-tree indexes accept only `GEOMETRY` columns. `CREATE INDEX ... USING RTREE (g POINT_2D)` fails with `RTree indexes can only be created over GEOMETRY columns`. | P7 | Probed |
| 31 | 2.0 uses `Rtree Index Scan` for `ST_Within`, `ST_Contains`, `ST_Intersects`, `ST_Covers`, `ST_Touches`, and `ST_DWithin`. The manual's list omits `ST_DWithin` and says joins are future work; the binary also plans a `Spatial Join` with an R-tree scan and `Bounds: deferred (from join filter)`. | P7; `r-tree_indexes.md` limitation list | Probed for Within/Contains/DWithin/join; Documented for the rest |
| 32 | `ST_Distance(geom, point) < d` does **not** use the R-tree: the plan is `Seq Scan`. Use `ST_DWithin` or a bbox prefilter. | P7 | Probed |
| 33 | The R-tree is used when one side is a constant or scalar subquery; a scalar subquery becomes a `Spatial Join` with deferred bounds and still uses the index. | P7 | Probed |
| 34 | In this build `ST_Read` parameters are `[file_name, open_options, allowed_drivers, sibling_files, layer, max_batch_size, keep_wkb]`. The manual snapshot also lists `spatial_filter`/`spatial_filter_box`; those are not in the binary signature. | `functions.md`; P8 signature query | Probed (binary wins) |
| 35 | `ST_Read` adds an `OGC_FID BIGINT` column. GeoJSON, Shapefile, GeoPackage, FlatGeobuf, and GPX drivers are present (`can_open = true`); Parquet is not a GDAL driver in `ST_Drivers()`. A valid GPX file was not read (GPX writing is schema-limited). | P8 | Probed for drivers; GPX read not exercised |
| 36 | There is no `ST_Write` in spatial `a3dbcd1781`. Writing is `COPY ... (FORMAT GDAL, DRIVER ...)`, native `COPY ... (FORMAT GEOJSON or GEOJSONL)`, or `COPY ... (FORMAT parquet)` for GeoParquet. | P8 function query; `gdal.md`; `data/json/writing_json.md` | Probed, Documented |
| 37 | Native `COPY ... (FORMAT GEOJSON)` writes a `FeatureCollection`; `FORMAT GEOJSONL` writes newline-delimited features. `ID_COLUMN` and `GEOMETRY_COLUMN` pick the feature id and geometry. This is new in 2.0. | `data/json/writing_json.md`; P8 | Documented, Probed |
| 38 | `COPY ... (FORMAT parquet)` writes GeoParquet metadata when `spatial` is loaded. `GEOPARQUET_VERSION` defaults to `V1`; `NONE` disables the metadata; `V2` writes `"version":"2.0.0"`. | `sql/statements/copy.md`; P9 | Documented, Probed |
| 39 | The 2.0 Parquet writer does **not** write min/max stats for a `GEOMETRY` column. In a 10-row-group file, `parquet_metadata` had `stats_min_value = NULL` for `geom`, while `id` had stats. | P16 | Probed |
| 40 | A separate `bbox STRUCT(xmin,xmax,ymin,ymax)` column **does** get row-group stats. A local 10-row-group file with `bbox` scanned `2 / 10` row groups and read `1.1 MB` instead of `11.5 MB`. Overture's `bbox` row-group stats are present in the Parquet footer. | P16 | Probed |
| 41 | Overture STAC top-level `latest` is currently `2026-10-21.0`. `SELECT latest FROM 'https://stac.overturemaps.org/catalog.json'` works after `LOAD httpfs`. | P10 | Probed |
| 42 | The release-calendar page is stale: its "Current release" block says `2026-09-23.1/`, while its own history table lists `2026-10-21.0` and STAC says `2026-10-21.0`. The STAC catalog is authoritative. | P10; live release-calendar page | Probed, Documented |
| 43 | A release catalog has 0 `collections`; it links to six theme child catalogs. Themes now: `addresses`, `base`, `buildings`, `divisions`, `places`, `transportation`. | P10, P17 | Probed |
| 44 | Types now: `addresses/address`; `base/{bathymetry,infrastructure,land,land_cover,land_use,water}`; `buildings/{building,building_part}`; `divisions/{division,division_area,division_boundary}`; `places/place`; `transportation/{connector,segment}`. | P17 | Probed |
| 45 | Layout is `s3://overturemaps-us-west-2/release/<release>/theme=<theme>/type=<type>/*.parquet`. Current file counts: places 16, buildings 512, transportation/segment 128, division_area 8, division 1, address 64. | P10, P17 | Probed |
| 46 | Places columns: `id, geometry, confidence, websites, emails, socials, phones, brand, addresses, names, sources, operating_status, basic_category, taxonomy, version, bbox` (plus hive `theme`,`type`). `geometry` is `GEOMETRY('OGC:CRS84')`, points only. | P11 | Probed |
| 47 | Current `taxonomy` is `STRUCT(primary VARCHAR, hierarchy VARCHAR[], alternates VARCHAR[])`. There is **no** `categories` column. `taxonomy.primary` is e.g. `coffee_shop`; `taxonomy.hierarchy` is e.g. `["lodging","hotel"]`; `basic_category` is a separate flattened VARCHAR (also `coffee_shop`). | P11; schema/places page | Probed, Documented |
| 48 | `confidence` is a 0-1 score; 0 means permanently closed. `sources` is an array of `STRUCT(property,dataset,license,record_id,update_time,confidence,between,provider,resource,version)`. | P11; schema/places page | Probed, Documented |
| 49 | Divisions: `division` is a point with `subtype,country,admin_level,class,population,hierarchies,parent_division_id`; `division_area` is a polygon with `division_id,is_land,is_territorial,country,region,admin_level` and **no** `population`; `division_boundary` is the boundary-line type. | P13; schema/divisions pages | Probed, Documented |
| 50 | Buildings: `id,names,sources,level,height,min_height,is_underground,num_floors,num_floors_underground,min_floor,subtype,class,facade_color,facade_material,roof_material,roof_shape,roof_direction,roof_orientation,roof_color,roof_height,geometry,has_parts,version,bbox`. `height` is meters; geometry is Polygon/MultiPolygon. | P12; schema/buildings page | Probed, Documented |
| 51 | Transportation `segment`: `geometry` is a LineString; fields include `subtype,class,subclass,names,connectors,road_surface,road_flags,speed_limits,access_restrictions,routes,destinations,width_rules,level_rules`. `connector` is a separate type. | schema/transportation page; P17 | Documented, Probed |
| 52 | Addresses: point, `street,number,unit,postcode,postal_city,address_levels,country,sources,version,bbox`. Base `land_use` geometry may be Point, LineString, Polygon, or MultiPolygon. | schema/addresses, schema/base pages | Documented |
| 53 | A keyless secret works: `CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');` read the public bucket with no keys. | P10-P13 | Probed |
| 54 | Overture geometry is CRS-typed. `geometry::POINT_2D` fails; `ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D` works. The skill's exact expression returned `36.885 m` to the first Starbucks. | P11 | Probed |
| 55 | `bbox` is `STRUCT(xmin,xmax,ymin,ymax)`. For points `xmin=xmax` and `ymin=ymax`, so `bbox.xmin BETWEEN ... AND bbox.ymin BETWEEN ...` is exact for points. For lines and polygons, min-corner containment drops a feature that starts outside the query but intersects it. Use full overlap on both axes (`bbox.xmax >= qxmin AND bbox.xmin <= qxmax AND bbox.ymax >= qymin AND bbox.ymin <= qymax`), then `ST_Intersects`. | P11-P13; schema/places page; probe 2026-10-26 | Probed, Documented |
| 56 | Worked places query: bbox + `taxonomy.primary='coffee_shop'` + spheroid distance, `ORDER BY m` inside a `MATERIALIZED` CTE, returned 5 rows (Starbucks 36.9 m, Dunkin' 59.5 m) in 25.5 s. | P11 | Probed |
| 57 | Worked buildings query: 0.002° bbox around the Empire State Building + `ST_Intersects`, `count(*)=18`, `avg(height)=45.5 m`, `max(height)=73.3 m`; runtime 2:36 with all 512 building files in the glob. | P12 | Probed |
| 58 | Worked divisions query: `country='US' AND subtype='region' AND is_land` on `division_area` returned Hawaii `a2a08395-...` (US-HI), Texas, Arizona, New Mexico, Oklahoma in 14 s. The US country row is `f39eb4af-5206-481b-b19e-bd784ded3f05`, `admin_level=0`. | P13 | Probed |
| 59 | DuckDB 2.0.0 has an internal error when a bbox-filtered Overture places scan is followed by `ORDER BY confidence` or `ORDER BY` a computed double distance: `Vector::Reference used on vector of different type (source STRUCT(...) referenced DOUBLE)`. `ORDER BY names.primary` worked. | P14 | Probed |
| 60 | Workaround for the above: materialize the filtered rows in a `WITH ... AS MATERIALIZED (...)` CTE, then sort. The same places query returned correct rows. | P14 | Probed |
| 61 | H3 installs with `INSTALL h3 FROM community; LOAD h3;`. Version `v1.5.6`, bound H3 `4.5.0`. | P15; community page | Probed, Documented |
| 62 | `h3_latlng_to_cell(lat, lng, resolution)` takes **latitude first**. NYC `(40.748,-73.985,9)` -> `617733123807641599`; `h3_latlng_to_cell_string` -> `892a100d28bffff`. | P15 | Probed |
| 63 | H3 resolutions are 0-15. Resolution 16 returns `NULL` rather than an error. `h3_get_resolution` returns the level. | P15 | Probed |
| 64 | `h3_cell_to_latlng(cell)` returns `DOUBLE[]` `[lat,lng]`, not a struct. `h3_cell_to_boundary_wkt` returns lon/lat WKT; `ST_GeomFromWKB(h3_cell_to_boundary_wkb(cell))` works. | P15 | Probed |
| 65 | `h3_grid_disk(cell, 1)` returns 7 cells including the center. `h3_cell_area` units are `'m^2'` and `'km^2'`; `'m2'` and `'km2'` raise `Invalid unit`. Res 9 cell area is `105,884.83 m²`; res 15 is `0.90 m²`. | P15 | Probed |
| 66 | Polygon fill: `h3_polygon_wkt_to_cells`, `h3_polygon_wkb_to_cells`, and `h3_cells_to_multi_polygon_wkt` exist. Use the WKT/WKB bridge to `GEOMETRY`. | P15 function list | Probed |
| 67 | `ST_Distance_Sphere` exists and is setting-sensitive. It returns Haversine meters and accepts a per-call `always_xy` boolean; `ST_Distance_Spheroid` returns ellipsoid meters and is slower. P3 measured 5,566,411.6 m with `always_xy=true` and 8,244,712.5 m with `false` for the same lon/lat input. | P3; probe 2026-10-26 | Probed |

## Existing skill audit

| Skill | Claim or omission | Verdict | Fix |
|-------|-------------------|---------|-----|
| `duckdb-spatial` | `SET geometry_always_xy = true;` | Correct | Keep, but add: default is `NULL`; unset makes `ST_Transform` and spheroid functions **error** in 2.0. |
| `duckdb-spatial` | "makes functions treat coordinates as longitude, then latitude" | Thin | It forces `(easting,northing)` for every CRS; for EPSG:4326 that is lon/lat. It does not affect `ST_Point`, `ST_X`, GeoJSON parsing, or topology predicates. |
| `duckdb-spatial` | "Real-world distance and area use the spheroid functions, and those functions want `POINT_2D`." | **Wrong** | Only `ST_Distance_Spheroid` wants two `POINT_2D`. `ST_Area_Spheroid` takes `GEOMETRY`/`POLYGON_2D`; `ST_Length_Spheroid` takes `GEOMETRY`/`LINESTRING_2D`. |
| `duckdb-spatial` | Overture geometry is generic; "Extract coordinates, then cast" + `ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D` | Correct, and necessary | Direct `geometry::POINT_2D` fails on `GEOMETRY('OGC:CRS84')`. Keep the rebuild; explain that the rebuild strips the CRS type. |
| `duckdb-spatial` | "`ST_Distance` on lon/lat is a planar number, not meters." | Correct | Keep. Add `ST_Distance_Sphere` (Haversine, faster) vs `ST_Distance_Spheroid` (ellipsoid, slowest). |
| `duckdb-spatial` | "Filter with `bbox.xmin` and `bbox.ymin` before any `ST_*` call." | Correct for points, wrong for lines and polygons | Keep for point themes. For lines and polygons use full overlap on both axes, then `ST_Intersects`. |
| `duckdb-spatial` | "For point data the partition column is the min corner." | **Wrong terminology** | `bbox` is a per-row struct, not a partition column. Hive partitions are `theme=`/`type=`. For points the bbox min corner equals the point. |
| `duckdb-spatial` | "A predicate on `xmax` and `ymax` drops edge partitions." | **Wrong if generalized** | For points it is redundant. For lines and polygons, `xmin`/`ymin` drops features that start outside and `xmax`/`ymax` drops features that end outside. Use full overlap on both axes. |
| `duckdb-spatial` | `ST_Read('file.geojson')`; Shapefile, GeoPackage, GPX use the same function | Correct | Keep. Add `OGC_FID`; GPX **writing** is schema-limited (only GPX fields). GPX reading was not exercised. |
| `duckdb-spatial` | `COPY ... (FORMAT GDAL, DRIVER 'GeoJSON')` | Correct | Keep, but note native `COPY ... (FORMAT GEOJSON)` is new in 2.0, simpler, and avoids single-threaded GDAL. Prefer native for GeoJSON; GDAL for GPKG/FGB/SHP. |
| `duckdb-spatial` | `INSTALL h3 FROM community`; no API details | Correct but thin | Add `h3_latlng_to_cell(lat,lng,res)`, `h3_cell_to_boundary_wkt`, `h3_grid_disk`, `h3_cell_area(...,'m^2')`, resolution 0-15. |
| `duckdb-spatial` | Overture release lookup via `SELECT latest FROM 'https://stac.overturemaps.org/catalog.json'` | Correct; good design | Keep. Do not bake `2026-10-21.0` into the skill. Add the release-calendar page is stale and the release catalog has no `collections`. |
| `duckdb-spatial` | "The keyless S3 secret only sets the region." | Thin / misleading | `PROVIDER config` selects the config credential provider; the public bucket needs no keys. Say "no keys; region `us-west-2`". |
| `duckdb-spatial` | "`categories.primary` was removed in the 2026-09-23 Overture schema. The category column is `taxonomy.primary`." | Correct in effect | Current v2.0.0 schema has `taxonomy` and no `categories`. Exact removal date was not verified against release notes; link the schema, not a date. |
| `duckdb-spatial` | "Buildings are `theme=buildings/type=building`. Roads are `theme=transportation/type=segment`." | Correct but incomplete | Add `building_part`, `connector`, `division_area`, `division_boundary`, and the `base` types only in the Overture reference. |
| `duckdb-spatial` | "Run `DESCRIBE` on a `LIMIT` subquery before you depend on a column." | Thin | Use `DESCRIBE SELECT ... LIMIT 0` (no rows) or read `table:columns` from the STAC collection. `DESCRIBE` still opens remote footers. |
| `duckdb-spatial` | "Function signatures that are not in this file belong in `duckdb-docs`, then a one-row test." | Thin | The manual's `core_extensions/spatial/functions.md` owns the signatures and `duckdb-docs` can retrieve it; Overture schema fields belong in `references/overture.md`. Keep the one-row test rule. |
| `duckdb-spatial` | Missing: `ST_Transform` errors, `GEOMETRY('CRS')` type, `duckdb_coordinate_systems()`, R-tree joins, native GeoJSON/GeoParquet, `ST_Write` absence | Omission | Add a short "CRS and types" block; put deep CRS and I/O detail in references. |

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |
|------|-----|----------------------|-----------------------------|
| 1 | Current Overture schema: places/taxonomy, divisions/division_area, buildings, transportation, addresses, base; exact theme/type paths | The old `categories.primary` and `places`-only mental model produces binder errors and wrong filters | `references/overture.md` |
| 2 | `geometry_always_xy` is mandatory in 2.0 and errors, not silently flips | An agent that omits it gets a hard failure on the first transform or spheroid call | SKILL.md |
| 3 | CRS-typed geometry cannot cast to `POINT_2D`; rebuild via `ST_Point(ST_X,ST_Y)` | Direct cast is the obvious simplification and it fails on real Overture data | SKILL.md |
| 4 | `bbox` prefilter is exact for points. For lines and polygons use full overlap on both axes, then `ST_Intersects`. | Prevents both missed rows and expensive full scans | SKILL.md |
| 5 | R-tree in 2.0: `ST_DWithin` and spatial joins use it; `ST_Distance` does not | Agents choose the wrong predicate or skip indexing | SKILL.md |
| 6 | Native GeoJSON/GeoParquet paths vs GDAL; `ST_Write` absent | Prevents inventing `ST_Write` and needless GDAL serialization | SKILL.md + `references/overture.md` |
| 7 | CRS type + `ST_Transform(geom,target)` + `duckdb_coordinate_systems()` | Agents can transform typed data without repeating source CRS | SKILL.md |
| 8 | H3 argument order, resolution range, area units, boundary bridge | `h3_latlng_to_cell` is lat-first; `m2` is invalid; wrong order puts NYC in the ocean | SKILL.md |
| 9 | Overture `ORDER BY` internal-error workaround | A natural "nearest coffee shop" query crashes on 2.0.0 | `references/overture.md` |
| 10 | `ST_Read` signature lacks `spatial_filter`; use bbox `WHERE` | Following the 2.0 manual's signature produces a binder error | `references/overture.md` |
| 11 | Overture file counts and per-file footer cost (512 buildings) | A tiny bbox query can take minutes; set expectations and prefer regional extracts | `references/overture.md` |
| 12 | `POINT_3D`/`ST_AsText` ambiguity; `LINESTRING`/`POLYGON` are not type names | Type-level binder errors are otherwise cryptic | SKILL.md |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
|------|--------------|--------------|----------|
| Omitting `SET geometry_always_xy` | `ST_Transform`, `ST_Distance_Spheroid`, `ST_Area_Spheroid`, `ST_Length_Spheroid` raise `Invalid Configuration Error` | Set it immediately after `LOAD spatial`; per-call `always_xy := true` also works | P2, P3 |
| Assuming the setting changes `ST_Point` | It does not; `ST_Point(x,y)` is always x,y | Use `ST_Point(lon,lat)` for CSV lon/lat | P2 |
| `geometry::POINT_2D` on Overture | `Unimplemented type for cast (GEOMETRY('OGC:CRS84') -> POINT_2D)` | `ST_Point(ST_X(geometry),ST_Y(geometry))::POINT_2D`, or `geometry::GEOMETRY::POINT_2D` | P4, P11 |
| `ST_X`/`ST_Y` on any geometry | `ST_X only supports POINT geometries` | Guard with `ST_GeometryType(g)='POINT'` or use the point column | P4 |
| `ST_Contains` for a boundary point | Returns false | Use `ST_Covers` or `ST_Intersects` when the boundary counts | P5 |
| `ST_Distance` for a radius search | Plan is `Seq Scan`; no R-tree | `ST_DWithin(geom, point, d)` or bbox first | P7 |
| Using a single bbox bound to filter lines or polygons | `xmin`/`ymin` drops features that start outside; `xmax`/`ymax` drops features that end outside | Use full overlap on both axes, then `ST_Intersects` | Fact 55; probe 2026-10-26 |
| `ORDER BY distance` on bbox-filtered Overture places | `INTERNAL Error: Vector::Reference ... STRUCT ... referenced DOUBLE` | Wrap the filtered scan in `WITH ... AS MATERIALIZED`, then order | P14 |
| Assuming GeoParquet geometry stats prune row groups | DuckDB 2.0 writes `stats_min_value = NULL` for `GEOMETRY`; `&&` scanned 10/10 row groups | Add a `bbox` struct column or filter on a scalar column; use a real bbox column for pruning | P16 |
| Downloading a whole theme | Places ~5.5M rows; buildings 512 files; a 0.002° building bbox took 2:36 just in footers | Always bbox-filter; for repeated work make a regional extract | P12; fact 45 |
| Transforming before filtering | PROJ runs per row; no index or stats can help afterward | Filter/bbox first, transform the small result | P2; design rule |
| H3 area units `m2`/`km2` | `Invalid Input Error: Invalid unit` | Use `'m^2'` / `'km^2'` | P15 |
| H3 latitude/longitude order | `h3_latlng_to_cell(lng,lat,res)` gives a cell in the wrong place | Latitude first: `h3_latlng_to_cell(lat,lng,res)` | P15 |
| `ST_AsText(POINT_3D)` | Binder ambiguity between `POINT_2D` and `GEOMETRY` overloads | Cast to `GEOMETRY` first | P4 |
| GPX writing with arbitrary columns | `Field of name 'id' is not supported in GPX schema` | `ST_Read` has a GPX driver; for writing, use only GPX fields or convert via GeoJSON/GPKG | P8 |
| Reading `current_setting('geometry_always_xy')` | `Catalog Error: Setting ... is not in the catalog, but it exists in the spatial extension`, even after `LOAD spatial` | Query `duckdb_settings()` instead; the setting itself still works | P1 |
| `duckdb_functions()` name casing | Spatial names are uppercase (`ST_Buffer`); H3 names are lowercase (`h3_...`); a lowercase equality filter misses spatial functions | Use `ILIKE` or exact casing; do not conclude the function is absent | P7, P15 |

## What not to add

- The full `spatial` function catalog (3,600+ lines in the manual). A decision table plus "check `duckdb_functions()`/docs" is enough.
- The full H3 API (76 functions). Only indexing, boundary, disk, area, and polygon fill earn space.
- A historical Overture release id. The lookup is the contract; `2026-10-21.0` is evidence, not a constant.
- Field-by-field Overture schema for every theme. Put the six themes and the columns an agent filters/selects in `references/overture.md`; link the schema pages.
- GPX write recipes and driver-specific creation options. Niche and schema-limited.
- PROJ grid-file installation instructions. Mention the accuracy limit and link the docs; do not turn the skill into a GIS setup guide.
- PostGIS `spatial_ref_sys` advice. DuckDB has no such table; `duckdb_coordinate_systems()` is the replacement.
- A CRS tutorial. State the 4326/3857/CRS84 facts and the `always_xy` rule; link PROJ for the rest.

## Probe log

```text
P1  $ duckdb -no-agent -c "INSTALL spatial; LOAD spatial; SELECT extension_name, extension_version, installed_from FROM duckdb_extensions() WHERE extension_name='spatial';"
    spatial | a3dbcd1781 | core
    $ ... SELECT name,value FROM duckdb_settings() WHERE name LIKE '%geometry%';
    geometry_always_xy | NULL | ignore the defined axis order ... always treat them as (easting, northing)
    geometry_minimum_shredding_size | 30000
    $ ... SELECT current_setting('geometry_always_xy');
    Catalog Error: Setting with name "geometry_always_xy" is not in the catalog, but it exists in the spatial extension.

P2  $ LOAD spatial; SET geometry_always_xy=true;
    SELECT ST_AsText(ST_Transform(ST_Point(4.892360,52.373123),'EPSG:4326','EPSG:3857'));
    POINT (544615.0239773799 6867874.103539125)
    SET geometry_always_xy=false; same call
    POINT (5830149.383613484 545278.0376602103)
    -- unset (default NULL):
    Invalid Configuration Error: 'ST_Transform' is sensitive to the coordinate axis order ...
    In DuckDB v2.0, the 'geometry_always_xy' setting must be set explicitly ...

P3  $ SET geometry_always_xy=true;
    ST_Distance_Spheroid(ST_Point(-73.985,40.748)::POINT_2D, ST_Point(-0.1276,51.5072)::POINT_2D)
    5581423.74634323
    SET geometry_always_xy=false; same lon/lat input -> 8231869.0562626375
    SET false; ST_Point(40.748,-73.985) -> 5581423.74634323
    -- unset: Invalid Configuration Error for ST_Distance_Spheroid / ST_Area_Spheroid / ST_Length_Spheroid
    ST_Area_Spheroid('POLYGON((0 0,0 1,1 1,1 0,0 0))'::GEOMETRY) = 12308778361.469452
    ST_Length_Spheroid('LINESTRING(0 0,1 1)'::GEOMETRY) = 156899.56829134029
    ST_Distance_Sphere(lon/lat, true) = 5566411.618444781
    ST_Distance_Sphere(lon/lat, false) = 8244712.451626792

P4  $ LINESTRING literal as ::LINESTRING
    Binder Error: Type with name LINESTRING does not exist! Did you mean "LINESTRING_2D"?
    typeof('LINESTRING(0 0,1 1)'::LINESTRING_2D) = LINESTRING_2D
    typeof('POLYGON(...)'::POLYGON_2D) = POLYGON_2D
    typeof(ST_MakeBox2D(ST_Point(0,0),ST_Point(1,1))) = BOX_2D
    ST_MakeEnvelope(0,0,1,1) = POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))
    ST_X('POLYGON(...)'::GEOMETRY) -> Invalid Input Error: ST_X only supports POINT geometries
    'POINT(-73.985 40.748)'::GEOMETRY('OGC:CRS84')::POINT_2D
    Conversion Error: Unimplemented type for cast (GEOMETRY('OGC:CRS84') -> POINT_2D)
    ...::GEOMETRY::POINT_2D -> POINT (-73.985 40.748)
    ST_AsText(ST_GeomFromText('POINT Z (1 2 3)')::POINT_3D) -> Binder Error: ambiguous ST_AsText

P5  $ ST_Contains(poly, POINT(0 5)) = false; ST_Covers(poly, POINT(0 5)) = true
    ST_Touches(adjacent polys) = true; ST_Intersects(adjacent polys) = true
    ST_ClosestPoint(line, point(5 5)) = POINT (5 0); ST_ShortestLine = LINESTRING (5 0, 5 5)
    ST_Union_Agg(two adjacent squares) = POLYGON ((0 1, 1 1, 2 1, 2 0, 1 0, 0 0, 0 1))
    ST_IsValid(bowtie) = false; ST_MakeValid -> MULTIPOLYGON (((0 2, 1 1, 0 0, 0 2)), ((2 0, 1 1, 2 2, 2 0)))

P6  $ LOAD spatial; SELECT duckdb_proj_version(), duckdb_proj_compiled_version();
    9.1.1 | Rel. 9.1.1, December 1st, 2022
    SELECT count(*) FROM duckdb_coordinate_systems(); -> 7246
    -- without spatial: 2 (OGC:CRS83, OGC:CRS84)
    SELECT * FROM spatial_ref_sys; -> Catalog Error: Table ... does not exist
    ST_Transform(ST_Point(-73.985,40.748),'EPSG:4326','EPSG:3857')
    POINT (-8235972.526340345 4975242.477853835)
    ST_Transform(...,'EPSG:4326','EPSG:32618')
    POINT (585688.0183420986 4511278.727780813)

P7  $ CREATE TABLE t AS SELECT point::GEOMETRY AS geom FROM st_generatepoints({min_x:0,min_y:0,max_x:100,max_y:100}::BOX_2D,200000,7);
    CREATE INDEX t_rtree ON t USING RTREE (geom);
    EXPLAIN SELECT count(*) FROM t WHERE ST_Within(geom, ST_MakeEnvelope(45,45,65,65));
    Rtree Index Scan | Table: t | Index: t_rtree
    EXPLAIN ... ST_DWithin(geom, ST_Point(50,50), 10); -> Rtree Index Scan
    EXPLAIN ... ST_Distance(geom, ST_Point(50,50)) < 10; -> Seq Scan
    EXPLAIN SELECT count(*) FROM a JOIN b ON ST_Within(a.geom,b.geom);
    Spatial Join | Conditions: ST_Within(geom, geom) | Rtree Index Scan (Bounds: deferred)
    CREATE INDEX p_idx ON p USING RTREE (g)  -- g POINT_2D
    Binder Error: RTree indexes can only be created over GEOMETRY columns.
    duckdb_functions(): spatial functions are registered as ST_With*, ST_Buffer, ... (uppercase).

P8  $ SELECT function_name, parameters FROM duckdb_functions() WHERE function_name='ST_Read';
    ST_Read | [file_name, open_options, allowed_drivers, sibling_files, layer, max_batch_size, keep_wkb]
    SELECT ... FROM ST_Read('out.gpkg'); -> 1 row, columns OGC_FID,id,geom GEOMETRY('EPSG:4326')
    ST_Drivers(): GeoJSON, GPKG, FlatGeobuf, GPX, ESRI Shapefile, KML; Parquet absent
    No ST_Write function in duckdb_functions()
    COPY ... TO 'out_copy.geojson' (FORMAT GDAL, DRIVER 'GeoJSON'); works
    COPY ... TO 'out_fmt.geojson' (FORMAT GEOJSON); works (FeatureCollection)
    GPX write with id/name -> Field of name 'id' is not supported in GPX schema

P9  $ COPY (SELECT ST_Point(-73.985,40.748) AS geom) TO 'out.parquet' (FORMAT parquet);
    parquet_kv_metadata -> {"version":"1.0.0","primary_column":"geom","columns":{"geom":{"encoding":"WKB","geometry_types":["Point"],"bbox":[-73.985,40.748,-73.985,40.748]}}}
    read_parquet -> geom GEOMETRY('OGC:CRS84')
    COPY typed GEOMETRY('EPSG:4326') -> geo key includes full PROJJSON crs; read back EPSG:4326
    GEOPARQUET_VERSION 'V2' -> "version":"2.0.0"; 'NONE' -> no geo key

P10 $ LOAD httpfs; SELECT latest FROM 'https://stac.overturemaps.org/catalog.json';
    2026-10-21.0
    CREATE SECRET (TYPE s3, PROVIDER config, REGION 'us-west-2');
    glob('s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/*.parquet') -> 16 files
    Release catalog: 0 collections; child links: addresses, base, buildings, divisions, places, transportation

P11 $ SET VARIABLE latest=(SELECT latest FROM 'https://stac.overturemaps.org/catalog.json');
    WITH f AS MATERIALIZED (
      SELECT names.primary AS name, taxonomy.primary AS category, basic_category, confidence,
             ST_Distance_Spheroid(ST_Point(ST_X(geometry),ST_Y(geometry))::POINT_2D,
                                  ST_Point(-73.985,40.748)::POINT_2D) AS m
      FROM read_parquet('s3://overturemaps-us-west-2/release/'||getvariable('latest')||'/theme=places/type=place/*.parquet')
      WHERE bbox.xmin BETWEEN -73.987 AND -73.983
        AND bbox.ymin BETWEEN 40.746 AND 40.750
        AND taxonomy.primary='coffee_shop')
    SELECT * FROM f ORDER BY m LIMIT 5;
    Starbucks 36.885 m; Dunkin' 59.484 m; Min Matcha 131.996 m (25.5 s)
    DESCRIBE -> geometry GEOMETRY('OGC:CRS84'), taxonomy STRUCT(primary VARCHAR,hierarchy VARCHAR[],alternates VARCHAR[]), bbox STRUCT(xmin,xmax,ymin,ymax)
    geometry::POINT_2D -> Unimplemented type for cast (GEOMETRY('OGC:CRS84') -> POINT_2D)

P12 $ SELECT count(*) AS buildings, round(avg(height),1) AS avg_h, max(height) AS max_h
    FROM read_parquet('.../theme=buildings/type=building/*.parquet')
    WHERE bbox.xmin BETWEEN -73.986 AND -73.984
      AND bbox.ymin BETWEEN 40.747 AND 40.749
      AND ST_Intersects(geometry, ST_MakeEnvelope(-73.986,40.747,-73.984,40.749));
    18 | 45.5 | 73.3       -- 2:36 total; 512 building files
    -- min-corner is safe only for points; use full overlap for buildings

P13 $ SELECT division_id, names.primary, country, region, admin_level, is_land, is_territorial
    FROM read_parquet('.../theme=divisions/type=division_area/*.parquet')
    WHERE country='US' AND subtype='region' AND is_land LIMIT 5;
    Hawaii (US-HI), Texas (US-TX), Arizona (US-AZ), New Mexico (US-NM), Oklahoma (US-OK) -- 14 s
    division country row: f39eb4af-5206-481b-b19e-bd784ded3f05 | United States | admin_level 0

P14 $ ... bbox-filtered places ... ORDER BY confidence LIMIT 3;
    INTERNAL Error: Vector::Reference used on vector of different type
      (source STRUCT(xmin DOUBLE, xmax DOUBLE, ymin DOUBLE, ymax DOUBLE) referenced DOUBLE)
    ORDER BY names.primary -> works
    WITH f AS MATERIALIZED (SELECT ... WHERE bbox...) SELECT * FROM f ORDER BY m -> works

P15 $ INSTALL h3 FROM community; LOAD h3; SELECT h3_version(); -> 4.5.0
    h3_latlng_to_cell(40.748,-73.985,9) = 617733123807641599
    h3_latlng_to_cell_string(...) = 892a100d28bffff
    h3_cell_to_latlng(cell) = [40.74734064563418, -73.98348648660567]
    h3_get_resolution(...15) = 15; h3_latlng_to_cell(...,16) = NULL
    h3_cell_area(cell9,'m^2') = 105884.82739613813; 'km^2' = 0.10588482739613814
    h3_cell_area(...,'m2') -> Invalid Input Error: Invalid unit; 'km2' likewise
    h3_grid_disk(cell,1) -> 7 cells
    h3_cell_to_boundary_wkt -> POLYGON ((-73.983555 40.749101, ...))
    ST_GeomFromWKB(h3_cell_to_boundary_wkb(cell)) -> same polygon

P16 $ COPY 1M points + bbox struct -> grid_bbox.parquet (10 row groups)
    EXPLAIN ANALYZE ... WHERE bbox.xmin BETWEEN 45 AND 55 AND bbox.ymin BETWEEN 45 AND 55
    Row Groups Scanned: 2 / 10; Data Read: 1.1 MB
    COPY 1M points -> grid.parquet; parquet_metadata: geom stats_min_value = NULL
    EXPLAIN ANALYZE ... WHERE geom && envelope -> Row Groups Scanned: 10 / 10; 11.5 MB

P17 $ for t in addresses base buildings divisions places transportation; fetch .../<release>/<theme>/catalog.json
    themes/types listed in fact 43-44; collection.json has partition:glob and table:columns
    places file_count 16; buildings 512; transportation/segment 128; division_area 8; division 1; address 64

P18 $ SELECT ST_CRS(geom) FROM ST_Read('pts.geojson') -> EPSG:4326
    SELECT ST_CRS(geometry) FROM read_json('pts.geojson', geojson:=true) -> NULL
    ST_AsGeoJSON(ST_Point(...)) -> JSON {"type":"Point","coordinates":[-73.985,40.748]}

P19 $ SET geometry_always_xy=true;
    WITH t AS (SELECT ST_MakeLine(ST_Point(-74.02,40.75), ST_Point(-74.0,40.75)) AS line)
    SELECT ST_XMin(ST_Extent(line)), ST_Intersects(line, ST_MakeEnvelope(-74.01,40.72,-73.96,40.77)),
           (ST_XMin(ST_Extent(line)) BETWEEN -74.01 AND -73.96) FROM t GROUP BY line;
    -74.02 | true | false
    SELECT ST_Area_Spheroid(ST_Point(10,20)::POINT_2D), ST_Length_Spheroid(ST_Point(10,20)::POINT_2D);
    0.0 | 0.0
    SELECT ST_Distance_Sphere(ST_Point(-73.985,40.748), ST_Point(-73.97,40.76)),
           ST_Distance_Spheroid(ST_Point(-73.985,40.748)::POINT_2D, ST_Point(-73.97,40.76)::POINT_2D);
    1837.62 | 1838.57
```

## Open questions

- Did `categories.primary` disappear exactly in the 2026-09-23 v2.0.0 release, or earlier? The v2.0.0 schema page has no `categories`; release notes were not fetched. A release-note check would settle it.
- Is the `ORDER BY` + bbox internal error specific to spatial `a3dbcd1781`, the Parquet dictionary filter, or Overture's `bbox` struct encoding? A minimal local Parquet reproduction with a dictionary-encoded double plus bbox struct would isolate it.
- Does `PROVIDER config` ever attach ambient AWS credentials to public Overture requests? It worked keyless here; a network trace or `SET` variant would settle whether the requests are anonymous.
- What is the actual per-row cost of `ST_Transform` after filtering? The naive benchmark was optimized away (unused projection), so no number is claimed.
- `division_area` for Texas returned `is_territorial=false` with `is_land=true` in the first five rows; is that a data-quality artifact or a second row per division? Not investigated.
- `ST_Distance_Sphere` with `geometry_always_xy` unset was not probed; it is setting-sensitive when set, but the default may error or default to lat/lon.
