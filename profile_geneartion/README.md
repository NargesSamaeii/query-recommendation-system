# Analisi e Profilazione Utenti: Dashboard Interattiva

Questo repository contiene l'applicativo sviluppato per l'estrazione, l'elaborazione e la visualizzazione di pattern di interesse a partire da dataset di interazioni. Il progetto ha l'obiettivo di generalizzare la descrizione degli interessi degli utenti, proponendo un formato architetturale standard e agnostico rispetto al dominio.

## Obiettivo del Progetto e Scalabilità
L'obiettivo è trasformare i log storici delle attività in "profili di interesse" strutturati in formato JSON. Il sistema calcola l'intensità dell'interesse normalizzata per categoria, permettendo di individuare sia le preferenze del singolo utente (Analisi Micro) sia di estrarre molteplici utenti in base a specifici target (Analisi Macro).

**Nota sull'Architettura Generale:**
In questo progetto dimostrativo, il dataset utilizzato è il "Netflix 2025 User Behavior Dataset" e lo script di preprocessing (`generazione_profili.py`) è stato specificamente adattato ai suoi tracciati. Tuttavia, l'obiettivo primario del lavoro è fornire un'architettura generale in grado di analizzare e descrivere qualsiasi profilo utente. Pertanto, in scenari di utilizzo futuri, la fase iniziale di data cleaning e preprocessing dovrà essere riadattata alle specifiche del nuovo dataset, ma la funzione core di modellazione dei dati (la funzione `aggiungi_nodi_al_profilo`) è progettata per essere universale.

## Struttura del Repository

* **`generazione_profili.py`**: Uno script Python basato su Pandas che si occupa del Data Preprocessing. Raggruppa le interazioni, calcola le metriche di intensità e genera massivamente i file JSON standardizzati a nodi.
* **`app.py`**: Il front-end di analisi. Una dashboard sviluppata in Streamlit che indicizza i file JSON in memoria e offre due strumenti:
  1. **Esplorazione Singolo Utente**: Visualizzazione delle metriche storiche e grafici temporali degli interessi principali.
  2. **Ricerca Avanzata Target**: Motore di ricerca globale con filtri per categoria, interesse, volume di interazioni e range temporale, con algoritmi di raggruppamento per l'estrazione di più utenti in formato CSV.

## Tecnologie Utilizzate
* **Linguaggio**: Python
* **Elaborazione Dati**: Pandas
* **Data Visualization & UI**: Streamlit
* **Gestione Dati**: JSON, CSV

## Dataset e Riproducibilità
Il progetto utilizza il dataset pubblico "Netflix 2025 User Behavior Dataset" disponibile su Kaggle al link "https://www.kaggle.com/datasets/sayeeduddin/netflix-2025user-behavior-dataset-210k-records"

**Istruzioni per il posizionamento dei dati:**
1. Scaricare i file originali da Kaggle.
2. All'interno della directory principale del progetto, creare una cartella denominata `data/`.
3. Inserire i file estratti in particolare `watch_history.csv` e `movies.csv` all'interno della cartella `data/`.
4. Eseguire lo script `generazione_profili.py`. Il codice si occupa in modo autonomo di effettuare il preprocessing necessario per questo specifico dataset (rimozione dei valori nulli, deduplicazione del catalogo, feature engineering temporale e join relazionali) prima di richiamare la funzione universale e generare la cartella finale con i profili JSON.

## Come avviare la Dashboard
1. Assicurarsi di aver attivato il proprio ambiente virtuale.
2. Installare le dipendenze necessarie (Streamlit, Pandas).
3. Lanciare l'applicazione da terminale con il comando:
   `streamlit run app.py`
