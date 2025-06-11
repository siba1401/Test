# Step 1: Load the raw file
file_path = "Exam_2.csv"  # Update this with your actual path
raw_df = pd.read_csv(file_path, header=None)

# Step 2: Detect the header row (where "Add.ID" first appears)
header_row_idx = raw_df[raw_df.apply(lambda row: row.astype(str).str.contains("Add.ID").any(), axis=1)].index[0]

# Step 3: Reload using multi-row header
df = pd.read_csv(file_path, header=[header_row_idx, header_row_idx + 1])
cols_df = df.columns.to_frame(index=False)
# Step 4: Clean column names
cols_df[0] = cols_df[0].replace(r'^Unnamed.*', pd.NA, regex=True).fillna(method='ffill')
cols_df[1] = cols_df[1].str.extract(r'([^_]+)$')[0]
df.columns = [
    f"{sub.strip().replace(' ', '_')}_{main.strip().replace(' ', '_')}"
    if pd.notna(main) and main.strip() != ''
    else sub.strip().replace(' ', '_')
    for main, sub in zip(cols_df[0], cols_df[1])
]
df = df.reset_index(drop=True)

def process_subject_failures(df):
    subjects = set()
    for col in df.columns:
        if col.startswith('TEE_'):
            subject = col.replace('TEE_', '')
            subjects.add(subject)

    for subject in subjects:
        tee_col = f'TEE_{subject}'
        ica_col = f'ICA_{subject}'
        fail_col = f'Fail_Reason_{subject}'

        # 🔁 Convert to numeric
        df[tee_col] = pd.to_numeric(df[tee_col], errors='coerce')
        df[ica_col] = pd.to_numeric(df[ica_col], errors='coerce')

        # Calculate new fields
        df[f'New_TEE_{subject}'] = df[tee_col] / 2
        df[f'Total_{subject}'] = df[f'New_TEE_{subject}'] + df[ica_col]
        df[f'TEE_Contribution_{subject}'] = 0.2 * (df[f'New_TEE_{subject}'] / 50) * 100
        df[f'ICA_Contribution_{subject}'] = 0.2 * (df[ica_col] / 50) * 100

        def fail_reason(row):
            if pd.isna(row[f'Total_{subject}']) or pd.isna(row[f'TEE_Contribution_{subject}']) or pd.isna(row[f'ICA_Contribution_{subject}']):
                return "Invalid Marks"

            total = row[f'Total_{subject}']
            tee_contrib = row[f'TEE_Contribution_{subject}']
            ica_contrib = row[f'ICA_Contribution_{subject}']

            if total >= 40:
                return "Pass"

            tee_low = tee_contrib < 20
            ica_low = ica_contrib < 20

            if tee_low and not ica_low:
                return "Low TEE"
            elif ica_low and not tee_low:
                return "Low ICA"
            elif tee_low and ica_low:
                if tee_contrib < ica_contrib:
                    return "Both TEE & ICA Low (TEE impacted more)"
                elif ica_contrib < tee_contrib:
                    return "Both TEE & ICA Low (ICA impacted more)"
                else:
                    return "Both TEE & ICA Low (Equal impact)"
            else:
                return "Other Issue"

        df[fail_col] = df.apply(fail_reason, axis=1)

    return df
# Apply the processing
df = process_subject_failures(df)

# Step 6: Identify columns
add_id_col = [col for col in df.columns if col.endswith('Add.ID')][0]
student_name_col = next((col for col in df.columns if col.endswith('Student_Name')), None)

# Step 7: Collect all failed students in a combined DataFrame
failures_list = []
subjects = [col.replace("Fail_Reason_", "") for col in df.columns if col.startswith("Fail_Reason_")]

for subject in subjects:
    fail_col = f'Fail_Reason_{subject}'
    failed = df[df[fail_col] != 'Pass'].copy()
    if not failed.empty:
        failed["Subject"] = subject.replace('_', ' ')
        failed["Reason"] = failed[fail_col]
        subset_cols = [add_id_col]
        if student_name_col:
            subset_cols.append(student_name_col)
        subset_cols += ["Subject", "Reason"]
        failures_list.append(failed[subset_cols])

# Step 8: Combine all failed records
failures_df = pd.concat(failures_list, ignore_index=True)

# Step 9: Display final result
print("🔴 All Failed Students (combined):")
failures_df.head(100)
