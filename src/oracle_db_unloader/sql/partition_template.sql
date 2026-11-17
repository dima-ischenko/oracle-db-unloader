select st.subpartition_name,
       st.high_bound,
       st.subpartition_position
  from dba_subpartition_templates st
 where st.user_name = upper(:schema)
   and st.table_name = :obj_name
 order by st.subpartition_position
