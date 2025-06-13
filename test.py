import streamlit as st
import pandas as pd
import numpy as np

st.title("📘 Student Exam Failure & Simulation Report")

uploaded_file = st.file_uploader("Upload Exam CSV File", type=["csv"])

if uploaded_file:
    uploaded_file.seek(0)
    raw_df = pd.read_csv(uploaded_file, header=None)

    header_row_idx = raw_df[raw_df.apply(lambda row: row.astype(str).str.contains("Add.ID").any(), axis=1)].index[0]
    subject_row = raw_df.iloc[header_row_idx].fillna(method='ffill')
    component_row = raw_df.iloc[header_row_idx + 1].fillna("")
    columns = pd.MultiIndex.from_arrays([subject_row.values, component_row.values])
    raw_df.columns = columns

    df = raw_df.drop(index=list(range(header_row_idx + 2))).reset_index(drop=True)

    # Identify and remove total marks row
    total_marks_row_idx = df[df.apply(lambda row: row.astype(str).str.contains(r'\d+\s*marks', case=False).any(), axis=1)].index
    if not total_marks_row_idx.empty:
        total_marks_row = df.loc[total_marks_row_idx[0]]
        df = df.drop(index=total_marks_row_idx[0]).reset_index(drop=True)
    else:
        total_marks_row = pd.Series(dtype=object)

    # --- Extract total marks into dictionary and table ---
    total_marks_dict = {}
    total_marks_table = []

    for (subject, component), value in total_marks_row.items():
        if pd.isna(value):
            continue
        try:
            value_str = str(value).strip()
            mark = int(value_str.split()[0])  # e.g., from "100 Marks"

            subject = subject.strip()
            component = component.strip()

            key1 = f"{component}_{subject}"
            key2 = f"{subject}_{component}"

            total_marks_dict[key1] = mark
            total_marks_dict[key2] = mark

            total_marks_table.append({
                "Subject": subject,
                "Component": component,
                "Total Marks": mark
            })
        except Exception:
            continue

    # --- Display total marks table ---
    if total_marks_table:
        st.subheader("📋 Total Marks for Each Subject Component")
        st.dataframe(pd.DataFrame(total_marks_table), use_container_width=True)

    # Flatten column names
    df.columns = [f"{component.strip()}_{subject.strip()}" if component else subject.strip() for subject, component in df.columns]

    # Convert all columns where possible
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors='ignore')
        except:
            continue

    # Detect important columns
    tee_cols = [col for col in df.columns if col.startswith("TEE_")]
    ica_cols = [col for col in df.columns if col.startswith("ICA_")]
    final_cols = [col for col in df.columns if "Final" in col]

    id_cols = [col for col in df.columns if 'Add.ID' in col or 'Student' in col]
    percent_df = df[id_cols].copy()
    has_percent_data = False

    # Compute TEE% and ICA% based on available total marks
    for col in tee_cols + ica_cols:
        if col in total_marks_dict and total_marks_dict[col] != 0:
            percent_df[f"{col}_Percent"] = pd.to_numeric(df[col], errors='coerce') / total_marks_dict[col] * 100
            percent_df[col] = pd.to_numeric(df[col], errors='coerce')
            has_percent_data = True

    if has_percent_data:
        st.subheader("📊 TEE% and ICA% per Subject")
        st.dataframe(percent_df, use_container_width=True)

        # User-defined TEE percentage range
        st.subheader("🎯 Filter Students by TEE Percentage")
        min_percent = st.number_input("Minimum TEE%", value=37.0, step=0.1)
        max_percent = st.number_input("Maximum TEE%", value=39.0, step=0.1)

        borderline_rows = []
        for col in tee_cols:
            percent_col = f"{col}_Percent"
            if percent_col in percent_df.columns:
                filtered_mask = (percent_df[percent_col] >= min_percent) & (percent_df[percent_col] <= max_percent)
                filtered_idx = percent_df[filtered_mask].index
                if not filtered_idx.empty:
                    subject = col.replace("TEE_", "")
                    tee_scores = pd.to_numeric(df.loc[filtered_idx, col], errors='coerce')
                    ica_col = f"ICA_{subject}"
                    ica_scores = pd.to_numeric(df.loc[filtered_idx, ica_col], errors='coerce') if ica_col in df.columns else pd.Series(np.nan, index=filtered_idx)

                    final_col = next((c for c in df.columns if ("Final_Marks" in c or "Final Marks" in c) and subject in c), None)
                    grade_col = next((c for c in df.columns if ("Final_Grade" in c or "Final Grade" in c) and subject in c), None)

                    final_scores = pd.to_numeric(df.loc[filtered_idx, final_col], errors='coerce') if final_col else pd.Series(np.nan, index=filtered_idx)
                    grades = df.loc[filtered_idx, grade_col] if grade_col else pd.Series(np.nan, index=filtered_idx)

                    filtered = percent_df.loc[filtered_idx].copy()
                    filtered["Subject"] = subject
                    filtered["TEE"] = tee_scores.values
                    filtered["ICA"] = ica_scores.values
                    filtered["Final_Marks"] = final_scores.values
                    filtered["Final_Grade"] = grades.values
                    filtered["TEE_Percentage"] = filtered[percent_col].values
                    borderline_rows.append(filtered)

        if borderline_rows:
            borderline_df = pd.concat(borderline_rows, ignore_index=True)
            st.subheader(f"🟡 Students with TEE% between {min_percent}% and {max_percent}%")
            display_cols = id_cols + ["Subject", "TEE", "ICA", "Final_Marks", "Final_Grade", "TEE_Percentage"]
            st.dataframe(borderline_df[display_cols], use_container_width=True)

            # Simulation section
            st.subheader("🎯 Simulate TEE Mark Increase")
            selected_index = st.selectbox("Select a student to simulate improvement:", borderline_df.index,
                                          format_func=lambda i: f"{borderline_df.loc[i, id_cols[0]]} - {borderline_df.loc[i, 'Subject']}")
            added_marks = st.slider("Increase TEE by:", 1, 15, 3)

            sim_row = borderline_df.loc[selected_index]
            subject = sim_row["Subject"]
            tee_col = f"TEE_{subject}"
            ica_col = f"ICA_{subject}"

            new_tee = sim_row["TEE"] + added_marks
            ica = sim_row["ICA"]
            total_tee_marks = total_marks_dict.get(tee_col, 100)

            # Compute new final marks
            if total_tee_marks == 100:
                new_final = (new_tee / 2) + ica
            elif total_tee_marks == 50:
                new_final = new_tee + ica
            else:
                new_final = np.nan

            st.write(f"🧮 Final Marks (already in sheet) for {sim_row[id_cols[0]]} in {subject}: **{sim_row['Final_Marks']}**")
            st.write(f"🔁 Simulated New Final Marks after increasing TEE by {added_marks}: **{new_final:.2f}**")
        else:
            st.info("✅ No students found in selected TEE% range.")
    else:
        st.info("ℹ️ No valid TEE or ICA data to display percentages.")
