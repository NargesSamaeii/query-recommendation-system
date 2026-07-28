import os
import json
import pandas as pd

# =====================================================================
# 1. FUNZIONE UNIVERSALE DI MODELLAZIONE
# =====================================================================
def aggiungi_nodi_al_profilo(profilo, df, dominio, categoria_nome, colonna_valore, colonna_data, colonna_conteggio):
    totali_periodo = df.groupby(colonna_data)[colonna_conteggio].sum().reset_index(name='Totale_Periodo')
    df_unito = pd.merge(df, totali_periodo, on=colonna_data)
    df_unito['Intensita'] = (df_unito[colonna_conteggio] / df_unito['Totale_Periodo']).round(2)

    for index, row in df_unito.iterrows():
        nodo = {
            "dominio": dominio,
            "categoria": categoria_nome,
            "valore": row[colonna_valore],
            "intensita_interesse": row['Intensita'],
            "finestra_temporale": {
                "tipo_intervallo": "Mensile",
                "valore_intervallo": row[colonna_data]
            },
            "metriche_grezze_supporto": {
                "interazioni_totali": int(row[colonna_conteggio])
            }
        }
        profilo["nodi_interesse"].append(nodo)
    return profilo

# =====================================================================
# 2. AVVIO ESPORTAZIONE MASSIVA PROFILI JSON
# =====================================================================
def main():
    print("\n--- AVVIO ESPORTAZIONE MASSIVA PROFILI JSON ---")
    
    # Definiamo le cartelle locali del progetto
    cartella_dati = "data"
    cartella_export = "Profili_Utenti_JSON"
    
    file_history = os.path.join(cartella_dati, "watch_history.csv")
    file_movies = os.path.join(cartella_dati, "movies.csv")
    
    # Controllo se l'utente ha inserito i file nella cartella giusta
    if not os.path.exists(file_history) or not os.path.exists(file_movies):
        print(f"\n[ERRORE] File non trovati!")
        print(f"Assicurati di creare una cartella chiamata '{cartella_dati}' e di inserire i file:")
        print(f"- {file_history}")
        print(f"- {file_movies}")
        return

    print("Caricamento dei dataset locali in corso...")
    df_history = pd.read_csv(file_history)
    df_movies = pd.read_csv(file_movies)

    print("Fase di Preprocessing e Pulizia Dati...")
    watch_history_pulito = df_history.dropna(subset=['user_id', 'movie_id']).copy()
    
    movies_pulito = df_movies.drop_duplicates(subset=['movie_id']).copy()
    movies_pulito['genre_primary'] = movies_pulito['genre_primary'].fillna("Unknown")
    movies_pulito['country_of_origin'] = movies_pulito['country_of_origin'].fillna("Unknown")
    movies_pulito['content_type'] = movies_pulito['content_type'].fillna("Unknown")

    print("Preparazione dei dati globali ed elaborazione temporale...")
    visioni_globali = pd.merge(watch_history_pulito, movies_pulito, on='movie_id', how='left')
    visioni_globali['Data_Ora'] = pd.to_datetime(visioni_globali['watch_date'])
    visioni_globali['Mese_Anno'] = visioni_globali['Data_Ora'].dt.to_period('M').astype(str)

    if not os.path.exists(cartella_export):
        os.makedirs(cartella_export)

    lista_utenti = visioni_globali['user_id'].unique()
    totale_utenti = len(lista_utenti)

    print(f"Trovati {totale_utenti} utenti unici. Inizio generazione dei profili...\n")
    conteggio_salvati = 0

    for utente_corrente in lista_utenti:
        dati_utente = visioni_globali[visioni_globali['user_id'] == utente_corrente]

        evoluzione_generi = dati_utente.groupby(['Mese_Anno', 'genre_primary']).size().reset_index(name='Conteggio')
        evoluzione_paesi = dati_utente.groupby(['Mese_Anno', 'country_of_origin']).size().reset_index(name='Conteggio')
        evoluzione_formato = dati_utente.groupby(['Mese_Anno', 'content_type']).size().reset_index(name='Conteggio')

        profilo_corrente = {
            "id_profilo_univoco": str(utente_corrente),
            "piattaforma_origine": "Netflix_Data_Export",
            "nodi_interesse": []
        }

        if not evoluzione_generi.empty:
            profilo_corrente = aggiungi_nodi_al_profilo(profilo_corrente, evoluzione_generi, "Intrattenimento Video", "Genere", "genre_primary", "Mese_Anno", "Conteggio")
        if not evoluzione_paesi.empty:
            profilo_corrente = aggiungi_nodi_al_profilo(profilo_corrente, evoluzione_paesi, "Intrattenimento Video", "Paese di Origine", "country_of_origin", "Mese_Anno", "Conteggio")
        if not evoluzione_formato.empty:
            profilo_corrente = aggiungi_nodi_al_profilo(profilo_corrente, evoluzione_formato, "Intrattenimento Video", "Formato Contenuto", "content_type", "Mese_Anno", "Conteggio")

        json_formattato = json.dumps(profilo_corrente, indent=4, ensure_ascii=False)
        nome_file = os.path.join(cartella_export, f"profilo_{utente_corrente}.json")

        with open(nome_file, 'w', encoding='utf-8') as f:
            f.write(json_formattato)

        conteggio_salvati += 1
        if conteggio_salvati % 500 == 0:
            print(f"Elaborati {conteggio_salvati} / {totale_utenti} utenti...")

    print(f"\n[!] OPERAZIONE COMPLETATA! {conteggio_salvati} profili salvati in '{cartella_export}'.")

if __name__ == "__main__":
    main()
