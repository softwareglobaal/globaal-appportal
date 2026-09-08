-- 142: Voorgestelde titel voor Elevait-gesprekken die nog niet door een mens
-- zijn gevalideerd. De brein-agent vult hem; het dashboard toont hem in grijs.
-- Bij validatie wordt het voorstel de titel (zonder tweede modelaanroep).

ALTER TABLE elevait.gesprek
    ADD COLUMN IF NOT EXISTS titel_voorstel text;

COMMENT ON COLUMN elevait.gesprek.titel_voorstel IS
    'Titelvoorstel van het model op de samenvatting; wordt titel bij validatie.';
