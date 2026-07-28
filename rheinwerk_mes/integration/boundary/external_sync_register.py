"""W3-7 — register of every existing external synchronisation (URS-W3-019).

This module is the *machine-readable* source of truth for the survey that must be
completed **before** the group-ERP interface contract is frozen (URS-W3-019 blocks
URS-W3-010…013). `docs/evidence/W3-external-sync-register.md` is the published,
human-readable register and is generated from `render_markdown()` — the acceptance test
`tests/acceptance/test_w3_external_sync_register.py` fails when the two drift.

Survey method (no live plant systems exist in this environment, so the survey is a
code-and-configuration survey of the pinned estate baselines):

* **Plant A — Qcadoo MES** (`SachetCognition/Chem_mes@81d6bb5`): every declaration and
  consumer of the `externalNumber` / `externalSynchronized` model fields was enumerated
  with a repository-wide search over `src/main/**` (generated `target/` output excluded).
  Each carrier entity (`order`, `masterOrder`, `delivery`, `technology`, `product`,
  `company`, `address`, `location`, `assignmentToShift`, `batch`, `trackingRecord`) is a
  register entry, because in Qcadoo the pair *is* the interface: `externalNumber` holds the
  foreign key of the owning system and `externalSynchronized = false` makes the record
  read-only in the MES UI (see the `technologyDetails.xml:253` / `deliveryDetails.xml:518`
  view hooks that disable the form, and `BatchModelHooks:79` which clears the reference on
  copy). The read-only REST controllers and the transactional-e-mail plugin are entered as
  well: they are outbound interfaces even though they carry no `externalNumber`.
* **Plant C — ERPNext** (`SachetCognition/Chem_erpnext@31e7970`): every integration the
  substrate ships and can activate was enumerated from `erpnext/hooks.py`
  (`scheduler_events`), `erpnext/erpnext_integrations/**`, `erpnext/edi/**` and
  `erpnext/telephony/**`. Nothing in the repository configures any of them — there is no
  committed `Plaid Settings`, `Webhook`, `Email Account`, `Code List` or
  `Voice Call Settings` record and no site fixture creating one — so their evidence of use
  is *confirmed unused* (the shipped-but-unconfigured state, dossier assumption A2).
* **Plant B — OFBiz** is out of scope for this register: it is the retired reference system
  (data-migration source only) and carries no live external sync of its own.

`evidence` is what was found, `evidence_paths` cites the file(s) and line(s) it was found
in, and `disposition` is one of `DISPOSITIONS`:

* **carry** — the sync survives consolidation and crosses the ADR-002 boundary. Every
  carried entry must name at least one contract fixture (URS-W3-019 AC-2); the test
  enforces that the named fixtures exist in `rheinwerk_mes/integration/boundary/fixtures/`.
* **replace** — the need survives but is met by a different mechanism in the target
  (migration of the reference, or a platform feature), so no boundary message is needed.
* **retire** — the sync does not survive; the capability it served is either across the
  boundary per ADR-002 (finance, buying, selling, HR) or superseded inside the MES.

Answering dossier open question §8.2 #6 (`docs/dossier/production-systems-dossier.md:1175`)
is part of AC-1; `ANSWER_82_6` is that answer, published in the register document.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

#: Allowed dispositions (URS-W3-019).
DISPOSITIONS: tuple[str, ...] = ("carry", "replace", "retire")

#: German-first labels for the published register.
DISPOSITION_LABELS: MappingProxyType[str, str] = MappingProxyType(
	{
		"carry": "Übernehmen (Schnittstelle bleibt)",
		"replace": "Ersetzen (anderer Mechanismus)",
		"retire": "Stilllegen",
	}
)

#: The programme answer to dossier open question §8.2 #6 (URS-W3-019 AC-1).
ANSWER_82_6 = (
	"Answered (W3-7, this register): no external WMS and no live external ERP interface is "
	"connected to any plant. Plant A carries Qcadoo's `externalNumber` / "
	"`externalSynchronized` field pair on eleven entities, but the pair is dormant — no "
	"synchronisation client, scheduler job, queue or endpoint exists in the estate that "
	"writes it, and the shipped REST controllers are read-only. Plant C runs no configured "
	"ERPNext integration at all (Plaid, Webhook, EDI code lists, e-mail and telephony are "
	"shipped but unconfigured). Consequently no legacy interface has to survive "
	"consolidation unchanged: the only synchronisations that cross the ADR-002 boundary in "
	"the target are the three new contract message types (orders in, confirmations out, GL "
	"postings out), and the legacy external references are carried as data, not as protocol."
)

REGISTER: tuple[MappingProxyType[str, Any], ...] = tuple(
	MappingProxyType(entry)
	for entry in (
		{
			"id": "XS-01",
			"system": "Gruppen-ERP (unbenannt) → Qcadoo Auftrag",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Fertigungsauftrag (order.externalNumber, order.externalSynchronized)",
			"evidence": (
				"Feldpaar auf dem Auftragsmodell deklariert und in der Auftragsliste "
				"ausgewertet; kein Synchronisationsclient im Bestand — Feld wird nie "
				"geschrieben (dormant)."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/"
				"constants/OrderFields.java:48,88; mes-plugins-orders/src/main/resources/orders/"
				"model/order.xml:51,111"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "carry",
			"rationale": (
				"Die Bedarfsübergabe aus dem Gruppen-ERP ist die Kernanforderung URS-W3-010; "
				"die externe Referenz wird als `external_order_ref` im Vertrag v1.0 fortgeführt."
			),
			"fixtures": ("erp-in-001-happy.json", "erp-in-001-duplicate.json"),
			"urs": "URS-W3-010",
		},
		{
			"id": "XS-02",
			"system": "Gruppen-ERP (unbenannt) → Qcadoo Sammelauftrag (masterOrder)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Sammelauftrag/Kundenbedarf (masterOrder.externalNumber, .externalSynchronized)",
			"evidence": (
				"Feldpaar auf Sammelauftrag und dessen DTO deklariert; kein Schreiber, keine "
				"Importschnittstelle im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-master-orders/src/main/java/com/qcadoo/mes/masterOrders/"
				"constants/MasterOrderFields.java:40,42; masterOrders/model/masterOrder.xml:43,45"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "carry",
			"rationale": (
				"Gleicher Nachrichtentyp wie XS-01: der Kundenbedarf kommt als orders-in "
				"Nachricht über die Grenze und wird im MES zur Planungseingabe (URS-W3-001)."
			),
			"fixtures": ("erp-in-003-master-order.json",),
			"urs": "URS-W3-010",
		},
		{
			"id": "XS-03",
			"system": "Gruppen-ERP → Qcadoo Lieferung (delivery)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Lieferung/Bestellung (delivery.externalNumber, .externalSynchronized)",
			"evidence": (
				"Feldpaar auf dem Lieferungsmodell; die Detailansicht sperrt das Formular bei "
				"`externalSynchronized == '0'`, d. h. extern gepflegte Lieferungen wären "
				"schreibgeschützt. Kein Schreiber im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-deliveries/src/main/java/com/qcadoo/mes/deliveries/"
				"constants/DeliveryFields.java:62,64; deliveries/model/delivery.xml:56,57; "
				"deliveries/view/deliveryDetails.xml:518"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "retire",
			"rationale": (
				"Beschaffung (buying) liegt nach ADR-002 dauerhaft jenseits der Grenze; das "
				"MES führt keine Lieferungen und braucht daher keine Lieferungs-Synchronisation."
			),
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-04",
			"system": "Gruppen-ERP → Qcadoo Technologie (technology)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Technologie/Rezeptur (technology.externalNumber, .externalSynchronized)",
			"evidence": (
				"Feldpaar auf Technologie und DTO; Technologieliste und -detail sperren extern "
				"synchronisierte Datensätze. Kein Schreiber im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/"
				"constants/TechnologyFields.java:43; technologies/model/technology.xml:46; "
				"technologies/view/technologyDetails.xml:253"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "retire",
			"rationale": (
				"Rezepturen sind im Zielbild MES-eigen und unterliegen der Rezeptur-Governance "
				"(W1-4, URS-W1-014…017); eine externe Rezepturhoheit widerspricht dem "
				"Änderungslenkungs-Gate und wird stillgelegt."
			),
			"fixtures": (),
			"urs": "URS-W1-016",
		},
		{
			"id": "XS-05",
			"system": "Gruppen-ERP → Qcadoo Artikelstamm (product)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Artikel (product.externalNumber) inkl. Kostennormen-Sperre",
			"evidence": (
				"`externalNumber` ist unique auf dem Artikelmodell; die Detail-Hooks schalten "
				"Felder je nach Vorhandensein der externen Nummer schreibgeschützt, auch in den "
				"Kostennormen. Kein Schreiber im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-basic/src/main/java/com/qcadoo/mes/basic/constants/"
				"ProductFields.java:47; basic/model/product.xml:50; basic/hooks/"
				"ProductDetailsHooks.java:143,175,247; mes-plugins-cost-norms-for-product/"
				"hooks/ProductDetailsHooksCNFP.java:193"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "replace",
			"rationale": (
				"Artikelstammdaten werden nicht laufend synchronisiert, sondern einmalig "
				"migriert (W0-5) und danach im MES geführt; die alte externe Nummer bleibt als "
				"Herkunftsnachweis im `legacy_ref`-Feld erhalten (CDM-01)."
			),
			"fixtures": (),
			"urs": "URS-W0-011",
		},
		{
			"id": "XS-06",
			"system": "Gruppen-ERP → Qcadoo Geschäftspartner/Adressen (company, address)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Firma, Adresse (company.externalNumber, address.externalNumber)",
			"evidence": (
				"`externalNumber` unique auf Firma und Adresse; Adress-Hooks verhindern das "
				"Löschen extern geführter Adressen. Kein Schreiber im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-basic/src/main/java/com/qcadoo/mes/basic/constants/"
				"CompanyFields.java:62, AddressFields.java:62; basic/model/company.xml:60, "
				"address.xml:62; basic/hooks/AddressHooks.java:89"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "replace",
			"rationale": (
				"Partnerstämme liegen nach ADR-002 beim Gruppen-ERP; das MES hält nur "
				"Referenzen. Offene Geschäftsentscheidung D5 (URS-W3 §3.7) bestätigt die "
				"Referenz-Only-Annahme; kein laufender Stammdaten-Sync."
			),
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-07",
			"system": "Externes WMS/Lagerverwaltung → Qcadoo Lagerort (location)",
			"plant": "A",
			"direction": "bidirektional (vorgesehen)",
			"data_objects": "Lagerort (location.externalNumber) und Lieferungs-Produktabgleich",
			"evidence": (
				"`ProductSynchronizationService.shouldSynchronize` schaltet den "
				"Produktabgleich genau dann ein, wenn der Lagerort eine `externalNumber` trägt "
				"— der einzige Ort im Bestand, an dem das Feldpaar Verhalten auslöst. Kein "
				"Lagerort im Bestand trägt eine externe Nummer, kein WMS-Client vorhanden."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-deliveries/src/main/java/com/qcadoo/mes/deliveries/"
				"ProductSynchronizationService.java:31-38,63-74; mes-plugins-material-flow/"
				"constants/LocationFields.java:36; materialFlow/model/location.xml:35"
			),
			"in_use": "bestätigt ungenutzt — kein Lagerort mit externer Nummer",
			"disposition": "retire",
			"rationale": (
				"Die Antwort auf offene Frage §8.2 #6: es existiert kein angebundenes WMS. Die "
				"Lagerführung ist im Zielbild MES-eigen (W1-6/W2-8), der Hook wird stillgelegt."
			),
			"fixtures": (),
			"urs": "URS-W3-019",
		},
		{
			"id": "XS-08",
			"system": "Gruppen-ERP → Qcadoo Schichtbelegung (assignmentToShift)",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Schichtbelegung (assignmentToShift.externalNumber, .externalSynchronized)",
			"evidence": (
				"Feldpaar auf dem Modell; die Detailansicht sperrt extern synchronisierte "
				"Belegungen. Kein Schreiber im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-assignment-to-shift/src/main/java/com/qcadoo/mes/"
				"assignmentToShift/constants/AssignmentToShiftFields.java:48,50; "
				"assignmentToShift/model/assignmentToShift.xml:52,53; view/"
				"assignmentToShiftDetails.xml:159"
			),
			"in_use": "dormant — Feld vorhanden, kein Schreiber",
			"disposition": "retire",
			"rationale": (
				"Personal-/Schichtplanung ist keine MES-Kernfähigkeit im Konsolidierungsumfang "
				"und liegt jenseits der Grenze; Schichtmodelle werden im MES nur als "
				"Kalender geführt."
			),
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-09",
			"system": "Fremdsystem → Qcadoo Charge / Rückverfolgungssatz",
			"plant": "A",
			"direction": "inbound",
			"data_objects": "Charge (batch.externalNumber), Rückverfolgungssatz (trackingRecord.externalNumber, unique)",
			"evidence": (
				"`BatchModelHelper.findByExternalNumber` sucht Chargen über die externe Nummer, "
				"`BatchModelValidators` erzwingt deren Eindeutigkeit, `BatchModelHooks:79` "
				"leert sie beim Kopieren, und `BatchViewHooks:80-83` sperrt extern geführte "
				"Chargen. Kein liefernder Client im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/"
				"advancedGenealogy/util/BatchModelHelper.java:49-54, hooks/"
				"BatchModelValidators.java:71-80, hooks/BatchModelHooks.java:79, hooks/"
				"BatchViewHooks.java:80-83; advancedGenealogy/model/trackingRecord.xml:50"
			),
			"in_use": "dormant — Lesepfad vorhanden, kein Schreiber",
			"disposition": "replace",
			"rationale": (
				"Chargen-Fremdnummern werden nicht als Protokoll fortgeführt, sondern als Daten: "
				"W2 migriert offene Chargen samt Genealogie-Historie und hält die "
				"Legacy-Referenz am kanonischen Batch (CDM-03)."
			),
			"fixtures": (),
			"urs": "URS-W2-030",
		},
		{
			"id": "XS-10",
			"system": "Qcadoo JSON-REST-Endpunkte → beliebige Leser",
			"plant": "A",
			"direction": "outbound (lesend)",
			"data_objects": "Technologien, Operationen, Materialien, Arbeitsplätze (read-only JSON)",
			"evidence": (
				"Nur lesende Controller ohne Schreiboperationen; kein Abnehmer im Bestand "
				"nachweisbar (keine Client-Konfiguration, kein Aufruf-Log im Repository)."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/"
				"controller/TechnologyApiController.java:40-72"
			),
			"in_use": "bestätigt ungenutzt — kein Abnehmer nachweisbar",
			"disposition": "retire",
			"rationale": (
				"Die generische, authentifizierte Frappe-/ERPNext-REST-API des Zielsystems "
				"ersetzt die vier Ad-hoc-Endpunkte vollständig."
			),
			"fixtures": (),
			"urs": "ADR-001",
		},
		{
			"id": "XS-11",
			"system": "Qcadoo E-Mail-Benachrichtigungen → Mandrill / Sendinblue",
			"plant": "A",
			"direction": "outbound",
			"data_objects": "Transaktionale E-Mails (Bestellungen, Ereignisse)",
			"evidence": (
				"Plugin `mes-plugins-email-notifications` mit Mandrill-/Sendinblue-Service; "
				"kein API-Schlüssel und keine Konfiguration im Bestand."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins/mes-plugins-email-notifications/src/main/java/com/qcadoo/"
				"mes/emailNotifications (MandrillServiceImpl)"
			),
			"in_use": "bestätigt ungenutzt — kein Schlüssel/keine Konfiguration",
			"disposition": "replace",
			"rationale": (
				"Benachrichtigungen laufen im Zielbild über die Frappe-E-Mail-Infrastruktur des "
				"MES-Standorts; kein Drittanbieter-Versanddienst an der Grenze."
			),
			"fixtures": (),
			"urs": "ADR-001",
		},
		{
			"id": "XS-12",
			"system": "ERPNext Plaid-Banking-Feed (Plant C)",
			"plant": "C",
			"direction": "inbound",
			"data_objects": "Bankkonten, Bankumsätze (automatic_synchronization Scheduler-Job)",
			"evidence": (
				"Scheduler-Eintrag und `Plaid Settings` DocType werden vom Substrat "
				"mitgeliefert; kein `Plaid Settings`-Datensatz, kein Token und keine "
				"Site-Fixture im Bestand."
			),
			"evidence_paths": (
				"Chem_erpnext: erpnext/hooks.py:491; erpnext/erpnext_integrations/doctype/plaid_settings"
			),
			"in_use": "bestätigt ungenutzt — nicht konfiguriert",
			"disposition": "retire",
			"rationale": (
				"Finanzen und Zahlungsverkehr liegen nach ADR-002 dauerhaft jenseits der Grenze; "
				"das MES führt kein Bankkonto und kein Hauptbuch."
			),
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-13",
			"system": "ERPNext EDI / Peppol-Codelisten (Plant C)",
			"plant": "C",
			"direction": "outbound",
			"data_objects": "Codelisten und Common Codes für elektronische Rechnungen",
			"evidence": (
				"`erpnext/edi` liefert `Code List` und `Common Code`; keine Codeliste, kein "
				"e-Invoicing-Endpunkt und keine Regionalkonfiguration im Bestand."
			),
			"evidence_paths": "Chem_erpnext: erpnext/edi/doctype/code_list, erpnext/edi/doctype/common_code",
			"in_use": "bestätigt ungenutzt — keine Codeliste angelegt",
			"disposition": "retire",
			"rationale": (
				"Ausgangsrechnungen und deren elektronischer Versand sind Aufgabe des "
				"Gruppen-ERP (ADR-002, selling/finance jenseits der Grenze)."
			),
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-14",
			"system": "Frappe Webhooks (Plant C)",
			"plant": "C",
			"direction": "outbound",
			"data_objects": "beliebige DocType-Ereignisse an HTTP-Empfänger",
			"evidence": (
				"Die Plattform bietet den `Webhook`-DocType; im Bestand ist kein Webhook "
				"angelegt und keiner als Fixture exportiert."
			),
			"evidence_paths": "Chem_erpnext: erpnext/hooks.py (keine Webhook-Fixture); Frappe-Plattform-DocType",
			"in_use": "bestätigt ungenutzt — kein Webhook angelegt",
			"disposition": "retire",
			"rationale": (
				"Ausgehende Nachrichten an der Grenze laufen ausschließlich über den "
				"versionierten Vertrag (confirmations out, GL postings out) mit dauerhafter "
				"Warteschlange und Audit — nicht über ungeprüfte Ad-hoc-Webhooks."
			),
			"fixtures": (),
			"urs": "URS-W3-013",
		},
		{
			"id": "XS-15",
			"system": "ERPNext E-Mail-Konten (Plant C)",
			"plant": "C",
			"direction": "bidirektional",
			"data_objects": "Ein-/ausgehende E-Mail (Bestellungen, Lieferantenkommunikation)",
			"evidence": (
				"Kein `Email Account`-Datensatz und keine Domänenkonfiguration im Bestand; die "
				"Fähigkeit ist Plattformstandard."
			),
			"evidence_paths": "Chem_erpnext: erpnext/hooks.py (keine Email-Account-Fixture)",
			"in_use": "bestätigt ungenutzt — nicht konfiguriert",
			"disposition": "replace",
			"rationale": (
				"E-Mail bleibt eine Plattformfunktion des MES-Standorts (z. B. Versand von "
				"Analysenzertifikaten, W2-5) und ist keine ERP-Schnittstelle."
			),
			"fixtures": (),
			"urs": "URS-W2-019",
		},
		{
			"id": "XS-16",
			"system": "ERPNext Telefonie (Exotel/Twilio Voice Call Settings, Plant C)",
			"plant": "C",
			"direction": "bidirektional",
			"data_objects": "Anrufprotokolle, eingehende Anrufweiterleitung",
			"evidence": (
				"`erpnext/telephony` liefert `Voice Call Settings`, `Incoming Call Settings` und "
				"`Call Log`; keine Einstellung und kein Anrufprotokoll im Bestand."
			),
			"evidence_paths": (
				"Chem_erpnext: erpnext/telephony/doctype/voice_call_settings, "
				"erpnext/telephony/doctype/incoming_call_settings"
			),
			"in_use": "bestätigt ungenutzt — nicht konfiguriert",
			"disposition": "retire",
			"rationale": "Telefonie ist keine MES-Fähigkeit im Konsolidierungsumfang (CONSOLIDATION.md).",
			"fixtures": (),
			"urs": "ADR-002",
		},
		{
			"id": "XS-17",
			"system": "ERPNext Bestandsbuchhaltung (perpetual inventory) → Gruppen-Hauptbuch",
			"plant": "C",
			"direction": "outbound",
			"data_objects": "Bestandsbuchungen aus Lagerbewegungen (GL-Buchungen je Lager/Konto)",
			"evidence": (
				"Das Substrat erzeugt aus jeder Lagerbewegung Hauptbuchbuchungen "
				"(perpetual inventory); im Zielbild führt das MES kein Hauptbuch, die Buchungen "
				"müssen die Grenze überqueren."
			),
			"evidence_paths": (
				"Chem_erpnext: erpnext/controllers/stock_controller.py (GL aus SLE); "
				"erpnext/stock/doctype/item/item.json:387-390 (Bewertungsverfahren)"
			),
			"in_use": "in Betrieb — Substratfunktion, im Zielbild grenzüberschreitend",
			"disposition": "carry",
			"rationale": (
				"URS-W3-012: Bestandswertbuchungen werden über die Kontenzuordnung auf "
				"Gruppen-ERP-Konten abgebildet und als `gl-posting-out` emittiert; ohne "
				"Zuordnung wird nichts emittiert (Halte-Warteschlange)."
			),
			"fixtures": ("gl-out-001-happy.json", "gl-out-001-duplicate.json"),
			"urs": "URS-W3-012",
		},
		{
			"id": "XS-18",
			"system": "MES → Gruppen-ERP Fertigmeldung (neu, kein Altbestand)",
			"plant": "A + C (Zielbild)",
			"direction": "outbound",
			"data_objects": "Fertigmeldung: Auftragsreferenz, Artikel, Ist-Menge, FG-Chargen",
			"evidence": (
				"Kein Vorläufer in einem der drei Altsysteme (Weißfleck): Qcadoo meldet "
				"Fertigstellung nur intern über den Auftragszustand, ERPNext hat keinen "
				"Fertigmeldungsversand. Als neue Vertragspflicht aufgenommen, damit die "
				"Grenzabdeckung vollständig ist."
			),
			"evidence_paths": (
				"Chem_mes: mes-plugins-orders/.../states/constants/OrderState.java:31-81 "
				"(nur interner Zustandswechsel); ADR-002 (Vertragsumfang)"
			),
			"in_use": "neu — kein Altbestand",
			"disposition": "carry",
			"rationale": (
				"URS-W3-011: der Übergang nach `exec_state` Completed emittiert genau eine "
				"Fertigmeldung; Ausfall des Endpunkts wird über die dauerhafte Warteschlange "
				"ohne Verlust und ohne Duplikat nachgeholt."
			),
			"fixtures": ("conf-out-001-happy.json", "conf-out-001-duplicate.json"),
			"urs": "URS-W3-011",
		},
	)
)

#: Fields every register entry must carry (URS-W3-019 AC-1).
REQUIRED_FIELDS: tuple[str, ...] = (
	"id",
	"system",
	"plant",
	"direction",
	"data_objects",
	"evidence",
	"evidence_paths",
	"in_use",
	"disposition",
	"rationale",
	"urs",
)


def entries(disposition: str | None = None) -> tuple[MappingProxyType[str, Any], ...]:
	"""The register, optionally filtered by disposition."""
	if disposition is None:
		return REGISTER
	if disposition not in DISPOSITIONS:
		raise ValueError(f"unknown disposition: {disposition}")
	return tuple(entry for entry in REGISTER if entry["disposition"] == disposition)


def carried_fixtures() -> dict[str, tuple[str, ...]]:
	"""Contract fixtures each carried sync is reflected in (URS-W3-019 AC-2)."""
	return {entry["id"]: tuple(entry["fixtures"]) for entry in entries("carry")}


def incomplete_entries() -> tuple[str, ...]:
	"""Ids of entries missing a required field or a disposition-mandated fixture."""
	broken = []
	for entry in REGISTER:
		missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
		if entry["disposition"] == "carry" and not entry.get("fixtures"):
			missing.append("fixtures")
		if entry["disposition"] not in DISPOSITIONS:
			missing.append("disposition")
		if missing:
			broken.append(entry["id"])
	return tuple(broken)


def render_markdown() -> str:
	"""The generated block of `docs/evidence/W3-external-sync-register.md`.

	The published document embeds this verbatim between the marker comments, so the
	register cannot drift from the code the interface contract is validated against.
	"""
	lines = [
		"### Dispositionsübersicht",
		"",
		"| Disposition | Anzahl | Ids |",
		"|---|---|---|",
	]
	for disposition in DISPOSITIONS:
		selected = entries(disposition)
		lines.append(
			"| {label} | {count} | {ids} |".format(
				label=DISPOSITION_LABELS[disposition],
				count=len(selected),
				ids=", ".join(entry["id"] for entry in selected),
			)
		)
	lines.extend(
		[
			"",
			"### Register",
			"",
			"| Id | System | Werk | Richtung | Datenobjekte | Nachweis der Nutzung | Disposition | Begründung | Vertragsfixtures |",
			"|---|---|---|---|---|---|---|---|---|",
		]
	)
	for entry in REGISTER:
		fixtures = ", ".join(f"`{name}`" for name in entry["fixtures"]) or "—"
		lines.append(
			"| {id} | {system} | {plant} | {direction} | {objects} | {in_use} | {disposition} | {rationale} ({urs}) | {fixtures} |".format(
				id=entry["id"],
				system=entry["system"],
				plant=entry["plant"],
				direction=entry["direction"],
				objects=entry["data_objects"],
				in_use=entry["in_use"],
				disposition=DISPOSITION_LABELS[entry["disposition"]],
				rationale=entry["rationale"],
				urs=entry["urs"],
				fixtures=fixtures,
			)
		)
	lines.extend(
		[
			"",
			"### Nachweisindex",
			"",
			"| Id | Befund | Nachweisstellen (Datei:Zeile am fixierten Commit) |",
			"|---|---|---|",
		]
	)
	for entry in REGISTER:
		lines.append(f"| {entry['id']} | {entry['evidence']} | {entry['evidence_paths']} |")
	return "\n".join(lines)


BEGIN_MARKER = "<!-- BEGIN generated: rheinwerk_mes.integration.boundary.external_sync_register -->"
END_MARKER = "<!-- END generated -->"


def publish(path: str | Path | None = None) -> str:
	"""Rewrite the generated block of the published register; returns the new document.

	The prose around the markers is written by hand, the tables are generated — so the
	published evidence can never drift from the register the contract is validated against
	(URS-W3-019, TC-W3-023).
	"""
	target = Path(path) if path else DEFAULT_EVIDENCE_PATH
	document = target.read_text(encoding="utf-8")
	head, _, rest = document.partition(BEGIN_MARKER)
	_, _, tail = rest.partition(END_MARKER)
	updated = f"{head}{BEGIN_MARKER}\n\n{render_markdown()}\n\n{END_MARKER}{tail}"
	target.write_text(updated, encoding="utf-8")
	return updated


DEFAULT_EVIDENCE_PATH = (
	Path(__file__).resolve().parents[3] / "docs" / "evidence" / "W3-external-sync-register.md"
)
