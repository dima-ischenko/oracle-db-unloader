select owner,
       object_name,
       object_type,
       last_ddl_time
  from (
        select o.owner,
               o.object_name,
               o.object_type,
               o.last_ddl_time
          from dba_objects o
         where o.owner = upper(:schema)
           and o.object_type in (
                 'TABLE',
                 'VIEW',
                 'MATERIALIZED VIEW',
                 'PACKAGE',
                 'PACKAGE BODY',
                 'FUNCTION',
                 'PROCEDURE',
                 'TRIGGER',
                 'TYPE',
                 'TYPE BODY',
                 'SEQUENCE',
                 'SYNONYM'
               )
           and o.object_name not like 'RB$%'
           and not (
                 o.object_type = 'TABLE'
                 and exists (
                       select null
                         from dba_mviews m
                        where m.owner = o.owner
                          and m.mview_name = o.object_name
                     )
               )
        union all
        select s.owner,
               s.synonym_name as object_name,
               'SYNONYM' as object_type,
               o.last_ddl_time
          from dba_synonyms s
          join dba_objects o
            on o.owner = s.owner
           and o.object_name = s.synonym_name
           and o.object_type = 'SYNONYM'
         where s.owner = 'PUBLIC'
           and s.table_owner = upper(:schema)
       ) objects
 order by object_type, object_name
