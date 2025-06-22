import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
import firebase_admin
from firebase_admin import credentials, firestore, storage, initialize_app
from datetime import datetime
import streamlit_authenticator as stauth
import bcrypt
import time
import json
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# Initialize Firebase
firebase_secrets = st.secrets["firebase"]

if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": firebase_secrets["type"],
        "project_id": firebase_secrets["project_id"],
        "private_key_id": firebase_secrets["private_key_id"],
        "private_key": firebase_secrets["private_key"].replace('\\n', '\n'),
        "client_email": firebase_secrets["client_email"],
        "client_id": firebase_secrets["client_id"],
        "auth_uri": firebase_secrets["auth_uri"],
        "token_uri": firebase_secrets["token_uri"],
        "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
        "client_x509_cert_url": firebase_secrets["client_x509_cert_url"]
    })
    firebase_admin.initialize_app(cred)
db = firestore.client()
storage_client = storage.bucket("fitness-tracker-c51bf.firebasestorage.app")

# Function to verify password
def verify_password(plain_password,hashed_password):
    return bcrypt.checkpw(plain_password.encode(),hashed_password.encode())

# Check if user is already logged in
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = None

# Fetch user credentials from Firestore
users_ref = db.collection("credentials").stream()
credentials_dict = {}
for user in users_ref:
    user_data = user.to_dict()
    if "username" in user_data:
        credentials_dict[user_data["username"]] = user_data

# If user is already logged in, skip login screen
if not st.session_state["authenticated"]:
    st.title("Login")

    if st.button("Login"):
        user_data = credentials_dict.get(username_input)

        if user_data and verify_password(password_input,user_data["password"]):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username_input
            st.session_state["name"] = user_data["name"]  # Store name in session state
            st.session_state["login_timestamp"] = time.time()
            st.success(f"Welcome, {user_data['name']}!")
            st.title('Homepage')
        else:
            st.error("Username/password is incorrect")

else:
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        username = st.session_state["username"]
        if not username == "admin":

            st.markdown("---")
            
            st.sidebar.title("Nutrition")
            sess_action = st.sidebar.radio("To View", ["Nutrition Log", "Food Table"])

            # Show what was done for Selected Session
            if sess_action == "Nutrition Log":

                st.write("### Nutrition Log")
                meal_options = ["Breakfast","Lunch","Dinner","Morning Snack","Afternoon Snack","Night Snack","Supper"]
                meal_selected = st.selectbox("Select Meal",meal_options)
                date_selected = st.date_input("Select Date")
                uploaded_file = st.file_uploader("Upload Meal Photo",type=["jpg","png","jpeg"])

                if st.button("Upload"):
                    if uploaded_file:
                        blob = storage_client.blob(f"nutrition/{username}/{date_selected}/{meal_selected}.jpg")
                        blob.upload_from_file(uploaded_file)
                        db.collection("nutrition").add({
                            "client_id": username,
                            "date": date_selected.strftime('%Y-%m-%d'),
                            "meal": meal_selected,
                            "image_url": blob.public_url
                        })
                        st.success("Meal uploaded successfully!")
                        st.rerun()

            if sess_action == "Food Table":
                # Google Sheets credentials and URL setup
                gs_scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                gs_creds = Credentials.from_service_account_file(
                    "google_sheets_credentials.json",
                    scopes=gs_scope
                )
                gc = gspread.authorize(gs_creds)

                sheet_url = "https://docs.google.com/spreadsheets/d/1nfQfBRdZkBcI7ZISrLu1ko-MYmizOTa_EV5panWtJjI"

                st.write("### Food Nutrition Table")
                st.write("##### Select and Filter Food Items")

                spreadsheet = gc.open_by_url(sheet_url)  # This gets the spreadsheet
                worksheet = spreadsheet.worksheet("Sheet1")  # This gets the first worksheet
                data = worksheet.get_all_records()  # This gets the records
                df = pd.DataFrame(data)
                df = df.fillna(0)
                df = df.replace(to_replace='N/A', value=0)
                df["Weight (g)"] = pd.to_numeric(df["Weight (g)"], errors="coerce").fillna(0)

                # Build grid options
                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_default_column(filter=True, sortable=True, resizable=True)  # ✅ Enable filters
                gb.configure_selection(selection_mode="multiple", use_checkbox=True)     # ✅ Enable checkbox
                gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)  # Optional: pagination
                gb.configure_side_bar()  # optional: adds filter/sort panel
                grid_options = gb.build()

                # Render interactive grid
                grid_response = AgGrid(df,
                                       gridOptions=grid_options,
                                       update_mode=GridUpdateMode.SELECTION_CHANGED,
                                       height=500, width='100%',
                                       fit_columns_on_grid_load=True, theme='streamlit')  # Optional: "alpine", "balham", "material"
                # Get selected rows
                selected = grid_response['selected_rows']
                if selected is not None and len(selected) > 0:
                    st.write("### Selected Items")
                    selected_df = pd.DataFrame(selected)
                    st.dataframe(selected_df)
                                        
                    # Ask user to input consumed weight for each item
                    weight_inputs = []
                    for i, row in selected_df.iterrows():
                        try:
                            default_weight = int(float(row["Weight (g)"])) if row["Weight (g)"] not in [None, "", "N/A"] else 100
                        except (ValueError, TypeError):
                            default_weight = 100
                        weight = st.number_input(
                            f"Enter weight (g) for {row['Item']} ({row['Brand']})",
                            min_value=0,
                            value=default_weight,
                            step=5,
                            key=f"weight_{i}"
                        )
                        weight_inputs.append(weight)

                    macro_columns = [
                        "Calories_per_100g (kcal)",
                        "Protein_per_100g (g)",
                        "Fat_per_100g (g)",
                        "Carbs_per_100g (g)",
                        "Sugars_per_100g (g)",
                        "Sodium_per_100g (mg)"
                    ]

                    for col in macro_columns:
                        selected_df[col] = pd.to_numeric(selected_df[col], errors='coerce').fillna(0)

                    # Compute macros based on user input
                    macro_table = pd.DataFrame({
                        "Item": selected_df["Item"],
                        "Calories": (selected_df["Calories_per_100g (kcal)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                        "Protein": (selected_df["Protein_per_100g (g)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                        "Fats": (selected_df["Fat_per_100g (g)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                        "Carbohydrates": (selected_df["Carbs_per_100g (g)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                        "Sugar": (selected_df["Sugars_per_100g (g)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                        "Sodium (mg)": (selected_df["Sodium_per_100g (mg)"] * pd.Series(weight_inputs) / 100).fillna(0).astype(int),
                    })

                    st.markdown("### 🥗 Macros Table")
                    st.dataframe(macro_table.style.format("{:.2f}"))

                    st.markdown("### 🔢 Total Macros")
                    st.write({
                        "Calories (kcal)": macro_table["Calories"].sum().round(1),
                        "Protein (g)": macro_table["Protein"].sum().round(1),
                        "Fats (g)": macro_table["Fats"].sum().round(1),
                        "Carbohydrates (g)": macro_table["Carbohydrates"].sum().round(1),
                        "Sugar (g)": macro_table["Sugar"].sum().round(1),
                        "Sodium (mg)": macro_table["Sodium (mg)"].sum().round(1),
                    })

