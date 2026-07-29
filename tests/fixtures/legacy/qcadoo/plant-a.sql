--
-- Plant A (Qcadoo MES) master-data dump subset — pg_dump COPY format.
-- Tables follow the Qcadoo model definitions in SachetCognition/Chem_mes:
--   mes-plugins/mes-plugins-basic/.../model/product.xml       -> basic_product
--   mes-plugins/mes-plugins-basic/.../model/unitConversionItem -> basic_unitconversionitem
--   mes-plugins/mes-plugins-basic/.../model/division.xml      -> basic_division
--   mes-plugins/mes-plugins-basic/.../model/workstation.xml   -> basic_workstation
--   mes-plugins/mes-plugins-technologies/.../model/technology.xml -> technologies_technology
--   mes-plugins/mes-plugins-material-flow/.../model/location.xml  -> materialflow_location
-- `additionalcode` carries the group-wide article code; `number` is the Qcadoo
-- trigger-generated identifier preserved in `legacy_refs` (URS-W0-014).
--

COPY public.basic_division (id, number, name) FROM stdin;
1	D-01	Werk Nord
2	D-02	Mischerei
\.

COPY public.basic_productionline (id, number, name, division_id) FROM stdin;
1	LINE-1	Linie 1	1
\.

COPY public.basic_product (id, number, name, unit, additionalcode, globaltypeofmaterial) FROM stdin;
1	P-000123	Rheinol 40 Basisharz	kg	RW-CHM-0001	01component
2	P-000124	Additiv K7	kg	RW-CHM-0002	01component
3	P-000125	Rheinol 40 Compound	kg	RW-CHM-0003	03finalProduct
\.

COPY public.basic_unitconversionitem (id, product_id, unitfrom, unitto, quantityfrom, quantityto) FROM stdin;
1	1	sack	kg	1	25
2	2	pail	kg	1	5
\.

COPY public.basic_workstation (id, number, name, productionline_id, division_id) FROM stdin;
1	MIX-02	Mischer 02	1	2
\.

COPY public.materialflow_location (id, number, name, type) FROM stdin;
1	MAG-01	RM Lager Nord	02warehouse
2	PROD-01	Produktionsplatz	01location
\.

COPY public.technologies_technology (id, number, name, product_id, state) FROM stdin;
1	000123/2025	Compound Rheinol 40	3	05accepted
\.
