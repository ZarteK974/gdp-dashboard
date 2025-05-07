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


#importation des fichiers de données json
with open("data/irr_event_coordinates.json", mode="r", encoding="utf-8") as irr_event_coordinates:
    irr_event_coordinates = json.load(irr_event_coordinates)
with open("data/ped_density_per_segment.json", mode="r", encoding="utf-8") as ped_density_per_segment:
    ped_density_per_segment = json.load(ped_density_per_segment)
with open("data/ped_speed_per_segment.json", mode="r", encoding="utf-8") as ped_speed_per_segment:
    ped_speed_per_segment = json.load(ped_speed_per_segment)
with open("data/slope_per_segment.json", mode="r", encoding="utf-8") as slope_per_segment:
    slope_per_segment = json.load(slope_per_segment)
#with open("data/unevenness_irregularity_per_segment.json", mode="r", encoding="utf-8") as unevenness_irregularity_per_segment:
    #unevenness_irregularity_per_segment = json.load(unevenness_irregularity_per_segment)
with open("data/width_per_segment.json", mode="r", encoding="utf-8") as width_per_segment:
    width_per_segment = json.load(width_per_segment)

# --- Configuration de la Page ---
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
def load_data(path_data_path, sensor_data_path, unevenness_irregularity_per_segment_path):
    # Charger les données du chemin (nouveau format: id, "[(lon, lat),...]")
    processed_path_df = pd.DataFrame(columns=['segment_id', 'locations']) # Init df vide
    try:
        # Lire en spécifiant les noms de colonnes attendus
        path_df = pd.read_csv(path_data_path, names=['segment_id', 'coordinates_str'], header=None) # Lire sans en-tête, nommer les colonnes

        # S'assurer que segment_id est une chaîne
        path_df['segment_id'] = path_df['segment_id'].astype(str)
        # Remplacer les NaN potentiels dans coordinates_str par des chaînes vides
        path_df['coordinates_str'] = path_df['coordinates_str'].fillna('')


        #st.write("Parsing segments coordinates...") # Feedback pour l'utilisateur

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

        #st.write(f"Parsing finished: {num_successfully_parsed} segments loaded successfully.")
        if num_failed > 0:
             st.warning(f"{num_failed} segments ignorés en raison d'erreurs de parsing.")
        # if num_empty_original > 0:
        #      st.info(f"{num_empty_original} lignes avaient des coordonnées vides à l'origine.")


    except FileNotFoundError:
        st.error(f"Erreur: Le fichier de chemin {path_data_path} n'a pas été trouvé.")
        # processed_path_df reste le df vide initialisé
    except Exception as e:
        st.error(f"Erreur lors du chargement ou du traitement de {path_data_path}: {e}")
        st.error(traceback.format_exc()) # Affiche l'erreur complète pour le débogage
        # processed_path_df reste le df vide initialisé

    # --- Chargement Sensor Data (inchangé) ---
    try:
        sensor_df = pd.read_csv(sensor_data_path)
        sensor_df['timestamp'] = pd.to_datetime(sensor_df['timestamp'])
        sensor_df['segment_id'] = sensor_df['segment_id'].astype(str)
    except FileNotFoundError:
        # st.warning(f"Le fichier de données capteurs {sensor_data_path} n'a pas été trouvé.")
        sensor_df = pd.DataFrame(columns=['segment_id', 'timestamp', 'latitude', 'longitude', 'irregularity_value', 'current_width', 'pedestrian_detected'])
    except Exception as e:
        st.error(f"Erreur lors du chargement de {sensor_data_path}: {e}")
        sensor_df = pd.DataFrame(columns=['segment_id', 'timestamp', 'latitude', 'longitude', 'irregularity_value', 'current_width', 'pedestrian_detected'])
    
    try:
        unevenness_irregularity_per_segment_df = pd.read_csv(unevenness_irregularity_per_segment_path)
    except FileNotFoundError:
        unevenness_irregularity_per_segment_df = pd.DataFrame(columns=['segment_id', 'average_unevenness_index', 'average_irregularity_index'])
    return processed_path_df, sensor_df, unevenness_irregularity_per_segment_df

# --- Chemins vers vos fichiers CSV ---
PATH_CSV_PATH = 'data/segments.csv' # Votre fichier avec id, "[(lon, lat),...]"
SENSOR_CSV_PATH = 'data/sensor_data.csv' # Fichier optionnel avec données temporelles
UNEVENNESS_IRREGULARITY_PER_SEGMENT_PATH = 'data/unevenness_irregularity_per_segment.csv'

path_df, sensor_df, unevenness_irregularity_per_segment_df = load_data(PATH_CSV_PATH, SENSOR_CSV_PATH, UNEVENNESS_IRREGULARITY_PER_SEGMENT_PATH)

# --- Interface Utilisateur ---
st.title("📊 Walkability analysis dashboard")
st.markdown("Data visualization of sidewalk state and caracteristics")

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
tab1, tab2 = st.tabs(["Context", "Data"])


#onglet d'affichage du contexte
with tab1 :
    st.subheader("🗺️ Context and Details about the project")

#Onglets d'affichage des données
with tab2 :

    

    # --- Affichage Principal (Carte et Données) ---
    col_map, col_data = st.columns([1,2], border=True)

    with col_map:
        
        # Créer les options pour le selectbox
        segment_options = ["Overview"] + sorted_ids # Utilise la liste triée numériquement

        selected_segment_id = st.selectbox("Sélectionnez un Segment :", options=segment_options)
        
        # --- **NOUVEAU : Préparation de la Palette et Mapping de Couleurs** ---
        # Utiliser les IDs triés pour une assignation stable si l'ordre importe peu,
        # sinon utiliser unique_ids_str directement si l'ordre original d'apparition doit dicter la couleur.
        # Utilisons sorted_ids pour la cohérence avec le selectbox.
        ids_for_colors = sorted_ids

        # Définir une palette de couleurs (ajoutez/modifiez selon vos goûts)
        # Couleurs de https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=10
        color_palette = ['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00','#cab2d6','#6a3d9a']
        num_colors = len(color_palette)

        # Créer un dictionnaire mappant chaque segment_id à une couleur
        segment_color_map = {}
        for i, seg_id in enumerate(ids_for_colors):
            # Assigner les couleurs de manière cyclique si plus d'IDs que de couleurs
            color_index = i % num_colors
            segment_color_map[seg_id] = color_palette[color_index]
        # --- FIN NOUVEAU ---

        test = st.segmented_control("test", ["Display segments number","Display Irregularities events"], label_visibility="collapsed")

        st.subheader("🗺️ Robot's path map")

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

            if irr_event_coordinates and test == "Display Irregularities events" : # Vérifier si la liste n'est pas vide
                for point_coords in irr_event_coordinates["irregularity events"]:
                    try:
                        # Assurer que les coordonnées sont des floats
                        lat = float(point_coords["lat"])
                        lon = float(point_coords["lon"])

                        folium.CircleMarker(
                            location=[lat, lon],
                            radius=5,  # Taille du cercle en pixels
                            color='red',  # Couleur du contour
                            fill=True,
                            fill_color='red', # Couleur de remplissage
                            fill_opacity=0.7, # Opacité du remplissage
                            # Ajouter un tooltip ou popup si nécessaire
                            #tooltip=f"Point Spécifique {i+1}: ({lat:.4f}, {lon:.4f})"
                            # popup=f"Détail du point {i+1}" # Optionnel
                        ).add_to(m)
                    except (ValueError, TypeError, IndexError) as e:
                        st.warning(f"Impossible d'afficher le point spécifique ({point_coords}): {e}")
            # --- FIN NOUVEAU BLOC ---

        # Afficher la carte
        map_data = st_folium(m, width='100%', height=500)

    with col_data:

        st.subheader("🔍 Segment's details")

        if selected_segment_id == "Overview":

            st.info("Select a segment in the drop-down menu on the left to display details.")

            
            tab_unirreg, tab_abslop = st.tabs(["unvenness and irregularity indices","Absolute slope"])
            
            with tab_unirreg:

                col_graph, col_details = st.columns([1, 0.5], border=True)
                with col_graph:
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

                    #fig_width = px.line(unevenness_irregularity_per_segment, x='segment id', y=['average unevenness index','average irregularity index'], title='Width evolution', labels={'segment id': 'segment id', 'average unevenness index': 'average unevenness index'})
                    #fig_width.update_layout(xaxis_title=None, yaxis_title="average unevenness index")

            with tab_abslop:
                col_graph, col_details = st.columns([1, 0.5], border=True)
                with col_graph:

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

            

        # Le reste de la logique pour afficher les détails (graphiques, etc.)
        # reste basé sur sensor_df et selected_segment_id.
        # Il faut s'assurer que le fichier sensor_data.csv existe et
        # contient une colonne 'segment_id' qui correspond aux IDs dans segments.csv

        elif 0<int(selected_segment_id)<10:

            # ... (code pour statistiques globales inchangé, peut nécessiter sensor_df) ...
            st.metric("Segment's number :", selected_segment_id)
            st.metric("Average pedestrian density :", round(ped_density_per_segment[int(selected_segment_id)-1]["average pedestrian density"],3))
            st.metric("Maximum pedestrian density :", round(ped_density_per_segment[int(selected_segment_id)-1]["maximum pedestrian density"],3))
            st.metric("Average pedestrian speed :", round(ped_speed_per_segment[int(selected_segment_id)-1]["average pedestrian speed"],3))
            st.metric("Average effective width :", round(width_per_segment[int(selected_segment_id)-1]["average effective width"],3))
            st.metric("Average minimum effective width :", round(width_per_segment[int(selected_segment_id)-1]["average minimum effective width"],3))


      

            #if not segment_data.empty:
                #st.markdown(f"**Segment ID : {selected_segment_id}**")
                # ... (affichage des métriques et graphiques basé sur segment_data) ...
                #col_metric1, col_metric2 = st.columns(2)
               # with col_metric1:
                #    metric_val = segment_data['current_width'].mean()
                #    st.metric("Mean width (m)", f"{metric_val:.2f}" if pd.notna(metric_val) else "N/A")
                #with col_metric2:
                   # metric_val = segment_data['irregularity_value'].max()
                    #st.metric("Max irregularity", f"{metric_val:.2f}" if pd.notna(metric_val) else "N/A")

                #st.markdown("---")
                #st.markdown("**Temporal data charts :**")

                # Graphique : Irrégularité
                #if 'irregularity_value' in segment_data.columns and segment_data['irregularity_value'].notna().any():
                    #fig_irreg = px.line(segment_data.sort_values('timestamp'), x='timestamp', y='irregularity_value', title='Irregularity evolution', labels={'timestamp': 'Time', 'irregularity_value': 'Irregularity'})
                    #fig_irreg.update_layout(xaxis_title=None, yaxis_title="irregularity")
                    #st.plotly_chart(fig_irreg, use_container_width=True)

                # Graphique : Largeur
                #if 'current_width' in segment_data.columns and segment_data['current_width'].notna().any():
                    #fig_width = px.line(segment_data.sort_values('timestamp'), x='timestamp', y='current_width', title='Width evolution', labels={'timestamp': 'Temps', 'current_width': 'Width (m)'})
                    #fig_width.update_layout(xaxis_title=None, yaxis_title="Width (m)")
                    #st.plotly_chart(fig_width, use_container_width=True)

                # Graphique : Passants
                #if 'pedestrian_detected' in segment_data.columns and segment_data['pedestrian_detected'].notna().any():
                    #segment_data['pedestrian_detected'] = segment_data['pedestrian_detected'].astype(int)
                    #if segment_data['pedestrian_detected'].sum() > 0:
                        #pedestrian_summary = segment_data.resample('T', on='timestamp')['pedestrian_detected'].sum().reset_index(name='detections')
                        #pedestrian_summary = pedestrian_summary[pedestrian_summary['detections'] > 0]
                        #fig_ped = px.bar(pedestrian_summary, x='timestamp', y='detections', title='Pedestrians detection per minute')
                        #fig_ped.update_layout(xaxis_title=None, yaxis_title="Number of detection")
                        #st.plotly_chart(fig_ped, use_container_width=True)
                    #else:
                        #st.markdown("*Aucun passant détecté sur ce segment.*")

                # Données brutes
                #st.markdown("---")
                #st.markdown("**Raw data**")
                #st.dataframe(segment_data.head())

            #else:
                #st.markdown(f"**Segment ID : {selected_segment_id}**")
                #st.info(f"Aucune donnée détaillée (capteurs) trouvée pour le segment {selected_segment_id} dans '{SENSOR_CSV_PATH}'.")
                # Afficher les points du chemin pour référence
                #segment_path_row = path_df[path_df['segment_id'] == selected_segment_id].iloc[0]
                #if segment_path_row is not None and segment_path_row['locations']:
                    #st.markdown("**Points du chemin (Lat, Lon) pour ce segment :**")
                    # Afficher les points sous forme de DataFrame pour la clarté
                    #points_df = pd.DataFrame(segment_path_row['locations'], columns=['Latitude', 'Longitude'])
                    #st.dataframe(points_df)

        else:
            st.warning(f"Le fichier de données capteurs '{SENSOR_CSV_PATH}' est vide ou n'a pas pu être chargé. Impossible d'afficher les détails du segment.")