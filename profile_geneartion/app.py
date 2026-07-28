import streamlit as st
import os
import json
import pandas as pd

# --- CONFIGURAZIONE E CACHE ---
st.set_page_config(page_title="Dashboard Profili Utente", layout="wide")

cartella_profili = "Profili_Utenti_JSON"

@st.cache_data
def carica_tutti_i_nodi():
    tutti_i_dati = []
    lista_utenti = []
    
    if os.path.exists(cartella_profili):
        file_json = [f for f in os.listdir(cartella_profili) if f.endswith('.json')]
        for file in file_json:
            id_utente = file.replace('profilo_', '').replace('.json', '')
            lista_utenti.append(id_utente)
            
            with open(os.path.join(cartella_profili, file), 'r', encoding='utf-8') as f:
                dati = json.load(f)
                nodi = dati.get("nodi_interesse", [])
                for nodo in nodi:
                    data_intervallo = nodo.get("finestra_temporale", {}).get("valore_intervallo", "Sconosciuta")
                    interazioni = nodo.get("metriche_grezze_supporto", {}).get("interazioni_totali", 0)
                    
                    tutti_i_dati.append({
                        "ID Utente": id_utente,
                        "Categoria": nodo.get("categoria"),
                        "Interesse": nodo.get("valore"),
                        "Data (Mese/Anno)": data_intervallo,
                        "Interazioni Totali": interazioni,
                        "Intensità Relativa": nodo.get("intensita_interesse", 0)
                    })
    return pd.DataFrame(tutti_i_dati), lista_utenti

df_globale, lista_utenti = carica_tutti_i_nodi()

# --- INTERFACCIA PRINCIPALE ---
st.title("Dashboard Estrazione Profili Utente")
st.write("Esplora i singoli profili o effettua ricerche incrociate sull'intero database.")

tab1, tab2 = st.tabs(["👤 Esplora Singolo Utente", "🔍 Ricerca Avanzata Target"])

# ==========================================
# TAB 1: SINGOLO UTENTE
# ==========================================
with tab1:
    st.sidebar.header("Pannello di Controllo")
    dataset_scelto = st.sidebar.selectbox("Scegli Dataset", ["Netflix_Data_Export"])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Ricerca Utente")
    
    utente_selezionato = st.sidebar.selectbox(
        "Digita l'ID per cercare o selezionalo:", 
        options=lista_utenti,
        index=None,
        placeholder="Es: user_03292..."
    )

    if utente_selezionato:
        percorso_file = os.path.join(cartella_profili, f"profilo_{utente_selezionato}.json")
        with open(percorso_file, 'r', encoding='utf-8') as f:
            dati_profilo = json.load(f)
            
        st.subheader(f"Analisi Preferenze: {utente_selezionato}")
        nodi = dati_profilo.get("nodi_interesse", [])
        
        if nodi:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Tabella Interessi e Filtri**")
                df_pulito = df_globale[df_globale['ID Utente'] == utente_selezionato].drop(columns=['ID Utente'])
                
                sub_col1, sub_col2, sub_col3 = st.columns(3)
                
                categorie_presenti = ["Tutte"] + list(df_pulito['Categoria'].dropna().unique())
                filtro_cat_utente = sub_col1.selectbox("Filtra Categoria:", categorie_presenti, key="cat_utente")
                
                lista_date_utente = sorted(list(df_pulito['Data (Mese/Anno)'].dropna().unique()))
                if len(lista_date_utente) > 1:
                    data_inizio_u, data_fine_u = sub_col2.select_slider(
                        "Filtra per Data:",
                        options=lista_date_utente,
                        value=(lista_date_utente[0], lista_date_utente[-1]),
                        key="date_utente"
                    )
                else:
                    data_inizio_u = data_fine_u = lista_date_utente[0] if lista_date_utente else None
                
                ordina_per = sub_col3.selectbox("Ordina per:", ["Intensità", "Interazioni", "Data"], key="ord_utente")
                
                if filtro_cat_utente != "Tutte":
                    df_pulito = df_pulito[df_pulito['Categoria'] == filtro_cat_utente]
                    
                if data_inizio_u and data_fine_u:
                    df_pulito = df_pulito[(df_pulito['Data (Mese/Anno)'] >= data_inizio_u) & (df_pulito['Data (Mese/Anno)'] <= data_fine_u)]
                
                if ordina_per == "Intensità":
                    df_pulito = df_pulito.sort_values(by=['Intensità Relativa', 'Data (Mese/Anno)'], ascending=[False, False])
                elif ordina_per == "Interazioni":
                    df_pulito = df_pulito.sort_values(by=['Interazioni Totali', 'Data (Mese/Anno)'], ascending=[False, False])
                else:
                    df_pulito = df_pulito.sort_values(by=['Data (Mese/Anno)', 'Interazioni Totali'], ascending=[False, False])
                
                st.dataframe(df_pulito, use_container_width=True, hide_index=True)
                
                st.markdown("**Grafico Top Interessi (nel periodo selezionato)**")
                # Raggruppiamo gli interessi uguali sparsi nei vari mesi e sommiamo i volumi
                if not df_pulito.empty:
                    df_grafico = df_pulito.groupby('Interesse', as_index=False)['Interazioni Totali'].sum()
                    # Ora ordiniamo e prendiamo i veri 10 interessi principali
                    df_grafico = df_grafico.sort_values(by='Interazioni Totali', ascending=False).head(10)
                    st.bar_chart(data=df_grafico, x='Interesse', y='Interazioni Totali')
                else:
                    st.info("Nessun dato disponibile per il grafico con i filtri attuali.")
            
            with col2:
                st.markdown("**Struttura JSON Originale**")
                st.json(dati_profilo)
                
            st.markdown("---")
            json_string = json.dumps(dati_profilo, indent=4, ensure_ascii=False)
            st.download_button(label="Scarica Profilo JSON", data=json_string, file_name=f"profilo_{utente_selezionato}.json", mime="application/json")
        else:
            st.warning("Questo utente non ha nodi di interesse registrati.")
            
# ==========================================
# TAB 2: RICERCA AVANZATA MIGLIORATA E EXPORT CSV
# ==========================================
with tab2:
    st.subheader("Filtra utenti per Categoria, Range Temporale e Volumi")
    
    if df_globale.empty:
        st.error("Nessun dato trovato.")
    else:
        riga1_col1, riga1_col2 = st.columns(2)
        riga2_col1, riga2_col2 = st.columns(2)
        
        lista_categorie = df_globale['Categoria'].dropna().unique()
        categoria_scelta = riga1_col1.selectbox("Scegli Categoria:", ["Tutte"] + list(lista_categorie))
        
        if categoria_scelta != "Tutte":
            lista_interessi = df_globale[df_globale['Categoria'] == categoria_scelta]['Interesse'].dropna().unique()
        else:
            lista_interessi = df_globale['Interesse'].dropna().unique()
        interesse_scelto = riga1_col2.selectbox("Scegli Specifico Interesse:", ["Tutti"] + list(lista_interessi))
        
        lista_date = sorted(list(df_globale['Data (Mese/Anno)'].dropna().unique()))
        if len(lista_date) > 1:
            data_inizio, data_fine = riga2_col1.select_slider(
                "Seleziona Range Temporale:",
                options=lista_date,
                value=(lista_date[0], lista_date[-1]) 
            )
        else:
            data_inizio = data_fine = lista_date[0] if lista_date else None
        
        df_risultato = df_globale.copy()
        
        # 1. Filtri di base (Categoria, Interesse, Date)
        if categoria_scelta != "Tutte":
            df_risultato = df_risultato[df_risultato['Categoria'] == categoria_scelta]
            
        if interesse_scelto != "Tutti":
            df_risultato = df_risultato[df_risultato['Interesse'] == interesse_scelto]
            
        if data_inizio and data_fine:
            df_risultato = df_risultato[(df_risultato['Data (Mese/Anno)'] >= data_inizio) & (df_risultato['Data (Mese/Anno)'] <= data_fine)]
            
        # --- RAGGRUPPAMENTO (GROUPBY) ---
        if not df_risultato.empty:
            df_risultato = df_risultato.groupby(['ID Utente', 'Categoria', 'Interesse']).agg(
                Interazioni_Totali=('Interazioni Totali', 'sum'),
                Intensita_Media=('Intensità Relativa', 'mean')
            ).reset_index()
            
            df_risultato = df_risultato.rename(columns={
                'Interazioni_Totali': 'Interazioni Totali',
                'Intensita_Media': 'Intensità (Media del periodo)'
            })
            
            if data_inizio == data_fine:
                df_risultato['Periodo'] = data_inizio
            else:
                df_risultato['Periodo'] = f"{data_inizio} ➔ {data_fine}"

        # 2. Filtro Interazioni Minime
        max_interazioni = int(df_risultato['Interazioni Totali'].max()) if not df_risultato.empty else 100
        interazioni_minime = riga2_col2.number_input("Interazioni minime (nel periodo):", min_value=1, max_value=max_interazioni if max_interazioni > 0 else 1, value=1)
        
        df_risultato = df_risultato[df_risultato['Interazioni Totali'] >= interazioni_minime]
        
        # 3. Ordinamento automatico (decrescente per Interazioni)
        df_risultato = df_risultato.sort_values(by=['Interazioni Totali', 'Intensità (Media del periodo)'], ascending=[False, False]).reset_index(drop=True)
        
        st.markdown(f"**Trovati {len(df_risultato)} risultati in questo intervallo di tempo.**")
        st.dataframe(df_risultato, use_container_width=True, hide_index=True)
        
        if not df_risultato.empty:
            csv_export = df_risultato.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica i risultati della ricerca (Formato CSV)",
                data=csv_export,
                file_name="risultati_ricerca_target.csv",
                mime="text/csv"
            )
