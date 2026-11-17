select 'create sequence ' ||
       case
         when regexp_like(ds.sequence_name, '^[A-Z][A-Z0-9_$#]*$') then lower(ds.sequence_name)
         else '"' || replace(ds.sequence_name, '"', '""') || '"'
       end
       || ';' as ddl
  from dba_sequences ds
 where ds.sequence_owner = upper(:schema)
   and ds.sequence_name = :obj_name
