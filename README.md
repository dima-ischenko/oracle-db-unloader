# Oracle DB unloader

Unload Oracle schema objects to a stable folder tree of SQL files. The tool
talks to Oracle through SQLAlchemy and `oracledb` (thin mode). Object DDL still
comes from packaged SQL scripts; Python lists objects, binds `:schema` /
`:obj_name` / `:obj_type`, writes files, and tracks incremental state.

Pass in a SQLAlchemy engine you already own (same pattern as xoverrr). The
unloader does not dispose it.

## Install

```bash
pip install -e ".[test]"
```

## CLI

```bash
db-unloader --db-url oracle+oracledb://system:pass@localhost:1521/?service_name=FREEPDB1 \
  --schemas scott,hr \
  --output-dir ./ddl \
  --max-connections 5 \
  --custom-sql-dir ./dictionary_sql
```

Login, password, and a TNS alias are also accepted:

```bash
db-unloader --db-login system --db-pass pass --db-tns orclpdb \
  --schemas scott --output-dir ./ddl
```

`--full` ignores the watermark and rewrites every object. `--lookback-minutes`
(default 5) widens the incremental cutoff so objects touched around the last
run are retried.

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
        output_dir='/data/ddl',
        max_connections=5,
        custom_sql_dir='/data/dictionary_sql',
    )
finally:
    engine.dispose()
```

## Output layout

```
output_dir/
  .unloader_state.json
  scott/functions/*.sql
  scott/packages/*_s.sql *_b.sql
  scott/tables/*.sql
  ...
  dml/<custom_script>.txt
```

The tree is reused across runs (no timestamp folder) so git and incremental
unloads work. Table and materialized-view files get an LLM comment header with
a bucketed `dba_tables.num_rows` label and a compact partition template
(no per-partition lists). Custom `*.sql` SELECTs are always re-run and written
as print_table HORIZONTAL text under `dml/`.

## Tests

```bash
make test-unit
make up-db
make test-integration
make down-db
```
