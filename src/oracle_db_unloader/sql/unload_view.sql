select replace(dbms_metadata.get_ddl('VIEW', upper(:obj_name), upper(:schema)), '"', '') as ddl
  from dual
/

select 'comment on table ' || lower(dtc.table_name) || ' is '
        || '''' || replace(dtc.comments, '''', '''''') || '''' || ';' as ddl
  from dba_tab_comments dtc
 where dtc.owner = upper(:schema)
   and dtc.table_name = upper(:obj_name)
   and dtc.comments is not null
/

select 'comment on column ' || lower(dcc.table_name) || '.' || lower(dcc.column_name) || ' is '
        || '''' || replace(dcc.comments, '''', '''''') || '''' || ';' as ddl
  from dba_col_comments dcc
  join dba_tab_columns col
    on col.owner = dcc.owner
   and col.table_name = dcc.table_name
   and col.column_name = dcc.column_name
 where dcc.owner = upper(:schema)
   and dcc.table_name = upper(:obj_name)
   and dcc.comments is not null
 order by col.column_id
