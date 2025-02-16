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
credentials_dict = {user.to_dict()["username"]: user.to_dict() for user in users_ref}

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

                try:
                    bucket = storage_client.bucket()
                    blob = bucket.blob(f"nutrition/{username}/{file_name}")
                    blob.upload_from_string(file.read(), content_type=file.type)
                    st.success("Photo uploaded successfully!")
                except Exception as e:
                    st.error(f"Upload failed: {str(e)}")
