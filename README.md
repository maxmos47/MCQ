# MCQ Answer Sheet — Multiple Exam Sets

## Google Sheet
Create 2 sheets:

### Sheet: Exams (A:D)
Exam_ID | Title | Question_Count | Correct_Answers
------- | ----- | ---------------| ----------------
EXAM1 | Midterm Set A | 20 | A,B,C,D,E,...(20)
EXAM2 | Midterm Set B | 20 | B,A,D,C,E,...(20)

### Sheet: Responses
Headers row 1:
`Timestamp | Exam_ID | Student_Name | Answers | Score | Percent | DetailJSON`

## GAS Endpoints
- GET `action=get_config` → `{ exams: [...] }`
- GET `action=get_exam&exam_id=EXAM1`
- GET `action=get_dashboard&exam_id=EXAM1`
- GET `action=check_submitted&exam_id=EXAM1&student_name=NAME`
- POST `action=submit` with `{ exam_id, student_name, answers }`
  - Duplicate submission (same exam_id + name) → `{ ok:false, error:'DUPLICATE_SUBMISSION' }`

## Streamlit
- Student page: select Exam Set → checkboxes A–E per item (single-choice per question) → submit
- Locks:
  - UI lock after successful submit
  - Server-side lock by (Exam_ID, Student_Name) to prevent resubmission
- Dashboard: choose Exam Set → see scores and item analysis
