import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# 1. Page Config (Best to have this at the very top)
st.set_page_config(page_title="Visitation Portal", page_icon="👤")

# --- 1. SESSION STATE & LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Visitation Portal")
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
st.title("📋 Visitation Portal")

# Main Navigation Menu
user_name = st.selectbox("Who is viewing?", options=["-- Select Name --"] + names)

if user_name != "-- Select Name --":
    st.divider()

    # Step 2: Present Menu Options based on that User
    menu_choice = st.radio(
        f"Hi {user_name}, what would you like to do?",
        ["View My Assignments", "View Scheduled Visitations"],
        horizontal=True
    )

    st.divider()

    # --- OPTION 1: PERSONAL ASSIGNMENTS ---
    if menu_choice == "View My Assignments":
        st.subheader(f"Assignments for {user_name}")

        my_assignments = [
            row for row in all_rows[4:]
            if len(row) > 6 and row[6].strip().lower() == user_name.lower()
        ]

        if my_assignments:
            for row in my_assignments:
                row_number = all_rows.index(row) + 1

                # Corrected Mapping (First Last)
                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()

                dob = row[2] if len(row) > 2 and row[2].strip() != "" else "N/A"
                anniversary = row[3] if len(row) > 3 and row[3].strip() != "" else "N/A"
                address_for_map = row[4] if len(row) > 4 else ""
                phone = row[5] if len(row) > 5 else "N/A"

                # Check Attempt Status
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

                    # 3. Progress Display
                    st.write("---")
                    if try_1 and try_2:
                        st.success("✅ **Goal Reached:** 2 of 2 attempts completed.")
                    elif try_1:
                        st.info("🟡 **Progress:** 1 of 2 attempts completed.")
                    else:
                        st.warning("⚪ **Not Started:** 0 attempts completed.")

                    # 4. Log Visit Section
                    with st.expander("📝 Log a Visitation Attempt"):
                        attempt_choice = st.selectbox(
                            "Which attempt did you complete?",
                            options=["-- Select --", "Try #1", "Try #2"],
                            key=f"status_{row_number}"
                        )

                        if st.button(f"Confirm attempt for {full_name}", key=f"btn_{row_number}"):
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

# Option 2: Scheduled Visitations
else:
    if user_name != "-- Select Name --":

        st.subheader("🗓️ Upcoming Scheduled Visitations")

        # Filter rows where Column J (index 9) is not empty
        scheduled = [row for row in all_rows[4:] if len(row) > 9 and row[9].strip() != ""]

        if not scheduled:
            st.info("No visitations are currently scheduled.")
        else:
            header_row = all_rows[3]
            officer_names = [header_row[i] for i in range(11, 19)]
            col_letters = ["L", "M", "N", "O", "P", "Q", "R", "S"]
            officer_cols = dict(zip(officer_names, col_letters))

            for row in scheduled:
                row_number = all_rows.index(row) + 1

                # --- DEFINE VARIABLES FIRST ---
                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()

                address = row[4] if len(row) > 4 else "No Address"
                visit_date = row[9]  # Column J
                visit_time = row[10] if len(row) > 10 else "TBD"  # Column K

                with st.container(border=True):
                    st.markdown(f"### 👤 {full_name}")
                    # Now visit_date and visit_time are defined and ready to go
                    st.write(f"📅 **Date:** {visit_date}    ⏰ **Time:** {visit_time}")
                    st.write(f"📍 **Location:** {address}")

                    # Attendance Check
                    attending = [all_rows[3][i] for i in range(11, 19) if len(row) > i and row[i].upper() == 'TRUE']
                    if attending:
                        st.success(f"👥 **Attending:** {', '.join(attending)}")
                    else:
                        st.caption("No officers have responded yet.")

                    # RSVP Section
                    st.divider()
                    if user_name in officer_names:
                        col_letter = officer_cols.get(user_name)
                        if user_name not in attending:
                            if st.button(f"🙋‍♂️ I can attend ({full_name})", key=f"rsvp_{row_number}"):
                                client = get_sheet_client()
                                sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").sheet1
                                sheet.update_acell(f"{col_letter}{row_number}", "TRUE")
                                st.success("RSVP Saved!")
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            st.button(f"✅ You are attending ({full_name})", disabled=True, key=f"done_{row_number}")
                    else:
                        st.warning("You are not listed in the attendance columns (L-S).")

# --- 4. EXTERNAL LINK SECTION ---
st.divider()
st.info("💡 **Tip:** If you need to view or update the spreadsheet manually, [click here](https://docs.google.com/spreadsheets/d/1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk/edit?usp=sharing).")

# Logout option in the bottom
if st.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()