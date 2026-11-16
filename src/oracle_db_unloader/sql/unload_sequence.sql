select 'create sequence ' || lower(ds.sequence_name) as ddl
  from dba_sequences ds
 where ds.sequence_owner = upper(:schema)
   and ds.sequence_name = upper(:obj_name)
/

select '/' as ddl
  from dual
