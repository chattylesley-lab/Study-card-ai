import io
import json
import os
import re
from typing import List, Dict

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="StudyCard AI", page_icon="📚", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.2rem 1.4rem; border: 1px solid rgba(128,128,128,.25); border-radius: 18px; margin-bottom: 1rem;}
.small-note {opacity: .75; font-size: .92rem;}
.card {border: 1px solid rgba(128,128,128,.28); border-radius: 16px; padding: 1rem 1.1rem; margin: .6rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>📚 StudyCard AI</h1><p>Upload a lesson, syllabus, study guide, or class document. StudyCard finds the most important ideas and turns them into flashcards and a quiz.</p></div>', unsafe_allow_html=True)


def extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


def extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()


def extract_text(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return extract_pdf(data)
    if name.endswith(".docx"):
        return extract_docx(data)
    if name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError("Unsupported file type")


def parse_json(text: str) -> Dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def create_study_pack(document_text: str, card_count: int, difficulty: str, model: str) -> Dict:
    client = OpenAI(api_key=st.session_state.api_key)
    prompt = f"""
You are a careful high-school study coach. Read the ENTIRE document below and create a study pack using ONLY information present in the document.

Student level: high-school freshman.
Difficulty: {difficulty}.
Target flashcard count: {card_count}.

Rules:
- Capture the most important ideas, definitions, dates, formulas, processes, requirements, people, vocabulary, and cause/effect relationships.
- Prioritize ideas that a teacher is most likely to test.
- Do not invent outside facts.
- Make flashcard questions clear and specific, not vague.
- Answers should be concise but complete.
- Quiz questions must each have exactly 4 answer choices and exactly one correct answer.
- Include a short explanation for the correct quiz answer.
- If the document is a syllabus, focus on key policies, deadlines, grading, expectations, materials, and course goals.
- If the document is a lesson or notes, focus on concepts and knowledge.

Return ONLY valid JSON in exactly this shape:
{{
  "title": "short title",
  "main_ideas": ["idea 1", "idea 2"],
  "takeaways": ["takeaway 1", "takeaway 2"],
  "flashcards": [
    {{"question": "...", "answer": "...", "topic": "..."}}
  ],
  "quiz": [
    {{
      "question": "...",
      "choices": ["...", "...", "...", "..."],
      "correct_index": 0,
      "explanation": "..."
    }}
  ]
}}

DOCUMENT:
---
{document_text}
---
"""
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return parse_json(response.output_text)


with st.sidebar:
    st.header("Settings")
    st.session_state.api_key = st.text_input(
        "OpenAI API key",
        type="password",
        value=st.session_state.get("api_key", os.getenv("OPENAI_API_KEY", "")),
        help="Your key stays in this app session and is sent only to the OpenAI API."
    )
    model = st.selectbox("AI model", ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"], index=0)
    card_count = st.slider("Number of flashcards", 5, 30, 12)
    difficulty = st.selectbox("Quiz difficulty", ["Easy", "Grade-level", "Challenge"], index=1)
    st.caption("Tip: Luna is the lowest-cost option; Terra and Sol can be stronger for harder documents.")

uploaded = st.file_uploader("Upload your class document", type=["pdf", "docx", "txt", "md"])

if uploaded:
    try:
        text = extract_text(uploaded)
        if not text:
            st.error("I couldn't find readable text in that file. Try a text-based PDF, DOCX, or TXT file.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("File", uploaded.name)
            c2.metric("Characters read", f"{len(text):,}")
            c3.metric("Words read", f"{len(text.split()):,}")
            with st.expander("Preview extracted text"):
                st.text(text[:12000])

            if not st.session_state.api_key:
                st.info("Enter your OpenAI API key in the sidebar, then click Generate study pack.")
            if st.button("✨ Generate study pack", type="primary", disabled=not bool(st.session_state.api_key)):
                with st.spinner("Reading the document and building your study pack..."):
                    try:
                        pack = create_study_pack(text, card_count, difficulty, model)
                        st.session_state.study_pack = pack
                        st.session_state.quiz_answers = {}
                        st.session_state.quiz_submitted = False
                    except Exception as e:
                        st.error(f"Could not generate the study pack: {e}")
    except Exception as e:
        st.error(f"Could not read this file: {e}")

pack = st.session_state.get("study_pack")
if pack:
    st.divider()
    st.header(pack.get("title", "Your Study Pack"))
    tab1, tab2, tab3 = st.tabs(["🧠 Main Ideas", "🗂️ Flashcards", "✅ Quiz"])

    with tab1:
        st.subheader("Main ideas")
        for item in pack.get("main_ideas", []):
            st.markdown(f"- {item}")
        st.subheader("Big takeaways")
        for item in pack.get("takeaways", []):
            st.markdown(f"- {item}")

    with tab2:
        flashcards: List[Dict] = pack.get("flashcards", [])
        if not flashcards:
            st.info("No flashcards were generated.")
        else:
            for i, card in enumerate(flashcards, start=1):
                with st.expander(f"Card {i}: {card.get('question', 'Question')}"):
                    st.markdown(f"**Answer:** {card.get('answer', '')}")
                    if card.get("topic"):
                        st.caption(f"Topic: {card['topic']}")

    with tab3:
        quiz: List[Dict] = pack.get("quiz", [])
        if not quiz:
            st.info("No quiz questions were generated.")
        else:
            with st.form("quiz_form"):
                selected = {}
                for i, q in enumerate(quiz):
                    st.markdown(f"**{i+1}. {q.get('question', '')}**")
                    choices = q.get("choices", [])
                    selected[i] = st.radio(
                        "Choose one",
                        options=list(range(len(choices))),
                        format_func=lambda idx, ch=choices: ch[idx],
                        key=f"quiz_{i}",
                        index=None,
                    )
                    st.write("")
                submitted = st.form_submit_button("Check my answers", type="primary")

            if submitted:
                score = 0
                for i, q in enumerate(quiz):
                    answer = selected.get(i)
                    correct = q.get("correct_index")
                    if answer == correct:
                        score += 1
                st.success(f"Score: {score}/{len(quiz)} ({round(score/len(quiz)*100)}%)")
                for i, q in enumerate(quiz):
                    choices = q.get("choices", [])
                    answer = selected.get(i)
                    correct = q.get("correct_index")
                    with st.expander(f"Review question {i+1}"):
                        if answer is None:
                            st.warning("You skipped this question.")
                        elif answer == correct:
                            st.success("Nice — you got it right.")
                        else:
                            st.error("That one needs another look.")
                        if isinstance(correct, int) and 0 <= correct < len(choices):
                            st.markdown(f"**Correct answer:** {choices[correct]}")
                        st.markdown(f"**Why:** {q.get('explanation', '')}")

st.divider()
st.markdown('<p class="small-note">StudyCard AI is a study helper. Always compare generated cards with your teacher\'s materials, especially for grades, deadlines, and test requirements.</p>', unsafe_allow_html=True)
