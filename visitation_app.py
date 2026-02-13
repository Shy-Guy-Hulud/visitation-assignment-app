import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SESSION STATE & LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Officer Portal")
    with st.form("login_form"):
        pwd_input = st.text_input("Enter Access Code", type="password")
        if st.form_submit_button("Login"):
            if pwd_input == st.secrets["APP_PASSWORD"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid Code")
    st.stop()


# --- 2. DATA FETCHING ---
@st.cache_data(ttl=600)  # Refreshes every 10 mins
def get_sheet_data():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").sheet1
    return sheet.get_all_values()


all_rows = get_sheet_data()

@st.cache_resource
def get_sheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scopes)
    return gspread.authorize(creds)

# Get list of officers for the dropdown
names = sorted(list(set(
    row[6].strip()
    for row in all_rows[4:]
    if len(row) > 6 and row[6].strip() != ""
)))

# --- 3. MAIN UI ---
st.title("📋 My Visitation Assignments")
st.write("Select your name below to view your current assignments.")

user_name = st.selectbox("Who is viewing?", options=["-- Select Name --"] + names)

if user_name != "-- Select Name --":
    st.divider()
    st.subheader(f"Assignments for {user_name}")

    # Filter rows for the selected officer
    my_assignments = [
        row for row in all_rows[4:]
        if len(row) > 6 and row[6].strip().lower() == user_name.lower()
    ]

    if my_assignments:
        for row in my_assignments:
            # Calculate real row number (Data starts on Row 1, index 0)
            row_number = all_rows.index(row) + 1

            # Mapping
            first_name = row[0] if len(row) > 0 else ""
            last_name = row[1] if len(row) > 1 else ""
            full_name = f"{first_name} {last_name}".strip()
            dob = row[2] if len(row) > 2 and row[2].strip() != "" else "N/A"
            anniversary = row[3] if len(row) > 3 and row[3].strip() != "" else "N/A"
            address_for_map = row[4] if len(row) > 4 else ""
            phone = row[5] if len(row) > 5 else "N/A"

            # Check Attempt Status (Col H index 7, Col I index 8)
            try_1 = len(row) > 7 and row[7].upper() == 'TRUE'
            try_2 = len(row) > 8 and row[8].upper() == 'TRUE'

            with st.container(border=True):
                # 1. Header and Dates
                st.markdown(f"### 👤 {full_name}")
                st.markdown(f"🎂 **DOB:** {dob}    💍 **Married:** {anniversary}")

                # 2. Action Buttons (Phone & Maps)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"📞 [{phone}](tel:{phone.replace('-', '').replace(' ', '')})")
                with col2:
                    if address_for_map:
                        map_search_url = f"https://www.google.com/maps/search/?api=1&query={address_for_map.replace(' ', '+')}"
                        st.link_button("🗺️ Open Maps", map_search_url, use_container_width=True)
                    else:
                        st.button("No Address Found", disabled=True, use_container_width=True)

                # 3. Progress Display (Now underneath buttons)
                st.write("---")
                if try_1 and try_2:
                    st.success("✅ **Goal Reached:** 2 of 2 attempts completed.")
                elif try_1:
                    st.info("🟡 **Progress:** 1 of 2 attempts completed.")
                else:
                    st.warning("⚪ **Not Started:** 0 attempts completed.")

                # 4. Log Visit Section
                with st.expander("📝 Log a Member Contact"):
                    attempt_choice = st.selectbox(
                        "Which attempt did you complete?",
                        options=["-- Select --", "Try #1", "Try #2"],
                        key=f"status_{row_number}"
                    )

                    if st.button(f"Confirm Visit for {full_name}", key=f"btn_{row_number}"):
                        if attempt_choice == "-- Select --":
                            st.warning("Please select an attempt number.")
                        else:
                            client = get_sheet_client()
                            sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").sheet1
                            col_to_update = "H" if attempt_choice == "Try #1" else "I"

                            with st.spinner("Updating spreadsheet..."):
                                sheet.update_acell(f"{col_to_update}{row_number}", "TRUE")
                                st.success("Updated!")
                                st.cache_data.clear()
                                st.rerun()
    else:
        st.info("No active assignments found for you at this time.")

# Logout option in the bottom
if st.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()