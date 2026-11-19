# Oracle DB unloader

Unload Oracle schema objects to a stable folder tree of SQL files. The tool
talks to Oracle through SQLAlchemy and `oracledb` (thin mode). Object DDL still
comes from packaged SQL scripts; Python lists objects, binds `:schema` /
`:obj_name` / `:obj_type`, writes files, and tracks incremental state.

Pass in a SQLAlchemy engine you already own. The
unloader does not dispose it.

## Install

```bash
pip install -e ".[test]"
```

## CLI

```bash
db-unloader --db-url oracle+oracledb://system:pass@localhost:1521/?service_name=FREEPDB1 \
  --schemas scott,hr \
  --object-types table,view,package \
  --output-dir ./ddl \
  --max-workers 5 \
  --custom-sql-dir ./dictionary_sql
```

Login, password, and a TNS alias are also accepted:

```bash
db-unloader --db-login system --db-pass pass --db-tns orclpdb \
  --schemas scott --output-dir ./ddl
```

`--object-types` limits the run to selected Oracle types (`table`, `view`,
`package`, `mview`, `function`, `procedure`, `trigger`, `type`, `sequence`,
`synonym`). `package` and `type` include spec and body. Incremental watermarks
are stored per schema and object type as the max ``last_ddl_time`` actually
seen in Oracle. For tables and materialized views that value is
``greatest`` of the object, its partitions/subpartitions, and its indexes.
The next run writes objects whose ``last_ddl_time`` is greater than or
equal to that watermark. `--full` ignores watermarks and rewrites every
selected object. `--lookback-minutes` (default 0) can widen the cutoff.
Any exception stops the whole run: remaining types and schemas are not
started, and the failed type's watermark is not moved. `--log-level
DEBUG|INFO|WARNING|ERROR` (default `INFO`) configures the CLI logger. Importing
the library does not attach handlers; the host process owns logging.

Quoted mixed-case names such as `"MixedCase_metrics"` are passed to
`dbms_metadata.get_ddl` as stored in the dictionary (not uppercased). File
names stay lowercase (`mixedcase_metrics.sql`). Simple uppercase identifiers
are unquoted and lowercased; mixed-case and other names that need quoting
stay quoted. SQL statements end with `;`; PL/SQL source still uses `/`.

Custom SELECTs live in underscore-prefixed folders at the output root (or in
`--custom-sql-dir`), for example `_meta/get_table_stats.sql`. Bind `:schema`
to run the same query for every schema. A script in `<schema>/_meta/*.sql`
runs only for that schema (and overrides a shared `_meta` script of the same
name). Results are written as `<schema>/_meta/<script>.txt`.

## Library

```python
from sqlalchemy import create_engine
from oracle_db_unloader import unload

engine = create_engine(
    'oracle+oracledb://system:pass@localhost:1521/?service_name=FREEPDB1',
    pool_size=5,
    max_overflow=0,
    pool_pre_ping=True,
)
try:
    unload(
        engine,
        schemas=['SCOTT'],
        object_types=['table', 'package'],
        output_dir='/data/ddl',
        max_workers=5,
        custom_sql_dir='/data/dictionary_sql',
    )
finally:
    engine.dispose()
```

## Output layout

```
output_dir/
  _meta/get_table_stats.sql
  scott/.unloader_state.json
  scott/functions/*.sql
  scott/packages/*_s.sql *_b.sql
  scott/tables/*.sql
  scott/_meta/get_table_stats.txt
  scott/_meta/local.sql
  scott/_meta/local.txt
  hr/.unloader_state.json
  hr/_meta/get_table_stats.txt
  ...
```

The tree is reused across runs (no timestamp folder) so git and incremental
unloads work. Incremental watermarks live in each schema folder as
`.unloader_state.json`. Table and materialized-view files get an `alter table ... modify`
partition by ...` statement (template only, no per-partition lists). Custom
`_*/` SELECT scripts are always re-run with `:schema`. Shared scripts write
under every schema; `<schema>/_meta/*.sql` writes only to that schema.

## Tests

```bash
make test-unit
make up-db
make test-integration
make down-db
```

## Release

Push a tag `vX.Y.Z` that matches `version` in `pyproject.toml` and
`__version__` in `src/oracle_db_unloader/__init__.py`. The Release workflow
runs tests, builds sdist/wheel, and publishes to PyPI with Trusted Publishing.
