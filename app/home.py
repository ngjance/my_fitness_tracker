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
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        username = st.session_state["username"]        
        
        # ------------------- View as Client -------------------
        if not username == "admin":

            # ------------------- Load Workout Data -------------------
            session_ref = db.collection("session").where("client_id","==",username).stream()
            session_raw = pd.DataFrame([doc.to_dict() for doc in session_ref])
    
            #-------------------engineer data-------------------
            # Duplicate raw df
            session = session_raw.copy()
            # Dropping the rows where reps are time-based
            session = session[session["rep"].str.contains("s") == False]
            # converting the string to datetime format
            session["sess_date"] = pd.to_datetime(session["sess_date"],format="%d/%m/%Y")
            # Convert "rep" to float64
            session.rep = session.rep.astype('float64')
            # Add 'One Rep Max' column to session
            session["one_rm"] = session["load_kg"] * (1 + 0.0333 * session["rep"])
            rm = session.groupby(["client_id","sess_date","exercise"])[["one_rm"]].mean().reset_index()

            if not session.empty:
                st.metric(label="**Sessions Done**", value= session['sess_date'].nunique(),delta=None,delta_color="normal",help=None,
                      label_visibility="visible",border=True)

                st.markdown("---")

                # Exercise Progress
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

                    st.write("### Exercise Progress")
                    exercise_table = rm[(rm['client_id'] == username)]
                    exercise_selected = st.selectbox("Select a exercise",exercise_table["exercise"].unique())
                    exercise_history = exercise_table[exercise_table["exercise"] == exercise_selected]
                    exercise_history = exercise_history.sort_values(by="sess_date",ascending=False)
    
                    fig = ff.create_table(exercise_history,colorscale=colorscale)
                    fig.layout.width = 1400
                    st.write(fig)
    
                    # Line chart for one rep max progression
                    fig = px.line(exercise_history.sort_values("sess_date"),x="sess_date",y="one_rm",
                                  title=f"{exercise_selected} - One Rep Max Progress")
                    st.plotly_chart(fig)


        # ------------------- View as Admin -------------------
        else:
            clients_ref = db.collection("client").stream()
            clients = [doc.to_dict() for doc in clients_ref]
            total_clients = len(clients)

            # ------------------- Load Workout Data -------------------
            sessions_ref = db.collection("session").stream()
            sessions_raw = pd.DataFrame([doc.to_dict() for doc in sessions_ref])
   
            #-------------------engineer data-------------------
            # Duplicate raw df
            session = sessions_raw.copy()
            # Dropping the rows where reps are time-based
            session = session[session["rep"].str.contains("s") == False]
            # converting the string to datetime format
            session["sess_date"] = pd.to_datetime(session["sess_date"],format="%d/%m/%Y")
            # Convert "rep" to float64
            session.rep = session.rep.astype('float64')
            # Add 'One Rep Max' column to session
            session["one_rm"] = session["load_kg"] * (1 + 0.0333 * session["rep"])
            rm = session.groupby(["client_id","sess_date","exercise"])[["one_rm"]].mean().reset_index()
            
            # session["sess_date"] = pd.to_datetime(session["sess_date"])
            current_month = datetime.today().month
            last_month = (datetime.today().replace(day=1) - pd.DateOffset(days=1)).strftime('%Y-%m')
            current_year = datetime.today().year
            active_sess = session[
                (session["sess_date"].dt.month == current_month) & (session["sess_date"].dt.year == current_year)]
            active_clients = active_sess["client_id"].unique()
            total_active_clients = len(active_clients)
            active_clients_last_month = session[session["sess_date"].dt.strftime('%Y-%m') == last_month][
                "client_id"].nunique()
            
            sessions_per_client = active_sess.groupby("client_id")[["sess_date"]].nunique()

            # st.metric(label="### **Total Clients**",value=total_clients,delta=None,delta_color="normal",
            #           help=None,
            #           label_visibility="visible",border=True)

            fig = go.Figure()
            fig.add_trace(go.Indicator(
                mode="number",
                value=total_clients,
                title={
                    "text": "Total Clients<span style='font-size:0.8em;color:black'></span>"},
                domain={'x': [0,0.5],'y': [0.6, 1]}))

            fig.add_trace(go.Indicator(
                mode="number+delta",
                value=total_active_clients,
                title={
                    "text": "MTD Active Clients<span style='font-size:0.8em;color:black'></span>"},
                delta={'reference': active_clients_last_month,'relative': True},
                domain={'x': [0, 0.5], 'y': [0, 0.5]}))

            st.write(fig)

            # st.write(f"Total Clients: {total_clients}")
            # st.write(f"MTD Active Clients: {total_active_clients}")
            st.write("### Breakdown: Sessions per Active Client:")
            st.dataframe(sessions_per_client)


