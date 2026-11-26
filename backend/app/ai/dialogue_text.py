"""Wording for the chat assistant in English, Hindi and Urdu, and a small native-script glossary.

*** DRAFT wording: the Hindi and Urdu text must be reviewed by native speakers and clinicians. ***

The assistant never diagnoses, prescribes or reassures. Every sentence either asks for information,
repeats what the patient said, or gives a PRELIMINARY department suggestion for staff to confirm.
"""

DIALOGUE_TEXT_VERSION = "dlg-text-2026-11-26"

# ---------------------------------------------------------------- templates
TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "empathy": "I'm sorry you're not feeling well.",
        "q_describe": ("Could you tell me what symptoms or problems you are having? For example pain, "
                       "fever, cough or vomiting, and where you feel it."),
        "q_describe_retry": ("I could not pick out a specific symptom. Please describe in a few simple "
                             "words what bothers you most (for example: stomach pain, fever, cough). "
                             "Medical staff will also read your original message."),
        "q_pain_location": "Where exactly is the pain?",
        "q_abdomen": ("Where exactly is the pain: upper abdomen, lower abdomen, or around the belly "
                      "button? And is it on the right side, the left side, or in the middle?"),
        "q_duration": "How long have you had {symptom}? (for example since yesterday, or 3 days)",
        "q_severity": "How strong is the {symptom}: mild, moderate or severe?",
        "q_associated": ("Do you also have any other symptoms, such as fever, vomiting, cough or trouble "
                         "breathing? If not, you can say no."),
        "q_medicines": "Are you taking any medicines, or do you have any allergies? If not, you can say no.",
        "urgent": ("Some of the symptoms you described can be serious. Please do not wait: go to the "
                   "nearest emergency department now or call {number}, and if possible ask someone to "
                   "go with you."),
        "caution": ("Pain in the lower right abdomen together with fever can sometimes need urgent "
                    "medical evaluation. Please seek prompt medical attention, especially if the pain "
                    "is severe or getting worse."),
        "understood": "What I understood: {list}.",
        "not_have": "You said you do not have: {list}.",
        "dept_clear": ("Based on this, {dept} looks like the right department for a first check. I "
                       "suggested it because you mentioned {why}."),
        "dept_likely": ("{dept} is my best match for a first check, because you mentioned {why}. Other "
                        "departments could also fit."),
        "dept_unclear": ("I could not narrow this down to one department yet. Medical staff will choose "
                         "the right one after reading your message."),
        "dept_default": ("I did not find a symptom that points to a specific department, so staff will "
                         "choose one for you after reading your message."),
        "prelim": ("This is only a preliminary suggestion to help the medical staff. I cannot diagnose "
                   "or prescribe, and staff will confirm the department."),
        "next": "You can add more details, or press Review and send when you are ready.",
        "worse": ("If your symptoms get worse or you feel very unwell, do not wait: go to the emergency "
                  "department or call {number}."),
        "and": " and ",
        "unsure": "(not sure)",
        "thanks": "Thank you.",
    },
    "hi": {
        "empathy": "आपकी तबीयत ठीक नहीं है, यह जानकर मुझे दुख है।",
        "q_describe": ("कृपया बताइए कि आपको कौन से लक्षण या परेशानियाँ हैं? जैसे दर्द, बुखार, खांसी या "
                       "उल्टी, और यह कहाँ महसूस होता है।"),
        "q_describe_retry": ("मैं कोई खास लक्षण नहीं पहचान पाया। कृपया कुछ आसान शब्दों में बताइए कि आपको सबसे "
                             "ज़्यादा क्या परेशान कर रहा है (जैसे: पेट दर्द, बुखार, खांसी)। चिकित्सा कर्मचारी आपका "
                             "मूल संदेश भी पढ़ेंगे।"),
        "q_pain_location": "दर्द ठीक किस जगह है?",
        "q_abdomen": ("दर्द ठीक कहाँ है: पेट के ऊपरी हिस्से में, निचले हिस्से में, या नाभि के आसपास? और क्या यह "
                      "दाईं तरफ़, बाईं तरफ़ या बीच में है?"),
        "q_duration": "आपको {symptom} कब से है? (जैसे कल से, या 3 दिन से)",
        "q_severity": "{symptom} कितना तेज़ है: हल्का, मध्यम या गंभीर?",
        "q_associated": ("क्या आपको और भी कोई लक्षण हैं, जैसे बुखार, उल्टी, खांसी या सांस लेने में तकलीफ़? "
                         "अगर नहीं, तो आप \"नहीं\" कह सकते हैं।"),
        "q_medicines": "क्या आप कोई दवा ले रहे हैं, या आपको कोई एलर्जी है? अगर नहीं, तो आप \"नहीं\" कह सकते हैं।",
        "urgent": ("आपके बताए कुछ लक्षण गंभीर हो सकते हैं। कृपया इंतज़ार न करें: अभी नज़दीकी आपातकालीन विभाग जाएँ "
                   "या {number} पर कॉल करें, और हो सके तो किसी को अपने साथ ले जाएँ।"),
        "caution": ("पेट के निचले दाएँ हिस्से में दर्द के साथ बुखार होने पर कभी-कभी तुरंत चिकित्सा जाँच की ज़रूरत "
                    "पड़ सकती है। कृपया जल्द चिकित्सा सहायता लें, खासकर अगर दर्द तेज़ हो या बढ़ रहा हो।"),
        "understood": "मैंने यह समझा: {list}।",
        "not_have": "आपने बताया कि आपको यह नहीं है: {list}।",
        "dept_clear": ("इसके आधार पर, पहली जाँच के लिए {dept} विभाग सही लगता है। मैंने इसे इसलिए सुझाया क्योंकि "
                       "आपने {why} बताया।"),
        "dept_likely": ("पहली जाँच के लिए {dept} मेरा सबसे अच्छा अनुमान है, क्योंकि आपने {why} बताया। दूसरे विभाग भी "
                        "सही हो सकते हैं।"),
        "dept_unclear": ("मैं अभी एक विभाग तक सीमित नहीं कर पाया। आपका संदेश पढ़ने के बाद चिकित्सा कर्मचारी सही "
                         "विभाग चुनेंगे।"),
        "dept_default": ("मुझे ऐसा कोई लक्षण नहीं मिला जो किसी खास विभाग की ओर इशारा करे, इसलिए आपका संदेश पढ़ने के "
                         "बाद कर्मचारी विभाग चुनेंगे।"),
        "prelim": ("यह केवल चिकित्सा कर्मचारियों की मदद के लिए एक प्रारंभिक सुझाव है। मैं निदान या दवा नहीं बता "
                   "सकता, और विभाग की पुष्टि कर्मचारी करेंगे।"),
        "next": "आप और जानकारी जोड़ सकते हैं, या तैयार होने पर \"समीक्षा करें और भेजें\" दबाएँ।",
        "worse": ("अगर आपके लक्षण बढ़ें या आप बहुत बीमार महसूस करें, तो इंतज़ार न करें: आपातकालीन विभाग जाएँ या "
                  "{number} पर कॉल करें।"),
        "and": " और ",
        "unsure": "(पक्का नहीं)",
        "thanks": "धन्यवाद।",
    },
    "ur": {
        "empathy": "مجھے افسوس ہے کہ آپ کی طبیعت ٹھیک نہیں ہے۔",
        "q_describe": ("براہ کرم بتائیں کہ آپ کو کون سی علامات یا تکلیفیں ہیں؟ مثلاً درد، بخار، کھانسی یا قے، "
                       "اور یہ کہاں محسوس ہوتی ہے۔"),
        "q_describe_retry": ("میں کوئی خاص علامت پہچان نہیں سکا۔ براہ کرم چند آسان لفظوں میں بتائیں کہ آپ کو سب سے "
                             "زیادہ کیا پریشان کر رہا ہے (مثلاً: پیٹ درد، بخار، کھانسی)۔ طبی عملہ آپ کا اصل پیغام "
                             "بھی پڑھے گا۔"),
        "q_pain_location": "درد ٹھیک کس جگہ ہے؟",
        "q_abdomen": ("درد ٹھیک کہاں ہے: پیٹ کے اوپری حصے میں، نچلے حصے میں، یا ناف کے آس پاس؟ اور کیا یہ دائیں طرف، "
                      "بائیں طرف یا درمیان میں ہے؟"),
        "q_duration": "آپ کو {symptom} کب سے ہے؟ (مثلاً کل سے، یا 3 دن سے)",
        "q_severity": "{symptom} کتنا تیز ہے: ہلکا، درمیانہ یا شدید؟",
        "q_associated": ("کیا آپ کو اور بھی کوئی علامت ہے، جیسے بخار، قے، کھانسی یا سانس لینے میں تکلیف؟ اگر نہیں تو "
                         "آپ \"نہیں\" کہہ سکتے ہیں۔"),
        "q_medicines": "کیا آپ کوئی دوا لے رہے ہیں، یا آپ کو کوئی الرجی ہے؟ اگر نہیں تو آپ \"نہیں\" کہہ سکتے ہیں۔",
        "urgent": ("آپ کی بتائی ہوئی کچھ علامات سنگین ہو سکتی ہیں۔ براہ کرم انتظار نہ کریں: ابھی قریبی ایمرجنسی "
                   "ڈیپارٹمنٹ جائیں یا {number} پر کال کریں، اور ممکن ہو تو کسی کو اپنے ساتھ لے جائیں۔"),
        "caution": ("پیٹ کے نچلے دائیں حصے میں درد کے ساتھ بخار ہو تو بعض اوقات فوری طبی معائنے کی ضرورت پڑ سکتی ہے۔ "
                    "براہ کرم جلد طبی مدد لیں، خاص طور پر اگر درد شدید ہو یا بڑھ رہا ہو۔"),
        "understood": "میں نے یہ سمجھا: {list}۔",
        "not_have": "آپ نے بتایا کہ آپ کو یہ نہیں ہے: {list}۔",
        "dept_clear": ("اس کی بنیاد پر، پہلے معائنے کے لیے {dept} شعبہ مناسب لگتا ہے۔ میں نے یہ اس لیے تجویز کیا "
                       "کیونکہ آپ نے {why} بتایا۔"),
        "dept_likely": ("پہلے معائنے کے لیے {dept} میرا بہترین اندازہ ہے، کیونکہ آپ نے {why} بتایا۔ دوسرے شعبے بھی "
                        "مناسب ہو سکتے ہیں۔"),
        "dept_unclear": ("میں ابھی ایک شعبے تک محدود نہیں کر سکا۔ آپ کا پیغام پڑھنے کے بعد طبی عملہ مناسب شعبہ "
                         "منتخب کرے گا۔"),
        "dept_default": ("مجھے ایسی کوئی علامت نہیں ملی جو کسی خاص شعبے کی طرف اشارہ کرے، اس لیے آپ کا پیغام پڑھنے کے "
                         "بعد عملہ شعبہ منتخب کرے گا۔"),
        "prelim": ("یہ صرف طبی عملے کی مدد کے لیے ایک ابتدائی تجویز ہے۔ میں تشخیص یا دوا نہیں بتا سکتا، اور شعبے کی "
                   "تصدیق عملہ کرے گا۔"),
        "next": "آپ مزید تفصیل شامل کر سکتے ہیں، یا تیار ہونے پر \"جائزہ لیں اور بھیجیں\" دبائیں۔",
        "worse": ("اگر آپ کی علامات بڑھ جائیں یا آپ بہت بیمار محسوس کریں تو انتظار نہ کریں: ایمرجنسی ڈیپارٹمنٹ جائیں "
                  "یا {number} پر کال کریں۔"),
        "and": " اور ",
        "unsure": "(یقین نہیں)",
        "thanks": "شکریہ۔",
    },
    # *** DRAFT Dogri (Devanagari). Written without a fluent-speaker review: it must be checked by a
    # native Dogri speaker and a clinician before real patients rely on it. ***
    "doi": {
        "empathy": "तुंदी तबीयत ठीक नेईं ऐ, एह् सुनियै मिगी दुख होआ।",
        "q_describe": ("मेहरबानी करियै दस्सो जे तुसेंगी केह् लक्षण जां परेशानियां न? जियां दर्द, बुखार, खांसी "
                       "जां उल्टी, ते एह् कुत्थें महसूस होंदा ऐ।"),
        "q_describe_retry": ("मैं कोई खास लक्षण नेईं पन्छान सकेआ। मेहरबानी करियै थोह्ड़े सौखे शब्दें च दस्सो जे "
                             "तुसेंगी सारें शा बद्ध केह् परेशान करदा ऐ (जियां: पेट दर्द, बुखार, खांसी)। मेडिकल "
                             "स्टाफ तुंदा असली संदेश बी पढ़ग।"),
        "q_pain_location": "दर्द ठीक कुत्थें ऐ?",
        "q_abdomen": ("दर्द ठीक कुत्थें ऐ: पेट दे उप्परले हिस्से च, थल्लले हिस्से च, जां नाभी दे आसै-पासै? ते केह् "
                      "एह् सज्जे पासे, खब्बे पासे जां बिच्च ऐ?"),
        "q_duration": "तुसेंगी {symptom} कदूं थमां ऐ? (जियां कल्ल थमां, जां 3 दिनें थमां)",
        "q_severity": "{symptom} किन्ना तेज ऐ: हौला, दरम्याना जां बड़ा तेज?",
        "q_associated": ("केह् तुसेंगी होर बी कोई लक्षण न, जियां बुखार, उल्टी, खांसी जां साह लैने च परेशानी? "
                         "जेकर नेईं, तां तुस \"नेईं\" आखी सकदे ओ।"),
        "q_medicines": ("केह् तुस कोई दवाई लैंदे ओ, जां तुसेंगी कुसै चीजै थमां ऐलर्जी ऐ? जेकर नेईं, तां तुस "
                        "\"नेईं\" आखी सकदे ओ।"),
        "urgent": ("तुंदे दस्से दे किश लक्षण गंभीर होई सकदे न। मेहरबानी करियै देर नेईं करो: हुन्नै नेड़ले "
                   "इमरजेंसी विभाग च जाओ जां {number} पर फोन करो, ते होई सकै तां कुसै गी अपने कन्नै लेई जाओ।"),
        "caution": ("पेट दे थल्ले सज्जे पासे दर्द कन्नै बुखार होऐ तां कदें-कदें तुरंत डाक्टरी जांच दी लोड़ पेई "
                    "सकदी ऐ। मेहरबानी करियै जल्दी डाक्टरी मदद लैओ, खास करियै जेकर दर्द तेज ऐ जां बधदा जा "
                    "करदा ऐ।"),
        "understood": "मैं एह् समझेआ: {list}।",
        "not_have": "तुसें दस्सेआ जे तुसेंगी एह् नेईं ऐ: {list}।",
        "dept_clear": ("इस आधार पर, पैह्ली जांच आस्तै {dept} विभाग ठीक लगदा ऐ। मैं एह् इस करी सुझाया कीजे तुसें "
                       "{why} दस्सेआ।"),
        "dept_likely": ("पैह्ली जांच आस्तै {dept} मेरा सारें शा ठीक अंदाजा ऐ, कीजे तुसें {why} दस्सेआ। होर "
                        "विभाग बी ठीक होई सकदे न।"),
        "dept_unclear": ("मैं हून इक विभाग तगर नेईं पुज्जी सकेआ। तुंदा संदेश पढ़ने परैंत मेडिकल स्टाफ ठीक "
                         "विभाग चुनग।"),
        "dept_default": ("मिगी कोई ऐसा लक्षण नेईं मिलेआ जेह्ड़ा कुसै खास विभाग वल्ल इशारा करदा होऐ, इस करी "
                         "तुंदा संदेश पढ़ने परैंत स्टाफ विभाग चुनग।"),
        "prelim": ("एह् सिर्फ मेडिकल स्टाफ दी मदद आस्तै इक शुरुआती सुझाव ऐ। मैं बमारी दी पन्छान नेईं करी "
                   "सकदा ते न दवाई दस्सी सकदा, ते विभाग दी पुष्टि स्टाफ करग।"),
        "next": "तुस होर जानकारी जोड़ी सकदे ओ, जां तैयार होने पर \"समीक्षा करो ते भेजो\" दबाओ।",
        "worse": ("जेकर तुंदे लक्षण बधी जान जां तुस बड़े बमार महसूस करो, तां देर नेईं करो: इमरजेंसी विभाग च "
                  "जाओ जां {number} पर फोन करो।"),
        "and": " ते ",
        "unsure": "(पक्का नेईं)",
        "thanks": "धन्नवाद।",
    },
}

# ---------------------------------------------------------------- display names
SYMPTOM_NAMES: dict[str, dict[str, str]] = {
    "hi": {
        "fever": "बुखार", "cough": "खांसी", "sore throat": "गले में दर्द",
        "runny or blocked nose": "नाक बहना या बंद होना", "headache": "सिर दर्द", "dizziness": "चक्कर आना",
        "fainting": "बेहोशी", "chest pain": "सीने में दर्द", "palpitations": "दिल की धड़कन तेज़ होना",
        "breathing difficulty": "सांस लेने में तकलीफ़", "stomach pain": "पेट दर्द", "nausea": "मिचली",
        "vomiting": "उल्टी", "diarrhoea": "दस्त", "constipation": "कब्ज़", "burning urination": "पेशाब में जलन",
        "back pain": "कमर दर्द", "knee pain": "घुटने में दर्द", "joint pain": "जोड़ों में दर्द",
        "neck pain": "गर्दन में दर्द", "injury": "चोट", "swelling": "सूजन", "rash": "त्वचा पर दाने",
        "itching": "खुजली", "ear pain": "कान में दर्द", "hearing problem": "सुनने में दिक्कत",
        "eye problem": "आँख की समस्या", "toothache": "दांत दर्द", "weakness": "कमज़ोरी", "tiredness": "थकान",
        "numbness": "सुन्नपन", "bleeding": "खून बहना", "weight change": "वज़न में बदलाव",
        "sleep problem": "नींद की समस्या", "low mood or anxiety": "उदासी या घबराहट", "body pain": "बदन दर्द",
        "chills": "ठंड लगना", "loss of appetite": "भूख न लगना", "pain (location not stated)": "दर्द",
    },
    "ur": {
        "fever": "بخار", "cough": "کھانسی", "sore throat": "گلے میں درد",
        "runny or blocked nose": "ناک بہنا یا بند ہونا", "headache": "سر درد", "dizziness": "چکر آنا",
        "fainting": "بے ہوشی", "chest pain": "سینے میں درد", "palpitations": "دل کی دھڑکن تیز ہونا",
        "breathing difficulty": "سانس لینے میں تکلیف", "stomach pain": "پیٹ درد", "nausea": "متلی",
        "vomiting": "الٹی", "diarrhoea": "دست", "constipation": "قبض", "burning urination": "پیشاب میں جلن",
        "back pain": "کمر درد", "knee pain": "گھٹنے میں درد", "joint pain": "جوڑوں میں درد",
        "neck pain": "گردن میں درد", "injury": "چوٹ", "swelling": "سوجن", "rash": "جلد پر دانے",
        "itching": "خارش", "ear pain": "کان میں درد", "hearing problem": "سننے میں دقت",
        "eye problem": "آنکھ کی تکلیف", "toothache": "دانت درد", "weakness": "کمزوری", "tiredness": "تھکاوٹ",
        "numbness": "سن ہونا", "bleeding": "خون بہنا", "weight change": "وزن میں تبدیلی",
        "sleep problem": "نیند کی تکلیف", "low mood or anxiety": "اداسی یا گھبراہٹ", "body pain": "جسم میں درد",
        "chills": "سردی لگنا", "loss of appetite": "بھوک نہ لگنا", "pain (location not stated)": "درد",
    },
    # DRAFT Dogri names (Devanagari); medical words are the same loanwords Dogri speakers use.
    "doi": {
        "fever": "बुखार", "cough": "खांसी", "sore throat": "गले च दर्द",
        "runny or blocked nose": "नाक बगना जां बंद होना", "headache": "सिर दर्द", "dizziness": "चक्कर औना",
        "fainting": "बेहोशी", "chest pain": "छाती च दर्द", "palpitations": "दिल दी धड़कन तेज होना",
        "breathing difficulty": "साह लैने च परेशानी", "stomach pain": "पेट दर्द", "nausea": "मितली",
        "vomiting": "उल्टी", "diarrhoea": "दस्त", "constipation": "कब्ज", "burning urination": "पेशाब च जलन",
        "back pain": "कमर दर्द", "knee pain": "गोड्डे च दर्द", "joint pain": "जोड़ें च दर्द",
        "neck pain": "गर्दन च दर्द", "injury": "चोट", "swelling": "सूजन", "rash": "चमड़ी उप्पर दाने",
        "itching": "खुजली", "ear pain": "कन्न च दर्द", "hearing problem": "सुनने च दिक्कत",
        "eye problem": "अक्ख दी परेशानी", "toothache": "दंद दर्द", "weakness": "कमजोरी", "tiredness": "थकान",
        "numbness": "सुन्नपन", "bleeding": "खून बगना", "weight change": "भार च बदलाऽ",
        "sleep problem": "नींद दी परेशानी", "low mood or anxiety": "उदासी जां घबराहट", "body pain": "शरीर दर्द",
        "chills": "ठंड लगना", "loss of appetite": "भुक्ख नेईं लगना", "pain (location not stated)": "दर्द",
    },
}

DEPARTMENT_NAMES: dict[str, dict[str, str]] = {
    "hi": {
        "general_medicine": "सामान्य चिकित्सा", "cardiology": "हृदय रोग (कार्डियोलॉजी)",
        "pulmonology": "फेफड़े (पल्मोनोलॉजी)", "gastroenterology": "पेट रोग (गैस्ट्रोएंटरोलॉजी)",
        "orthopaedics": "हड्डी रोग (ऑर्थोपेडिक्स)", "neurology": "न्यूरोलॉजी", "ent": "कान, नाक और गला (ईएनटी)",
        "dermatology": "त्वचा रोग", "ophthalmology": "नेत्र रोग", "urology": "मूत्र रोग (यूरोलॉजी)",
        "dental": "दंत चिकित्सा", "psychiatry": "मनोचिकित्सा",
    },
    "ur": {
        "general_medicine": "جنرل میڈیسن", "cardiology": "امراضِ قلب (کارڈیالوجی)",
        "pulmonology": "پھیپھڑوں کے امراض (پلمونولوجی)", "gastroenterology": "معدے کے امراض (گیسٹرو)",
        "orthopaedics": "ہڈیوں کے امراض (آرتھوپیڈکس)", "neurology": "نیورولوجی", "ent": "کان، ناک اور گلا (ای این ٹی)",
        "dermatology": "جلد کے امراض", "ophthalmology": "آنکھوں کے امراض", "urology": "یورولوجی",
        "dental": "دانتوں کا شعبہ", "psychiatry": "نفسیات",
    },
}
# Dogri hospital departments are named with the same Devanagari loanwords as Hindi (DRAFT, to review).
DEPARTMENT_NAMES["doi"] = dict(DEPARTMENT_NAMES["hi"])

# ---------------------------------------------------------------- native-script glossary
# canonical vocabulary term -> (English phrase used in the internal analysis text,
#                                Hindi phrases, Urdu phrases)
# This is a SAFETY NET next to the translation model: it lets the assistant still recognise common
# symptoms if the model is not installed or mistranslates a medical word. Literal phrases only.
NATIVE_GLOSSARY: dict[str, tuple[str, list[str], list[str]]] = {
    "fever": ("fever", ["बुखार", "ज्वर"], ["بخار"]),
    "cough": ("cough", ["खांसी", "खाँसी"], ["کھانسی"]),
    "sore throat": ("sore throat", ["गले में दर्द", "गला खराब", "गले में खराश"], ["گلے میں درد", "گلا خراب", "گلے میں خراش"]),
    "runny or blocked nose": ("runny nose", ["बहती नाक", "नाक बह", "नाक बंद", "जुकाम"], ["ناک بہ", "ناک بند", "نزلہ"]),
    "headache": ("headache", ["सिर दर्द", "सिरदर्द", "सर दर्द", "सिर में दर्द", "सर में दर्द"], ["سر درد", "سردرد", "سر میں درد"]),
    "dizziness": ("dizzy", ["चक्कर"], ["چکر"]),
    "fainting": ("fainted", ["बेहोश"], ["بے ہوش", "بیہوش"]),
    "chest pain": ("chest pain", ["सीने में दर्द", "छाती में दर्द", "सीने का दर्द", "सीने में जकड़न"], ["سینے میں درد", "سینے کا درد", "چھاتی میں درد"]),
    "palpitations": ("palpitations", ["धड़कन तेज", "दिल की धड़कन", "दिल धड़क"], ["دھڑکن تیز", "دل کی دھڑکن", "دل دھڑک"]),
    "breathing difficulty": ("shortness of breath", ["सांस लेने में तकलीफ", "साँस लेने में तकलीफ", "सांस लेने में दिक्कत", "साँस लेने में दिक्कत", "सांस फूल", "साँस फूल", "सांस में तकलीफ", "सांस नहीं आ"], ["سانس لینے میں تکلیف", "سانس لینے میں دشواری", "سانس پھول", "سانس کی تکلیف", "سانس میں تکلیف", "سانس نہیں آ"]),
    "stomach pain": ("stomach pain", ["पेट दर्द", "पेट में दर्द", "पेट का दर्द"], ["پیٹ درد", "پیٹ میں درد", "پیٹ کا درد"]),
    "nausea": ("nausea", ["मिचली", "मितली", "जी मिचल"], ["متلی", "جی متلا"]),
    "vomiting": ("vomiting", ["उल्टी", "उलटी"], ["الٹی", "قے"]),
    "diarrhoea": ("diarrhea", ["दस्त", "पतले दस्त", "लूज़ मोशन", "लूज मोशन"], ["دست", "پتلے دست"]),
    "constipation": ("constipation", ["कब्ज"], ["قبض"]),
    "burning urination": ("burning urination", ["पेशाब में जलन"], ["پیشاب میں جلن"]),
    "back pain": ("back pain", ["कमर दर्द", "कमर में दर्द", "पीठ दर्द", "पीठ में दर्द"], ["کمر درد", "کمر میں درد", "پیٹھ میں درد"]),
    "knee pain": ("knee pain", ["घुटने में दर्द", "घुटनों में दर्द", "घुटने का दर्द"], ["گھٹنے میں درد", "گھٹنوں میں درد"]),
    "joint pain": ("joint pain", ["जोड़ों में दर्द", "जोड़ों का दर्द"], ["جوڑوں میں درد", "جوڑوں کا درد"]),
    "neck pain": ("neck pain", ["गर्दन में दर्द", "गर्दन दर्द"], ["گردن میں درد", "گردن درد"]),
    "injury": ("injury", ["चोट"], ["چوٹ"]),
    "swelling": ("swelling", ["सूजन"], ["سوجن"]),
    "rash": ("rash", ["दाने", "चकत्ते"], ["دانے", "جلد پر نشان"]),
    "itching": ("itching", ["खुजली"], ["خارش"]),
    "ear pain": ("ear pain", ["कान में दर्द", "कान दर्द"], ["کان میں درد", "کان درد"]),
    "hearing problem": ("hearing loss", ["सुनाई नहीं", "सुनने में दिक्कत"], ["سنائی نہیں", "سننے میں دقت"]),
    "eye problem": ("eye pain", ["आँख में दर्द", "आंख में दर्द", "धुंधला दिख", "आँखें लाल"], ["آنکھ میں درد", "دھندلا نظر", "آنکھیں لال"]),
    "toothache": ("toothache", ["दांत दर्द", "दाँत दर्द", "दांत में दर्द", "दाँत में दर्द"], ["دانت درد", "دانت میں درد"]),
    "weakness": ("weakness", ["कमजोरी", "कमज़ोरी"], ["کمزوری"]),
    "tiredness": ("tired", ["थकान", "थकावट"], ["تھکاوٹ", "تھکن"]),
    "numbness": ("numbness", ["सुन्न", "झनझनाहट"], ["سن ہو", "جھنجھناہٹ"]),
    "bleeding": ("bleeding", ["खून बह", "खून आ", "रक्तस्राव"], ["خون بہ", "خون آ"]),
    "sleep problem": ("can't sleep", ["नींद नहीं आ"], ["نیند نہیں آ"]),
    "low mood or anxiety": ("anxiety", ["घबराहट", "उदासी", "चिंता"], ["گھبراہٹ", "اداسی", "پریشانی"]),
    "body pain": ("body pain", ["बदन दर्द", "शरीर में दर्द", "बदन में दर्द"], ["جسم میں درد", "بدن درد", "بدن میں درد"]),
    "chills": ("chills", ["ठंड लगना", "ठंड लग", "कंपकंपी"], ["سردی لگ", "کپکپی"]),
    "loss of appetite": ("loss of appetite", ["भूख नहीं", "भूख कम"], ["بھوک نہیں", "بھوک کم"]),
    "pain (location not stated)": ("pain", ["दर्द"], ["درد"]),
}

# Dogri (Devanagari) phrases, used IN ADDITION to the Hindi phrases above (which Dogri shares for loanwords
# such as बुखार / उल्टी). Dogri puts the postposition "च" where Hindi has "में", so "पेट च दर्द" must be
# listed explicitly. DRAFT: a fluent Dogri speaker should extend and correct this list.
DOGRI_GLOSSARY: dict[str, list[str]] = {
    "sore throat": ["गले च दर्द", "गले च खराश", "गले च पीड़"],
    "runny or blocked nose": ["नाक बगदा", "नाक बगना", "नाक बंद", "नाक बन्द"],
    "headache": ["सिर च दर्द", "सिर च पीड़", "सिर पीड़"],
    "chest pain": ["छाती च दर्द", "छाती च पीड़", "सीने च दर्द", "छाती च जकड़न", "छाती दा दर्द"],
    "palpitations": ["धड़कन तेज", "दिल दी धड़कन", "दिल धड़कदा"],
    "breathing difficulty": ["साह लैने च परेशानी", "साह लैने च तकलीफ", "साह लैने च दिक्कत", "सांस लैने च परेशानी",
                             "सांस लैने च तकलीफ", "सांस लैने च दिक्कत", "साह लैना औखा", "सांस लैना औखा",
                             "साह फुल्ल", "सांस फुल्ल", "साह नेईं आ", "सांस नेईं आ"],
    "stomach pain": ["पेट च दर्द", "पेट च पीड़", "पेट दा दर्द", "ढिड्ड च दर्द"],
    "nausea": ["जी मिचल", "जी खराब"],
    "vomiting": ["उल्टियां", "उल्टी आ"],
    "burning urination": ["पेशाब च जलन"],
    "back pain": ["कमर च दर्द", "पिट्ठ च दर्द", "पिट्ठ दर्द"],
    "knee pain": ["गोड्डे च दर्द", "गोडें च दर्द", "गोड्डे दर्द"],
    "joint pain": ["जोड़ें च दर्द", "जोड़ां च दर्द"],
    "neck pain": ["गर्दन च दर्द"],
    "injury": ["सट्ट"],
    "swelling": ["सुज्ज"],
    "itching": ["खाज"],
    "ear pain": ["कन्न च दर्द", "कान च दर्द", "कन्न दर्द"],
    "hearing problem": ["सुनाई नेईं", "सुनने च दिक्कत"],
    "eye problem": ["अक्ख च दर्द", "अक्खीं च दर्द", "आंख च दर्द", "अक्खीं लाल"],
    "toothache": ["दंद च दर्द", "दंद दर्द", "दांत च दर्द"],
    "tiredness": ["थकेवां"],
    "bleeding": ["खून बग", "खून आ"],
    "sleep problem": ["नींद नेईं आ"],
    "body pain": ["शरीर च दर्द", "बदन च दर्द"],
    "chills": ["कम्बनी", "ठंड लग"],
    "loss of appetite": ["भुक्ख नेईं", "भूख नेईं", "भुक्ख घट"],
    "pain (location not stated)": ["पीड़"],
}

# Words that deny a symptom when they follow it ("बुखार नहीं है") or come just before it ("बिना बुखार").
NEGATION_AFTER = {"hi": ["नहीं", "नही", "ना है"], "ur": ["نہیں", "نہ ہے", "نہ"],
                  "doi": ["नेईं", "नेई", "नहीं", "नही"]}
NEGATION_BEFORE = {"hi": ["बिना", "कोई नहीं", "नहीं है"], "ur": ["بغیر", "کوئی نہیں", "نہیں ہے"],
                   "doi": ["बिना", "बगैर", "कोई नेईं", "कोई नहीं"]}
CLAUSE_BREAKS = ["।", "۔", ".", ",", "،", ";", "!", "?", "؟", "\n", "लेकिन", "मगर", "लेकिन", "لیکن", "مگر", "और", "اور",
                 " ते ", " पर ", " लेकन "]

# Details given as answers to the assistant's questions, in Hindi / Urdu.
SIDE_WORDS = {  # the last Devanagari entries in each list are Dogri (सज्जा = right, खब्बा = left)
    "right": ["दाएं", "दायीं", "दाईं", "दाहिने", "दाहिनी", "दाया", "दायाँ", "دائیں", "دایاں", "دائی",
              "सज्जा", "सज्जे", "सज्जी"],
    "left": ["बाएं", "बायीं", "बाईं", "बायाँ", "बाया", "بائیں", "بایاں", "بائی", "खब्बा", "खब्बे", "खब्बी"],
}
REGION_WORDS = {
    "upper": ["ऊपर", "اوپر", "اوپری", "उप्पर"],
    "lower": ["नीचे", "निचले", "निचला", "نیچے", "نچلے", "نچلا", "थल्ले", "थल्लले", "थल्ला"],
    "middle": ["बीच", "नाभि", "درمیان", "بیچ", "ناف", "बिच्च", "नाभी", "बश्कार"],
}
SEVERITY_NATIVE = {
    "mild": ["हल्का", "हल्की", "ہلکا", "ہلکی", "हौला", "हौली"],
    "moderate": ["मध्यम", "درمیانہ", "درمیانی", "दरम्याना"],
    "severe": ["गंभीर", "बहुत तेज", "तेज दर्द", "असहनीय", "شدید", "بہت تیز", "ناقابل برداشت",
               "बड़ा तेज", "बौहत तेज", "बड़ा सख्त", "सहन नेईं"],
}
NO_WORDS = {"en": ["no", "none", "nothing", "nope", "no other"], "hi": ["नहीं", "कुछ नहीं", "नही"],
            "ur": ["نہیں", "کچھ نہیں"], "doi": ["नेईं", "नेई", "नहीं", "किश नेईं", "कुछ नेईं", "कोई नेईं"]}
