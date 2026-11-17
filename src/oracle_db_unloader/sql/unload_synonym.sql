select 'create or replace synonym ' ||
       '"' || replace(s.synonym_name, '"', '""') || '"'
       || ' for '
       || case
            when s.table_owner is null then null
            else '"' || replace(s.table_owner, '"', '""') || '".'
          end
       || '"' || replace(s.table_name, '"', '""') || '"'
       || decode(s.db_link, null, null, '@') || s.db_link
       || ';' as ddl
  from (
        select owner,
               synonym_name,
               nvl2(db_link, table_owner, nullif(table_owner, owner)) as table_owner,
               table_name,
               db_link
          from dba_synonyms
       ) s
 where s.owner = upper(:schema)
   and s.synonym_name = :obj_name
