"""Versioned consent wording shown to patients.

*** DRAFT WORDING — must be reviewed and approved by the hospital's legal,
privacy and clinical teams before any real patient uses the system. ***

Every consent record stores CONSENT_VERSION, so you can always tell exactly which
text a patient agreed to. When the wording changes, bump the version: patients
with an older version are then asked to consent again.
"""

from app.core.enums import ConsentType, UiLanguage

CONSENT_VERSION = "draft-2026-11-24"

_TEXTS: dict[ConsentType, dict[UiLanguage, tuple[str, str]]] = {
    ConsentType.DATA_PROCESSING: {
        UiLanguage.EN: (
            "Consent to use your information",
            "HealthSpeak AI collects the information you give us — your name, contact "
            "details, date of birth, gender and the health concerns you describe by voice "
            "or text — so that hospital staff can register you and prepare for your visit. "
            "Voice input is processed on the hospital's own computers to create a written "
            "transcript and, if needed, an English translation; it is not sent to outside "
            "AI services. HealthSpeak AI does not diagnose illness or prescribe treatment: "
            "authorised medical staff review everything you share. You can ask staff to "
            "show or correct your information, and you can withdraw this consent at any "
            "time. Withdrawing does not affect care you have already received.",
        ),
        UiLanguage.HI: (
            "आपकी जानकारी के उपयोग के लिए सहमति",
            "HealthSpeak AI आपके द्वारा दी गई जानकारी — आपका नाम, संपर्क विवरण, जन्म तिथि, "
            "लिंग और आवाज़ या लिखित रूप में बताई गई स्वास्थ्य संबंधी समस्याएँ — एकत्र करता है, "
            "ताकि अस्पताल के कर्मचारी आपका पंजीकरण कर सकें और आपकी विज़िट की तैयारी कर सकें। "
            "आवाज़ से दी गई जानकारी अस्पताल के अपने कंप्यूटरों पर ही लिखित रूप में और ज़रूरत "
            "होने पर अंग्रेज़ी अनुवाद में बदली जाती है; इसे बाहरी AI सेवाओं को नहीं भेजा जाता। "
            "HealthSpeak AI बीमारी का निदान नहीं करता और न ही दवा लिखता है: आपकी दी गई सारी "
            "जानकारी अधिकृत चिकित्सा कर्मचारी देखते हैं। आप कर्मचारियों से अपनी जानकारी देखने "
            "या उसमें सुधार करने के लिए कह सकते हैं, और किसी भी समय यह सहमति वापस ले सकते हैं। "
            "सहमति वापस लेने से पहले मिल चुकी देखभाल पर कोई असर नहीं पड़ता।",
        ),
        UiLanguage.UR: (
            "آپ کی معلومات کے استعمال کے لیے رضامندی",
            "HealthSpeak AI آپ کی فراہم کردہ معلومات — آپ کا نام، رابطے کی تفصیلات، تاریخِ "
            "پیدائش، جنس اور آواز یا تحریر کے ذریعے بتائے گئے صحت کے مسائل — جمع کرتا ہے تاکہ "
            "ہسپتال کا عملہ آپ کا اندراج کر سکے اور آپ کی آمد کی تیاری کر سکے۔ آواز کے ذریعے دی "
            "گئی معلومات ہسپتال کے اپنے کمپیوٹرز پر ہی تحریری شکل میں اور ضرورت ہو تو انگریزی "
            "ترجمے میں تبدیل کی جاتی ہیں؛ انہیں بیرونی AI سروسز کو نہیں بھیجا جاتا۔ HealthSpeak "
            "AI بیماری کی تشخیص نہیں کرتا اور نہ ہی دوا تجویز کرتا ہے: آپ کی تمام معلومات مجاز "
            "طبی عملہ دیکھتا ہے۔ آپ عملے سے اپنی معلومات دکھانے یا درست کرنے کا کہہ سکتے ہیں، "
            "اور کسی بھی وقت یہ رضامندی واپس لے سکتے ہیں۔ رضامندی واپس لینے سے پہلے مل چکی "
            "دیکھ بھال پر کوئی اثر نہیں پڑتا۔",
        ),
    }
}


def consent_text(consent_type: ConsentType, language: UiLanguage) -> tuple[str, str]:
    """(title, body) for the current version in the requested language.

    There is no reviewed Dogri consent wording yet. A legal consent text must not be machine-written, so
    Dogri readers (who read Devanagari) are shown the Hindi text until a reviewed Dogri version exists.
    """
    texts = _TEXTS[consent_type]
    return texts.get(language) or texts[UiLanguage.HI if language == UiLanguage.DOI else UiLanguage.EN]
