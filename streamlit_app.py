import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os
import ast # Pour parser la chaîne de liste de tuples en toute sécurité
import traceback # Pour afficher les erreurs de parsing détaillées
import json
import plotly.graph_objects as go
import datetime


#Json files importation
with open("data/irr_event_coordinates.json", mode="r", encoding="utf-8") as irr_event_coordinates:
    irr_event_coordinates = json.load(irr_event_coordinates)
with open("data/ped_density_per_segment.json", mode="r", encoding="utf-8") as ped_density_per_segment:
    ped_density_per_segment = json.load(ped_density_per_segment)
with open("data/ped_speed_per_segment.json", mode="r", encoding="utf-8") as ped_speed_per_segment:
    ped_speed_per_segment = json.load(ped_speed_per_segment)
with open("data/slope_per_segment.json", mode="r", encoding="utf-8") as slope_per_segment:
    slope_per_segment = json.load(slope_per_segment)
with open("data/width_per_segment.json", mode="r", encoding="utf-8") as width_per_segment:
    width_per_segment = json.load(width_per_segment)

# --- Setting up page configuration ---
st.set_page_config(
    page_title="Walkability Analysis Dashboard",
    page_icon="🚶",
    layout="wide"
)

# --- Fonction de Parsing et Conversion des Coordonnées ---
def parse_and_convert_coordinates(coord_str):
    """
    Parse une chaîne représentant une liste de tuples (lon, lat)
    et la convertit en une liste de tuples (lat, lon).
    Retourne une liste vide en cas d'erreur.
    """
    if not isinstance(coord_str, str) or not coord_str.strip():
        return []
    try:
        # 1. Parser la chaîne en liste de tuples
        # Utilise ast.literal_eval pour la sécurité (évite l'exécution de code arbitraire)
        lon_lat_list = ast.literal_eval(coord_str)

        # 2. Vérifier si le résultat est une liste
        if not isinstance(lon_lat_list, list):
            st.warning(f"Format de coordonnées non reconnu (pas une liste): {coord_str[:100]}...")
            return []

        # 3. Convertir [(lon, lat), ...] en [(lat, lon), ...] et en float
        lat_lon_list = []
        for item in lon_lat_list:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    # Important : Conversion lon, lat -> lat, lon
                    lat = float(item[1])
                    lon = float(item[0])
                    lat_lon_list.append((lat, lon))
                except (ValueError, TypeError):
                    st.warning(f"Coordonnées non numériques dans le tuple: {item} dans {coord_str[:100]}...")
                    # Décider si on ignore juste ce point ou tout le segment
                    continue # Ignore ce point et passe au suivant
            else:
                 st.warning(f"Élément non conforme (pas un tuple/liste de 2) trouvé: {item} dans {coord_str[:100]}...")
                 # Décider si on ignore juste ce point ou tout le segment
                 continue # Ignore ce point

        return lat_lon_list

    except (SyntaxError, ValueError, TypeError) as e:
        st.error(f"Erreur de parsing de la chaîne de coordonnées: {coord_str[:100]}...")
        # Afficher l'erreur détaillée dans les logs ou en mode debug
        print(f"Erreur de parsing pour: {coord_str}")
        traceback.print_exc()
        return [] # Retourne une liste vide en cas d'échec

# --- Chargement des Données ---
@st.cache_data
def load_data(path_data_path, unevenness_irregularity_per_segment_path):
    # Charger les données du chemin (nouveau format: id, "[(lon, lat),...]")
    processed_path_df = pd.DataFrame(columns=['segment_id', 'locations']) # Init df vide
    try:
        # Lire en spécifiant les noms de colonnes attendus
        path_df = pd.read_csv(path_data_path, names=['segment_id', 'coordinates_str'], header=None) # Lire sans en-tête, nommer les colonnes

        # S'assurer que segment_id est une chaîne
        path_df['segment_id'] = path_df['segment_id'].astype(str)
        # Remplacer les NaN potentiels dans coordinates_str par des chaînes vides
        path_df['coordinates_str'] = path_df['coordinates_str'].fillna('')


        #st.write("Parsing segments coordinates...") # User Feedback

        # Appliquer la fonction de parsing
        # Note: parse_and_convert_coordinates retourne [] en cas d'erreur
        path_df['locations'] = path_df['coordinates_str'].apply(parse_and_convert_coordinates)

        # --- Section de rapport d'erreur améliorée ---
        # Identifier les lignes où le parsing a échoué (locations est une liste vide)
        # Exclure les lignes où la chaîne originale était déjà vide/NaN
        failed_parsing_mask = (path_df['locations'].apply(len) == 0) & (path_df['coordinates_str'].str.strip() != '')
        failed_parsing_df = path_df[failed_parsing_mask]

        if not failed_parsing_df.empty:
            st.error("Erreur de parsing des coordonnées pour les segments suivants :")
            # Afficher max 10 erreurs pour ne pas surcharger
            for index, row in failed_parsing_df.head(10).iterrows():
                st.error(f"  - Segment ID: {row['segment_id']}")
                # Afficher un extrait de la chaîne problématique
                st.code(f"    Données (extrait): {row['coordinates_str'][:200]}...")
            if len(failed_parsing_df) > 10:
                st.error(f"  ... et {len(failed_parsing_df) - 10} autres segments.")
        # --- Fin Section de rapport d'erreur ---

        # Filtrer les segments qui n'ont pas pu être parsés ou qui sont vides
        original_rows = len(path_df)
        processed_path_df = path_df[path_df['locations'].apply(len) > 0][['segment_id', 'locations']].copy() # Garde seulement les succès

        num_failed = len(failed_parsing_df)
        num_empty_original = original_rows - len(path_df[path_df['coordinates_str'].str.strip() != ''])
        num_successfully_parsed = len(processed_path_df)

        #st.write(f"Parsing finished: {num_successfully_parsed} segments loaded successfully.") User Feedback
        if num_failed > 0:
             st.warning(f"{num_failed} segments ignorés en raison d'erreurs de parsing.")


    except FileNotFoundError:
        st.error(f"Erreur: Le fichier de chemin {path_data_path} n'a pas été trouvé.")
        # processed_path_df reste le df vide initialisé
    except Exception as e:
        st.error(f"Erreur lors du chargement ou du traitement de {path_data_path}: {e}")
        st.error(traceback.format_exc()) # Affiche l'erreur complète pour le débogage
        # processed_path_df reste le df vide initialisé

    try:
        unevenness_irregularity_per_segment_df = pd.read_csv(unevenness_irregularity_per_segment_path)
    except FileNotFoundError:
        unevenness_irregularity_per_segment_df = pd.DataFrame(columns=['segment_id', 'average_unevenness_index', 'average_irregularity_index'])
    return processed_path_df, unevenness_irregularity_per_segment_df

  
def process_pedestrian_data_per_quarter_hour(file_path):
    """
    Charge les données de détection de piétons, les agrège par quart d'heure
    en comptant les piétons uniques.

    Args:
        file_path (str): Chemin vers le fichier CSV. Le CSV doit avoir
                         les colonnes 'timestamp' et 'pedestrian_ids'.
                         'pedestrian_ids' doit être une chaîne représentant une liste
                         d'IDs, ex: "[101, 102, 103]".

    Returns:
        pandas.DataFrame: Un DataFrame avec les colonnes 'timestamp_quarter'
                          (début du quart d'heure) et 'unique_pedestrian_count'.
                          Retourne un DataFrame vide en cas d'erreur.
    """
    try:
        df = pd.read_csv(file_path, sep=';')

        # Vérification des colonnes nécessaires
        if 'time_rounded' not in df.columns or 'persons' not in df.columns:
            # Dans Streamlit, on utiliserait st.error(), hors Streamlit, print() ou lever une exception
            print(f"Erreur: Le fichier CSV '{file_path}' doit contenir les colonnes 'time_rounded' et 'persons'.")
            return pd.DataFrame(columns=['timestamp_quarter', 'unique_pedestrian_count'])

        # 1. Convertir la colonne 'timestamp' en objets datetime
        df['time_rounded'] = pd.to_datetime(df['time_rounded'], format="%H:%M")
        df['time_rounded'] = df['time_rounded'].dt.floor('15min').dt.time
        # 2. Parser la colonne 'pedestrian_ids' (chaîne) en listes Python d'IDs
        def parse_id_list_from_string(id_list_str):
            if pd.isna(id_list_str) or not isinstance(id_list_str, str) or not id_list_str.strip():
                return [] # Retourne une liste vide si la chaîne est vide, NaN ou pas une chaîne
            try:
                # ast.literal_eval est plus sûr que eval()
                ids = ast.literal_eval(id_list_str)
                # S'assurer que c'est une liste et que les IDs sont (par exemple) des entiers
                if isinstance(ids, list):
                    return [int(pid) for pid in ids] # ou str(pid) si vos IDs sont des chaînes
                return []
            except (ValueError, SyntaxError, TypeError):
                # Gérer les chaînes mal formées
                return []
        
        df['parsed_ids'] = df['persons'].apply(parse_id_list_from_string)

        # 3. Mettre 'timestamp' comme index pour la fonction resample
        df = df.set_index('time_rounded')

        # 4. & 5. Regrouper par quart d'heure ('15T') et agréger
        # Définir la fonction d'agrégation pour compter les IDs uniques 
        def aggregate_unique_ids(series_of_lists_of_ids):
            # series_of_lists_of_ids contient toutes les listes 'parsed_ids' pour un quart d'heure donné
            if series_of_lists_of_ids.empty:
                return 0
             
            combined_list = []
            for id_list in series_of_lists_of_ids:
                combined_list.extend(id_list) # Concaténer toutes les listes
            
            if not combined_list:
                return 0
            
            #unique_ids = set(combined_list) # Enlever les doublons
            return len(combined_list)         # Compter les uniques
        
        # 3. Regrouper par la colonne de quart d'heure fournie
        quarter_hour_summary = df.groupby(['segment_id','time_rounded'])['parsed_ids'].apply(aggregate_unique_ids)

        # Renommer la série résultante et la transformer en DataFrame
        quarter_hour_summary_df = quarter_hour_summary.rename('unique_pedestrian_count').reset_index()
        quarter_hour_summary_df.rename(columns={'time_rounded': 'timestamp_quarter'}, inplace=True)

        # S'assurer que les résultats sont triés par temps pour le graphique
        quarter_hour_summary_df = quarter_hour_summary_df.sort_values(by=['segment_id','timestamp_quarter'])
        return quarter_hour_summary_df

    except FileNotFoundError:
        print(f"Erreur: Fichier non trouvé à l'emplacement '{file_path}'.")
        return pd.DataFrame(columns=['timestamp_quarter', 'unique_pedestrian_count'])
    except Exception as e:
        print(f"Une erreur est survenue lors du traitement du fichier: {e}")
        # Pour un débogage plus détaillé dans un environnement de développement :
        # import traceback
        # traceback.print_exc()
        return pd.DataFrame(columns=['timestamp_quarter', 'unique_pedestrian_count'])


# --- Chemins vers vos fichiers CSV ---
PATH_CSV_PATH = 'data/segments.csv' # Votre fichier avec id, "[(lon, lat),...]"
UNEVENNESS_IRREGULARITY_PER_SEGMENT_PATH = 'data/unevenness_irregularity_per_segment.csv'
CHEMIN_FICHIER_PASSANTS = 'data/ExperimentData_quentin.csv'

path_df, unevenness_irregularity_per_segment_df = load_data(PATH_CSV_PATH, UNEVENNESS_IRREGULARITY_PER_SEGMENT_PATH)
Pedestrian_df = process_pedestrian_data_per_quarter_hour(CHEMIN_FICHIER_PASSANTS)

# --- Interface Utilisateur ---
st.title("📊 Sidewalk Mobility Data Dashboard")
st.markdown("Data visualization of sidewalk usage and caracteristics")

if path_df.empty:
    st.warning("Impossible d'afficher la carte car les données du chemin n'ont pas pu être chargées ou parsées.")
    st.stop()

# --- Sélection du Segment ---
# Les IDs sont maintenant bien des strings grâce à la correction dans load_data
unique_ids_str = path_df['segment_id'].unique().tolist()

# Définir une fonction clé pour trier numériquement (gère entiers et potentiellement flottants)
def robust_num_key(item_str):
    try:
        # Essayer de convertir en flottant pour la comparaison (gère entiers et décimaux)
        return float(item_str)
    except ValueError:
        # Si ce n'est pas un nombre, le placer à la fin lors du tri
        # On retourne l'infini positif pour qu'il soit classé après tous les nombres.
        # Vous pourriez aussi retourner une valeur spécifique ou lever une erreur si
        # tous les IDs sont censés être numériques.
        return float('inf')

# Trier les IDs (qui sont des strings) en utilisant la clé numérique
sorted_ids = sorted(unique_ids_str, key=robust_num_key)

#création des deux onglets, le premier étant context et le deuxième celu qui va générer les données
tab1, tab2 = st.tabs(["# Data", "# Project Background"])



#Onglets d'affichage des données
with tab1 :

    # --- Affichage Principal (Carte et Données) ---
    col_map, col_data = st.columns([1,1.3], border=True)

    with col_map:
        
        # Créer les options pour le selectbox
        segment_options = ["Overview"] + sorted_ids # Utilise la liste triée numériquement

        selected_segment_id = st.selectbox("Select a segment to display infos :", options=segment_options)
        
        # --- **NOUVEAU : Préparation de la Palette et Mapping de Couleurs** ---
        # Utiliser les IDs triés pour une assignation stable si l'ordre importe peu,
        # sinon utiliser unique_ids_str directement si l'ordre original d'apparition doit dicter la couleur.
        # Utilisons sorted_ids pour la cohérence avec le selectbox.
        ids_for_colors = sorted_ids

        # Définir une palette de couleurs (ajoutez/modifiez selon vos goûts)
        # Couleurs de https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=10
        color_palette = ['#a83500','#1f78b4','#50b800','#0a6100','#7d4c2c','#e31a1c','#129778','#ff7f00','#781297','#6a3d9a']
        num_colors = len(color_palette)

        # Créer un dictionnaire mappant chaque segment_id à une couleur
        segment_color_map = {}
        for i, seg_id in enumerate(ids_for_colors):
            # Assigner les couleurs de manière cyclique si plus d'IDs que de couleurs
            color_index = i % num_colors
            segment_color_map[seg_id] = color_palette[color_index]
        # --- FIN NOUVEAU ---

        test = st.pills("test", "Display segments number", label_visibility="collapsed")

        st.subheader("🗺️ Studied Sidewalk Network")

        map_center = [59.346639,18.072167]

        m = folium.Map(location=map_center, zoom_start=16) # Centre/zoom par défaut

        # Afficher tous les segments sur la carte
        if not path_df.empty:
            # Itérer sur les lignes du DataFrame traité
            for index, segment_row in path_df.iterrows():
                segment_id = segment_row['segment_id']
                locations = segment_row['locations'] # Récupère la liste de (lat, lon)

                if len(locations) >= 2: # Besoin d'au moins 2 points pour une ligne
                    line_color = "#FF0000" if segment_id == selected_segment_id else "#007bff"
                    if selected_segment_id == "Overview" : 
                        line_color = segment_color_map.get(segment_id, '#808080') # Gris si ID non trouvé
                    line_weight = 10 if segment_id == selected_segment_id else 6
                    if test == "Display segments number":
                        folium.PolyLine(
                            locations=locations, # Utilise directement la liste de (lat, lon)
                            color=line_color,
                            weight=line_weight,
                            opacity=0.8,
                            # Remplacer le tooltip simple par un Tooltip permanent
                            tooltip=folium.Tooltip(
                                f"{segment_id}", # Affiche juste l'ID
                                permanent=True,   # Rend le tooltip toujours visible
                                direction='center', # Essaye de le centrer (autres options: 'auto', 'top', 'bottom', 'left', 'right')
                                sticky=False,     # Empêche le tooltip de suivre la souris
                                opacity=0.7,      # Un peu transparent pour ne pas masquer la ligne
                                # Optionnel: classe CSS pour styler plus tard
                                # className='folium-permanent-tooltip'
                            )
                        ).add_to(m)
                    else : 
                        folium.PolyLine(
                            locations=locations, # Utilise directement la liste de (lat, lon)
                            color=line_color,
                            weight=line_weight,
                            opacity=0.8,
                            tooltip=f"Segment ID: {segment_id}"
                        ).add_to(m)
                        
                elif len(locations) == 1:
                    folium.Marker(
                        location=locations[0],
                        tooltip=f"Segment ID: {segment_id} (point unique)",
                        icon=folium.Icon(color='gray', icon='info-sign')
                    ).add_to(m)

        # Afficher la carte
        map_data = st_folium(m, width='100%', height=600)

    with col_data:

        st.subheader("🔍 Segment's details")

        if selected_segment_id == "Overview":

            st.info("Select a segment in the drop-down menu on the left to display details.")

            
            tab_unirreg, tab_abslop, tab_pedestrian = st.tabs(["Unvenness and irregularity indices","Absolute slope","Pedestrian data"])
            
            with tab_unirreg:

                #col_graph, col_details = st.columns([1, 0.5], border=True)
                #with col_graph:
                    st.subheader("Indices of unevenness and irregularity across sidewalks (excluding crossings)")

                    # --- Création de la Figure avec Deux Axes Y ---
                    fig_combined = go.Figure()
                    # 1. Ajouter la trace pour l'Irrégularité (Axe Y Primaire - Gauche)
                    fig_combined.add_trace(go.Scatter(
                        x=unevenness_irregularity_per_segment_df['segment_id'],
                        y=unevenness_irregularity_per_segment_df['average_unevenness_index'],
                        name='Unevenness', # Nom dans la légende
                        yaxis='y1',         # Associer à l'axe y1 (par défaut)
                        line=dict(color='royalblue') # Couleur spécifique
                    ))

                    # 2. Ajouter la trace pour la Largeur (Axe Y Secondaire - Droite)
                    fig_combined.add_trace(go.Scatter(
                        x=unevenness_irregularity_per_segment_df['segment_id'],
                        y=unevenness_irregularity_per_segment_df['average_irregularity_index'],
                        name='irregularity', # Nom dans la légende
                        yaxis='y2',        # Important: Associer à l'axe y2
                        line=dict(color='darkorange') # Couleur spécifique
                    ))

                    # 3. Configurer le Layout (Titres, Axes, Plage dynamique)
                    fig_combined.update_layout(
                        xaxis_title="segment id",
                        # Configuration Axe Y Primaire (Gauche) pour l'Irrégularité
                        yaxis=dict(
                            title="unevenness",
                            
                            tickfont=dict(color="royalblue"),
                            side='left', # Positionner à gauche
                            # Vous pourriez aussi rendre cet axe ajustable avec des widgets
                            range=[0, 1],
                            showgrid=False
                        ),
                        # Configuration Axe Y Secondaire (Droite) pour la Largeur
                        yaxis2=dict(
                            title="irregularity",
                            tickfont=dict(color="darkorange"),
                            side='right',       # Positionner à droite
                            overlaying="y",    # Superposer à l'axe Y principal (partage l'axe X)
                            # *** Appliquer la plage définie par le widget ***
                        ),
                        legend=dict(x=0.1, y=1.1, orientation="h"), # Position de la légende
                        margin=dict(l=50, r=50, t=80, b=50) # Marges
                    )

                    # Afficher le graphique combiné
                    st.plotly_chart(fig_combined, use_container_width=True)
                
                #with col_details:
                    st.subheader("Graph explanation")
                    st.text("The graph illustrates the indices of unevenness and irregularity across nine sidewalk segments, with the irregularity events marked as red points. The unevenness index, which ranges from 0 to 1, remains relatively consistent across most segments. Segment 1 shows the highest unevenness, primarily due to the presence of broken and uneven bricks.")


            with tab_abslop:

                #col_graph, col_details = st.columns([1, 0.5], border=True)

                #with col_graph:

                    st.subheader("Absolute slope across segments")
                    Graph_color="royalblue"
                    fig_abslop = px.line(slope_per_segment, x='segment id', y='absolute slope', labels={'segment id': 'segment id', 'absolute slope': 'absolute slope'})
                    fig_abslop.update_traces(line_color=Graph_color)
                    fig_abslop.update_layout(
                        xaxis=dict(
                        title="Segment id",
                        tickfont=dict(color=Graph_color),
                        tickvals= [i for i in range (11)],
                        range=[0, 10]
                    ),
                    
                    yaxis=dict(
                        title="Absolute slope",
                        tickfont=dict(color=Graph_color),
                        side='left', # Positionner à gauche
                        # Vous pourriez aussi rendre cet axe ajustable avec des widgets
                        range=[0, 0.07]
                    )
                    )
                    st.plotly_chart(fig_abslop, use_container_width=True)

                #with col_details:
                    st.subheader("Graph explanation")
                    st.text("This graph describe the absolute slope values across the sidewalks. It represents the steepness of each segment regardless of direction. The highest absolute slope is observed at Segment 7. Segment 1 and 2 exhibit the lowest slope values. This measurement can well reflect the varying elevation characteristics of different sidewalks, which is important for evaluating walkability or planning sidewalk robot navigation.")
            
            with tab_pedestrian:
                fig_passants = go.Figure()
                    # Ajouter la trace principale des barres (toutes les données de la journée)
                pedestrian_overview = Pedestrian_df.groupby('timestamp_quarter')['unique_pedestrian_count'].sum()
                pedestrian_overview = pedestrian_overview.rename('total_pedestrian').reset_index()
                #st.dataframe(pedestrian_overview)
                fig_passants.add_trace(go.Bar(
                    x=pedestrian_overview['timestamp_quarter'],
                    y=pedestrian_overview['total_pedestrian'],
                    name='Number of pedestrian',
                    marker_color='rgb(26, 118, 255)' # Couleur bleue pour les barres
                    ))
                fig_passants.update_layout(
                        title_text="Pedestrians count along the day",
                        xaxis_title="Time of day",
                        yaxis_title="Number of pedestrian detected",
                        bargap=0.2, # Espace entre les barres
                        # Optionnel: forcer l'affichage de tous les timestamps sur l'axe X si besoin
                        # xaxis=dict(type='category') # Peut aider si les timestamps ne sont pas réguliers
                    )
                st.plotly_chart(fig_passants, use_container_width=True)

        # Le reste de la logique pour afficher les détails (graphiques, etc.)
        # reste basé sur sensor_df et selected_segment_id.
        # Il faut s'assurer que le fichier sensor_data.csv existe et
        # contient une colonne 'segment_id' qui correspond aux IDs dans segments.csv

        else :
            
            tab_data,tab_graph = st.tabs(["Detailed data and explanation","Pedestrian graph"])

            with tab_data:
                if 0<int(selected_segment_id)<10:

                    st.metric("Segment's number :", selected_segment_id)
                    with st.popover("Average pedestrian density :"):
                        st.markdown("The estimation of sidewalk pedestrian density is based on the three-dimensional pedestrian timespace diagram proposed by Saberi and Mahmassani (2014), which extends Edie’s definitions of fundamental traffic variables(Edie, 1963).")
                    st.metric("Average pedestrian density :", str(round(ped_density_per_segment[int(selected_segment_id)-1]["average pedestrian density"],3))+" ped/m\u00b2",label_visibility="collapsed")
                    with st.popover("Maximum pedestrian density :"):
                        st.markdown("The estimation of sidewalk pedestrian density is based on the three-dimensional pedestrian timespace diagram proposed by Saberi and Mahmassani (2014), which extends Edie’s definitions of fundamental traffic variables(Edie, 1963).")
                    st.metric("Maximum pedestrian density :", str(round(ped_density_per_segment[int(selected_segment_id)-1]["maximum pedestrian density"],3))+" ped/m\u00b2",label_visibility="collapsed")
                    with st.popover("Average pedestrian speed :"):
                        st.markdown("This feature represents the average speed of all pedestrians detected by the robot while traversing the given segment.")
                    st.metric("## Average pedestrian speed :", str(round(ped_speed_per_segment[int(selected_segment_id)-1]["average pedestrian speed"],3))+" m/s",label_visibility="collapsed")
                    
                    st.metric("Average effective width :", str(round(width_per_segment[int(selected_segment_id)-1]["average effective width"],3))+" m")
                    with st.popover("Average minimum effective width :"):
                        st.markdown("Details about Average effective width")
                    st.metric("Average minimum effective width :", str(round(width_per_segment[int(selected_segment_id)-1]["average minimum effective width"],3))+" m",label_visibility="collapsed")

                else:
                    st.info("No data is available for this specific segment")
            
            with tab_graph:
                st.subheader("Pedestrian count over the day on the selected segment")
                
                if Pedestrian_df.empty:
                    st.warning("Aucune donnée de passant à afficher. Vérifiez le fichier CSV ou les erreurs ci-dessus.")
                else:
                    # Créer la figure Plotly
                    fig_passants = go.Figure()
                    # Ajouter la trace principale des barres (toutes les données de la journée)
                    fig_passants.add_trace(go.Bar(
                        x=Pedestrian_df.loc[Pedestrian_df['segment_id'] == int(selected_segment_id)]['timestamp_quarter'],
                        y=Pedestrian_df.loc[Pedestrian_df['segment_id'] == int(selected_segment_id)]['unique_pedestrian_count'],
                        name='Number of pedestrian',
                        marker_color='rgb(26, 118, 255)' # Couleur bleue pour les barres
                    ))

                    # Configurer le layout du graphique
                    fig_passants.update_layout(
                        title_text="Pedestrians count along the day",
                        xaxis_title="Time of day",
                        yaxis_title="Number of pedestrian detected",
                        bargap=0.2, # Espace entre les barres
                        # Optionnel: forcer l'affichage de tous les timestamps sur l'axe X si besoin
                        # xaxis=dict(type='category') # Peut aider si les timestamps ne sont pas réguliers
                    )
                    st.plotly_chart(fig_passants, use_container_width=True)


        
#onglet d'affichage du contexte
with tab2 :

    st.subheader("Investigating Sidewalks’ Mobility and Improving it with Robots (ISMIR)” Project")
    st.markdown("Sidewalk delivery robots offer a promising solution for sustainable City Logistics. These robots can be deployed from hubs, retail locations, or even retrofitted vehicles to perform short-range deliveries, partially replacing traditional, less sustainable methods. The ISMIR project aims to develop a deeper, data-driven understanding of sidewalk robot operations in realistic urban settings and to explore sidewalk mobility through the lens of robotic navigation.")
    st.markdown("ISMIR is a collaborative project involving researchers from [The Division of Transport and Systems Analysis](https://www.kth.se/en/som/avdelningar/sek/transport-och-systemanalys-1.17211) and the [Integrated Transport Research Lab (ITRL)](https://www.itrl.kth.se/integrated-transport-research-lab-itrl-1.1081637)  at KTH Royal Institute of Technology (Stockholm, Sweden).")
    st.markdown("The Investigating Sidewalks’ Mobility and Improving it with Robots (ISMIR)” project was funded by [Digital Futures](https://www.digitalfutures.kth.se/project/investigating-sidewalks-mobility-and-improving-it-with-robots-ismir/) and was carried out between 2023 and 2025.")
    
    st.markdown("##### Objective")
    st.markdown("Using empirical data from sidewalk robot trips between October, 2024 and March, 2025 on the KTH campus, the project involved:")
    st.markdown("- Analysis of sidewalk mobility patterns and assess delivery efficiency.")
    st.markdown("- Application of statistical and machine learning methods to evaluate the relation between sidewalk users’ patterns, contextual variables such as weather conditions, and pedestrian infrastructure features")
    st.markdown("## Team")

    col_robot,col_Xing, col_Michele,col_Kaj,col_Sulthan,col_Jonas = st.columns(6, border=False)
    with col_robot:
        st.image("data/pictures/Robot_photo.jpg",use_container_width=True)
        st.markdown("#### SVEA Robot")
        st.markdown("The SVEA robot used for sidewalk data collection and the mini network on KTH campus where the robot operates")
    with col_Xing:
        st.image("data/pictures/xingtong.jfif",use_container_width=True)
        st.markdown("#### Xing Tong")
        st.markdown("I am a Ph.D. student in the Division of Transport and Systems Analysis, engaging in the ISMIR project. My expertise lies in traffic analysis, GIS, and machine learning.")
        
    with col_Michele:
        st.image("data/pictures/micheles.jfif",use_container_width=True)
        st.markdown("#### Michele Simoni")
        st.markdown("Michele D. Simoni currently serves as an Assistant Professor in Transport Systems Analysis. Michele’s main research activity is currently focused on modeling and optimization of advanced transportation solutions.")
    
    with col_Kaj:
        st.image("data/pictures/kajarf.jfif",use_container_width=True)
        st.markdown("#### Kaj Munhoz Arfvidsson")
        st.markdown("I am a Ph.D. student in the Division of Transport and Systems Analysis, engaging in the ISMIR project. My expertise lies in traffic analysis, GIS, and machine learning.")
    
    with col_Sulthan:
        st.image("data/pictures/missing-profile-image.png",use_container_width=True)
        st.markdown("#### Sulthan Suresh Fazeela")
        st.markdown("I am a Research Engineer working primarily with sidewalk mobility and safe autonomous navigation for the small vehicles for autonomy (svea) platform at the Smart Mobility Lab.")

    with col_Jonas:
        st.image("data/pictures/jonas1.jfif",use_container_width=True)
        st.markdown("#### Jonas Mårtensson")
        st.markdown("Jonas Mårtensson is Professor of Automatic Control with applications in Transportation Systems at KTH Royal Institute of Technology in Stockholm, Sweden. He is the director of the Integrated Transport Research Lab (ITRL).")
        