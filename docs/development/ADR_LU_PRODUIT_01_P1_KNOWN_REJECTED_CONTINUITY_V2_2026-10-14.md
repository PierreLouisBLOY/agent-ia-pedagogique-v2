# ADR — P1 V2 : tentative connue capturée et rejetée

**Statut : PROPOSÉ, revue distincte préalable requise avant implémentation.** Même LU-PRODUIT-01. Architecture générique uniquement : décisions d'orientation/inspection/rattachement et identités privées sont injectées de confiance hors Git. Aucune donnée runtime, output fournisseur, slot/grant/profil réel ou path privé n'est fourni ici.

## 1. Portée et décision architecturale

Créer un successeur **P0-PRODUCT-CONTINUITY V2**, dans de nouveaux fichiers, pour reconnaître **une seule tentative historique exactement désignée**, capturée puis rejetée localement. Sa disposition est `TENTATIVE_CAPTUREE_REJETEE_A_CONSERVER_ET_COMPTER`. Elle n'est ni CONSUMED, ni une production utilisable, ni une qualification du COURSE.

Les chemins V1 et profiles1–3 restent byte-identiques : confirmed, validate_events, P1/G1/F1, decode des businessreceipts, publishers, permissions et règles de source ne sont pas modifiés. Le successeur ne constitue ni un mutateur SQL, ni un mutateur de ledger historique, ni un nouveau droit de transfert. Aucun booléen “allow_rejected” global, alias de state ou normalisation d'ancien reçu.

Le backend métier conserve les DTO/Application sous work_orchestration ; le lecteur Windows et les predicates fournisseur restent outbound/infrastructure. Les agents utilisent uniquement l'inbound Application. Aucun nouveau routage HTTP/capability/agent_tools et aucune dépendance/framework/SDK nouveau.

Les formats décrits dans les tableaux ci-dessous sont fermés ; ils seront figés dans le spec JSON compagnon avant review. Ils ne dépendent d'aucun type HTTP/SDK/Path dans les DTO Application. Toute extension hors delta fermé exige une nouvelle disposition avant code.

## 2. Invariants acquis et données privées

### Commun immuable

Rootpermission, rootLOCK bytes/identité, namespace de campagne, runtime complet `path/data_root/sha256`, saved_root et receipt_root exacts, identités natives, SID/profil Windows, delegation/credential_ref logique, tokenizer/tarif/évidence tarifaire, catalogue institutionnel et manifests sources/contextes admis restent ceux des ancêtres exacts. Aucun champ d'autorité source supplémentaire.

Les mêmes limites sont conservées : 14 CREATE maximum dans la campagne commune, 0.14USD par appel, 1.96USD cumulés ; 4096 sorties, Terra exact low/default ; COUNT/REVIEW/MODIFY0, retry0, fallbackNONE, parallelism1, outils0, store/stream/background=false. La fenêtre racine reste exactement celle de la permission racine adoptée, sans renouvellement ni valeur de campagne codée dans le source. Chaque permission/grant conserve sa fenêtre propre incluse dans la fenêtre racine.

Tout champ source/package/profile/output_schema peut seulement évoluer par un rattachement exact ; il n'emporte aucune ancienne réservation, permission opérationnelle ou consentement. SourceAdmissionOwner reste un ancêtre unique exact avec **les mêmes manifests disciplinaires et contextuels**. Les nouveaux choix M02–M04 ou l'overlay local ne deviennent pas transmissibles via ce mécanisme.

### Aucune constante runtime dans Git

Ancres, namespaces réels, bodies, output fournisseur, slot/grant/permission réels, SID/paths privés, sommes historiques et décisions runtime demeurent hors Git. Le source fournit schemas/predicates uniquement ; les fixtures sont entièrement synthétiques, via les mêmes factories et sans bypass/monkeypatch de pins réels.

Une SHA de preuve technique ne démontre pas seule une décision humaine. La composition vérifie une transcription de la réponse humaine réellement reçue, liée à la proposition exacte et fournie trusted hors requête. Aucune signature cryptographique humaine n'est affirmée.

## 3. DAG versionné et absence de cycles

Le DAG fermé est :

```text
anciens root/profile/permission/decision/manifests/anchorV1
  -> décision d'orientation acquise + plan exact d'inspection adopté
  -> inspection Application OFF (retour metadata uniquement, sans écriture métier)
  -> preuve complète de disposition + anchorV2 (horsGit, NON_ADOPTE avant rattachement)
  -> manifestV2 (ancêtres exacts + témoins historiques inchangés + disposition unique)
  -> profile4 OFF -> permission policy1 -> decision4 -> permission1 finale/envelope
  -> profile4 ON distinct, OFF comme ancêtre, après adoption opérationnelle exacte
```

Le profile n'embarque pas sa permission/decision courante ; l'envelope les désigne. PermissionPolicyHash exclut uniquement owner_decision_sha256, comme le contrat existant. La decision4 lie profileHash/permissionPolicyHash/manifests/descriptors et la permission finale lie la decision4. AnchorV2 ne référence jamais le profile/tip futur.

**Deux rôles d'adoption sans cycle :** le descriptor adoption_decision de la disposition pointe exclusivement sur l'orientation antérieure acquise. Il ne référence ni witness nouvellement observé, ni disposition, anchor/manifest, source/package/profile4/permission/decision4 ou book futur. L'autorité finale de rattachement groupé (y compris le witness exact) reste un input trusted extérieur à tous ces composants : elle peut les désigner par leurs SHA, mais eux ne la désignent jamais. Aucun nouveau vote préalable inconnu n'est exigé pour construire le DAG ; la décision antérieure sélectionne le cas, et la seule preuve externe finale applicable lie le book exact après observation/qualification.


Les ancêtres1/2 sont liés par leur bind_profile original ; chaque ancêtre3 réutilise son manifestV1 et son anchorV1 exacts, revalidés sur son préfixe plus court. Chaque ancêtre4 réutilise son manifestV2 et son anchorV2 exacts sur le préfixe plus court. Aucun latest/branche/détection automatique. Maximum14 ancêtres ; cycle/doubletip/préfixe divergent/manquant = STOP. Aucun ancêtre V1 n'est rebâti avec l'anchorV2.

Tous les descriptors complets path+rawSHA sont comparés aux envelopes/manifests, pas seulement leur hash. Root, communs, bornes, admis et témoins minimums sont comparés à la racine ; les listes historiques antérieures sont incluses sans retrait, même entre versions. Les preuves rejetées exactes adoptées sont incluses sans disparition.

## 4. Bootstrap readonly OFF : fermer les pins absents sans les inventer

L'orientation acquise et les seuls diagnostics filtrés ne fournissent pas tous les hashes slot/DISPATCH/RESULT/événements. **Aucun manifest/profile4 applicable n'est déclaré prêt aujourd'hui.**

Le futur plan `P0-KNOWN-REJECTED-INSPECTION-PLAN-1.0` est technique, injecté trusted hors requête, sans grant. Champs fermés :

- schema ; operation=`INSPECT_KNOWN_REJECTION_AND_CAMPAIGN_READ_ONLY` ;
- source_manifest et package descriptors, baseline_commit40, source_tree40 ;
- origin_tip_permission_sha256, liste ordonnée ancestor descriptors complète, original_anchor descriptor ;
- proposal, owner_orientation_adoption, owner_diagnostic descriptors ; expected_operator_delegation descriptor ;
- saved_root/receipt_root native identity descriptors acquis, target_runtime objet fermé path/data_root/sha256 identique au runtime racine ;
- target_attempt fermé : permission_sha256, namespace_sha256, request_sha256, request_bytes entier, reserved_usd décimal exact, output_text_sha256 ;
- issued_at_utc/expires_at_utc ; ledger_writes_allowed=false, provider_calls_allowed=0 entier ;
- expected_plan_adoption descriptor, fourni séparément du plan pour éviter un cycle, en input trusted de composition.

Le plan exact source/package/roots/SID/effets doit être rattaché au vrai accord propriétaire avant un accès métier avec le nouveau code. L'adoption d'architecture et orientation seule ne crée pas implicitement ce rattachement. Les chemins sont infrastructure uniquement ; le request DTO Application ne porte que des refs logiques/checksums, jamais plan/permission/grant/SID/path.

La factory défautOFF est inertielle : sans plan adopté, aucun I/O, callback, root, allocation, resolver, tokenizer, transport ou grant. Avec un plan INSPECT_ONLY exact adopté, elle installe seulement l'inbound de lecture. Aucun binding génération/consent. Elle vérifie rawSHA des décisions, source/package actuels et ancêtres propres, tokens Windows/natives/stores/readcapability existante, puis ouvre le LOCK original retenu. Mauvais SID/root/package/source/clock/proof/descriptor ou plan expiré = STOP.

Le bootstrap applique les contrôles §7 et toutes les contrôles consommés V1 aux autres slots, retrouve tous les historiques et vérifie les orphelins. Il retourne un **witness metadata complet en état OBSERVED_NOT_ADOPTED**, et le cumul pessimiste observé, sans aucune publication au ledger, fichier métier, proof autoADOPTED ou grant. Le caller trusted pourra conserver cette réponse dans le dossier technique avec un nouveau plan exact si nécessaire ; l'inbound ne lui donne aucun écrivain métier.

Ce bootstrap n'ouvre pas la gate live. Un type pur ValidatedInspectionPlan ne peut être utilisé comme BoundChainV2 : il permet uniquement le reader readonly et retourne OBSERVED_NOT_ADOPTED. Le broker ON n'accepte que BoundChainV2 avec disposition/profile4 effectivement adoptés. Aucun booléen de bypass ne convertit ces deux modes. Le bootstrap permet de matérialiser les composants V2 nonadoptés et de les soumettre au rattachement groupé. Si un pin requis ne peut être acquis conforme, STOP ciblé et fiche du manque ; aucun placeholder dans un ensemble applicable.

## 5. Formats fermés du successeur

Les hashes sont lowercase64 ; commit/tree40 ; command_id lowercase32. Booleans stricts, entiers stricts (bool refusé), listes uniques/bornées et ordre canonique déclaré. Les sommes sont Decimal finies strictement positives, jamais float. Les business JSON sont UTF8 strict, objet fermé, doublons/NaN/nonobjet refusés et rawbytes canoniques par decodeV1 inchangé. Les décisions/diagnostics techniques historiques indentés acceptent seulement un decoder technique dédié après rawSHA exact, sans relâcher les receipts métier.

| Format | Champs précis |
|---|---|
| `P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0` | schema ; observation_state=OBSERVED_NOT_ADOPTED ; campaign_namespace_sha256 ; root_permission_sha256 ; origin_permission_sha256 ; namespace_sha256 ; request_sha256 ; request_bytes ; reserved_usd ; slot_sha256 ; grant_sha256 ; preview_sha256 ; command_id ; dispatch_capture_sha256 ; dispatch_payload_sha256 ; preflight_sha256 ; result_sha256 ; output_text_sha256 ; response_status=completed ; provider_attempts=1 ; event_sha256s objet fermé des quatre états ; event_timestamps même keys ; usage fermé aux six champs normaux ; disposition fixed ; local_rejection_code ; owner_orientation_adoption descriptor ; owner_diagnostic descriptor ; transport_metadata_scope=NOT_RETAINED_TIER_AND_INCOMPLETE_REASON ; qualification=REJECTED_NOT_CONSUMED ; timestamp_utc ; inspection_plan_sha256. Aucun output/body. |
| `P0-PRODUCT-KNOWN-REJECTED-DISPOSITION-1.0` | schema ; disposition fixed ; target_attempt fermé ; observed_evidence descriptor ; observed_evidence_sha256 ; adoption_decision descriptor ; owner_orientation_adoption descriptor ; owner_diagnostic descriptor ; source_origin_manifest_sha256 ; operation=READ_ONLY_RECONCILIATION ; no_grant_reuse=true ; preserve_reservation=true ; no_runtime_mutation=true. adoption_decision désigne uniquement la décision d'orientation préalable acquise, indépendante du tip et de tout nouveau witness. Son descriptor complet doit égaler owner_orientation_adoption. Elle sélectionne la tentative exacte, mais n'adopte pas le witness OBSERVED. Le vrai rattachement final groupé est un input trusted EXTERNE au book et aux composants qu'il adopte ; aucun composant ne le référence ou ne le rehash. |
| `P0-PRODUCT-CONTINUITY-ANCHOR-2.0` | ANCHOR_FIELDSV1 plus original_anchor descriptor et required_rejected_dispositions liste de descriptors ; schema2. Requiredhistoricalreserves reste la liste exacte rootV1, nonvide ; requiredrejecteddispositions contient exactement une disposition applicable. implementation_decision/conditions désignent la décision réelle/proposition d'orientation et son ADR relu horsGit. |
| `P0-PRODUCT-CONTINUITY-MANIFEST-2.0` | MANIFEST_FIELDSV1 plus rejected_dispositions liste de descriptors ; schema2. Historical_reservations contient les consommées antérieures inchangées ; rejet séparé, jamais codé comme witness consommé. continuitéanchor=descriptoranchor2 exact ; communs, limits/window/rootlock restent identiques. |
| `P0-NORMAL-PROFILE-4.0` | PROFILE3_FIELDS plus rejected_disposition descriptor ; schema4. continuity_enabled bool strict defaultfalse. Continuitymanifest/anchor désignent2 ; disposition correspond à la seule entry de manifest/anchor ; sourceadmissionowner original exact ; runtime/stores/delegation/source manifests inchangés. |
| `P0-NORMAL-OWNER-DECISION-4.0` | DECISION3_FIELDS plus rejected_disposition_sha256 et continuity_version entier2 ; schema4/statusADOPTED. Les trois flags d'exclusion/UNKNOWN/delegation true ; parentPermissionHash/manifest/anchor/sourceowner/descriptors/profileHash/permissionPolicyHash exacts. Vrai reçu de rattachement au book injecté hors envelope et vérifié à part. |
| `P0-PRODUCT-CAMPAIGN-SNAPSHOT-2.0` | Champs snapshotV1 plus known_rejected_count entier1, consumed_count entier, disposition_sha256, inspection_scope, historic_transport_scope, course_qualification=NOT_COMPLETED, current_context_contract_scope, observation_plan_sha256. Réservé exclusivement à BoundChainV2 effectivement adopté : State=CURRENT_RESERVATIONS_RECONCILED, financial_basis=RESERVATIONS_NOT_BILLED_COST, live_enabled=false en OFF. Aucun bootstrap_state ou conversion d'état ne peut produire ce format. Aucune production qualifiée inférée. |
| `P0-PRODUCT-REJECTED-OBSERVATION-1.0` | Retour exclusivement ValidatedInspectionPlan : schema, state=OBSERVED_NOT_ADOPTED, timestamp_utc, observed_evidence, observed_evidence_sha256, campaign_namespace_sha256, root_permission_sha256, observed_slots_reserved, observed_reserved_budget_usd, consumed_count, known_rejected_count, financial_basis=RESERVATIONS_NOT_BILLED_COST, live_enabled=false, provider_calls=0, ledger_mutations=0, inspection_plan_sha256. Aucun champ disposition/profile/tip courant ou solde disponible. |

target_attempt de disposition : permission_sha256, namespace_sha256, request_sha256, request_bytes, reserved_usd, output_text_sha256. Il correspond exactement à l'orientation et au diagnostic acquis. Les hashes supplémentaires viennent du witness natif effectif, pas d'un reçu inventé.

La permission et les grants gardent schema1/P1/G1/F1 existants ; leurs prédicats financiers/temps/contexte restent identiques. Un helperV2 fermé vérifie explicitement profile4/decision4 pour la source locale, et délègue aux mêmes contraintes communes. Il ne se présente jamais comme profile3, ne convertit pas silencieusement son schema ou sa permission, et n'amende pas validate_source_receiptsV1.

## 6. Binding anchor/profil/decision et source

- original_anchor est un descriptor exact du témoinV1 ; ses root/campaign/requiredhistorical et décision d'origine restent égaux. Toute disparition/duplication de witness ou de disposition est refusée.
- Le manifest2 lie son anchor2 par rawSHA et descriptor ; profile4 lie les deux plus la disposition exact. La disposition lie le witness exact et la décision d'orientation préalable seulement. Le rattachement final réel est vérifié comme input trusted EXTERNE : il lie witness, disposition, anchor/manifest, profiles OFF/ON, source/package et book exacts, sans être référencé dans ces composants. Le witness OBSERVED_NOT_ADOPTED et les payloads ADOPTED proposés n'ont aucune autorité avant ce contrôle externe.
- Le sourceowner est un ancêtre unique dont envelope decision descriptor complet égale source_admission_owner_decision courant. Source-admission et localcontext manifests complets identiques à cet ancêtre, pas seulement rehashés.
- Le profile4 contrôle runtime complet, catalogue, stores exacts, identitiesnatives et delegationSID/profil courants. Tokenizer/tariff/tariffevidence/delegation descriptors égalent root. Ne pas reconstruire/reinstalle un environnement, réécrire permissions ou harden des objets historiques.
- Source/package courants sont vérifiés via le verifier existant sur le nouveau checkout qualifié, jamais en installant un ancien package dans le checkout actuel.
- La factory relit les bytes de tous descriptors et natives à chaque inspection/opération sousLOCK ; mutation/tempfilealias/parent substitution, UTF8/duplicateJSON/schéma divergent = STOP.
- OFF et ON ont des profile/permission/decision SHA distincts. ON inclut OFF en ancêtre, conserve rootquota/namespace/LOCK et porte un rattachement opérationnel frais. Aucun retoggle d'un booléen sans recomposition/adoption exact.

## 7. Algorithme natif d'une inspection de slot

L'agent n'ouvre aucun fichier. Un port reader de confiance hors request atteint l'adapter Windows via Application. Retenir les parents et le **même handle exclusif originalLOCK** pour toute la lecture, le classement des slots, les natives et le calcul. Lire le LOCK depuis ce handle et vérifier sa rawSHA/rootpermission binding ; ne jamais créer/renommer/remplacer/harden ce LOCK.

Inventaire borné : ≤14 slots P1 exacts de cette campagne ; normalnamespaces bornés commeV1, nommalformé/noncanonique/orphelin/identité de campagne incertaine STOP. Ne pas attribuer une autre campagne à Boréal/P1 par son seul dossier ; règlesV1 d'orphelins inchangées et conservatrices. Aucun ignorerecord pour obtenir un solde acceptable.

Pour chaque slot : validate_slotV1 inchangé lie nom, permissionorigine, namespace/grant/request/preview/command/preflight/reserve. Permissionorigine est un ancêtre exact (pas “current” arbitraire), validée à son issued. Grant issued ≥permissionissued et grant expiry ≤permissionexpiry. Reserved percall ≤borneorigine/root.

### A. Slot consommé

Appeler `P0NormalReceipt.confirmed(grantorigine)` réel et validate_eventsV1, conserver les cinq events exacts, capture hashes, usage/grantbindings/chronologie. Aucun traitement spécial du rejet sur ce chemin. Appliquer les metadata witnessesV1 exacts et minimums originaux.

### B. Unique slot désigné rejeté

Cette branche existe seulement enV2 et exige plan adopté ou disposition adoptée exacte ; aucun choix depuis un request/HTTP ou un simple stateflag.

1. Ensemble existant **exact** : RESERVED, PROVIDER_ATTEMPTED, RESPONSE_CAPTURED, PARSING_REJECTED, DISPATCH, RESULT. UNKNOWN/PARSED/CONSUMED doivent être physiquement absents ; tout autre event, doublon/alias, namespacecopié ou pièce manquante STOP.
2. Lire les six fichiers par decode businessV1, rawSHA et noms exacts ; compter provider_attempts strictint0 pourRESERVED, strictint1 pourles trois autres. Aucun indice de deuxième tentative, retry ou fallback ; si cet absence ne peut être démontrée par le protocole exact, STOP.
3. DISPATCH closedfieldsV1 : schema/grant exactslot, grantHash, namespace, requestHash/bodyUTF8bytes/hash, dispatchPayloadHash/canonicaldispatch, preflightHash/canonicalpreflight. Request_bytes =grant exact et plan. Intrinsiccontext/reference/preparation/checksums originaux sont comparés aux valeurs enregistrées/grant, sans préparer avec le code courant, sans reparsing du chapitre.
4. PreflightclosedF1V1/typedfields : request hash/bytes, tariff/tokenizer, structuralreserve/inputbound/max4096/costbound/ceiling/count0/retry0/fallbackNONE/statuslocalpolicy ; réserve égale au slot et au grant/percall historique. Vérifier calcul arithmétique depuis les bornes enregistrées et le tarif origine exact, sans tokenizer/fournisseur/secret. Jamais NOT_ESTABLISHED→0.
5. RESULT closedfields et usage utilisent **les contraintes exactes de recover_bindingV1** uniquement comme validation pure d'intégrité, sans appeler recovery/technical_result/binder/generation. Schema/statuscompleted, grant/request/dispatchHash et outputnonvide liés ; les six champs usage int≥0 ou null, cohérence cache/reasoning/totaltokens, output≤4096. Le texte est hashé puis non exposé ; aucun enrichissement/repair/prompt/renderer.
6. RESPONSE_CAPTURED fermeEVENT_FIELDS : artifactHash=rawSHARESULT, statuscompleted, usage exactementRESULTusage ; autres events status/artifact/usage null. Tous les grant/request/preflight/ns/reserved/usd/observedcoststatus identiques ; state/schematypés exacts. Les timestamps sont ordonnés RESERVED≤ATTEMPTED≤CAPTURED≤REJECTED et compris entre grantissued incluse et grantexpiry exclusive. Une incertitude ou incohérence STOP.
7. Diagnosticpropriétaire exact lie origin candidate/request/namespace/outputSHA, code rejet exact P0_RICH_COURSE_NOTION_UNKNOWN, disposition bounded et nooutputdisclosure ; il est historique, pas un parse actuel. Tier/incomplete_reason restent NOT_RETAINED. La branche qualifie seulement une capture retenue/rejetée à compter ; aucune conformité transport/pédagogie du RESULT.
8. Avec disposition finale, comparer **tous** les rawSHA slot/DISPATCH/RESULT/events, grant/preview/command/preflight/dispatch/text/usage/temps au witness adopté. Avecbootstrap, émettre ces valeursobservées NON_ADOPTE ; ne jamais les adopter automatiquement.
9. Conserver le slot/reservation une fois dans le tableau comptable, classé KNOWN_CAPTURED_REJECTED_UNQUALIFIED. Pas d'appel confirmed sur cette branche, pas de CONSUMED publié ou inféré.
10. Tout slot rejeté différent, même mêmeerreurCODE, demeure STOP_OUTCOME_RECONCILIATION_REQUIRED. Currentnewrequest échouée n'est jamais automatiquement couverte par l'ancienne disposition.

### C. OwnPending d'un futur appel autorisé

Réutiliser uniquement l'exceptionV1 liée à l'instance broker vivante, permissioncourante/grant/namespace/request/preflight/command/dispatch exacts, sousLOCK, mémoirepending et **aucun event P0 existant**. Cette exception n'est ni historique ni persistable. Aucun blanket RESERVED toléré, aucune conversion d'un rejected/UNKNOWN verspending.

Après les branches : minimumshistoricalconsumed + requiredrejected, exact inclusion des ancêtres, orphelins et uniqueness namespace/command/preview, sommes et quotas communs. Toute absence d'un historique attesté = STOP ; aucune restitution.

## 8. Cumul et projection Application

Additionner la réservation de chaque slot de la campagne exactement une fois, consumed ou connu rejeté. La somme reste pessimiste, sans déduire la consommation observée, coût facturé, réserve libérée ou succès. La tentative rejected reste un slotconsommé de quota d'appels, **pas un eventCONSUMED**.

Observer <=14slots et réserve cumulée <=1.96USD/limitesracine. Chaque réserve >0 et <=0.14USD/borneorigine ; collisions preview/command/namespace interdites. En cas d'échec, pas de snapshot CURRENT/remainingbudget disponible ; le résultat Application porte failure/refus et une projectiondiagnostique minimisée, jamais un solde inventé.

`InspectP1Campaign` est une query readonly, pas une commande de repair/promotion. DTO `P1CampaignInspectionRequest` fermé : inspection_ref logique + expected_plan_or_profile_sha25664 ; aucune donnée d'autorité/path/permission/slot/grant/hash de tentative modifiable. Un Protocol reader injecté hors requête produit une projection safe revalidée. Inbound renvoie ApplicationOutcome ; failureAF_MAPPING_CORRUPTION/AF_CONCURRENCY/AF_PORT_UNAVAILABLE/AF_COMMIT_OUTCOME_UNKNOWN selon observation, pas “SUCCESS malgré stateUNKNOWN”.

En absence de toute intervention, side_effects vide et operation_ref de lecture uniquement ; pas de nouveauxIDs métier. Le callback metadata existant P0CreationEndpoint.campaign_snapshot peut recevoir **l'inbound query trusted** en composition explicite ; aucune nouvelle route ni autoritéHTTP. OFF ne lie jamais consent_execute, generation ou resolver. L'endpoint est le transport, l'Application possède la query et sa projection.

Trois modes distincts : OFF_DISABLED_NO_ACCESS ne retourne aucune inspection ; ValidatedInspectionPlan retourne seulement P0-PRODUCT-REJECTED-OBSERVATION-1.0 avec observed_evidence et cumul observé sous état OBSERVED_NOT_ADOPTED ; BoundChainV2 adopté peut retourner P0-PRODUCT-CAMPAIGN-SNAPSHOT-2.0 après revalidation complète. Bootstrap n'a ni disposition_sha256, ni current_permission/profile, ni remaining_calls/remaining_budget, ni projection CURRENT. Ce sont deux types fermés distincts, pas un changement de state au runtime. live_enabled=false en OFF. UNKNOWN/INCOMPLETE/FAILSTOP ne deviennent pas un de ces succès.

## 9. Chemin normal futur ON et refus des anciens grants

Le nouveau brokerV2, dans un fichier neuf, reuse les méthodes P0ProductGenerationAdapter nonaffectées, la leaseLOCK et le normaladapter existants. Son constructor ne publie rien ; ses variantes fermées _snapshot/accept et sourcepolicy4 n'utilisent jamais une conversiondeprofile3. Réserver un futur slot neuf reste délégué au reserveP1 existant uniquement après les mêmes consentement/derive_grant/budgetchecks et un nouveau grantG1 frais. **Aucun nouveau mutateur des fichiers historiques.**

Les fonctions derive_grantV2/sourcepolicy4 conservent strictement P1/G1/F1/preview/consent/onecall/namespacefresh et servent seulement à vérifier profile4/decision4/manifest2/sourceowneradmis. Reuse directe des helperspure nonmodifiés ; là où un appel hardcodéV1 exige schema3, brancheV2 séparée, pas alias/monkeypatch/globalexception.

ON exige futureadoption exacte source/package/profile/decision/manifest/schema/book/body, puis une inspection fraîche conforme sousLOCK, financiersdémontrés et deuxconsentementsfreshV2. Création courante utilise le **nouveau contexte COURSE4/schema/body**, pas le body historique rejected. Code source de conservation/reopen/export validatorsCOURSE4 existant reste inchangé ici.

Les adapters historiques ne sont construits que pour la permission courante exacte et les receipts réellementconfirmed ; l'ancienrejected grant est explicitement exclu de confirmed_dispatches/recover_confirmed/control_evidence. Une demande ciblant l'ancienne dispatch même checksum = OLD_GRANT_CURRENT_RECOVERY_REFUSED, sans parser la sortie. Une nouvellefailedattempt UNKNOWN/PARSING_REJECTED bloque les prochainsslots tant qu'une nouvelle disposition exacten'estpasadoptée.

Cet ADR d'implémentation n'autorise pas le ON ni un live. Aucune campagne automatique14, aucun COUNT/REVIEW/MODIFY/retry/fallback, aucun merge/release/deploy ou changement runtime utilisateur.

## 10. Delta fermé source futur

**Neuf nouveaux fichiers Python, quatre tests, un ADR générique, deux drivers modifiés pour le seul dispatch** : les neuf owners ci-dessous et le complément fermé §14. Les treize fichiers V1 restent inchangés.

1. `backend/adapters/outbound/generation/openai/p0_product_rejected_continuity_contract.py` — structuresV2, exactDAG/witness/rejectedpurepredicates, arithmetic/projection ; SDK/FS0.
2. `backend/adapters/outbound/generation/openai/p0_product_rejected_continuity_ledger.py` — subclassreadonly de V1 nativeLOCK, slotsV2 exacts, consumedbranchV1, no newpublish/remove/repair. Reuse inheritedreserve uniquement parbrokerON futur.
3. `backend/adapters/outbound/generation/openai/p0_product_rejected_policy.py` — source4/deriveGrantV2 fermés, mêmespureP1/G1/F1predicates.
4. `backend/adapters/outbound/generation/openai/p0_product_rejected.py` — brokerV2 fermé et refus recoveryrejected, ownPendingidentique.
5. `backend/infrastructure/composition/factories/p0_rejected_profile_contract.py` — profil4/decision4/inspectionplan/bindingpur ; nouveau schema strict, aucuneautoritéHTTP.
6. `backend/infrastructure/composition/factories/p0_rejected_profile.py` — factoryoff/readonly/ONdistincttrusted, rawdescriptors/natives/operator/sourcepackage checks ; reuse primitivesexistantes sans weakening.
7. `backend/modules/work_orchestration/contracts/dto/p1_campaign_inspection.py` — DTOrequest/metadata typedclosed/protocolread, sansPath/SDK/HTTP.
8. `backend/modules/work_orchestration/application/queries/inspect_p1_campaign.py` — queryreadonly/outcome/refusclosed.
9. `backend/adapters/inbound/application/p1_campaign_inspection.py` — wrapperApplicationstrict, noFS/SQL/provider.

Tests nouveaux :
- `tests/unit/test_p0_product_rejected_continuity.py`
- `tests/integration/test_p0_product_rejected_continuity_native.py`
- `tests/unit/test_p1_campaign_inspection.py`

ADRsource : `docs/development/ADR_LU_PRODUIT_01_P1_KNOWN_REJECTED_CONTINUITY_V2_2026-10-14.md`, générique horsrawruntime.

Aucun changement testsCP645trio, guards/pins, oldnormal/profile/policy/product/ledger/receipt, sourcecontext/UI/M02/Word/exporteurs, oldsourcebook/profil actif. Les seules mutations de drivers sont les deux selectors décrits au §14. Si un inventaire fermé exige un refresh, proposition précise séparée puis revue préalable ; aucun broadprefix. Le reviewer qualifie aussi la nécessité de chaque fichier avantcode, pas un delta anticipémentqualifié.

## 11. QA synthétique et native par impact

Aucune exécution n'est revendiquée par cet ADR. Le source futur n'utilise aucune donnée réelle ni clé. Les scénariosfixture fournissent anchors/decisions/profile/namespace entièrement synthétiques avec la mêmecomposition, jamais un seam bool ou une préimage de hash réel.

### Positifs obligatoires

- OFFsansplan : zéroI/O/callback/broker/resolver/tokenizer/transport/allocation.
- BootstrapINSPECT_ONLY exact synthétique : véritables files du protocole Normal/P1 avec transportdouble, timestamps event() réels, unancienCONSUMED + uncapturedPARSING_REJECTED ; originalLOCK partagé ; factory4 + Application query → witness complet OBSERVED_NOT_ADOPTED/cumulreserved/livefalse.
- Rattachement synthétique du witness/profile4OFF : mêmebytes/root/op/natives, snapshot2 réconcilié ; aucunepublication auledger (inventaire+rawSHAavant/après).
- Profil4ON futur strict, source4receipts actuels admis exact : nouveaupreflight/consent/grantnamespace, un CREATEdouble, vieuxslotrejected inchangé et compté ; read/save/reopen/export COURSEconsumers seulement siimpact.
- AncêtresV1 exacts et consumed validationunchanged ; OFF→ON viaDAG sanscycle, pasretoggle ; current ownPendingexactsouslock seulement.
- Readonlybootstrap/profileOFF viainbound/callbackmetadataexisting : génération/consent nonliés, aucuneclé/SDKcall, pas nouveauHTTP route.
- NativeWindows lock etparentshandles réels, contentioncrossversion V1/V2/2processes, nativeidentitysubstitutionrefus, closealways ; pas simulationpourannoncerqualificationnative.

### Mutations/refus

Closedtypes/bool-as-int/dupJSON/NaN/UTF8/extrafields ; expectedownerhash/décision/transcription/adoptionplan incorrects ; missing/changednative/SID/profile/store/package/manifests/tariff/tokenizer ; rootLOCK manquant/changed/replaced/concurrent ; chainbranch/cycle/ancestormissing/ambiguity/descriptorcollision/rootwindoworcommuns changed/sourceownerabsent/newadmissions.

Missing/changed/dupliqueslot/preview/command/ns/grant/recordSHA/dispatchbodybyte/requestsize/hash/preflight/RESULT/eventartifact/output/usage/status; ordertimes/outrangeorigin/grant/booleancount/attempt2; UNKNOWN/PARSED/CONSUMED présents surrejected; rejectedautre ns/erreur/code/tipcurrent ; witnessinventé/missing/unadopted/historicaldropped/orphan; oldgrantrecover/pasnouveauconsent/source4payloadold/schemahashdivergent; over14/percall/cumulative ; absenttier/incomplete exigé commeconforme ; totalreserved supposébill/reset/refund ; missingcountremainingnevermakesavailable.

Incompleterésponse/status ou nouveaucallreject se refusent ; le snapshotneproposeaucunsoldevalide. Une fenêtre divergente ou expirée n'ouvre aucun live.

Régressions sélectionnées : existing P1 policies/broker/ledger/profile1–3/destination/recovery/consentHTTPmetadata/normalgrant/payload guards, sélection node_ids exacte seulement aprèsdiff pourrisqueconcret. Pas de nouveauglobal ni rejeu mécanique des anciens tests. Streams/coderetour/JUnit/pinsnécessaires ; SKIP natif est conservéetdiagnostiqué, pasconvertiPASS. Ruff/typecheck/compile etfitness parimpact aprèscode ; aucun modèle/budget permissionnecompenseuneQAéchouée.

## 12. Retour OFF et limites opérationnelles

Fermer leshandles et la sessionfuture ; désinstaller uniquementbindingdecompositionV2, sélectionnerexplicitementpackage/profileOFFadopté. Conserver sources/branches/archives/oldnewprofiles/proofs/slots/events/LOCK/bases/sauvegardes. Aucun nettoyage/purge, ledgerwritehistorique, mutationSQL, rollback propriétaire, resetquota/namespace/window, HKCU/ACL/privileges/UAC/DeveloperMode.

Les reservations consommées et rejetées restent dansle cumul. AprèsretourV1 l'ancien STOP surPARSING_REJECTED est correct ; nepasleprésentercommeunecorruptionàréparer.

L'orientation et sa miseenœuvrelocale ne sontpas uneacceptationpédagogique, unereleaseouunepermission live. La recetteenseignante reste exclusivementdernièreétape, nonréalisée/nonsignée.

## 13. Gates et livrables avant accès réel/futur ON

1. ADR exact et spec/sourceADRgénérique relus dans une passe distincte avantsource ; décisionimpllocaleacquise appliquée seulementdansce périmètre.
2. Implémentationpure/native/defaultOFF, tests réels parimpact et revueexactcodetarget, candidate/package/source_manifest/scopesfigés ; noproprietarysourceGIT.
3. Plan réelINSPECT_ONLY exactsource/package/origin/descriptors/native/SID/stores/decisionacts reprisdepreuveseffectives, adoptiondeceplanavantlectureinboundV2 ; absencede pin =STOPetunmanqueréelgroupé.
4. InspectionApplicationOFFcourante produit hasheswitness/cumul/noeffect ; projectionresteNONADOPTE sans décisionexacte finale. Aucune donnéeobservéeimprovisée.
5. Propositionsgroupéesmanifest2/anchor2/disposition/profile4OFF puisON/envelopes/permissions/decisions exacts, maintienrootquota/ns/LOCK/window/sources ; adoptiondesSHAetpermissionsduplanexplicite, pasdegranttransféré.
6. RevalidationApplication sousLOCK aprèsadoptionOFF, puisactivationONdistincteadoptée ; aucunecurrentremaining présumée àpartird'unreçudaté.
7. NouveauCOURSE4body réellementpréparé, financierdémontré et deuxconsentementsfreshV2 avantl'uniqueCREATEdequalificationexplicitementautorisé ; conservation/reouverture/export/contrôlestechniquespropres,puisrecetteenseignantedernière.

Aucun de ces accès/adoptions/effetsfuturs n'est simulé dans le présent ADR. Aucun nouveau lotA06/global/merge/déploiement implicite.

## 14. Raccordement explicite au lanceur normal — amendement R3

Le lanceur actuellement transmet uniquement `--p0-normal-profile`, et la CLI instancie seulement P0NormalProductCompositionV1. Les neuf modules neufs ne suffisent donc pas au parcours normal. **Deux drivers existants sont ajoutés au delta, pour ce dispatch uniquement** : `backend/adapters/inbound/cli/local_browser.py` et `tools/launch-local.ps1`. Aucun des treize fichiers V1 de contract/policy/ledger/profile/normal/API n'est modifié. Aucun monkeypatch, aliasprofile3, auto-latest, wrapper Codex ou nouveau routageHTTP n'est utilisé en production.

### 14.1 Options et configuration fermées

| Clé JSON locale | Option CLI | Contrat |
|---|---|---|
| `p0_rejected_profile` | `--p0-rejected-profile` | Chemin absolu local littéral vers envelope profile4 final exactement adopté. Exclusif du plan et du p0_normal_profileV1. |
| `p0_rejected_inspection_plan` | `--p0-rejected-inspection-plan` | Chemin absolu local littéral vers le plan INSPECT_ONLY exactement adopté. Exclusif du profile4 et de p0_normal_profileV1. |
| `p0_rejected_adoption` | `--p0-rejected-adoption` | Chemin absolu local littéral de la preuve trusted EXTERNE d'adoption du plan ou du book/profile exact. Obligatoire pour chacune des deux branches ; aucune authority depuisHTTP. |
| `p0_rejected_mode` | `--p0-rejected-mode` | Valeurs case-sensitive `inspect-only`, `off`, `on`. Omission pour profile4 signifie `off`. Plan requiert inspect-only explicite. Ce sélecteur n'accorde aucune activation. |

Les chemins nouveaux sont des données d'infrastructure de l'opérateur local : strings nonvides, absolus drive-local, sans UNC/relative ou substitution d'environnement. Aucun envsecret n'est lu/expansé pour ces quatre options. La factory effectue ensuite les contrôles nofollow/native/descriptor/SID/sourcePackage/authority exacts ; la validation lexicale du driver n'atteste jamais le fichier ou l'adoption.

Les clés nouvelles null/bool/int/vides, mode hors enum/casevariant et optionorpheline sont refusés, pas ignorés ni convertis. Une nouvelle clé avec casing différent du nomcanonique est refusée, sans fallback versoffline/V1. Le reste du contrat de launcher.json demeure historique : ces quatre clés ajoutent seulement un sélecteur, pas permission/grant/window/secret. Aucun configuser réel n'est modifié par ce lot. `config/local-v2.example.json` reste inchangé et sans optionV2 ; son défaut horsfournisseur reste acquis. Un futur fichier exact de lancement V2 est préparé horsGit et soumis à ses gates.

**Exclusivité avant I/O métier :**
- p0_normal_profileV1 présent avec un quelconque selectorV2 = refus ;
- profile4 et plan ensemble = refus, même mêmechemin ;
- adoption/mode seuls ou nouveaux champs sans selector = refus ;
- selectorV2 avec saved-only/create-saved/R2enable-conversation/R3enable-review-modify/R2liveauthorization/R5scope/R5authorization = refus ;
- saved_root absent, runtime/data_root/runtimeSHA absents ou word_profile différent de product-v7 = refus ;
- profile4 avec inspect-only ou plan avec off/on/mode omis = refus ;
- aucun selector présent : comportementV1/offline antérieur inchangé.

“Avant I/O” signifie avant ouverture profile/plan/adoption/target/stores, allocation, callback, tokenizer/resolver/SDK, probing du port ou invocationPython par le lanceur. La seule lecture de la configuration explicitement choisie et les imports/parsing des drivers sont nécessaires au routage ; ils n'accordent aucune autorité métier. Les guards s'exécutent avant les branches R2/R3/R5 et avant build_local_read15.

CLI : default argparse du mode nonfourni est None pour distinguer une optionorpheline ; le modeeffectif d'un profile4 est off. Ne jamais lire un schema fichier pour choisir implicitement une factory. Une CLI direct en erreur émet un code générique fermé et retourne1 ; argparse hors-enum retourne2. Launcherconfig invalide retourne2 avant Python/port/target. Aucune erreur n'affiche de path privé, clé, payload ou output.

### 14.2 Classes, signatures et branchements exacts

Dans le seul nouveau module déjà prévu `backend/infrastructure/composition/factories/p0_rejected_profile.py` :

- `P0RejectedInspectionComposition(plan_path, adoption_path, target, saved_root)` : exclusivement inspect-only. Exige plan/proof exacts et nativechecks. `generation=None`, aucunresolver/tokenizer/transport/consent. `bind(service,endpoint)` installe exclusivement la query inbound Application d'observation, portée ValidatedInspectionPlan ; elle ne fabrique pas BoundChainV2. Callback metadata existant, pas de nouvelle route.
- `P0RejectedProductComposition(path, adoption_path, target, saved_root, mode='off')` : exclusivement profile4. Require mode off/on exact et égal au bool continuity_enabled immuable du profile4 adopté. OFF sur profileON ou ON sur profileOFF = refus, sans toggle/réécriture. OFF : generationNone et query Application snapshot2 seulement après vrai rattachement externe et BoundChainV2. ON : mêmespréflights/sourcepolicy4/consents/finance/normaladapter stricts, activation séparément adoptée ; présence du flag ne suffit jamais.
- Les deux classes exposent `generation` (None en OFF/inspect-only), `bind(service,endpoint)` et `close()`, avec lifecyclefermé. Aucun sideeffect à l'import ; close ferme handles/session, n'efface rien.
- Le driverCLI emploie une interface locale pure de composition (Protocol generation/bind/close, types Application existants sous TYPE_CHECKING si nécessaire), pour supporterV1/V2 sanscast permissif ou importSDK. L'interface n'est ni un registry ni une autorité.

Après refuslexicaux/exclusivité, la CLI choisit exactement un constructeur :
1. p0_normal_profile seul → import/constructor P0NormalProductComposition existants, sansnewfactory ni effetsV2.
2. p0_rejected_inspection_plan + adoption + inspect-only → nouvelle InspectionComposition.
3. p0_rejected_profile + adoption + modeeffectif off/on → nouvelle ProductComposition.
4. aucun → normal=None, ancien offline.
Aucune autre combinaison n'atteint un constructor. Erreur de nouvellecomposition = P0_REJECTED_COMPOSITION_NOT_ADOPTED_OR_INVALID ; aucune fallback versV1/offline. Les erreurs/fonctions de la brancheV1 sont préservées.

La suite est le build_local_read15 et son API existants : `p0_generation=composition.generation` et `p0_product_binder=composition.bind`. OFF/inspect-only passent None et bind ne lie que leur Applicationquery. En startupfailure, servicefailure, KeyboardInterrupt ou fermeture normale, fermer la compositionlocale et le server existants. Aucun serveur, port, grant ou keyprompt ne reste inventé comme “ready”.

Le lanceur traduit les quatre clés validées en argvarray exacts, sans interpolation shell, et transmet le modeeffectif. Il affiche un message horsfournisseur pour inspect-only/OFF, et pour ON rappelle seulement les consentements exacts ; aucun succès de gate déduit d'une option. App normale ensuite reste le même parcours V2, sansintervention Codex pour chaque opération.

### 14.3 Delta et tests additionnels fermés

DeltafinalR3 : **9 nouveaux modules + 2 drivers modifiés + 4 nouveaux tests + 1 ADR générique**. Les trois tests P1/Native/Application initiaux restent prévus ; nouveau fichier unique `tests/unit/test_p0_rejected_launch_dispatch.py` possède les tests de sélectionCLI et launcherPowerShellréels. Aucun autre code/config/testbaseline modifié. Les guards ferméspaths peuvent recevoir une proposition séparée précisément relue, jamais un préfixepermissif.

Tests obligatoires de dispatch, pas encore exécutés :
- CLI main réelle : ancienoffline/defaultV1 et p0_normal_profileV1 routent commeavant ; optionsV2 absentes ne construisentaucunefactoryV2.
- CLI réelle : profile4modeomis/off, profile4on et planinspect-only atteignent le seul constructeur exact ; kwargs mode/path/adoption/target/savedroot corrects. Les doubles de server/lifecycle servent uniquement au test de routage, pas à qualification d'autorité/factory.
- Erreurs/exclusivités/orphelins/modes/chemins/types : sentinelles refusent toute construction/target/builder/callback/secret/SDK avant ces refus. Aucun test de transport ne doit prétendre réussir la qualificationnative du factory.
- LauncherPowerShell réel, configuration et argv synthétiques : absenceV2 préserve ancienargv ; nouvellebranche émet les flags/modes exacts ; positiveforwarding vers un capture-executable synthétique ne démarre pas fournisseur et qualifie seulement le transport d'argv.
- Launcher réel négatif : occupationport + conflitV2 doit retourner CONFIG_INVALID avant PORT_IN_USE ; types/casing/relative/UNC/orphelins/incompatibles/modeincorrect échouent avantinvocationPython. Aucun besoin de privilège/ACL/ExecutionPolicy changement ou dépendance nouvelle ; prerequis indisponible = diagnostic/SKIP réel, pas bypass.
- Dans `tests/integration/test_p0_product_rejected_continuity_native.py`, relier aussi mainCLI réel au factoryV2 réel sur fixturesneuves synthétiques ; limiter le serverloop à une frontièreinstrumentée de fermeture, sans mock de native/auth/descriptor/ledger/protocol. Les callbacks passent par le vrai inbound Application, generation/consentNone inspect-only/OFF, puis close et inventorybefore/after. Positifs/negatives bootstrap/profile4OFF/ON et mismatchmode/profile restent qualifiés dans leur portée native.
- Régressions parimpact au moins tests/unit/test_p0_normal_cli.py, tests/unit/test_h3_launcher_contract.py et consumers composition affectés, avec leur protocole qualifié explicite, sansmodifier leurs assertions ou annoncerPASSsansrun. Une conditionhost/permission manquante resteouverte ; aucun override de sécurité ajouté pour rendre les nouveauxtests disponibles.

Le protocole de QA futur distinguera : arguments réellementdispatchés, lifecycle normal réellementexercé, factories/native effectivementqualifiés et parties contrôlées par doubles. Il conservera stdout/stderr/coderetour/JUnit/pins sans conflation. Aucun nouveauglobal ni appel réel.

## Projection Application de l’inspection

La sécurité canonique des `ApplicationOutcome` reste inchangée. Les descriptors physiques du witness complet appartiennent à l’infrastructure ; ils ne passent pas dans les données publiques de l’Outcome.

La query readonly valide la liaison logique du request avant son unique appel de port. Elle valide ensuite les champs fermés du résultat. Pour le bootstrap, elle vérifie l’empreinte du witness complet sur sa sérialisation canonique exacte UTF-8, clés triées, séparateurs virgule/deux-points, `ensure_ascii=false`, `allow_nan=false`, sans newline. Ce calcul est pur dans le module Application ; aucun import outbound n’est ajouté au domaine.

La vue bootstrap porte `P1-CAMPAIGN-INSPECTION-OBSERVATION-1.0` et son témoin projeté `P1-KNOWN-REJECTED-EVIDENCE-METADATA-1.0`. Les deux descriptors internes `owner_orientation_adoption` et `owner_diagnostic` deviennent des objets fermés `{ref, sha256}`, avec `ref=p1-evidence:<sha256>`. Le witness complet reste intact. `observed_evidence_sha256` désigne ses octets complets, pas la vue ; `evidence_hash_basis=UNDERLYING_FULL_EVIDENCE_RAW_BYTES` le précise. Aucun body, texte fournisseur ou chemin privé n’est publié. La vue projetée ne peut pas remplacer le witness natif dans un rattachement.

Le snapshot2 conforme est conservé dans sa forme sûre, avec ses réservations et son absence de qualification du COURSE. Le bootstrap reste `OBSERVED_NOT_ADOPTED`, sans disponibilité de budget. Aucun side effect, grant, allocation ou mutation historique n’est produit par cette query.

Les erreurs de port et de mapping sont classées par les quatre catégories Application prévues ; aucune exception brute n’est retournée. Les tests synthétiques vérifient la liaison du hash complet, la séparation des schemas, l’intégrité du witness d’entrée, les refus de types/états/valeurs privées, l’absence d’appel avant un binding valide et la classification des refus. Ils ne qualifient aucun store ou witness réel.

## Correctif minimal des lectures répétées du ledger

Le choix minimal a été relu avant implémentation : ADR de proposition SHA-256 `f3fd19d56ddab39a20155d3bc3f78cd22e4da6812681f7f97bf8f4f59f8af958`, avis préalable distinct SHA-256 `63c92e7ecf6abb4ff7c2f5104ebbc5510b56da27e179e2ddde85bf2fa6298be4`. Ces références qualifient le design borné, pas un résultat réel ni une activation.

Chaque composition possède un objet ledger natif stable, créé après sa validation initiale. Son getter ne refait pas cette construction. À chaque opération, `locked()` conserve le LOCK original et appelle un `chain_loader` frais : source, package, descripteurs, identités, slots, événements et cumul sont encore vérifiés. Aucun `BoundChain`, résultat financier ou proof de source n'est réutilisé entre deux opérations. Les états internes du ledger se ferment en `finally` et une tentative précédente incomplète ou UNKNOWN ne devient pas admissible par l'identité de l'instance.

La mesure d'une distribution publique plus courte est une qualification technique distincte de la copie activable adoptée. Elle ne transfère aucun droit, chemin de store, grant ou quota. Les fichiers publics importés et leurs empreintes doivent être attestés ; les sources, worktrees, archives et résultats précédents sont conservés.

Les délais frontend restent inchangés. Les mesures avec resolver et transport synthétiques immédiats ne garantissent pas le délai d'un fournisseur réel, dont le timeout reste séparé. Une borne dépassée conserve le défaut de readiness ouvert, même si le parcours fonctionne et qu'un autre contrôle passe. Le lanceur synchrone n'a pas de timeout READY identifié ; cela ne qualifie pas la rapidité de sa construction. Aucune optimisation supplémentaire, cache global ou déduplication entre phases n'est autorisée par ce correctif minimal.

## Read-set natif limité à une phase V2

La correction complémentaire a été relue avant son implémentation : proposition R2 SHA-256 `d6f2503154621e514bd0998dc122fc25ffa82f02b17eb1c59fe7b87a649cbff5`, spécification fermée SHA-256 `07773ead8f85e76bbfb79bbb2f532f9d15435a897c0a0fb7d78da89db0fe4d13`, avis préalable distinct SHA-256 `59d70f6c339933e0f6f27987e47023b61c050e0280619dbd11f2872d58abc63f`. Elle ajoute le seul helper natif `p0_rejected_readset.py`, sans changer les treize propriétaires V1 ni la projection Application.

Seules les phases PREVIEW, ACCEPT et GENERATE de la factory V2 désignée peuvent retenir une preuve à l'intérieur de leur invocation, sous le LOCK original déjà détenu, sur le même thread, broker, ledger, permission et namespace. Le graphe fermé contient les composants exacts, sources publiques, package, descripteurs et reçus historiques de la campagne. Il est borné à 4096 fichiers ; un graphe absent, ambigu, trop grand, partiellement acquis ou non protégé est refusé. Les fichiers historiques existants sont protégés ; les répertoires de publication mutables restent ouverts aux créations normales, avec contrôle frais de leur identité.

Chaque fichier est ouvert sans suivre un reparse point, avec un handle asynchrone dont le partage autorise seulement READ. Le hash provient exclusivement de ce handle retenu, par ReadFile avec offsets et OVERLAPPED, buffer et événement de lecture distincts de l'oplock. Les transferts sont vérifiés et bornés. Un READ oplock doit rester en attente après le retour FALSE/ERROR_IO_PENDING de la demande exacte. Il complète la barrière des nouveaux writers par le refus documenté des mappings writable préexistants ; il n'est ni un mutex ni une garantie atomique universelle. Aucun ACK, re-grant ou élargissement de partage silencieux n'existe.

À chaque réemploi, les attributs et identités de tous les parents, l'absence de reparse, les liaisons path-vers-handle, les événements d'oplock, la couverture source, l'absence de `.git`, les identités natives et l'inventaire courant des slots/namespaces restent contrôlés. Un nouvel orphelin ne devient pas une autre campagne présumée. Les étapes Normal du seul OwnPending exact sont distinguées : vide réellement observé, puis RESERVED+DISPATCH intégralement liés avant effet. Un lifecycle partiel, prématuré, UNKNOWN ou PARSING_REJECTED est refusé. Après le vrai retour de Normal.generate, le ledger valide le terminal par le protocole confirmed et les événements réels, puis le broker confirme le résultat. Aucun reçu CONSUMED n'est inventé.

Le `finally` invalide la preuve avant la cancellation/terminaison des I/O et la fermeture de tous les handles/événements. Un état non terminé conserve sa mémoire native et empoisonne la composition ; il ne peut pas être réutilisé. La validation de début d'opération, GET/startup et AUTHORIZE reste fraîche. Il n'y a aucun cache global, de session, entre requêtes ou entre preview, accept et effet. Les paramètres, consentements, corps, temps, préflight financier, cumul et quotas restent contrôlés aux frontières réelles.

Les probes natifs, refus de mutation et mesures de la distribution effectivement importée restent des preuves techniques distinctes. Leurs chemins et chronométrages restent hors Git. Un manque de prérequis ou un dépassement de délai n'est pas qualifié comme réussite. Aucun de ces mécanismes ne produit une adoption, une activation, un appel fournisseur ou un droit supplémentaire.
