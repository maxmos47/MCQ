# MCQ Answer Sheet System (Google Sheet + GAS + Streamlit)

## Google Sheet Template
Create a spreadsheet with 2 sheets:

### Sheet: Config (A:B)
A | B
--|--
Question_Count | 20
Correct_Answers | A,B,C,D,E,A,B,C,D,E,A,B,C,D,E,A,B,C,D,E

### Sheet: Responses
Headers (row 1): `Timestamp | Student_Name | Answers | Score | Percent | DetailJSON`  
Leave empty under the header; it will be filled by the app.

---

## Google Apps Script
1. Extensions → Apps Script → New project
2. Paste `Code.gs`
3. Set `SHEET_ID`
4. Deploy → New deployment → Type: Web app  
   - Execute as: Me  
   - Who has access: Anyone with the link  
   - Copy the Web app URL

## Streamlit App
1. Put `app.py` and `requirements.txt` in a repo / folder
2. Create `.streamlit/secrets.toml` and fill:
```
[gas]
webapp_url = "YOUR_WEBAPP_URL"

[app]
teacher_key = "YOUR_SECRET"
```
3. Run locally: `streamlit run app.py`
4. Or deploy on Streamlit Cloud and set the same secrets

## Usage
- Students open the app (default `mode=exam`) and submit answers with their **name**.
- Teacher opens `?mode=dashboard` and enters the **teacher_key** to view the dashboard.
- Score is shown to the student immediately after submit.
