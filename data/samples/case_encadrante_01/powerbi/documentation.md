# Documentation technique - sales_demo

Généré automatiquement le 2026-07-01 14:18:55

## 1. Vue d'ensemble

Ce rapport Power BI, nommé 'sales_demo', présente une analyse des données de ventes. Le modèle de données est structuré autour d'une table de faits centrale, 'Sales', qui contient les transactions, et de tables de dimensions pour les clients ('Customers') et les produits ('Products'). Cette structure permet une analyse multidimensionnelle des performances commerciales.

Le rapport inclut plusieurs pages, telles que 'Executive Overview' et 'Advanced Analytics', suggérant des niveaux d'analyse variés, allant du résumé de haut niveau à l'exploration de métriques détaillées. Les calculs sont centralisés dans une table dédiée aux mesures, '_Measures', qui contient des indicateurs de performance clés (KPIs) comme le total des ventes, la croissance annuelle et la marge moyenne.

Les données sont intégrées à partir de plusieurs sources, incluant des données saisies manuellement dans Power Query, un fichier Excel et un fichier CSV. Le modèle utilise également des techniques avancées, comme une table de paramètres pour permettre une sélection dynamique des dimensions dans les visuels, offrant ainsi une expérience utilisateur interactive.

## 2. Synthèse du modèle

- Culture du modèle: en-US
- Nombre de tables: 6
- Nombre de colonnes: 23
- Nombre de mesures: 13
- Nombre de relations: 2
- Nombre de pages de rapport: 3
- Nombre de filtres de rapport: 0
- Nombre de visuels personnalisés: 0

### Points clés

- Le modèle est organisé selon un schéma en étoile de base, avec la table de faits 'Sales' reliée aux dimensions 'Customers' et 'Products'.
- Une table dédiée ('_Measures') centralise l'ensemble des 13 mesures DAX, ce qui constitue une bonne pratique pour la maintenance et la clarté du modèle.
- Le modèle intègre une table de paramètres DAX ('Sales by Product Dimension Selector') pour permettre aux utilisateurs de changer dynamiquement l'axe d'analyse des produits dans les rapports.
- Les données proviennent de sources hétérogènes (Excel, CSV, données entrées manuellement), consolidées via des requêtes Power Query.

### Pages du rapport

- Advanced Analytics (jyex)
- Executive Overview (mddprh)
- Advanced Metrics (ygzmvds)

## 3. Tables et résumés

### Customers

Table de dimension contenant les informations sur les clients, telles que l'identifiant, le nom, le segment et l'adresse. Les données sont issues d'une combinaison de données saisies manuellement et d'un fichier externe Excel.

- Catégorie: Semantic
- Sources: Sheet1
- Colonnes: 4
- Mesures: 0

### _Measures

Table technique calculée via DAX, servant de conteneur pour toutes les mesures du modèle. Elle n'est pas reliée aux autres tables et a pour but d'organiser les calculs.

- Catégorie: Calculée (DAX)
- Sources: non détectées
- Colonnes: 1
- Mesures: 13

### Products

Table de dimension décrivant les produits avec leur identifiant, nom, catégorie et un groupe personnalisé. Les données sont définies manuellement dans la requête Power Query.

- Catégorie: Semantic
- Sources: non détectées
- Colonnes: 4
- Mesures: 0

### Sales

Table de faits principale qui enregistre les transactions de vente. Elle contient des détails sur les commandes, les dates, les montants, les quantités et les marges, ainsi que les clés pour la relier aux dimensions.

- Catégorie: Semantic
- Sources: non détectées
- Colonnes: 11
- Mesures: 0

### SalesChannels

Table de dimension destinée à contenir les informations sur les canaux de vente. Les données sont importées depuis un fichier CSV externe. Les colonnes de cette table ne sont pas détectées.

- Catégorie: Semantic
- Sources: non détectées
- Colonnes: 0
- Mesures: 0

### Sales by Product Dimension Selector

Table de paramètres calculée via DAX. Elle est utilisée pour permettre la sélection dynamique d'une colonne de la table 'Products' ('Product Name' ou 'Product ID') dans les visuels du rapport.

- Catégorie: Calculée (DAX)
- Sources: non détectées
- Colonnes: 3
- Mesures: 0

## 4. Relations

| Table source | Colonne source | Table cible | Colonne cible | Cardinalité |
| --- | --- | --- | --- | --- |
| Sales | Customer ID | Customers | Customer ID | non detectee |
| Sales | Product ID | Products | Product ID | non detectee |

## 5. Explication automatique des mesures

| Dossier | Mesure | Table source | Colonne source | Explication |
| --- | --- | --- | --- | --- |
| General | Total Sales | Sales | Sales Amount | Calcule la somme totale des montants des ventes à partir de la colonne 'Sales Amount' de la table 'Sales'. |
| General | Selected Metric Value | Sales | Sales Amount | Calcule la somme totale des montants des ventes. L'expression est identique à celle de la mesure [Total Sales]. |
| General | Previous Year Sales | Sales | Order Date | Calcule le total des ventes pour la même période de l'année précédente en se basant sur la mesure [Total Sales]. |
| General | Sales Year Over Year Growth | non detecte | non detectee | Calcule le taux de croissance des ventes en pourcentage en comparant le [Total Sales] avec le [Previous Year Sales]. |
| General | Latest Year Sales | Sales | Sales Amount | Calcule le total des ventes pour l'année la plus récente disponible dans l'ensemble du jeu de données, indépendamment des filtres de date appliqués. |
| General | Current Year Sales | Sales | Year | Calcule le total des ventes pour l'année sélectionnée dans le contexte de filtre actuel. |
| General | Average Margin | Sales | Margin | Calcule la marge moyenne à partir de la colonne 'Margin' de la table 'Sales'. |
| General | Total Orders | Sales | Order ID | Compte le nombre de commandes uniques en se basant sur la colonne 'Order ID'. |
| General | Latest Month Sales | Sales | Order Date | Calcule le total des ventes pour le mois le plus récent disponible dans l'ensemble du jeu de données. |
| General | Year To Date Sales | Sales | Order Date | Calcule la somme cumulative des ventes depuis le début de l'année jusqu'à la date sélectionnée dans le contexte de filtre. |
| General | Distinct Customer Count | Sales | Customer ID | Compte le nombre de clients uniques ayant effectué au moins une commande. |
| General | Sales Excluding North Region | Sales | Region | Calcule le total des ventes de l'année en cours, en excluant toutes les transactions de la région 'North'. |
| General | Average Sales Per Customer | Sheet1 | Customer ID | Calcule le montant moyen des ventes par client en utilisant le [Total Sales] et la liste des clients. |

## 6. Notes techniques

- Les requêtes Power Query pour les tables 'Customers' et 'SalesChannels' contiennent des chemins de fichiers en dur ('C:\data\Address.xlsx', 'C:\data\Channels.csv'). Ces chemins devront être mis à jour pour que le rafraîchissement des données fonctionne dans un autre environnement.
- La cardinalité des relations entre les tables n'a pas été détectée.
- Le modèle de données ne contient aucun visuel personnalisé.
- Aucun filtre n'est appliqué au niveau du rapport.

## 7. Annexe sémantique

| Dossier / Sous-Dossier | Nom du Champ / Mesure | Type de Format | Visibilité | Table Source | Colonne Source | Règle de Gestion / Formule & Filtres |
| --- | --- | --- | --- | --- | --- | --- |
| Customers | Customer ID | TEXT | Oui | Sheet1 | Customer ID | Copie |
| Customers | Customer Name | TEXT | Oui | Sheet1 | Customer Name | Copie |
| Customers | Segment | TEXT | Oui | Sheet1 | Segment | Copie |
| Customers | Customer Adress | TEXT | Oui | Sheet1 | Customer Adress | Copie |
| Mesure\General | Total Sales | ENTIER | Oui | Sales | Sales Amount | SUM(Sales[Sales Amount]) |
| Mesure\General | Selected Metric Value | ENTIER | Oui | Sales | Sales Amount | SUM(Sales[Sales Amount]) |
| Mesure\General | Previous Year Sales | NUMERIQUE | Oui | Sales | Order Date | CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Sales'[Order Date])) |
| Mesure\General | Sales Year Over Year Growth | DECIMAL | Oui | non detecte | non detectee | DIVIDE([Total Sales] - [Previous Year Sales], [Previous Year Sales]) |
| Mesure\General | Latest Year Sales | ENTIER | Oui | Sales | Sales Amount | CALCULATE(<br>    SUM(Sales[Sales Amount]),<br>    Sales[Year] = CALCULATE(MAX(Sales[Year]), ALL(Sales))<br>) |
| Mesure\General | Current Year Sales | NUMERIQUE | Oui | Sales | Year | CALCULATE([Total Sales], 'Sales'[Year] = MAX('Sales'[Year])) |
| Mesure\General | Average Margin | DECIMAL | Oui | Sales | Margin | AVERAGE(Sales[Margin]) |
| Mesure\General | Total Orders | NUMERIQUE | Oui | Sales | Order ID | DISTINCTCOUNT(Sales[Order ID]) |
| Mesure\General | Latest Month Sales | NUMERIQUE | Oui | Sales | Order Date | VAR _LatestDate = CALCULATE(MAX(Sales[Order Date]), REMOVEFILTERS(Sales))<br>VAR _LatestYear = YEAR(_LatestDate)<br>VAR _LatestMonth = MONTH(_LatestDate)<br>RETURN<br>    CALCULATE(<br>        [Total Sales],<br>        KEEPFILTERS(Sales[Year] = _LatestYear),<br>        KEEPFILTERS(Sales[Month] = _LatestMonth)<br>    ) |
| Mesure\General | Year To Date Sales | NUMERIQUE | Oui | Sales | Order Date | TOTALYTD([Total Sales], 'Sales'[Order Date]) |
| Mesure\General | Distinct Customer Count | ENTIER | Oui | Sales | Customer ID | DISTINCTCOUNT(Sales[Customer ID]) |
| Mesure\General | Sales Excluding North Region | NUMERIQUE | Oui | Sales | Region | CALCULATE([Total Sales], 'Sales'[Region] <> "North", 'Sales'[Year] = MAX('Sales'[Year])) |
| Mesure\General | Average Sales Per Customer | NUMERIQUE | Oui | Sheet1 | Customer ID | AVERAGEX(VALUES(Customers[Customer ID]), [Total Sales]) |
| _Measures | Placeholder | TEXT | Non | Calculée (DAX) | [Placeholder] | Copie |
| Products | Product ID | TEXT | Oui | non detecte | Product ID | Copie |
| Products | Product Name | TEXT | Oui | non detecte | Product Name | Copie |
| Products | Category | TEXT | Oui | non detecte | Category | Copie |
| Products | Product Groupe | TEXT | Oui | non detecte | Product Groupe | Copie |
| Sales | Order ID | INT64 | Oui | non detecte | Order ID | Copie |
| Sales | Order Date | TIMESTAMP | Oui | non detecte | Order Date | Copie |
| Sales | Year | INT64 | Oui | non detecte | Year | Copie |
| Sales | Month | INT64 | Oui | non detecte | Month | Copie |
| Sales | Customer ID | TEXT | Oui | non detecte | Customer ID | Copie |
| Sales | Product ID | TEXT | Oui | non detecte | Product ID | Copie |
| Sales | Channel ID | INT64 | Oui | non detecte | Channel ID | Copie |
| Sales | Region | TEXT | Oui | non detecte | Region | Copie |
| Sales | Sales Amount | DECIMAL | Oui | non detecte | Sales Amount | Copie |
| Sales | Quantity | INT64 | Oui | non detecte | Quantity | Copie |
| Sales | Margin | DECIMAL | Oui | non detecte | Margin | Copie |
| Sales by Product Dimension Selector | Sales by Product Dimension Selector | TEXT | Oui | Calculée (DAX) | [Value1] | Copie |
| Sales by Product Dimension Selector | Sales by Product Dimension Selector Fields | TEXT | Non | Calculée (DAX) | [Value2] | Copie |
| Sales by Product Dimension Selector | Sales by Product Dimension Selector Order | INT64 | Non | Calculée (DAX) | [Value3] | Copie |

## 8. Mesures par visuel et par page

_Données non disponibles pour ce format de rapport (format Fabric definition)._
