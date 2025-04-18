import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.figure_factory as ff
import firebase_admin
from firebase_admin import credentials, firestore, storage, initialize_app
from datetime import datetime
import streamlit_authenticator as stauth
import bcrypt
import time
import json

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

st.title("My Fitness Tracker")

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
if st.session_state["authenticated"]:
    st.success(f"Welcome back, {st.session_state.get('name')}!")
else:
    st.title("Login")
    username_input = st.text_input("Username")
    password_input = st.text_input("Password", type="password")

    if st.button("Login"):
        user_data = credentials_dict.get(username_input)

        if user_data and verify_password(password_input, user_data["password"]):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username_input
            st.session_state["name"] = user_data["name"]  # Store name in session state
            st.session_state["login_timestamp"] = time.time()
            st.success(f"Welcome, {user_data['name']}!")
            st.title('Homepage')

        else:
            st.error("Username/password is incorrect")

# Logout button
if st.session_state["authenticated"]:
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.success("You have been logged out.")

    # ------------------- Load Workout Data -------------------
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        username = st.session_state["username"]
        if not username == "admin":
            session_ref = db.collection("session").where("client_id","==",username).stream()
            session = pd.DataFrame([doc.to_dict() for doc in session_ref])

            #-------------------engineer data-------------------
            # Dropping the rows where reps are time-based
            session = session = session[~session["rep"].astype(str).str.contains("s", na=False)]
            # converting the string to datetime format
            session["sess_date"] = pd.to_datetime(session["sess_date"],format="%d/%m/%Y")
            # Convert "rep" to float64
            session.rep = session.rep.astype('float64')
            # Add 'One Rep Max' column to session
            session["one_rm"] = session["load_kg"] * (1 + 0.0333 * session["rep"])
            rm = session.groupby(["client_id","sess_date","exercise"])[["one_rm"]].mean().reset_index()

            pages = {
                "Menu": [
                    st.Page("home.py",title="Home"),
                    st.Page("session_log.py",title="Session Logs"),
                    st.Page("nutrition.py",title="Nutrition")]
            }
            pg = st.navigation(pages)
            pg.run()

        else:
            pages = {
                "Menu": [
                    st.Page("home.py",title="Home"),
                    st.Page("admin.py",title="Admin")]
            }
            pg = st.navigation(pages)
            pg.run()
