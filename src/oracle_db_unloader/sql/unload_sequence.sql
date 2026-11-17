select 'create sequence ' ||
       '"' || replace(ds.sequence_name, '"', '""') || '"'
       || ';' as ddl
  from dba_sequences ds
 where ds.sequence_owner = upper(:schema)
   and ds.sequence_name = :obj_name
