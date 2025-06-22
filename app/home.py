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
credentials_dict = {}
for user in users_ref:
    user_data = user.to_dict()
    if "username" in user_data:
        credentials_dict[user_data["username"]] = user_data

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
            # Fetch session data
            session_ref = db.collection("session").where("client_id","==",username).stream()
            session = pd.DataFrame([doc.to_dict() for doc in session_ref])

            # Fetch client data
            client_ref = db.collection("client").where("client_id","==",username).stream()
            client_data = {doc.id: doc.to_dict() for doc in client_ref}

            # Fetch body_composition data
            body_com_ref = db.collection("body_composition").where("client_id","==",username).stream()
            body_com = pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in body_com_ref])

            # Fetch activity_level data
            activity_level_ref = db.collection("activity_level").stream()
            activity_level = pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in activity_level_ref])

            # Fetch goal_diet data
            goal_diet_ref = db.collection("goal_diet").stream()
            goal_diet = pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in goal_diet_ref])

            # Fetch exercise data
            exercise_ref = db.collection("exercise").stream()
            exercise_list = [doc.to_dict()["exercise"] for doc in exercise_ref]

            # -------------------engineer data-------------------

            # Dropping the rows where reps are time-based
            # session = session[session["rep"].str.contains("s") == False]
            session = session[~session["rep"].astype(str).str.contains("s",na=False)]
            # converting the string to datetime format
            session["sess_date"] = pd.to_datetime(session["sess_date"],format="%d/%m/%Y")
            # Convert "rep" to float64
            session.rep = session.rep.astype('float64')
            # Add 'One Rep Max' column to session
            session["one_rm"] = session["load_kg"] * (1 + 0.0333 * session["rep"])
            rm = session.groupby(["client_id","sess_date","exercise"])[["one_rm"]].mean().reset_index()

            # Convert to float
            body_com = body_com.astype({'body_wt_kg': 'float','body_fats_%': 'float'})
            # Add 'fat_mass' column to body_com
            body_com["fat_mass"] = body_com["body_wt_kg"] * body_com["body_fats_%"] / 100
            # Add 'lean_mass' column to body_com
            body_com["lean_mass"] = body_com["body_wt_kg"] - body_com["fat_mass"]
            # Add 'age' column to body_com
            today = pd.to_datetime("today")
            body_com["dob"] = pd.to_datetime(body_com["dob"],format="%d/%m/%Y")
            body_com["age"] = body_com["dob"].apply(lambda dob: today.year - dob.year - ((today.month,today.day) < (dob.month,dob.day)))
            # Add 'bmr' column to body_com
            body_com["bmr"] = 10*body_com["body_wt_kg"]+6.25*body_com["ht_cm"]-5*body_com["age"]+5
            # Merge body_com, activity_level and goal_diet
            body_com_merged = body_com.merge(activity_level,on='activity_level').merge(goal_diet,on='diet')
            # Add 'tee' column to body_com_merged
            body_com_merged["tee"] = body_com_merged["bmr"] * body_com_merged["bmr_multiplier"]
            # Add 'goal_cal' column to body_com_merged
            body_com_merged["goal_cal"] = body_com_merged["tee"] + body_com_merged["cal_adjustment"]
            # Add 'goal_pro' column to body_com_merged
            body_com_merged["goal_pro"] = body_com_merged["goal_cal"] * body_com_merged["protein_%"]/100/4
            # Add 'goal_carbs' column to body_com_merged
            body_com_merged["goal_carbs"] = body_com_merged["goal_cal"] * body_com_merged["carbs_%"] / 100 / 4
            # Add 'goal_fats' column to body_com_merged
            body_com_merged["goal_fats"] = body_com_merged["goal_cal"] * body_com_merged["fats_%"] / 100 / 9
            # Rounding
            body_com_merged.round({'body_wt_kg': 2,'body_fats_%': 2,'fat_mass': 2,'lean_mass': 2,'bmr': 0,'tee': 0,'goal_cal': 0,'goal_pro': 0,'goal_carbs': 0,'goal_fats': 0})

            # Add time periods
            session["month"] = session["sess_date"].dt.to_period("M")
            # session["week"] = session["sess_date"].dt.to_period("W")

            # Group session counts
            monthly_sessions = session.groupby("month")["sess_date"].nunique().reset_index()
            monthly_sessions.columns = ["Year-Month", "No. of Sessions"]
            # weekly_sessions = session.groupby("week")["sess_date"].nunique()

            # Ensure 'Year-Month' is a string for matching
            monthly_sessions["Year-Month"] = monthly_sessions["Year-Month"].astype(str)

            # Get current year-month as string
            current_year_month = pd.to_datetime("today").strftime("%Y-%m")

            # Get sessions for current month
            sess_current_month = monthly_sessions.loc[
                monthly_sessions["Year-Month"] == current_year_month,"No. of Sessions"
            ].values
            sess_current_month = int(sess_current_month[0]) if len(sess_current_month) > 0 else 0


            if not body_com_merged.empty:
                # Dropna values once and reuse them
                goal_calories = body_com_merged["goal_cal"].dropna()
                bmr = body_com_merged["bmr"].dropna()
                tee = body_com_merged["tee"].dropna()
                weight = body_com_merged["body_wt_kg"].dropna()
                fats = body_com_merged["body_fats_%"].dropna()
                lean_mass = body_com_merged["lean_mass"].dropna()
                fat_mass = body_com_merged["fat_mass"].dropna()

                st.write("### Body Composition")
                a, b = st.columns(2)
                if not bmr.empty:
                    a.metric(label="**BMR**", value=body_com_merged["bmr"].round(0).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)
                if not tee.empty:
                    b.metric(label="**TEE**", value=body_com_merged["tee"].round(0).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)

                a, b, c, d = st.columns(4)
                if not weight.empty:
                    a.metric(label="**Body Weight in KG**",
                             value=body_com_merged["body_wt_kg"].round(2).dropna().iloc[-1], delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)
                if not fats.empty:
                    b.metric(label="**Body Fats %**", value=body_com_merged["body_fats_%"].round(2).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)
                if not lean_mass.empty:
                    c.metric(label="**Fat Free Mass in KG**",
                             value=body_com_merged["lean_mass"].round(2).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)
                if not fat_mass.empty:
                    d.metric(label="**Fat Mass in KG**", value=body_com_merged["fat_mass"].round(2).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)

                st.write("### Macros Goals")
                if not goal_calories.empty:
                    st.metric(label="**Calories Goal**", value=body_com_merged["goal_cal"].round(0).dropna().iloc[-1],
                              delta=None,
                              delta_color="normal", help=None,
                              label_visibility="visible", border=True)

                a, b, c = st.columns(3)
                if not goal_calories.empty:
                    a.metric(label="**Protein Goal in Grams**",
                             value=body_com_merged["goal_pro"].round(0).dropna().iloc[-1], delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)

                    b.metric(label="**Carbs Goal in Grams**",
                             value=body_com_merged["goal_carbs"].round(0).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)

                    c.metric(label="**Fats Goal in Grams**",
                             value=body_com_merged["goal_fats"].round(0).dropna().iloc[-1],
                             delta=None,
                             delta_color="normal", help=None,
                             label_visibility="visible", border=True)

                st.markdown("---")
            st.write("### Workouts Overview")
            if not session.empty:
                st.metric(label="**TOTAL Sessions Done**", value= session['sess_date'].nunique(),delta=None,delta_color="normal",help=None,
                      label_visibility="visible",border=True)

                a,b = st.columns(2)
                a.metric(label="**Sessions This Month**",value=sess_current_month)

                st.write("#### No. of Sessions by Month")
                colorscale = [[0,'#4d004c'],[.5,'#ffffff'],[1,'#ffffff']]
                fig = ff.create_table(monthly_sessions,colorscale = colorscale)
                fig.layout.width = 1400
                st.write(fig)

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
            session = session = session[~session["rep"].astype(str).str.contains("s", na=False)]
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


