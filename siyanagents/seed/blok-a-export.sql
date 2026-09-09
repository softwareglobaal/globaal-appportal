-- Momentopname van blok A (verkoop, marketing, klantenservice, partners) met de
-- agent per taak, voor de Disciplines-pagina van siyanagents. Draaien via
-- seed/blok-a-export.sh; het resultaat komt in seed/blok-a.json.
SELECT json_agg(row_to_json(t)) FROM (
 SELECT d.sleutel, d.naam AS discipline, d.code AS dcode,
        s.code AS scode, s.naam AS subpijler, s.definitie, s.pcf_code,
        e.code AS ecode, e.naam AS taak,
        (SELECT string_agg(ta.agent_code, ',' ORDER BY ta.agent_code)
           FROM kern.subelement_agent ta WHERE ta.subelement_code = e.code) AS agents
   FROM kern.discipline d
   JOIN kern.subdiscipline s ON s.discipline_sleutel = d.sleutel
   JOIN kern.subelement e ON e.subdiscipline_code = s.code
  WHERE d.sleutel IN ('sales_bizdev', 'marketing_communicatie',
                      'customer_service', 'partnerships_relaties')
  ORDER BY d.volgorde, s.volgorde, e.volgorde) t;
