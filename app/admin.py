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

        if username == "admin":
            st.sidebar.title("Admin Panel")
            admin_action = st.sidebar.radio("Choose Actions",["Add Client","Edit Client","View Client session","Add Session","Edit/Delete Workout"])

            # Fetch client data
            client_ref = db.collection("client").stream()
            client_data = {doc.id: doc.to_dict() for doc in client_ref}
            client_list = [f"{data['first_name']} {data['last_name']}" for data in client_data.values()]
            client_docs = list(client_ref)

            # Fetch session data
            session_ref = db.collection("session").stream()
            session = pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in session_ref])
            session = session[['id','client_id','sess_date','exercise','set','rep','load_kg']]

            # Fetch exercise data
            exercise_ref = db.collection("exercise").stream()
            exercise_list = [doc.to_dict()["exercise"] for doc in exercise_ref]

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

            if admin_action == "Add Client":
                with st.form("Add Client Form"):
                    client_id = st.text_input("Client ID")
                    first_name = st.text_input("First Name")
                    last_name = st.text_input("Last Name")
                    dob = st.date_input("Date of Birth")
                    program = st.text_input("Program")
                    source = st.text_input("Source")
                    submitted = st.form_submit_button("Add Client")
                    if submitted:
                        db.collection("client").add({
                            "client_id": client_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "dob": dob.strftime('%d/%m/%Y'),
                            "program": program,
                            "source": source
                        })
                        st.success("Client added successfully!")

            elif admin_action == "Edit Client":
                # client_ref = db.collection("client").where("client_id","==",username).stream()
                # client_data = {doc.id: doc.to_dict() for doc in client_ref}
                # client_list = [f"{data['first_name']} {data['last_name']}" for data in client_data.values()]

                selected_client = st.selectbox("Select Client",client_list)
                client_doc_id = list(client_data.keys())[client_list.index(selected_client)]
                client_details = client_data[client_doc_id]

                with st.form("Edit Client Form"):
                    first_name = st.text_input("First Name",client_details["first_name"])
                    last_name = st.text_input("Last Name",client_details["last_name"])
                    dob = st.date_input("Date of Birth",datetime.strptime(client_details["dob"],'%d/%m/%Y'))
                    program = st.text_input("Program",client_details["program"])
                    source = st.text_input("Source",client_details["source"])
                    submitted = st.form_submit_button("Update Client")
                    if submitted:
                        db.collection("client").document(client_doc_id).update({
                            "first_name": first_name,
                            "last_name": last_name,
                            "dob": dob.strftime('%d/%m/%Y'),
                            "program": program,
                            "source": source
                        })
                        st.success("Client updated successfully!")

            elif admin_action == "View Client session":
                selected_client = st.selectbox("Select Client",session["client_id"].unique())
                client_session = session[session["client_id"] == selected_client]
                session_selected = st.selectbox("Select a session date",client_session["sess_date"].unique())
                session_data = client_session[client_session["sess_date"] == session_selected].sort_values('sess_date',ascending=False)
                session_data = session_data.drop(['id'],axis=1)
                
                st.markdown("---")
                st.write("### Client's Session Details")
                st.write(session_data)

                st.markdown("---")

                st.write("### Client's Exercise Progress")
                exercise_table = rm[(rm['client_id'] == selected_client)]
                exercise_selected = st.selectbox("Select a exercise",exercise_table["exercise"].unique())
                exercise_history = exercise_table[exercise_table["exercise"] == exercise_selected]
                exercise_history = exercise_history.sort_values(by="sess_date",ascending=False)

                fig = ff.create_table(exercise_history)
                fig.layout.width = 1400
                st.write(fig)

                # Line chart for one rep max progression
                fig = px.line(exercise_history.sort_values("sess_date"),x="sess_date",y="one_rm",
                              title=f"{exercise_selected} - One Rep Max Progress")
                st.plotly_chart(fig)
                
            elif admin_action == "Add Session":
                with st.form("Add Session Form"):
                    client_id = st.selectbox("Client ID", session["client_id"].unique())
                    sess_date = st.date_input("Session Date")
                    exercise = st.selectbox("Select an Exercise",exercise_list)
                    sets = st.number_input("Sets",min_value=1,max_value=10,value=3)
                    reps = st.number_input("Reps",min_value=1,max_value=20,value=10)
                    load_kg = st.number_input("Load (kg)",min_value=0,max_value=200,value=50)
                    submitted = st.form_submit_button("Add Workout")
                    if submitted:
                        db.collection("session").add({
                            "client_id": client_id,
                            "sess_date": sess_date.strftime('%d/%m/%Y'),
                            "exercise": exercise,
                            "set": sets,
                            "rep": reps,
                            "load_kg": load_kg
                        })
                        st.success("Workout added successfully!")

            elif admin_action == "Edit/Delete Workout":
                st.write("### Edit/Delete Client's Workout")
                selected_client = st.selectbox("Select Client",session["client_id"].unique())
                client_session = session[session["client_id"] == selected_client]
                session_selected = st.selectbox("Select a session date",client_session["sess_date"].unique())
                session_data = client_session[client_session["sess_date"] == session_selected].sort_values('sess_date',ascending=False)
                workout_to_edit = st.selectbox("Select a workout to edit/delete",session_data["exercise"].unique())
                selected_workout = session_data[session_data["exercise"] == workout_to_edit].copy()
                workout_id = selected_workout.at[selected_workout.index[0],"id"]

                sets = st.number_input("Sets",min_value=1,max_value=10,value=int(selected_workout["set"].iloc[0]))
                reps = st.number_input("Reps",min_value=1,max_value=20,value=int(selected_workout["rep"].iloc[0]))
                load = st.number_input("Load (kg)",min_value=0,max_value=200,value=int(selected_workout["load_kg"].iloc[0]))

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
