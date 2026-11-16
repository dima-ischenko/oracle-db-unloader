select t.num_rows
  from dba_tables t
 where t.owner = upper(:schema)
   and t.table_name = upper(:obj_name)
