select pt.partitioning_type,
       pt.subpartitioning_type,
       pt.interval,
       (
         select listagg(lower(pk.column_name), ', ') within group (order by pk.column_position)
           from dba_part_key_columns pk
          where pk.owner = pt.owner
            and pk.name = pt.table_name
            and pk.object_type = 'TABLE'
       ) as part_key,
       (
         select listagg(lower(sk.column_name), ', ') within group (order by sk.column_position)
           from dba_subpart_key_columns sk
          where sk.owner = pt.owner
            and sk.name = pt.table_name
            and sk.object_type = 'TABLE'
       ) as subpart_key
  from dba_part_tables pt
 where pt.owner = upper(:schema)
   and pt.table_name = :obj_name
