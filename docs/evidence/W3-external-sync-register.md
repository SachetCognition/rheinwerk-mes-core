# W3-7 — Register aller bestehenden externen Synchronisationen (URS-W3-019, TC-W3-023)

**Status:** abgeschlossen · **Vertragsfreigabe:** v1.0 eingefroren auf Basis dieses Registers ·
**Dossier-Offenpunkt §8.2 #6:** beantwortet (siehe unten)

Dieses Register ist die Voraussetzung für die Freigabe des Grenzvertrags: URS-W3-019 blockiert
URS-W3-010…013. Es wurde vor der Vertragsfixierung erstellt, und die Vertragsfixtures unter
`rheinwerk_mes/integration/boundary/fixtures/` decken jede mit *Übernehmen* dispositionierte
Synchronisation ab.

Die Tabellen unten sind **generiert** aus
`rheinwerk_mes/integration/boundary/external_sync_register.py`
(`python -c "from rheinwerk_mes.integration.boundary import external_sync_register as r; r.publish()"`).
`tests/acceptance/test_w3_external_sync_register.py` schlägt fehl, sobald Code und Dokument
auseinanderlaufen.

## 1 Erhebungsmethode

Es existiert in dieser Umgebung kein laufendes Altsystem; die Erhebung ist deshalb eine
Code- und Konfigurationserhebung über die eingefrorenen Bestandsstände:

| Werk | System | Stand | Vorgehen |
|---|---|---|---|
| A | Qcadoo MES (`SachetCognition/Chem_mes`) | `81d6bb5939` | Repository-weite Suche nach `externalNumber` und `externalSynchronized` über `src/main/**` (generierte `target/`-Ausgaben ausgeschlossen); jede Trägerentität und jeder Konsument wurde als Registereintrag erfasst. Zusätzlich erfasst: die lesenden JSON-REST-Controller und das Plugin für transaktionale E-Mails, weil sie ausgehende Schnittstellen sind. |
| C | ERPNext (`SachetCognition/Chem_erpnext`) | `31e7970764` | Erhebung aller mitgelieferten Integrationen über `erpnext/hooks.py` (`scheduler_events`), `erpnext/erpnext_integrations/**`, `erpnext/edi/**`, `erpnext/telephony/**` sowie Suche nach konfigurierenden Datensätzen/Fixtures (`Plaid Settings`, `Webhook`, `Email Account`, `Code List`, `Voice Call Settings`). |
| B | OFBiz (`SachetCognition/VM_ofbiz-framework`) | `trunk` | Nicht im Registerumfang: stillgelegtes Referenzsystem, ausschließlich Datenmigrationsquelle, ohne eigene externe Synchronisation. |

Für jeden Eintrag wird unterschieden zwischen

* **Feldvorhandensein** (das Modell deklariert `externalNumber`/`externalSynchronized`),
* **Leseverhalten** (Hooks/Views werten das Feld aus, z. B. Formularsperre bei
  `externalSynchronized == '0'`),
* **tatsächlich konfigurierter Nutzung** (ein Client, Scheduler-Job, Endpunkt oder
  Konfigurationsdatensatz schreibt bzw. liest über eine Systemgrenze) und
* **stillliegender Fähigkeit** (mitgeliefert, aber nicht konfiguriert).

Der Befund lautet in allen Fällen entweder *dormant* (Feld/Lesepfad vorhanden, kein
Schreiber) oder *bestätigt ungenutzt* (mitgeliefert, nicht konfiguriert). Kein Eintrag ist
eine im Betrieb laufende externe Kopplung; die einzige *in Betrieb* befindliche Funktion ist
die substrateigene Bestandsbuchhaltung (XS-17), die im Zielbild zur Grenznachricht wird.

## 2 Antwort auf Dossier-Offenpunkt §8.2 #6

> **§8.2 #6 — "Welche externen Synchronisationen bestehen, und existiert ein angebundenes
> WMS bzw. eine ERP-Schnittstelle?"**

Beantwortet durch dieses Register: **kein externes WMS und keine aktive externe
ERP-Schnittstelle** ist an ein Werk angebunden. Plant A trägt Qcadoos Feldpaar
`externalNumber` / `externalSynchronized` auf elf Entitäten, das Paar ist jedoch stillgelegt —
im Bestand existiert kein Synchronisationsclient, kein Scheduler-Job, keine Warteschlange und
kein Endpunkt, der es schreibt; die mitgelieferten REST-Controller sind ausschließlich lesend.
Plant C betreibt keine konfigurierte ERPNext-Integration (Plaid, Webhook, EDI-Codelisten,
E-Mail und Telefonie sind mitgeliefert, aber unkonfiguriert). Folglich muss keine
Altschnittstelle die Konsolidierung unverändert überleben: die einzigen Synchronisationen, die
im Zielbild die ADR-002-Grenze überqueren, sind die drei neuen Vertragsnachrichtentypen
(*orders in*, *confirmations out*, *GL postings out*); die alten externen Referenzen werden als
**Daten** übernommen (`legacy_refs`, CDM-01/CDM-03), nicht als Protokoll.

Der einzige Ort im Bestand, an dem das Feldpaar überhaupt Verhalten auslöst, ist
`ProductSynchronizationService.shouldSynchronize` (XS-07): der Produktabgleich einer Lieferung
schaltet sich genau dann ein, wenn der Lagerort eine `externalNumber` trägt. Kein Lagerort im
Bestand trägt eine — der Beweis, dass die WMS-Kopplung nie in Betrieb war.

## 3 Konsequenz für den Vertrag v1.0

* Vier Einträge sind mit **Übernehmen** dispositioniert: XS-01 und XS-02 (Bedarf eingehend),
  XS-17 (Buchungen ausgehend) und XS-18 (Fertigmeldung ausgehend, ein Weißfleck ohne
  Altbestand). Genau diese drei Nachrichtentypen bilden den eingefrorenen Vertrag v1.0.
* Fünf Einträge sind mit **Ersetzen** dispositioniert: der Bedarf bleibt, wird aber durch
  Migration (Artikel-, Partner-, Chargenreferenzen) oder eine Plattformfunktion (E-Mail)
  erfüllt — keine Grenznachricht.
* Neun Einträge sind **stillgelegt**: die zugehörige Fähigkeit liegt nach ADR-002 dauerhaft
  jenseits der Grenze (Finanzen, Beschaffung, Vertrieb, Personal/Schicht, Telefonie) oder ist
  innerhalb des MES überholt (Rezepturhoheit, Ad-hoc-REST, Webhooks).
* Jeder übernommene Eintrag nennt mindestens eine Vertragsfixture; die Fixtures existieren und
  werden in CI maschinell gegen die Schemata unter
  `rheinwerk_mes/integration/boundary/contract/v1.0/` validiert.

## 4 Register

<!-- BEGIN generated: rheinwerk_mes.integration.boundary.external_sync_register -->

### Dispositionsübersicht

| Disposition | Anzahl | Ids |
|---|---|---|
| Übernehmen (Schnittstelle bleibt) | 4 | XS-01, XS-02, XS-17, XS-18 |
| Ersetzen (anderer Mechanismus) | 5 | XS-05, XS-06, XS-09, XS-11, XS-15 |
| Stilllegen | 9 | XS-03, XS-04, XS-07, XS-08, XS-10, XS-12, XS-13, XS-14, XS-16 |

### Register

| Id | System | Werk | Richtung | Datenobjekte | Nachweis der Nutzung | Disposition | Begründung | Vertragsfixtures |
|---|---|---|---|---|---|---|---|---|
| XS-01 | Gruppen-ERP (unbenannt) → Qcadoo Auftrag | A | inbound | Fertigungsauftrag (order.externalNumber, order.externalSynchronized) | dormant — Feld vorhanden, kein Schreiber | Übernehmen (Schnittstelle bleibt) | Die Bedarfsübergabe aus dem Gruppen-ERP ist die Kernanforderung URS-W3-010; die externe Referenz wird als `external_order_ref` im Vertrag v1.0 fortgeführt. (URS-W3-010) | `erp-in-001-happy.json`, `erp-in-001-duplicate.json` |
| XS-02 | Gruppen-ERP (unbenannt) → Qcadoo Sammelauftrag (masterOrder) | A | inbound | Sammelauftrag/Kundenbedarf (masterOrder.externalNumber, .externalSynchronized) | dormant — Feld vorhanden, kein Schreiber | Übernehmen (Schnittstelle bleibt) | Gleicher Nachrichtentyp wie XS-01: der Kundenbedarf kommt als orders-in Nachricht über die Grenze und wird im MES zur Planungseingabe (URS-W3-001). (URS-W3-010) | `erp-in-003-master-order.json` |
| XS-03 | Gruppen-ERP → Qcadoo Lieferung (delivery) | A | inbound | Lieferung/Bestellung (delivery.externalNumber, .externalSynchronized) | dormant — Feld vorhanden, kein Schreiber | Stilllegen | Beschaffung (buying) liegt nach ADR-002 dauerhaft jenseits der Grenze; das MES führt keine Lieferungen und braucht daher keine Lieferungs-Synchronisation. (ADR-002) | — |
| XS-04 | Gruppen-ERP → Qcadoo Technologie (technology) | A | inbound | Technologie/Rezeptur (technology.externalNumber, .externalSynchronized) | dormant — Feld vorhanden, kein Schreiber | Stilllegen | Rezepturen sind im Zielbild MES-eigen und unterliegen der Rezeptur-Governance (W1-4, URS-W1-014…017); eine externe Rezepturhoheit widerspricht dem Änderungslenkungs-Gate und wird stillgelegt. (URS-W1-016) | — |
| XS-05 | Gruppen-ERP → Qcadoo Artikelstamm (product) | A | inbound | Artikel (product.externalNumber) inkl. Kostennormen-Sperre | dormant — Feld vorhanden, kein Schreiber | Ersetzen (anderer Mechanismus) | Artikelstammdaten werden nicht laufend synchronisiert, sondern einmalig migriert (W0-5) und danach im MES geführt; die alte externe Nummer bleibt als Herkunftsnachweis im `legacy_ref`-Feld erhalten (CDM-01). (URS-W0-011) | — |
| XS-06 | Gruppen-ERP → Qcadoo Geschäftspartner/Adressen (company, address) | A | inbound | Firma, Adresse (company.externalNumber, address.externalNumber) | dormant — Feld vorhanden, kein Schreiber | Ersetzen (anderer Mechanismus) | Partnerstämme liegen nach ADR-002 beim Gruppen-ERP; das MES hält nur Referenzen. Offene Geschäftsentscheidung D5 (URS-W3 §3.7) bestätigt die Referenz-Only-Annahme; kein laufender Stammdaten-Sync. (ADR-002) | — |
| XS-07 | Externes WMS/Lagerverwaltung → Qcadoo Lagerort (location) | A | bidirektional (vorgesehen) | Lagerort (location.externalNumber) und Lieferungs-Produktabgleich | bestätigt ungenutzt — kein Lagerort mit externer Nummer | Stilllegen | Die Antwort auf offene Frage §8.2 #6: es existiert kein angebundenes WMS. Die Lagerführung ist im Zielbild MES-eigen (W1-6/W2-8), der Hook wird stillgelegt. (URS-W3-019) | — |
| XS-08 | Gruppen-ERP → Qcadoo Schichtbelegung (assignmentToShift) | A | inbound | Schichtbelegung (assignmentToShift.externalNumber, .externalSynchronized) | dormant — Feld vorhanden, kein Schreiber | Stilllegen | Personal-/Schichtplanung ist keine MES-Kernfähigkeit im Konsolidierungsumfang und liegt jenseits der Grenze; Schichtmodelle werden im MES nur als Kalender geführt. (ADR-002) | — |
| XS-09 | Fremdsystem → Qcadoo Charge / Rückverfolgungssatz | A | inbound | Charge (batch.externalNumber), Rückverfolgungssatz (trackingRecord.externalNumber, unique) | dormant — Lesepfad vorhanden, kein Schreiber | Ersetzen (anderer Mechanismus) | Chargen-Fremdnummern werden nicht als Protokoll fortgeführt, sondern als Daten: W2 migriert offene Chargen samt Genealogie-Historie und hält die Legacy-Referenz am kanonischen Batch (CDM-03). (URS-W2-030) | — |
| XS-10 | Qcadoo JSON-REST-Endpunkte → beliebige Leser | A | outbound (lesend) | Technologien, Operationen, Materialien, Arbeitsplätze (read-only JSON) | bestätigt ungenutzt — kein Abnehmer nachweisbar | Stilllegen | Die generische, authentifizierte Frappe-/ERPNext-REST-API des Zielsystems ersetzt die vier Ad-hoc-Endpunkte vollständig. (ADR-001) | — |
| XS-11 | Qcadoo E-Mail-Benachrichtigungen → Mandrill / Sendinblue | A | outbound | Transaktionale E-Mails (Bestellungen, Ereignisse) | bestätigt ungenutzt — kein Schlüssel/keine Konfiguration | Ersetzen (anderer Mechanismus) | Benachrichtigungen laufen im Zielbild über die Frappe-E-Mail-Infrastruktur des MES-Standorts; kein Drittanbieter-Versanddienst an der Grenze. (ADR-001) | — |
| XS-12 | ERPNext Plaid-Banking-Feed (Plant C) | C | inbound | Bankkonten, Bankumsätze (automatic_synchronization Scheduler-Job) | bestätigt ungenutzt — nicht konfiguriert | Stilllegen | Finanzen und Zahlungsverkehr liegen nach ADR-002 dauerhaft jenseits der Grenze; das MES führt kein Bankkonto und kein Hauptbuch. (ADR-002) | — |
| XS-13 | ERPNext EDI / Peppol-Codelisten (Plant C) | C | outbound | Codelisten und Common Codes für elektronische Rechnungen | bestätigt ungenutzt — keine Codeliste angelegt | Stilllegen | Ausgangsrechnungen und deren elektronischer Versand sind Aufgabe des Gruppen-ERP (ADR-002, selling/finance jenseits der Grenze). (ADR-002) | — |
| XS-14 | Frappe Webhooks (Plant C) | C | outbound | beliebige DocType-Ereignisse an HTTP-Empfänger | bestätigt ungenutzt — kein Webhook angelegt | Stilllegen | Ausgehende Nachrichten an der Grenze laufen ausschließlich über den versionierten Vertrag (confirmations out, GL postings out) mit dauerhafter Warteschlange und Audit — nicht über ungeprüfte Ad-hoc-Webhooks. (URS-W3-013) | — |
| XS-15 | ERPNext E-Mail-Konten (Plant C) | C | bidirektional | Ein-/ausgehende E-Mail (Bestellungen, Lieferantenkommunikation) | bestätigt ungenutzt — nicht konfiguriert | Ersetzen (anderer Mechanismus) | E-Mail bleibt eine Plattformfunktion des MES-Standorts (z. B. Versand von Analysenzertifikaten, W2-5) und ist keine ERP-Schnittstelle. (URS-W2-019) | — |
| XS-16 | ERPNext Telefonie (Exotel/Twilio Voice Call Settings, Plant C) | C | bidirektional | Anrufprotokolle, eingehende Anrufweiterleitung | bestätigt ungenutzt — nicht konfiguriert | Stilllegen | Telefonie ist keine MES-Fähigkeit im Konsolidierungsumfang (CONSOLIDATION.md). (ADR-002) | — |
| XS-17 | ERPNext Bestandsbuchhaltung (perpetual inventory) → Gruppen-Hauptbuch | C | outbound | Bestandsbuchungen aus Lagerbewegungen (GL-Buchungen je Lager/Konto) | in Betrieb — Substratfunktion, im Zielbild grenzüberschreitend | Übernehmen (Schnittstelle bleibt) | URS-W3-012: Bestandswertbuchungen werden über die Kontenzuordnung auf Gruppen-ERP-Konten abgebildet und als `gl-posting-out` emittiert; ohne Zuordnung wird nichts emittiert (Halte-Warteschlange). (URS-W3-012) | `gl-out-001-happy.json`, `gl-out-001-duplicate.json` |
| XS-18 | MES → Gruppen-ERP Fertigmeldung (neu, kein Altbestand) | A + C (Zielbild) | outbound | Fertigmeldung: Auftragsreferenz, Artikel, Ist-Menge, FG-Chargen | neu — kein Altbestand | Übernehmen (Schnittstelle bleibt) | URS-W3-011: der Übergang nach `exec_state` Completed emittiert genau eine Fertigmeldung; Ausfall des Endpunkts wird über die dauerhafte Warteschlange ohne Verlust und ohne Duplikat nachgeholt. (URS-W3-011) | `conf-out-001-happy.json`, `conf-out-001-duplicate.json` |

### Nachweisindex

| Id | Befund | Nachweisstellen (Datei:Zeile am fixierten Commit) |
|---|---|---|
| XS-01 | Feldpaar auf dem Auftragsmodell deklariert und in der Auftragsliste ausgewertet; kein Synchronisationsclient im Bestand — Feld wird nie geschrieben (dormant). | Chem_mes: mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/constants/OrderFields.java:48,88; mes-plugins-orders/src/main/resources/orders/model/order.xml:51,111 |
| XS-02 | Feldpaar auf Sammelauftrag und dessen DTO deklariert; kein Schreiber, keine Importschnittstelle im Bestand. | Chem_mes: mes-plugins-master-orders/src/main/java/com/qcadoo/mes/masterOrders/constants/MasterOrderFields.java:40,42; masterOrders/model/masterOrder.xml:43,45 |
| XS-03 | Feldpaar auf dem Lieferungsmodell; die Detailansicht sperrt das Formular bei `externalSynchronized == '0'`, d. h. extern gepflegte Lieferungen wären schreibgeschützt. Kein Schreiber im Bestand. | Chem_mes: mes-plugins-deliveries/src/main/java/com/qcadoo/mes/deliveries/constants/DeliveryFields.java:62,64; deliveries/model/delivery.xml:56,57; deliveries/view/deliveryDetails.xml:518 |
| XS-04 | Feldpaar auf Technologie und DTO; Technologieliste und -detail sperren extern synchronisierte Datensätze. Kein Schreiber im Bestand. | Chem_mes: mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/constants/TechnologyFields.java:43; technologies/model/technology.xml:46; technologies/view/technologyDetails.xml:253 |
| XS-05 | `externalNumber` ist unique auf dem Artikelmodell; die Detail-Hooks schalten Felder je nach Vorhandensein der externen Nummer schreibgeschützt, auch in den Kostennormen. Kein Schreiber im Bestand. | Chem_mes: mes-plugins-basic/src/main/java/com/qcadoo/mes/basic/constants/ProductFields.java:47; basic/model/product.xml:50; basic/hooks/ProductDetailsHooks.java:143,175,247; mes-plugins-cost-norms-for-product/hooks/ProductDetailsHooksCNFP.java:193 |
| XS-06 | `externalNumber` unique auf Firma und Adresse; Adress-Hooks verhindern das Löschen extern geführter Adressen. Kein Schreiber im Bestand. | Chem_mes: mes-plugins-basic/src/main/java/com/qcadoo/mes/basic/constants/CompanyFields.java:62, AddressFields.java:62; basic/model/company.xml:60, address.xml:62; basic/hooks/AddressHooks.java:89 |
| XS-07 | `ProductSynchronizationService.shouldSynchronize` schaltet den Produktabgleich genau dann ein, wenn der Lagerort eine `externalNumber` trägt — der einzige Ort im Bestand, an dem das Feldpaar Verhalten auslöst. Kein Lagerort im Bestand trägt eine externe Nummer, kein WMS-Client vorhanden. | Chem_mes: mes-plugins-deliveries/src/main/java/com/qcadoo/mes/deliveries/ProductSynchronizationService.java:31-38,63-74; mes-plugins-material-flow/constants/LocationFields.java:36; materialFlow/model/location.xml:35 |
| XS-08 | Feldpaar auf dem Modell; die Detailansicht sperrt extern synchronisierte Belegungen. Kein Schreiber im Bestand. | Chem_mes: mes-plugins-assignment-to-shift/src/main/java/com/qcadoo/mes/assignmentToShift/constants/AssignmentToShiftFields.java:48,50; assignmentToShift/model/assignmentToShift.xml:52,53; view/assignmentToShiftDetails.xml:159 |
| XS-09 | `BatchModelHelper.findByExternalNumber` sucht Chargen über die externe Nummer, `BatchModelValidators` erzwingt deren Eindeutigkeit, `BatchModelHooks:79` leert sie beim Kopieren, und `BatchViewHooks:80-83` sperrt extern geführte Chargen. Kein liefernder Client im Bestand. | Chem_mes: mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/advancedGenealogy/util/BatchModelHelper.java:49-54, hooks/BatchModelValidators.java:71-80, hooks/BatchModelHooks.java:79, hooks/BatchViewHooks.java:80-83; advancedGenealogy/model/trackingRecord.xml:50 |
| XS-10 | Nur lesende Controller ohne Schreiboperationen; kein Abnehmer im Bestand nachweisbar (keine Client-Konfiguration, kein Aufruf-Log im Repository). | Chem_mes: mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/controller/TechnologyApiController.java:40-72 |
| XS-11 | Plugin `mes-plugins-email-notifications` mit Mandrill-/Sendinblue-Service; kein API-Schlüssel und keine Konfiguration im Bestand. | Chem_mes: mes-plugins/mes-plugins-email-notifications/src/main/java/com/qcadoo/mes/emailNotifications (MandrillServiceImpl) |
| XS-12 | Scheduler-Eintrag und `Plaid Settings` DocType werden vom Substrat mitgeliefert; kein `Plaid Settings`-Datensatz, kein Token und keine Site-Fixture im Bestand. | Chem_erpnext: erpnext/hooks.py:491; erpnext/erpnext_integrations/doctype/plaid_settings |
| XS-13 | `erpnext/edi` liefert `Code List` und `Common Code`; keine Codeliste, kein e-Invoicing-Endpunkt und keine Regionalkonfiguration im Bestand. | Chem_erpnext: erpnext/edi/doctype/code_list, erpnext/edi/doctype/common_code |
| XS-14 | Die Plattform bietet den `Webhook`-DocType; im Bestand ist kein Webhook angelegt und keiner als Fixture exportiert. | Chem_erpnext: erpnext/hooks.py (keine Webhook-Fixture); Frappe-Plattform-DocType |
| XS-15 | Kein `Email Account`-Datensatz und keine Domänenkonfiguration im Bestand; die Fähigkeit ist Plattformstandard. | Chem_erpnext: erpnext/hooks.py (keine Email-Account-Fixture) |
| XS-16 | `erpnext/telephony` liefert `Voice Call Settings`, `Incoming Call Settings` und `Call Log`; keine Einstellung und kein Anrufprotokoll im Bestand. | Chem_erpnext: erpnext/telephony/doctype/voice_call_settings, erpnext/telephony/doctype/incoming_call_settings |
| XS-17 | Das Substrat erzeugt aus jeder Lagerbewegung Hauptbuchbuchungen (perpetual inventory); im Zielbild führt das MES kein Hauptbuch, die Buchungen müssen die Grenze überqueren. | Chem_erpnext: erpnext/controllers/stock_controller.py (GL aus SLE); erpnext/stock/doctype/item/item.json:387-390 (Bewertungsverfahren) |
| XS-18 | Kein Vorläufer in einem der drei Altsysteme (Weißfleck): Qcadoo meldet Fertigstellung nur intern über den Auftragszustand, ERPNext hat keinen Fertigmeldungsversand. Als neue Vertragspflicht aufgenommen, damit die Grenzabdeckung vollständig ist. | Chem_mes: mes-plugins-orders/.../states/constants/OrderState.java:31-81 (nur interner Zustandswechsel); ADR-002 (Vertragsumfang) |

<!-- END generated -->

## 5 Verweise

* Anforderungen: `docs/urs/URS-W3-planning-boundary.md` §3.6 (URS-W3-019), §3.3 (URS-W3-010…014)
* Testfall: `docs/test/TST-W3-planning-boundary.md` TC-W3-023
* Entwurf: `docs/design/W3-erp-boundary.md`
* Architekturentscheidung: `docs/adr/ADR-002-erp-boundary.md`
