# 🎣 Projeto end-to-end de Análise da balança comercial de pescado

![status](https://img.shields.io/badge/status-in%20development-yellow)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Docker](https://img.shields.io/badge/docker-29.3.1-blue.svg)
![DBT](https://img.shields.io/badge/dbt-1.9-orange.svg)

**Da ingestão ao dashboard:** esse projeto apresenta uma solução completa de um pipeline de dados utilizando ferramentas open source, partindo desde a ingestão de dados do comércio internacional de pescado da API COMEX STAT, até a elaboração de um dashboard no Power BI demonstrando as principais KPI's envonvidas no setor.

>O papel desse projeto é demonstrar o dia-a-dia de um Analitycs Engineer, utilizando ferramentas para tratar de ingestão, qualidade de dados, documentação, performance, e análise de dados.

## 🔎 Problema

Decisões estratégicas de negócio, seja no ambiente privado ou institucional, se não são, deveriam ser tomadas através de dados que sejam confiáveis. Porém, quando se trata de recursos pesqueiros, sejam eles advindos da pesca ou da aquicultura, a disponibilidades de dados e estatísticas é muito carente.

Pensando nisso, esse projeto constrói uma solução do início ao fim e demonstra, através de uma série de processos que vão desde a ingestão incremental dos dados, tratamento de registros e visualização, que através dos dados grandes decisões podem ser tomadas de maneira eficiente e com confiança.

## 🛠️ Stack Tecnológico

| Componente | Ferramenta | Função |
|:--|:--|:--|
| 🔄 Ingestão | **Python** | API request (Full/Incremental) |
| 🗄️ Data Warehouse | **PostgreSQL 15** | Armazenamento estruturado (OLAP) |
| 🔨 Transformação | **DBT 1.9** | ELT com testes e documentação automática |
| 🔀 Orquestração | **Apache Airflow 2.8** | DAGs, scheduling, retry |
| 📊 Visualização | **Power BI** | Dashboards e KPIs de negócio |
| 🐳 Infra | **Docker Compose** | Todos os serviços containerizados |