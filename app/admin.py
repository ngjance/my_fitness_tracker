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
firebase_secrets = json.loads(st.secrets["firebase"])
cred = credentials.Certificate("firebase_secrets")
if not firebase_admin._apps:
    initialize_app(cred)
db = firestore.client()
storage_client = storage.bucket("fitness-tracker-c51bf.firebasestorage.app")

# st.title("My Fitness Tracker")

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
    # username_input = st.text_input("Username")
    # password_input = st.text_input("Password",type="password")

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
    # ------------------- Load Workout Data -------------------
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        username = st.session_state["username"]

        client_ref = db.collection("client").where("client_id","==",username).stream()
        client_data = {doc.id: doc.to_dict() for doc in client_ref}
        client_list = [f"{data['first_name']} {data['last_name']}" for data in client_data.values()]

        session_ref = db.collection("session").where("client_id","==",username).stream()
        sessions = pd.DataFrame([doc.to_dict() for doc in session_ref])

        exercise_ref = db.collection("exercise").stream()
        exercise_list = [doc.to_dict()["exercise"] for doc in exercise_ref]

        if username == "admin":
            st.sidebar.title("Admin Panel")
            admin_action = st.sidebar.radio("Choose Actions",["Add Client","Edit Client","Add Session","Edit Session"])

            if admin_action == "Add Client":
                with st.form("Add Client Form"):
                    first_name = st.text_input("First Name")
                    last_name = st.text_input("Last Name")
                    dob = st.date_input("Date of Birth")
                    program = st.text_input("Program")
                    source = st.text_input("Source")
                    submitted = st.form_submit_button("Add Client")
                    if submitted:
                        db.collection("client").add({
                            "first_name": first_name,
                            "last_name": last_name,
                            "dob": dob.strftime('%Y-%m-%d'),
                            "program": program,
                            "source": source
                        })
                        st.success("Client added successfully!")

            elif admin_action == "Edit Client":
                selected_client = st.selectbox("Select Client",client_list)
                client_doc_id = list(client_data.keys())[client_list.index(selected_client)]
                client_details = client_data[client_doc_id]

                with st.form("Edit Client Form"):
                    first_name = st.text_input("First Name",client_details["first_name"])
                    last_name = st.text_input("Last Name",client_details["last_name"])
                    dob = st.date_input("Date of Birth",datetime.strptime(client_details["dob"],'%Y-%m-%d'))
                    program = st.text_input("Program",client_details["program"])
                    source = st.text_input("Source",client_details["source"])
                    submitted = st.form_submit_button("Update Client")
                    if submitted:
                        db.collection("client").document(client_doc_id).update({
                            "first_name": first_name,
                            "last_name": last_name,
                            "dob": dob.strftime('%Y-%m-%d'),
                            "program": program,
                            "source": source
                        })
                        st.success("Client updated successfully!")

            elif admin_action == "Add Session":

                with st.form("Add Session Form"):
                    client_id = st.selectbox("Client ID",client_list)
                    sess_date = st.date_input("Session Date")
                    exercise = st.selectbox("Select an Exercise",exercise_list)
                    set = st.number_input("Sets",min_value=1,max_value=10,value=3)
                    rep = st.number_input("Reps",min_value=1,max_value=20,value=10)
                    load_kg = st.number_input("Load (kg)",min_value=1,max_value=200,value=50)
                    submitted = st.form_submit_button("Add Session")
                    if submitted:
                        db.collection("session").add({
                            "client_id": client_id,
                            "sess_date": sess_date.strftime('%d/%m/%Y'),
                            "exercise": exercise,
                            "set": set,
                            "rep": rep,
                            "load_kg": load_kg
                        })
                        st.success("Session added successfully!")

            elif admin_action == "Edit Session":
                selected_client = st.selectbox("Select Client",client_list)
                client_doc_id = list(client_data.keys())[client_list.index(selected_client)]
                client_details = client_data[client_doc_id]

                with st.form("Edit Session Form"):
                    first_name = st.text_input("First Name",client_details["first_name"])
                    last_name = st.text_input("Last Name",client_details["last_name"])
                    dob = st.date_input("Date of Birth",datetime.strptime(client_details["dob"],'%Y-%m-%d'))
                    program = st.text_input("Program",client_details["program"])
                    source = st.text_input("Source",client_details["source"])
                    submitted = st.form_submit_button("Update Client")
                    if submitted:
                        db.collection("client").document(client_doc_id).update({
                            "first_name": first_name,
                            "last_name": last_name,
                            "dob": dob.strftime('%Y-%m-%d'),
                            "program": program,
                            "source": source
                        })
                        st.success("Client updated successfully!")
