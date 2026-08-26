"""Server-side OpenAI / Groq helpers.

Keeping these calls on the backend means the API keys never ship to the browser.
Each function returns a ``(code, message, response)`` tuple that the views wrap
into the standard ``{ code, message, response }`` envelope.
"""
from __future__ import annotations

import httpx
from django.conf import settings

HOSPITAL_SYSTEM_PROMPT = """You are Eos, the virtual assistant for NU Hospitals (India).
Answer only questions related to NU Hospitals, healthcare, doctors, departments, appointments, surgeries, visiting, insurance, and patient support.
Be warm, clear, and concise (2-5 short sentences unless more detail is needed).
Language: The user may speak or type in English, Hindi, or Hinglish (mixed). Always reply in the same language the user used. If mixed, prefer clear Hinglish or match their dominant language.
Known hospital facts you may use:
- Branches: NU Hospitals Rajajinagar, Kalyan Nagar, Padmanabhanagar
- Specialities: Urology, Nephrology, Gynaecology, Andrology, Orthopaedics, General Medicine
- Phone: +91-8042489999
- Email: care@nuhospitals.com
- WhatsApp: +91-8951889724
- Website: https://www.nuhospitals.com
- Privacy policy: https://www.nuhospitals.com/privacy-policy
If the user wants to book, cancel, or reschedule an appointment, tell them to say "book appointment" / "अपॉइंटमेंट बुक करें", "cancel appointment" / "अपॉइंटमेंट कैंसल", or "reschedule" / "अपॉइंटमेंट बदलें", or choose those options from the menu.
If asked something unrelated to the hospital or healthcare, politely say you can only help with NU Hospitals related queries.
Do not invent doctor availability, prices, or medical diagnoses. Suggest contacting the hospital for clinical advice."""


def _extract_api_error(exc: httpx.HTTPStatusError, fallback: str = "") -> str:
    try:
        body = exc.response.json()
        return body.get("error", {}).get("message") or fallback or str(exc)
    except Exception:
        return fallback or str(exc)


def ask_hospital_assistant(
    message: str, history: list[dict], system_prompt: str = ""
) -> tuple[int, str, str]:
    if not settings.OPENAI_API_KEY:
        return (
            503,
            "OpenAI not configured",
            "AI chat is not configured yet. Please choose an option below, "
            "or ask the admin to set the OpenAI API key.",
        )

    system_prompt = (system_prompt or "").strip() or HOSPITAL_SYSTEM_PROMPT

    # Keep last 8 turns to control token usage.
    trimmed = [
        {"role": t.get("role"), "content": t.get("content")}
        for t in (history or [])
        if t.get("role") in ("user", "assistant") and t.get("content")
    ][-8:]

    messages = [
        {"role": "system", "content": system_prompt},
        *trimmed,
        {"role": "user", "content": message},
    ]
    body = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.4,
        "max_tokens": 350,
        "messages": messages,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(settings.OPENAI_API_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        answer = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        ) or "Sorry, I could not generate a response right now."
        return 200, "OK", answer
    except httpx.HTTPStatusError as exc:
        return 500, "OpenAI error", _extract_api_error(exc)
    except httpx.HTTPError:
        return (
            500,
            "OpenAI error",
            "Unable to reach AI assistant. Please try again or choose an option below.",
        )


def transcribe_audio(
    filename: str,
    content: bytes,
    content_type: str,
    language: str = "",
    context: str = "",
) -> tuple[int, str, str]:
    if not settings.GROQ_API_KEY:
        return (
            503,
            "Groq not configured",
            "Voice input needs a Groq API key. Set GROQ_API_KEY in the backend "
            ".env. Get one at https://console.groq.com/",
        )

    files = {"file": (filename or "speech.webm", content, content_type or "audio/webm")}
    latin_contexts = {"name", "age", "phoneNumber", "managePhone", "surgeryName"}
    ctx = (context or "").strip()
    lang = (language or "").strip().lower()

    if ctx in latin_contexts:
        lang = "en"
        prompts = {
            "name": (
                "NU Hospitals patient registration. Transcribe the spoken full name using "
                "English Latin letters only (A-Z). Example: Raghvendra Kumar, Priya Sharma, "
                "Amit Singh. Do not use Devanagari or Hindi script."
            ),
            "age": (
                "NU Hospitals patient age. Transcribe as English digits only, e.g. 25, 42, 18."
            ),
            "phoneNumber": (
                "NU Hospitals mobile number. Transcribe as English digits only, 10 digits."
            ),
            "managePhone": (
                "NU Hospitals mobile number. Transcribe as English digits only, 10 digits."
            ),
            "surgeryName": (
                "NU Hospitals surgery name. Transcribe in English Latin letters."
            ),
        }
        prompt = prompts.get(ctx, prompts["name"])
    else:
        prompt = (
            "NU Hospitals chatbot. The user may speak Hindi, English, or Hinglish. "
            "Transcribe exactly what was spoken in the natural script for that language. "
            "Menu phrases: book appointment, cancel appointment, self, agree, find doctor, "
            "appointment with doctor, अपॉइंटमेंट बुक करें, खुद, सहमत."
        )

    form = {
        "model": settings.GROQ_WHISPER_MODEL,
        "response_format": "json",
        "temperature": "0",
        "prompt": prompt,
    }
    if lang in ("en", "hi"):
        form["language"] = lang

    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                settings.GROQ_WHISPER_URL, data=form, files=files, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        text = (data.get("text") or "").strip()
        if not text:
            return 404, "Empty transcript", ""
        return 200, "OK", text
    except httpx.HTTPStatusError as exc:
        return (
            500,
            "Groq Whisper error",
            _extract_api_error(exc, "Could not convert speech to text. Please try again."),
        )
    except httpx.HTTPError:
        return (
            500,
            "Groq Whisper error",
            "Could not convert speech to text. Please try again.",
        )
