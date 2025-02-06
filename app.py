import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import re
import requests
from PIL import Image
import io
import os
from dotenv import load_dotenv
from datetime import date
import time
 
# Load environment variables and configure Gemini
load_dotenv()
api_key = os.getenv("API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")
# Path to the CSV file
CSV_FILE_PATH = "repo1.csv"
# Existing functions here (parse_query_with_gemini, filter_images_by_players_and_action, etc.)
def parse_query_with_gemini(user_query):
    prompt = f"""
    You are an assistant for a sports analytics platform. Parse the following query into structured parameters:
    Query: "{user_query}"
    Output format:
    {{"Players": [List of player names], "Action": "Action type" Any one of the given(posing, walking, playing, bowling, batting, observing, speaking, celebrating, discussion, award ceremony, sitting, standing, laughing, smiling, eating, event, departure, greeting, running, cheering)(optional), "Environment": "Environment type (optional)", "Day/Night": "Day or Night (optional)", "ShotType": "Type of shot (optional)", "Date": "Date (optional)", "Location": "Location (optional)", "Results": "Number of results (optional)"}}
    """
    response = model.generate_content(prompt)
    return response.text
# Updated function to filter the DataFrame
def filter_images_by_players_and_action(df, players=None, action=None, environment=None, day_night=None, shot_type=None, date=None, location=None):
    grouped = df.groupby("ID").agg(
        {"Name": lambda x: set(x), "URL": "first", "Action": lambda x: set(x), "Environment": "first",
         "Day/Night": "first", "ShotType": "first", "Date": "first", "Location": "first" if "Location" in df.columns else lambda x: None}
    )
    # Start with all rows
    result = grouped
    # Check for generic player terms
    generic_terms = {"players", "person", "people"}
    if players and not generic_terms.intersection(set(map(str.lower, players))):
        result = result[result["Name"].apply(lambda x: set(players).issubset(x))]
    # Filter by action if specified
    if action:
        result = result[result["Action"].apply(lambda x: action in x)]
    # Filter by environment if specified
    if environment:
        if "Environment" in df.columns:
            result = result[result["Environment"].str.contains(environment, case=False, na=False)]
    # Filter by day/night if specified
    if day_night:
        if "Day/Night" in df.columns:
            result = result[result["Day/Night"].str.contains(day_night, case=False, na=False)]
    # Filter by shot type if specified
    if shot_type:
        if "ShotType" in df.columns:
            result = result[result["ShotType"].str.contains(shot_type, case=False, na=False)]
    # Filter by date if specified
    if date:
        if "Date" in df.columns:
            result = result[result["Date"].str.contains(date, case=False, na=False)]
    # Filter by location if specified
    if location:
        if "Location" in df.columns:
            result = result[result["Location"].str.contains(location, case=False, na=False)]
    return result["URL"].tolist()
 
# Function to extract view URL and direct image URL from Google Drive URL
def get_drive_view_url_and_direct_link(url):
    file_id = url.split("/")[-2]  # Extract file ID from Google Drive URL
    view_link = f"https://drive.google.com/file/d/{file_id}/view"
    direct_link = f"https://drive.google.com/uc?id={file_id}"
    return view_link, direct_link
 
# Function to fetch the image with retry logic
def fetch_image_with_retry(direct_link, retries=3):
    for _ in range(retries):
        try:
            response = requests.get(direct_link)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"Error fetching image: {e}")
    return None
 
# Function to display results as a grid of 2 rows and 3 columns
def display_results():
    current_page = st.session_state.current_page
    num_results = st.session_state.num_results
    result_urls = st.session_state.result_urls
    df = pd.read_csv(CSV_FILE_PATH)  # Load the CSV file to retrieve captions
    start_idx = current_page * num_results
    end_idx = start_idx + num_results
    st.write(f"Displaying results {start_idx + 1} to {min(end_idx, len(result_urls))}:")
    current_results = result_urls[start_idx:end_idx]
    # Create 2 rows of results
    rows = 2
    cols = 3
    num_cells = rows * cols
    current_results = current_results[:num_cells]
 
    for row_idx in range(rows):
        cols_in_row = st.columns(cols)
        start_idx_in_row = row_idx * cols
        end_idx_in_row = start_idx_in_row + cols
        for col_idx, (url, col) in enumerate(zip(current_results[start_idx_in_row:end_idx_in_row], cols_in_row)):
            with col:
                if "drive.google.com" in url:
                    view_link, direct_link = get_drive_view_url_and_direct_link(url)
                    image_content = fetch_image_with_retry(direct_link)
                    if image_content:
                        image = Image.open(io.BytesIO(image_content))
                        col.image(image, use_container_width=True)
 
                        # Fetch the caption for the current URL
                        caption_row = df[df['URL'] == url]
                        caption = caption_row["Captions"].iloc[0] if not caption_row.empty and "Captions" in df.columns else "No caption available"
                       
                        # Display the caption
                        #col.write(f"**{caption}**")
                       
                        # Add a link to open in Google Drive
                        col.markdown(f'<a href="{view_link}" target="_blank" style="color: blue;">Open in Google Drive</a>', unsafe_allow_html=True)
                    else:
                        col.write("Error fetching image.")
                else:
                    col.write(f"Invalid URL: {url}")
    if end_idx >= len(result_urls):
        st.write("No more results to display.")
 
# --- Main Streamlit app with tabs ---
def app():
    custom_html = """
    <style>
        .banner {
            width: 100%;
            height: 100px;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #FFD700;
            text-align: center;
        }
        .banner img {
            max-height: 100px;
        }
    </style>
    <div class="banner">
        <img src="https://logotyp.us/file/super-kings.svg" width="200" height="100">
    </div>
    """
    st.markdown(custom_html, unsafe_allow_html=True)
    st.title("Image Search Application")
    df = pd.read_csv(CSV_FILE_PATH)
    # Create two tabs
    tab1, tab2 = st.tabs(["Text-based Search", "Filter-based Search"])
    # Tab 1: Search Images
    with tab1:
        st.markdown("Find images based on Player Names, Action, Environment")
        user_query = st.text_input("Enter your query:")
        if "current_page" not in st.session_state:
            st.session_state.current_page = 0
        if "query_submitted" not in st.session_state:
            st.session_state.query_submitted = False
        if "result_urls" not in st.session_state:
            st.session_state.result_urls = []
        if "num_results" not in st.session_state:
            st.session_state.num_results = 6
        if st.button("Submit"):
            st.session_state.current_page = 0
            st.session_state.query_submitted = True
            if user_query:
                try:
                    parsed_query_raw = parse_query_with_gemini(user_query)
                    cleaned_response = parsed_query_raw.strip("```").strip()
                    start_idx = cleaned_response.find("{")
                    end_idx = cleaned_response.rfind("}") + 1
                    valid_json = cleaned_response[start_idx:end_idx]
                    if valid_json:
                        parsed_query = json.loads(valid_json)
                    else:
                        st.error("Valid JSON not found in the response.")
                        return
                    query_players = parsed_query.get("Players", [])
                    query_action = parsed_query.get("Action", None)
                    query_environment = parsed_query.get("Environment", None)
                    query_day_night = parsed_query.get("Day/Night", None)
                    query_shot_type = parsed_query.get("ShotType", None)
                    query_date = parsed_query.get("Date", None)
                    query_location = parsed_query.get("Location", None)
 
                    match = re.search(r"\b(\d+)\s*images?\b", user_query)
                    num_results = int(match.group(1)) if match else 6
 
                    result_urls = filter_images_by_players_and_action(
                        df, query_players, query_action, query_environment, query_day_night,
                        query_shot_type, query_date, query_location
                    )
                    st.session_state.result_urls = result_urls
                    st.session_state.num_results = num_results
                    if result_urls:
                        display_results()
                    else:
                        st.write("No matching images found.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        # Pagination
        if st.session_state.query_submitted and st.session_state.result_urls:
            if st.button("Back"):
                if st.session_state.current_page > 0:
                    st.session_state.current_page -= 1
                    display_results()
            if st.button("Next"):
                if (st.session_state.current_page + 1) * st.session_state.num_results < len(st.session_state.result_urls):
                    st.session_state.current_page += 1
                    display_results()
    # Tab 2: About
    with tab2:
        #st.header("Filter based Search")
        # Initialize session state
        if "selected_player" not in st.session_state:
            st.session_state.selected_player = None
        if "players" not in st.session_state:
            st.session_state.players = []
        if "display_index" not in st.session_state:
            st.session_state.display_index = 0
        available_players = ["Mitchell Santner", "Nishant Sindhu", "Moeen Ali", "Ajay Mandal", "Ben Stokes",
            "Ajinkya Rahane", "Shivam Dube", "Deepak Chahar", "Devon Conway", "Maheesh Theekshana",
            "R Russell", "Akash Singh", "Gregory King", "Lakshmi", "Tushar Deshpande", "Ms Dhoni",
            "Suresh Raina", "Ruturaj Gaikwad", "Simarjeet Singh", "Ravindra Jadeja", "Eric Simon",
            "Shaik Rasheed", "Stephen Fleming", "Subhranshu Senapati", "Dwayne Bravo", "Ambati Rayudu",
            "Bhagath Varma", "Tommy Simsek", "Sanjay Natarajan", "Prashant Solanki", "Rajvardhan Hangargekar",
            "Dwaine Pretorius", "Matheesha Pathirana", "Mukesh Choudhary", "Kasi", "Gerald Coetzee",
            "David Miller", "Faf Du Plessis", "Lahiru Milantha", "Imran Tahir", "Saiteja Mukkamalla",
            "Rusty Theron", "Cameron Stevenson", "Zia Shahzad", "Cody Chetty", "Milind Kumar",
            "Sami Aslam", "Calvin Savage", "Muhammad Mohsin", "Zia Ul Haq"]
         # Function to add a player
        def add_player():
            new_player = st.session_state.new_player
            if new_player and new_player not in st.session_state.players:
                st.session_state.players.append(new_player)
 
        # Function to remove a player
        def remove_player(player):
            if player in st.session_state.players:
                st.session_state.players.remove(player)
        # Input area for adding players via dropdown
        st.write("##### Name")
        col1 ,col2, col3 = st.columns([3,1,1])
        with col1:
            st.selectbox(
                " ",
                options=[""] + available_players,
                key="new_player",
                on_change=add_player,
                label_visibility="collapsed",
            )
        # Display added players as tags in a single line
        st.write("##### Selection List")
        if st.session_state.players:
            for player in st.session_state.players:
                # Create a button with "✖️" to remove player
                if st.button(f"✖️ {player}", key=f"remove_{player}"):
                    remove_player(player)
        else:
            st.info("No players added yet. Please add players to proceed.")
        # Input for location
        st.write("")  # Spacer
        col5, col6, col8, col9, col10= st.columns(5)
        with col5:
            Action = st.selectbox(
                "ACTION",
                ["Unspecified", "Award Ceremony", "Batting", "Bowling", "Catching", "Cheering", "Departure",  "Eating", "Event", "Greeting", "Holding Signs", "Hugging", "Laughing",     "Observing", "Playing", "Posing", "Practicing", "Receiving", "Running",     "Smiling", "Speaking", "Standing", "Sitting", "Warm Up", "Walking" ],
                label_visibility="visible",
            )
        with col6:
        # Combining Day/Night, Environment, and Distance in a single Location filter dropdown
            activity = st.selectbox(
                "ACTIVITY",
                ["Unspecified", "Day","Night","Outdoor","Indoor","Unknown","Close"],
                label_visibility="visible"
            )
        with col8:
            start_date = st.date_input(
                "From Date",
                date.today(),
                label_visibility="visible",
            )
        with col9:
            end_date = st.date_input(
                "To Date",
                date.today(),
                label_visibility="visible",
            )
        with col10:
            no_of_faces = st.number_input(
                "NO OF FACES",
                min_value=0,
                value=0,  # Default value
                step=1,
                label_visibility="visible",
            )
        # Function to filter dataframe based on action
        def filter_by_Action(df, action="all"):
            if "Action" in df.columns:
                if action != "all":
                    # Check if the Caption contains the selected action keyword (case-insensitive)
                    return df[df["Action"].str.contains(action, case=False, na=False)]
                else:
                    # If no action is provided, return the dataframe unfiltered
                    return df
            else:
                st.warning("The uploaded CSV does not contain a 'action' column. Please include it.")
                return df
        # Function to filter dataframe based on place
        def filter_by_no_of_faces(df, no_of_faces=0):
            if "No_of_faces" in df.columns:
                return df[df["No_of_faces"] == no_of_faces]
            else:
                st.warning("The uploaded CSV does not contain a 'No_of_faces' column. Please include it.")
                return df
        # Function to filter dataframe based on location
        def filter_by_activity(df, day_night=None, environment=None, distance=None):
            if day_night and "Day_Night" in df.columns:
                df = df[df["Day_Night"].str.contains(day_night, case=False, na=False)]
            if environment and "Environment" in df.columns:
                df = df[df["Environment"].str.contains(environment, case=False, na=False)]
            if distance and "Distance" in df.columns:
                df = df[df["Distance"].str.contains(distance, case=False, na=False)]
            return df
        def filter_by_date(df, from_date, to_date):
            if "Date" in df.columns:
                # Convert the 'Date' column to pandas datetime with infer_datetime_format for flexible formats
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                # Convert Streamlit date inputs to pandas datetime
                from_date = pd.to_datetime(from_date.strftime("%Y-%m-%d"))
                to_date = pd.to_datetime(to_date.strftime("%Y-%m-%d"))
                # Filter the DataFrame for dates within the specified range
                return df[(df["Date"] >= from_date) & (df["Date"] <= to_date)]
            else:
                st.warning("The uploaded CSV does not contain a 'Date' column. Please include it.")
                return df
               
        # Function to filter players with the same URL
        def filter_by_same_url(df):
            # Group by URL and filter groups where all players in the group have the same URL
            grouped = df.groupby("URL").nunique()
            valid_urls = grouped[grouped > 1].index  # URLs with more than one unique name
            return df[df["URL"].isin(valid_urls)]
        # Functionality for the yellow button
        # Functionality for the yellow button
        if st.button("Find Image", key="yellow_button"):
            st.session_state.display_index = 0  # Reset index for new generation
            if st.session_state.players and CSV_FILE_PATH:
                # Filter by selected player names
                filtered_df = df[df["Name"].isin(st.session_state.players)]
                # Apply Action filter if it's not set to "All"
                if Action != "All":
                    filtered_df = filtered_df[filtered_df["Action"].str.contains(Action, case=False, na=False)]
                # Apply location filter if it's not "unspecified"
                if activity != "unspecified":
                    filtered_df = filter_by_activity(
                        df=filtered_df,
                        day_night=activity if activity in ["Day", "Night"] else None,
                        environment=activity if activity in ["Outdoor", "Indoor"] else None,
                        distance=activity if activity in ["Close", "Far"] else None
                    )
                if no_of_faces > 0:
                    filtered_df = filter_by_no_of_faces(filtered_df, no_of_faces)
                if start_date and end_date:
                    filtered_df = filter_by_date(filtered_df, from_date=start_date, to_date=end_date)
                # Filter to include only players with the same URL (if applicable)
                filtered_df = filter_by_same_url(filtered_df)
                # Ensure only unique URLs in the session state
                st.session_state.filtered_urls = filtered_df["URL"].drop_duplicates().tolist()
                if not st.session_state.filtered_urls:
                    # st.warning("No images match the selected filters. Showing all images for selected players.")
                    st.session_state.filtered_urls = df[df["Name"].isin(st.session_state.players)]["URL"].drop_duplicates().tolist()
            else:
                st.warning("No players selected or no CSV uploaded.")
                st.session_state.filtered_urls = []
        # Add custom CSS for the yellow button
        st.markdown(
            """
            <style>
            div.stButton > button:first-child {
                background-color: #FFD700;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                padding: 12px 24px;
                border-radius: 10px;
                cursor: pointer;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                transition: background-color 0.3s ease, transform 0.2s ease;
            }
            div.stButton > button:first-child:hover {
                background-color: #FFC107;
                transform: scale(1.05);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
 
        def convert_to_drive_direct_view_url(url):
            """Converts a Google Drive file link to a direct download link."""
            try:
                if "drive.google.com/file/d/" in url:
                    # Extract the file ID from the link
                    file_id = url.split("/file/d/")[1].split("/")[0]
                    # Create the direct download link
                    return f"https://drive.google.com/uc?id={file_id}"
                else:
                    st.error(f"Not a valid Google Drive file URL: {url}")
                    return None
            except Exception as e:
                st.error(f"Failed to process Google Drive URL: {url}")
                st.write(f"Error: {e}")
                return None
        def fetch_image_with_retry(direct_url, retries=3, delay=5):
            for attempt in range(retries):
                try:
                    response = requests.get(direct_url, timeout=5)
                    if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                        return response.content  # Return the image content
                    else:
                        raise Exception(f"Invalid image response: {response.status_code}")
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(delay)  # Wait before retrying
                        continue
                    else:
                        st.error(f"Failed to load image after {retries} attempts: {e}")
                        return None
        # Display images in a grid layout
        if "filtered_urls" in st.session_state and st.session_state.filtered_urls:
            start_index = st.session_state.display_index
            end_index = start_index + 6
            urls_to_display = st.session_state.filtered_urls[start_index:end_index]
            cols = st.columns(3)  # 3 images per row
            for i, url in enumerate(urls_to_display):
                with cols[i % 3]:
                    try:
                        if "drive.google.com" in url:
                            view_link, direct_link = get_drive_view_url_and_direct_link(url)
                            if direct_link:
                                image_content = fetch_image_with_retry(direct_link)
                                if image_content:
                                    image = Image.open(io.BytesIO(image_content))
                                    st.image(image, use_container_width=True)
                                    if view_link:
                                        st.markdown(f'<a href="{view_link}" target="_blank" style="color: blue;">Open in Google Drive</a>', unsafe_allow_html=True)
                        else:
                            st.image(url, use_container_width=True)
                            st.markdown(f'<a href="{url}" target="_blank" style="color: blue;">{url}</a>', unsafe_allow_html=True)
                    except Exception as e:
                        st.warning(f"Failed to load image from URL: {url}")
                        st.write(e)
            # Load More Button
            if end_index < len(st.session_state.filtered_urls):
                if st.button("Load More"):
                    st.session_state.display_index = end_index
       
        # Add some custom CSS to adjust the spacing and alignment
        st.markdown(
            """
        <style>
            .stSelectbox, .stDateInput {
                background-color: #e3f2fd;
                border-radius: 15px;
                border: 1px solid #90caf9;
                padding: 8px 12px;
                font-size: 15px;
            }
        </style>
            """,
            unsafe_allow_html=True,
        )
        # Style section
        st.markdown(
            """
        <style>
        .image-gallery {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
        }
        .image-gallery img {
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            margin: 10px;
        }
        .center-buttons {
            text-align: center;
            margin-top: 20px;
        }
        .yellow-button {
            background-color: #FFD700;
            border: none;
            padding: 10px 20px;
            color: white;
            font-size: 16px;
            cursor: pointer;
            border-radius: 5px;
        }
        .red-button {
            background-color: #FF4500;
            border: none;
            padding: 10px 20px;
            color: white;
            font-size: 16px;
            cursor: pointer;
            border-radius: 5px;
        }
        .yellow-button:hover {
            background-color: #FFC107;
        }
        .red-button:hover {
            background-color: #FF6347;
        }
        </style>
            """,
            unsafe_allow_html=True,
        )
# Run the app
if __name__ == "__main__":
    app()