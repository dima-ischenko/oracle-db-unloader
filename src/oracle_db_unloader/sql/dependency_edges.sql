select owner,
       name,
       type,
       referenced_owner,
       referenced_name,
       referenced_type
  from dba_dependencies
 where owner not in ('SYS', 'SYSTEM', 'PUBLIC')
   and referenced_owner not in ('SYS', 'SYSTEM', 'PUBLIC')
   and referenced_type != 'NON-EXISTENT'
