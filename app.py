import io
import re
import random
from collections import Counter
from typing import List, Dict

import streamlit as st
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="StudyCard", page_icon="📚", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.2rem 1.4rem; border: 1px solid rgba(128,128,128,.25); border-radius: 18px; margin-bottom: 1rem;}
.small-note {opacity: .75; font-size: .92rem;}
.card {border: 1px solid rgba(128,128,128,.28); border-radius: 16px; padding: 1rem 1.1rem; margin: .6rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>📚 StudyCard</h1><p>Upload a lesson, syllabus, study guide, or class document. StudyCard reads it and turns the most important material into main ideas, flashcards, and a quiz — no API key required.</p></div>', unsafe_allow_html=True)

STOPWORDS = set("""a an the and or but if then than to of in on at for from with by as is are was were be been being it its this that these those you your we our they their he she his her i me my not no do does did can could should would may might will shall about into over under between during before after above below up down out off again further once here there when where why how all any both each few more most other some such only own same so too very s t just don now also has have had who whom which what while because until against through per via""".split())

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

def clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def split_sentences(text: str) -> List[str]:
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    out = []
    for p in parts:
        p = p.strip(" •\t-")
        if 35 <= len(p) <= 420 and len(p.split()) >= 6:
            out.append(p)
    return out

def words(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)]

def top_keywords(text: str, limit: int = 30) -> List[str]:
    counts = Counter(w for w in words(text) if w not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]

def sentence_score(sentence: str, freq: Counter) -> float:
    toks = [w for w in words(sentence) if w not in STOPWORDS]
    if not toks:
        return 0
    score = sum(freq.get(w, 0) for w in toks) / (len(toks) ** 0.7)
    if re.search(r"\b(important|means|defined|definition|because|therefore|must|required|exam|test|due|grade|percent|formula|causes?|results?|purpose|process|first|second|finally)\b", sentence, re.I):
        score *= 1.25
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d{1,2}[/-]\d{1,2}|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", sentence, re.I):
        score *= 1.15
    return score

def choose_key_sentences(text: str, n: int) -> List[str]:
    sents = split_sentences(text)
    freq = Counter(w for w in words(text) if w not in STOPWORDS)
    ranked = sorted(enumerate(sents), key=lambda x: sentence_score(x[1], freq), reverse=True)
    selected = []
    seen = set()
    for idx, sent in ranked:
        norm = re.sub(r"\W+", " ", sent.lower()).strip()
        key = " ".join(norm.split()[:8])
        if key in seen:
            continue
        seen.add(key)
        selected.append((idx, sent))
        if len(selected) >= n:
            break
    selected.sort(key=lambda x: x[0])
    return [s for _, s in selected]

def find_focus_term(sentence: str, keywords: List[str]) -> str:
    # Prefer capitalized terms / phrases, then frequent keywords.
    caps = re.findall(r"\b(?:[A-Z][A-Za-z0-9'-]+(?:\s+[A-Z][A-Za-z0-9'-]+){0,2})\b", sentence)
    caps = [c for c in caps if c.lower() not in {"The", "This", "These", "A", "An"}]
    if caps:
        return max(caps, key=len)
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", sentence, re.I):
            return kw
    toks = [w for w in words(sentence) if w not in STOPWORDS]
    return toks[0] if toks else "this idea"

def make_question(sentence: str, term: str) -> str:
    patterns = [
        (r"^(.{2,80}?)\s+(?:is|are|means|refers to)\s+(.+)$", "What is {term}?"),
        (r"^(.{2,80}?)\s+(?:causes?|results? in|leads? to)\s+(.+)$", "What happens because of {term}?"),
    ]
    for pattern, q in patterns:
        m = re.match(pattern, sentence, re.I)
        if m:
            return q.format(term=m.group(1).strip())
    if re.search(r"\b(must|required|should|need to)\b", sentence, re.I):
        return "What requirement or expectation should you remember here?"
    if re.search(r"\b\d+(?:\.\d+)?%|\bgrade\b|\bdue\b|\bdeadline\b", sentence, re.I):
        return "What important number, grade detail, or deadline is stated here?"
    return f"What should you remember about {term}?"

def shorten(sentence: str, max_chars: int = 260) -> str:
    sentence = sentence.strip()
    return sentence if len(sentence) <= max_chars else sentence[:max_chars-1].rstrip() + "…"

def build_pack(text: str, card_count: int) -> Dict:
    keywords = top_keywords(text, 40)
    key_sents = choose_key_sentences(text, max(card_count + 8, 12))
    main_ideas = [shorten(s, 220) for s in key_sents[:6]]
    takeaways = [shorten(s, 220) for s in key_sents[6:10]] or main_ideas[:4]

    flashcards = []
    for sent in key_sents[:card_count]:
        term = find_focus_term(sent, keywords)
        flashcards.append({"question": make_question(sent, term), "answer": shorten(sent), "topic": term.title()})

    # Build quiz distractors from other document facts, so all choices stay grounded in the uploaded material.
    answer_pool = [f["answer"] for f in flashcards]
    quiz = []
    for i, card in enumerate(flashcards[:min(10, len(flashcards))]):
        correct = card["answer"]
        others = [a for j, a in enumerate(answer_pool) if j != i and a != correct]
        if len(others) < 3:
            continue
        random.seed(i + len(text))
        distractors = random.sample(others, 3)
        choices = distractors + [correct]
        random.shuffle(choices)
        quiz.append({
            "question": card["question"],
            "choices": choices,
            "correct_index": choices.index(correct),
            "explanation": correct,
        })
    title_words = [k.title() for k in keywords[:3]]
    title = "Study Pack" if not title_words else " • ".join(title_words) + " Study Pack"
    return {"title": title, "main_ideas": main_ideas, "takeaways": takeaways, "flashcards": flashcards, "quiz": quiz}

with st.sidebar:
    st.header("Settings")
    card_count = st.slider("Number of flashcards", 5, 25, 12)
    st.caption("This version works without an API key. It creates study material from the text already inside your uploaded document.")

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

            if st.button("✨ Generate study pack", type="primary"):
                with st.spinner("Reading the document and building your study pack..."):
                    st.session_state.study_pack = build_pack(text, card_count)
                    st.session_state.quiz_answers = {}
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
        for i, card in enumerate(flashcards, start=1):
            with st.expander(f"Card {i}: {card.get('question', 'Question')}"):
                st.markdown(f"**Answer:** {card.get('answer', '')}")
                st.caption(f"Topic: {card.get('topic', '')}")

    with tab3:
        quiz: List[Dict] = pack.get("quiz", [])
        if not quiz:
            st.info("I need a little more text in the document to build a quiz.")
        else:
            with st.form("quiz_form"):
                selected = {}
                for i, q in enumerate(quiz):
                    st.markdown(f"**{i+1}. {q['question']}**")
                    selected[i] = st.radio(
                        "Choose one", list(range(4)),
                        format_func=lambda idx, ch=q["choices"]: ch[idx],
                        key=f"quiz_{i}", index=None,
                    )
                    st.write("")
                submitted = st.form_submit_button("Check my answers", type="primary")

            if submitted:
                score = sum(selected.get(i) == q["correct_index"] for i, q in enumerate(quiz))
                st.success(f"Score: {score}/{len(quiz)} ({round(score/len(quiz)*100)}%)")
                for i, q in enumerate(quiz):
                    with st.expander(f"Review question {i+1}"):
                        ans = selected.get(i)
                        if ans == q["correct_index"]:
                            st.success("Nice — you got it right.")
                        elif ans is None:
                            st.warning("You skipped this question.")
                        else:
                            st.error("That one needs another look.")
                        st.markdown(f"**Correct answer:** {q['choices'][q['correct_index']]}")
                        st.markdown(f"**Why:** {q['explanation']}")

st.divider()
st.markdown('<p class="small-note">StudyCard is a study helper. Double-check dates, grades, deadlines, and test requirements against your teacher\'s original material.</p>', unsafe_allow_html=True)
