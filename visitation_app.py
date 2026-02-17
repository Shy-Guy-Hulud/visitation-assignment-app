import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime
import requests

def send_telegram_message(message, chat_id):
    """Sends a notification via your existing Telegram bot."""
    token = st.secrets["TELEGRAM_TOKEN"] # Updated key
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Failed to send Telegram notification: {e}")

# 1. Page Config (Best to have this at the very top)
st.set_page_config(page_title="Visitation App", page_icon="👤")

# --- 1. SESSION STATE & LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Visitation App")
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
@st.cache_resource
def get_tab_names():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk")
    # Get all worksheet titles
    return [sh.title for sh in spreadsheet.worksheets()]

@st.cache_data(ttl=600)
def get_sheet_data(tab_name):
    # (Existing code to fetch all_rows)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").worksheet(tab_name)
    return sheet.get_all_values()

# --- INITIAL LOAD ---
available_tabs = get_tab_names()
hidden_tabs = ["Monthly Template", "Roster"]
month_list = [t for t in available_tabs if t not in hidden_tabs]

# Determine the safe starting tab
current_month_name = datetime.datetime.now().strftime("%B")
if current_month_name in month_list:
    initial_tab = current_month_name
else:
    initial_tab = month_list[0] if month_list else None

if not initial_tab:
    st.error("No month tabs found!")
    st.stop()

all_rows = get_sheet_data(initial_tab)

# (Names list logic follows...)

names = sorted(list(set(
    row[6].strip()
    for row in all_rows[4:]
    if len(row) > 6 and row[6].strip() != ""
)))

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
st.title("📋 Visitation App")

user_name = st.selectbox("Who is viewing?", options=["-- Select Name --"] + names)

if user_name != "-- Select Name --":
    # (Admin notification logic remains the same)

    # 1. Dynamic Month Selector
    # Use initial_tab to set the default index
    try:
        default_idx = month_list.index(initial_tab)
    except ValueError:
        default_idx = 0

    target_tab = st.selectbox("Select Month to View", options=month_list, index=default_idx)

    # 2. Re-fetch data ONLY if the user changes the dropdown
    if target_tab != initial_tab:
        all_rows = get_sheet_data(target_tab)

    st.divider()

    # Step 2: Present THREE Menu Options
    menu_choice = st.radio(
        f"Hi {user_name}, what would you like to do?",
        ["View My Assignments", "View Scheduled Visitations", "Assign officers (leadership)"],
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
                last_visited = row[20] if len(row) > 20 and row[20].strip() != "" else None
                address_for_map = row[4] if len(row) > 4 else ""
                phone = row[5] if len(row) > 5 else "N/A"

                # Check Attempt Status
                try_1 = len(row) > 7 and row[7].upper() == 'TRUE'
                try_2 = len(row) > 8 and row[8].upper() == 'TRUE'

                with st.container(border=True):
                    # 1. Header and Dates
                    st.markdown(f"### 👤 {full_name}")
                    st.markdown(f"🎂 **DOB:** {dob}    💍 **Married:** {anniversary}")

                    # Display Last Visited only if it exists
                    if last_visited:
                        st.info(f"🕒 **Last Visited:** {last_visited}")

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
                                sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").worksheet(target_tab)
                                col_to_update = "H" if attempt_choice == "Try #1" else "I"

                                with st.spinner("Updating spreadsheet..."):
                                    sheet.update_acell(f"{col_to_update}{row_number}", "TRUE")
                                    st.success("Updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                    # --- NEW: SCHEDULE VISITATION SECTION ---
                    with st.expander("📅 Schedule a Future Visitation"):
                        st.write(
                            f"Have you been able to schedule a visitation for **{full_name}**? If so, enter the details below:")

                        col_d, col_t = st.columns(2)
                        with col_d:
                            # 'format' changes how it looks in the app
                            v_date = st.date_input(
                                "Select Date",
                                key=f"date_in_{row_number}",
                                format="MM/DD/YYYY"
                            )
                        with col_t:
                            # 1. Generate a clean list of 30-minute increments
                            time_options = []
                            periods = ["AM", "PM"]
                            # We'll use 12, then 1-11 to keep the standard clock order
                            hours = [12] + list(range(1, 12))

                            for period in periods:
                                for hour in hours:
                                    # format to 2 digits for cleaner look, e.g., "01:00 PM"
                                    h_str = str(hour).zfill(2)
                                    time_options.append(f"{h_str}:00 {period}")
                                    time_options.append(f"{h_str}:30 {period}")

                            # 2. Let the user pick from the list
                            # Setting index 26 usually lands on 01:00 PM
                            selected_time_str = st.selectbox(
                                "Select Time",
                                options=time_options,
                                index=26 if len(time_options) > 26 else 0,
                                key=f"time_select_{row_number}"
                            )

                        if st.button("Save Schedule", key=f"sched_btn_{row_number}"):
                            client = get_sheet_client()
                            sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").worksheet(
                                target_tab)

                            # Format for the Google Sheet
                            date_str = v_date.strftime("%m/%d/%Y")
                            # FIX: Use the string from the selectbox directly
                            time_str = selected_time_str

                            with st.spinner("Saving to spreadsheet..."):
                                sheet.update_acell(f"J{row_number}", date_str)
                                sheet.update_acell(f"K{row_number}", time_str)

                                # --- UPDATED: NOTIFY ALL OFFICERS INDIVIDUALLY ---
                                app_url = "https://visitation-assignment-app.streamlit.app/"
                                officer_map = st.secrets["USER_MAP"]

                                notification_msg = (
                                    f"📅 **New Visitation Scheduled!**\n\n"
                                    f"A visitation has been scheduled for **{full_name}** on {date_str} at {time_str}.\n\n"
                                    f"Please click the link below to let everyone know if you can attend:\n"
                                    f"{app_url}"
                                )

                                # This loops through every officer in your secrets and sends a DM
                                for off_name, chat_id in officer_map.items():
                                    try:
                                        send_telegram_message(notification_msg, chat_id)
                                    except Exception as e:
                                        st.error(f"Could not notify {off_name}: {e}")

                                st.success(f"Scheduled and all officers notified!")
                                st.cache_data.clear()
                                st.rerun()
                        st.caption("⚠️ **FYI:** Clicking the button above will immediately notify the rest of the officers via Telegram.")
        else:
            st.info("No active assignments found for you at this time.")

    # Option 2: Scheduled Visitations
    elif menu_choice == "View Scheduled Visitations":
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

                            st.caption(f"💡 Click the button below if you can make the visitation for **{full_name}**")

                            if st.button(f"🙋‍♂️ I can attend ({full_name})", key=f"rsvp_{row_number}"):
                                client = get_sheet_client()
                                sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").worksheet(target_tab)
                                sheet.update_acell(f"{col_letter}{row_number}", "TRUE")
                                st.success("RSVP Saved!")
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            st.button(f"✅ You are attending ({full_name})", disabled=True, key=f"done_{row_number}")
                    else:
                        st.warning("You are not listed in the attendance columns (L-S).")

    # --- OPTION 3: ASSIGN OFFICERS ---
    else:
        st.subheader("🛠️ Assign Officers (Leadership)")

        all_members = [
            row for row in all_rows[4:]
            if len(row) > 19 and str(row[19]).strip().upper() == "YES"
        ]

        if not all_members:
            st.warning("⚠️ No members found. Ensure Column T is 'YES' in the spreadsheet.")
        else:
            # --- 1. BATCH NOTIFICATION SECTION ---
            st.info("Assign everyone first, then use the button below to notify all officers.")

            with st.container(border=True):
                col_notif, col_switch = st.columns([2, 1])
                with col_switch:
                    confirm_all = st.toggle("Unlock Batch Notify", key="unlock_top")
                with col_notif:
                    if st.button("📢 Send New Assignments via Telegram", disabled=not confirm_all,
                                 type="primary", use_container_width=True):

                        officer_map = st.secrets["USER_MAP"]
                        notified_count = 0
                        summary = {}

                        # Loop 1: Just gather data for the messages
                        for row in all_members:
                            off = row[6].strip().title() if len(row) > 6 else ""
                            member_name = f"{row[1]} {row[0]}".strip()

                            if off in officer_map:
                                if off not in summary: summary[off] = []
                                summary[off].append(member_name)

                        # Loop 2: Send the grouped messages
                        for off, assigned_members in summary.items():
                            # The URL of your web app
                            app_url = "https://visitation-assignment-app.streamlit.app/"

                            # Constructing the clean Markdown message
                            msg = (
                                f"📋 **{target_tab} Visitation Assignments Have Been Made**\n\n"
                                f"To see your assignments, [click here]({app_url})"
                            )

                            send_telegram_message(msg, officer_map[off])
                            notified_count += 1

                        # SUCCESS MESSAGE: Now safely inside the button logic
                        st.success(f"Sent summaries to {notified_count} officers!")

            st.divider()

            # --- 2. INDIVIDUAL MEMBER CARDS SECTION ---
            # Loop 3: Create the UI cards
            for row in all_members:
                row_idx = all_rows.index(row)
                row_number = row_idx + 1
                unique_key = f"{target_tab}_{row_number}"

                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()
                current_officer = row[6].strip() if len(row) > 6 else ""
                last_visited = row[20] if len(row) > 20 and row[20].strip() != "" else None

                with st.container(border=True):
                    col_info, col_action = st.columns([1.5, 1])
                    with col_info:
                        st.markdown(f"### {full_name}")
                        if last_visited:
                            st.write(f"🕒 **Last Visited:** {last_visited}")
                        st.caption(f"📍 Currently: **{current_officer if current_officer else 'Unassigned'}**")

                    with col_action:
                        try:
                            default_index = names.index(current_officer) + 1 if current_officer in names else 0
                        except ValueError:
                            default_index = 0

                        new_assignment = st.selectbox(
                            "Assign:",
                            options=["-- Select --"] + names,
                            index=default_index,
                            key=f"reassign_{unique_key}"
                        )

                        if new_assignment != current_officer and new_assignment != "-- Select --":
                            if st.button("Update Sheet", key=f"upd_btn_{unique_key}"):
                                client = get_sheet_client()
                                sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").worksheet(
                                    target_tab)
                                with st.spinner(f"Updating {full_name}..."):
                                    sheet.update_acell(f"G{row_number}", new_assignment)
                                    st.success("Updated!")
                                    st.cache_data.clear()
                                    st.rerun()

# --- 4. EXTERNAL LINK SECTION ---
st.divider()
st.info("💡 **Tip:** If you need to view or update the spreadsheet manually, [click here](https://docs.google.com/spreadsheets/d/1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk/edit?usp=sharing).")

# Logout option in the bottom
if st.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()