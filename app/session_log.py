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
    # ------------------- Load Data -------------------
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        username = st.session_state["username"]
        if not username == "admin":
            client_ref = db.collection("client").where("client_id","==",username).stream()
            client_data = {doc.id: doc.to_dict() for doc in client_ref}

            session_ref = db.collection("session").where("client_id","==",username).stream()
            session = pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in session_ref])

            # ------------------- Engineer Data -------------------

            # Dropping the rows where reps are time-based
            session = session = session[~session["rep"].astype(str).str.contains("s", na=False)]
            # converting the string to datetime format
            session["sess_date"] = pd.to_datetime(session["sess_date"],format="%d/%m/%Y")
            # Convert "rep" to float64
            session.rep = session.rep.astype('float64')
            # Add 'One Rep Max' column to session
            session["one_rm"] = session["load_kg"] * (1 + 0.0333 * session["rep"])
            rm = session.groupby(["client_id","sess_date","exercise"])[["one_rm"]].mean().reset_index()

            st.markdown("---")

            if not session.empty:
                st.sidebar.title("Session Logs")
                sess_action = st.sidebar.radio("To View",["Session Details", "Add Workout", "Edit/Delete Workout"])

                # session = session[['client_id','sess_date','exercise','set','rep','load_kg']]
                session = session[['id','client_id','sess_date','exercise','set','rep','load_kg']]
                sess_table = session[(session['client_id'] == username)].sort_values('sess_date',ascending=False)
                session_selected = st.selectbox("Select a session date",sess_table["sess_date"].unique())
                session_data = sess_table[sess_table["sess_date"] == session_selected].sort_values('sess_date', ascending=False)
                session_dates = session["sess_date"].unique()

                # Show what was done for Selected Session
                if sess_action == "Session Details":

                    dataset = st.container()
                    with dataset:
                        st.markdown("""
                                   <style>
                                   .big-font {
                                       font-size:38px;
                                   }
                                   </style>
                                   """,unsafe_allow_html=True)

                    colorscale = [[0,'#4d004c'],[.5,'#ffffff'],[1,'#ffffff']]

                    st.write("### Session Details")

                    fig = ff.create_table(session_data)
                    fig.layout.width = 2000
                    st.write(fig)

                # Add Workouts
                elif sess_action == "Add Workout":
                    st.write("## Add New Workout Session")

                    session_date = st.date_input("Select Date")
                    exercise_ref = db.collection("exercise").stream()
                    exercise_list = [doc.to_dict()["exercise"] for doc in exercise_ref]
                    exercise_selected = st.selectbox("Select an Exercise",exercise_list)
                    sets = st.number_input("Sets",min_value=1,max_value=10,value=3)
                    reps = st.number_input("Reps",min_value=1,max_value=20,value=10)
                    load = st.number_input("Load (kg)",min_value=0,max_value=200,value=50)

                    if st.button("Add Workout"):
                        db.collection("session").add({
                            "client_id": username,
                            "sess_date": session_date.strftime('%d/%m/%Y'),
                            "exercise": exercise_selected,
                            "set": sets,
                            "rep": reps,
                            "load_kg": load
                        })
                        st.success("Workout added successfully!")
                        st.rerun()

                # Edit/Delete Workouts
                elif sess_action == "Edit/Delete Workout":
                    st.write("### Edit/Delete Workout")
                    workout_to_edit = st.selectbox("Select a workout to edit/delete",session_data["exercise"].unique())
                    selected_workout = session_data[session_data["exercise"] == workout_to_edit].copy()
                    workout_id = selected_workout.at[selected_workout.index[0],"id"]

                    sets = st.number_input("Sets",min_value=1,max_value=10,value=int(selected_workout["set"].iloc[0]))
                    reps = st.number_input("Reps",min_value=1,max_value=20,value=int(selected_workout["rep"].iloc[0]))
                    load = st.number_input("Load (kg)",min_value=0,max_value=200, value=int(selected_workout["load_kg"].iloc[0]))

                    if st.button("Update Workout"):
                        db.collection("session").document(workout_id).update({
                            "set": sets,
                            "rep": reps,
                            "load_kg": load
                        })
                        st.success("Workout updated successfully!")
                        st.rerun()

                    if st.button("Delete Workout"):
                        db.collection("session").document(workout_id).delete()
                        st.success("Workout deleted successfully!")
                        st.rerun()   
