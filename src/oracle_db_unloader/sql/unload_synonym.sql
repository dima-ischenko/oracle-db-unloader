select 'create or replace synonym ' || s.synonym_name || ' for '
       || s.table_owner || decode(s.table_owner, null, null, '.')
       || s.table_name || decode(s.db_link, null, null, '@') || s.db_link as ddl
  from (
        select owner,
               synonym_name,
               nvl2(db_link, table_owner, nullif(table_owner, owner)) as table_owner,
               table_name,
               db_link
          from dba_synonyms
       ) s
 where s.owner = upper(:schema)
   and s.synonym_name = upper(:obj_name)
/

select '/' as ddl
  from dual
