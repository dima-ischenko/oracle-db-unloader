select decode(
         d.line,
         1,
         'create or replace ' || replace(d.text, '"' || d.owner || '".'),
         d.text
       ) as ddl
  from dba_source d
 where d.type = :obj_type
   and d.owner = upper(:schema)
   and d.name = :obj_name
 order by d.line
