select 'create or replace synonym ' ||
       case
         when regexp_like(s.synonym_name, '^[A-Z][A-Z0-9_$#]*$') then s.synonym_name
         else '"' || replace(s.synonym_name, '"', '""') || '"'
       end
       || ' for '
       || case
            when s.table_owner is null then null
            when regexp_like(s.table_owner, '^[A-Z][A-Z0-9_$#]*$') then s.table_owner || '.'
            else '"' || replace(s.table_owner, '"', '""') || '".'
          end
       || case
            when regexp_like(s.table_name, '^[A-Z][A-Z0-9_$#]*$') then s.table_name
            else '"' || replace(s.table_name, '"', '""') || '"'
          end
       || decode(s.db_link, null, null, '@') || s.db_link as ddl
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
/

select '/' as ddl
  from dual
