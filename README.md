# 🔍 Agent d'audit intelligent de migration Qlik Sense → Power BI

Agent d'audit automatisé pour les migrations **Qlik Sense → Power BI**, combinant rapprochement de données, analyse fonctionnelle et intelligence artificielle pour fiabiliser et accélérer les projets de migration BI.

> Juillet – Août 2026 · Projet développé en environnement de production, 31 tests automatisés validés.

---

## 🎯 Pourquoi ce projet ?

Migrer un rapport Qlik Sense vers Power BI est un exercice à risque : un KPI mal recalculé, une visualisation manquante ou une règle métier oubliée peuvent passer inaperçus jusqu'à ce qu'un utilisateur final s'en aperçoive. Cet agent automatise le contrôle qualité de bout en bout, pour donner aux équipes de migration une vision claire et objective de ce qui a été correctement repris — et de ce qui ne l'a pas été.

## ✨ Fonctionnalités

- **Rapprochement de KPI** : extraction et comparaison automatique des indicateurs entre Qlik Sense (Qlik Engine API) et Power BI (moteur Analysis Services local).
- **Détection des écarts** : identification des écarts de données, des lacunes structurelles (modèles, mesures, relations) et des problèmes de couverture fonctionnelle (visuels manquants ou incomplets).
- **Règles de rapprochement intelligentes** : moteur de règles pour distinguer les écarts réels des simples différences de présentation.
- **Assistant LLM intégré** (Mistral via Ollama, exécuté en local) :
  - analyse sémantique des écarts détectés,
  - assistant Q&A pour explorer les résultats en langage naturel,
  - génération de suggestions de correction DAX.
- **Rapports consolidés** : synthèse exportable (Word/PDF), suivi historique des audits, plan d'action priorisé.
- **Interface Streamlit** : pilotage de l'audit et consultation des résultats via une interface web simple.

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Qlik Sense  │────▶│  Module A         │────▶│                  │
│ (Engine API)│     │  Extraction &     │     │  Module B        │
└─────────────┘     │  comparaison KPI  │────▶│  Analyse de      │
┌─────────────┐     │                   │     │  couverture &    │
│  Power BI   │────▶│                   │     │  écarts          │
│ (Analysis   │     └──────────────────┘     └────────┬─────────┘
│  Services)  │                                        │
└─────────────┘                                        ▼
                                              ┌──────────────────┐
                                              │  Orchestrateur    │
                                              │  + LLM (Ollama)   │
                                              │  → Rapports,      │
                                              │  suivi, plan       │
                                              │  d'action          │
                                              └──────────────────┘
```

## 🛠️ Stack technique

| Catégorie | Technologies |
|---|---|
| Langage | Python |
| Interface | Streamlit |
| Sources de données | Qlik Sense (Engine API), Power BI (Analysis Services local) |
| Analyse & modélisation | Pandas, DAX |
| IA / LLM | Ollama + Mistral (exécution locale) |
| Stockage | SQLite |
| Tests | Pytest (31 tests automatisés) |

## 🚀 Installation

### Prérequis

- Python 3.11+
- [Ollama](https://ollama.com) installé localement avec le modèle Mistral (`ollama pull mistral`)
- Accès à une instance Qlik Sense (Engine API) et à un modèle Power BI local (Analysis Services)

### Étapes

```bash
# 1. Cloner le repo
git clone https://github.com/motezjerbi/qlik-pbi-reconciliation-agent.git
cd qlik-pbi-reconciliation-agent

# 2. Créer et activer l'environnement virtuel
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Puis éditer .streamlit/secrets.toml avec vos identifiants Qlik / Power BI

# 5. Lancer l'application
streamlit run app.py
```

## 🧪 Tests

```bash
pytest
```

31 tests automatisés couvrent les modules d'extraction, de comparaison, d'analyse de couverture et de génération de rapports.

## 📁 Structure du projet

```
qlik-pbi-reconciliation-agent/
├── app.py                     # Point d'entrée Streamlit
├── src/
│   ├── module_a/               # Extraction & rapprochement des KPI
│   │   └── extractors/         # Clients Qlik Engine / PBI Analysis Services
│   ├── module_b/                # Analyse de couverture & écarts fonctionnels
│   ├── orchestrator/            # Orchestration, rapports, historique, alerting
│   └── llm/                     # Intégration Ollama / Mistral
├── tests/                       # Suite de tests Pytest
├── data/
│   └── samples/                 # Jeux de données de démonstration
└── assets/                      # Ressources graphiques
```

## 🗺️ Roadmap

- [ ] Support multi-espaces de travail Power BI
- [ ] Export des rapports en PDF
- [ ] Intégration CI/CD pour audits automatiques planifiés

## 📄 Licence

Projet personnel — usage libre à des fins d'apprentissage et de démonstration.

## 👤 Auteur

**Motez Jerbi**
[GitHub](https://github.com/motezjerbi)