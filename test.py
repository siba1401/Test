import streamlit as st
import pandas as pd

st.title("📘 Student Exam Failure Report")

# Upload CSV file
uploaded_file = st.file_uploader("Upload Exam CSV File", type=["csv"])

if uploaded_file:
    # Step 0: Read file safely
    uploaded_file.seek(0)
    try:
        raw_bytes = uploaded_file.read()
        content = raw_bytes.decode('utf-8').strip()
        if not content:
            st.error("🚫 Uploaded file is empty. Please check your CSV file.")
            st.stop()
    except Exception as e:
        st.error(f"🚫 Error reading file: {e}")
        st.stop()

    uploaded_file.seek(0)  # Reset for pandas read_csv
    try:
        raw_df = pd.read_csv(uploaded_file, header=None)
    except pd.errors.EmptyDataError:
        st.error("🚫 CSV file is unreadable or contains no data.")
        st.stop()
    except Exception as e:
        st.error(f"🚫 Could not read CSV file: {e}")
        st.stop()

    # Step 1: Detect header row
    try:
        header_row_idx = raw_df[raw_df.apply(
            lambda row: row.astype(str).str.contains("Add.ID").any(), axis=1)].index[0]
    except IndexError:
        st.error("🚫 Could not detect header row. Ensure your file contains 'Add.ID' as a column name.")
        st.stop()

    # Step 2: Reload using multi-row header
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, header=[header_row_idx, header_row_idx + 1])
    cols_df = df.columns.to_frame(index=False)

    # Step 3: Clean column names
    cols_df[0] = cols_df[0].replace(r'^Unnamed.*', pd.NA, regex=True).fillna(method='ffill')
    cols_df[1] = cols_df[1].str.extract(r'([^_]+)$')[0]
    df.columns = [
        f"{sub.strip().replace(' ', '_')}_{main.strip().replace(' ', '_')}"
        if pd.notna(main) and main.strip() != ''
        else sub.strip().replace(' ', '_')
        for main, sub in zip(cols_df[0], cols_df[1])
    ]
    df = df.reset_index(drop=True)

    # Step 4: Process failure logic
    def process_subject_failures(df):
        subjects = {col.replace('TEE_', '') for col in df.columns if col.startswith('TEE_')}
        for subject in subjects:
            tee_col = f'TEE_{subject}'
            ica_col = f'ICA_{subject}'
            fail_col = f'Fail_Reason_{subject}'

            df[tee_col] = pd.to_numeric(df[tee_col], errors='coerce')
            df[ica_col] = pd.to_numeric(df[ica_col], errors='coerce')

            df[f'New_TEE_{subject}'] = df[tee_col] / 2
            df[f'Total_{subject}'] = df[f'New_TEE_{subject}'] + df[ica_col]
            df[f'TEE_Contribution_{subject}'] = 0.2 * (df[f'New_TEE_{subject}'] / 50) * 100
            df[f'ICA_Contribution_{subject}'] = 0.2 * (df[ica_col] / 50) * 100

            def fail_reason(row):
                if pd.isna(row[f'Total_{subject}']) or pd.isna(row[f'TEE_Contribution_{subject}']) or pd.isna(row[f'ICA_Contribution_{subject}']):
                    return "Invalid Marks"
                if row[f'Total_{subject}'] >= 40:
                    return "Pass"
                tee_low = row[f'TEE_Contribution_{subject}'] < 20
                ica_low = row[f'ICA_Contribution_{subject}'] < 20
                if tee_low and not ica_low:
                    return "Low TEE"
                elif ica_low and not tee_low:
                    return "Low ICA"
                elif tee_low and ica_low:
                    if row[f'TEE_Contribution_{subject}'] < row[f'ICA_Contribution_{subject}']:
                        return "Both TEE & ICA Low (TEE impacted more)"
                    elif row[f'ICA_Contribution_{subject}'] < row[f'TEE_Contribution_{subject}']:
                        return "Both TEE & ICA Low (ICA impacted more)"
                    else:
                        return "Both TEE & ICA Low (Equal impact)"
                return "Other Issue"

            df[fail_col] = df.apply(fail_reason, axis=1)
        return df

    df = process_subject_failures(df)

    # Step 5: Identify ID and Name columns
    add_id_col = next((col for col in df.columns if col.endswith('Add.ID')), None)
    student_name_col = next((col for col in df.columns if col.endswith('Student_Name')), None)

    if not add_id_col:
        st.error("🚫 Could not find 'Add.ID' column after parsing. Check the CSV structure.")
        st.stop()

    # Step 6: Compile failures
    failures_list = []
    borderline_tee = []
    borderline_final = []

    subjects = [col.replace("Fail_Reason_", "") for col in df.columns if col.startswith("Fail_Reason_")]
    for subject in subjects:
        fail_col = f'Fail_Reason_{subject}'
        tee_col = f'TEE_{subject}'
        total_col = f'Total_{subject}'

        failed = df[df[fail_col] != 'Pass'].copy()
        if not failed.empty:
            failed["Subject"] = subject.replace('_', ' ')
            failed["Reason"] = failed[fail_col]
            subset_cols = [add_id_col]
            if student_name_col:
                subset_cols.append(student_name_col)
            subset_cols += ["Subject", "Reason"]
            failures_list.append(failed[subset_cols].copy())

        # TEE between 37 and 39
        tee_filtered = df[(df[tee_col] >= 37) & (df[tee_col] <= 39)].copy()
        tee_filtered["Subject"] = subject.replace('_', ' ')
        tee_filtered["TEE_Score"] = tee_filtered[tee_col]
        if not tee_filtered.empty:
            subset_cols = [add_id_col]
            if student_name_col:
                subset_cols.append(student_name_col)
            subset_cols += ["Subject", "TEE_Score"]
            borderline_tee.append(tee_filtered[subset_cols].copy())

        # Final marks between 37 and 39
        final_filtered = df[(df[total_col] >= 37) & (df[total_col] <= 39)].copy()
        final_filtered["Subject"] = subject.replace('_', ' ')
        final_filtered["Final_Marks"] = final_filtered[total_col]
        if not final_filtered.empty:
            subset_cols = [add_id_col]
            if student_name_col:
                subset_cols.append(student_name_col)
            subset_cols += ["Subject", "Final_Marks"]
            borderline_final.append(final_filtered[subset_cols].copy())

    # Step 7: Output
    if failures_list:
        failures_df = pd.concat(failures_list, ignore_index=True)
        failures_df = failures_df.loc[:, ~failures_df.columns.duplicated()]
        st.subheader("🔴 Failed Students List:")
        st.dataframe(failures_df.head(100), use_container_width=True)

        csv = failures_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Full Failure Report", data=csv, file_name="failed_students.csv", mime="text/csv")
    else:
        st.success("✅ All students passed!")

    if borderline_tee:
        tee_df = pd.concat(borderline_tee, ignore_index=True)
        tee_df = tee_df.loc[:, ~tee_df.columns.duplicated()]
        st.subheader("🟠 Students with TEE Scores Between 37 and 39:")
        st.dataframe(tee_df.head(100), use_container_width=True)

        tee_csv = tee_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download TEE Borderline Report", data=tee_csv, file_name="tee_37_39.csv", mime="text/csv")

    if borderline_final:
        final_df = pd.concat(borderline_final, ignore_index=True)
        final_df = final_df.loc[:, ~final_df.columns.duplicated()]
        st.subheader("🟡 Students with Final Marks Between 37 and 39:")
        st.dataframe(final_df.head(100), use_container_width=True)

        final_csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Final Marks Borderline Report", data=final_csv, file_name="final_37_39.csv", mime="text/csv")
