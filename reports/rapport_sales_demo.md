# Rapport de réconciliation post-migration — sales_demo

*Généré le 16/07/2026 à 12:07*

## Résumé exécutif

 Rapport de réconciliation post-migration Power BI/Qlik Sense :

Résumé exécutif :
- Un problème bloquant a été identifié dans la réconciliation de données du module A (écart de 9900.00% entre Qlik et Power BI).
- Un problème majeur a été détecté dans l'audit de couverture fonctionnelle du module B (absence de mesure DAX correspondante pour left_join).

Ce rapport indique un niveau élevé de risque en matière de cohérence des données et de fonctionnalité entre les deux solutions. Il est recommandé d'attaquer ces problèmes prioritairement pour garantir la validité de la migration.

## Détail des findings

### [BLOQUANT] Laptop
- **Module source :** Module A - Réconciliation de données
- **Détail :** Valeur Qlik: 116.67 vs Power BI: 11666.67 (écart 9900.00%)
- **Diagnostic :** Format d'affichage incorrect (%) probable.
- **Statut :** ⬜ à valider par le consultant

### [MAJEUR] left_join (left join()
- **Module source :** Module B - Audit de couverture fonctionnelle
- **Détail :** Mesure DAX correspondante : aucune trouvée
- **Diagnostic :** Aucune relation DAX équivalente identifiée clairement.
- **Statut :** ⬜ à valider par le consultant
