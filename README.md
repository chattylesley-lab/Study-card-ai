# StudyCard AI

A beginner-friendly Streamlit app for turning class documents into summaries, flashcards, and quizzes.

## What it does

- Upload PDF, DOCX, TXT, or Markdown files
- Extract the document text
- Identify main ideas and key takeaways
- Generate study flashcards
- Generate a 4-choice quiz
- Score the quiz and explain each correct answer

## Run it

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the app:

```bash
streamlit run app.py
```

5. Open the local address Streamlit shows you.
6. Paste an OpenAI API key into the app sidebar.

You can also set the key as an environment variable:

```bash
export OPENAI_API_KEY="your_key_here"
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

## Notes

This starter version works best with text-based PDFs. Scanned image PDFs would need OCR or vision support in a future version.
