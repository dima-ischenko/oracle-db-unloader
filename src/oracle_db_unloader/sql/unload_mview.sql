select dbms_metadata.get_ddl('MATERIALIZED_VIEW', :obj_name, upper(:schema)) as ddl
  from dual
