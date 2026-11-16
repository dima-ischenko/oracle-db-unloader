select replace(dbms_metadata.get_ddl('MATERIALIZED_VIEW', upper(:obj_name), upper(:schema)), '"', '') as ddl
  from dual
