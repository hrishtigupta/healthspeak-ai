import React, { useMemo, useState, useRef } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  AudioLines,
  Bell,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileText,
  HeartPulse,
  Languages,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageCircle,
  Mic,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Stethoscope,
  User,
  UserRound,
  Users,
  X,
  Eye,
  EyeOff,
  Phone,
  History,
  ClipboardList,
  Sparkles,
  Headphones,
} from "lucide-react";
const patients0 = [
  [
    "#42",
    "Rohan Das",
    45,
    "Male",
    "09:30 AM",
    "Dr. Kumar",
    "Cardiology",
    "Waiting",
    "Intake done",
    "Fever, headache, weakness",
  ],
  [
    "#43",
    "Ananya Mehta",
    32,
    "Female",
    "09:35 AM",
    "Dr. Kapoor",
    "General medicine",
    "Checked-in",
    "Intake done",
    "Persistent cough, mild fever",
  ],
  [
    "#44",
    "Meera Patel",
    58,
    "Female",
    "09:40 AM",
    "Dr. Sharma",
    "General medicine",
    "Waiting",
    "In review",
    "Stomach pain, nausea",
  ],
  [
    "#45",
    "Arjun Singh",
    27,
    "Male",
    "09:45 AM",
    "Dr. Rao",
    "Orthopaedics",
    "Waiting",
    "Pending",
    "Knee pain",
  ],
  [
    "#46",
    "Fatima Khan",
    39,
    "Female",
    "09:50 AM",
    "Dr. Kapoor",
    "Pulmonology",
    "Waiting",
    "Intake done",
    "Breathing discomfort",
  ],
  [
    "#47",
    "Vikram Shah",
    51,
    "Male",
    "09:55 AM",
    "Dr. Dev",
    "Cardiology",
    "Completed",
    "Intake done",
    "Routine follow-up",
  ],
  [
    "#48",
    "Lakshmi Nair",
    63,
    "Female",
    "10:00 AM",
    "Dr. Rao",
    "Neurology",
    "Waiting",
    "Pending",
    "Headache",
  ],
  [
    "#49",
    "Suresh Kumar",
    34,
    "Male",
    "10:05 AM",
    "Dr. Sharma",
    "General medicine",
    "Completed",
    "Intake done",
    "Annual health checkup",
  ],
].map(
  ([id, name, age, gender, time, doctor, dept, status, intake, symptoms]) => ({
    id,
    name,
    age,
    gender,
    time,
    doctor,
    dept,
    status,
    intake,
    symptoms,
  }),
);
const records = [
  {
    date: "Oct 15, 2026",
    symptoms: "Stomach pain, Nausea",
    dept: "Gastroenterology",
    doctor: "Dr. Priya Sharma",
    quote:
      "Doctor, I have been having severe stomach pain since yesterday morning, and I feel very nauseous, especially after eating anything.",
    confidence: "98%",
    location: "HealthSpeak Main City Hospital (Room 203)",
    meds: "Pantoprazole 40mg (1-0-0) · Ondansetron 4mg (SOS)",
  },
  {
    date: "Sep 28, 2026",
    symptoms: "Persistent cough, Mild fever",
    dept: "Pulmonology",
    doctor: "Dr. Rajesh Verma",
    quote:
      "I have a persistent dry cough that isn’t going away, and a mild fever that comes and goes for the last 5 days.",
    confidence: "97%",
    location: "HealthSpeak North Wing Clinic (Cabin 4)",
    meds: "Ascoril LS Syrup (10ml) · Paracetamol 500mg (1-1-1)",
  },
  {
    date: "Jun 10, 2026",
    symptoms: "Routine Health Checkup (None)",
    dept: "General Medicine",
    doctor: "Dr. Sanjeev Kumar",
    quote:
      "I just want to get my annual routine health checkup done. I have no specific symptoms, just need my blood work and general vitals checked.",
    confidence: "99%",
    location: "HealthSpeak Main City Hospital (Room 304)",
    meds: "Comprehensive Blood Panel (CBC) · Supradyn Multivitamins",
  },
];
const Btn = ({ children, kind = "", ...p }) => (
  <button className={"btn " + kind} {...p}>
    {children}
  </button>
);
const Brand = ({ go }) => (
  <button className="brand" onClick={() => go("home")}>
    <span>∿</span> HealthSpeak AI
  </button>
);
const Field = ({ label, ...p }) => (
  <label className="field">
    <span>{label}</span>
    <input {...p} />
  </label>
);
const Info = ({ label, value }) => (
  <div className="info">
    <small>{label}</small>
    <b>{value}</b>
  </div>
);
const Status = ({ value }) => (
  <span
    className={
      "status " +
      (value === "Completed"
        ? "done"
        : value === "Checked-in"
          ? "blue"
          : "wait")
    }
  >
    {value}
  </span>
);
export default function App() {
  const [page, S] = useState("home"),
    [role, R] = useState("Patient"),
    [email, E] = useState(""),
    [password, P] = useState(""),
    [showPass, SP] = useState(false),
    [name, N] = useState(""),
    [mobile, M] = useState(""),
    [dob, D] = useState(""),
    [gender, G] = useState(""),
    [pref, Pref] = useState("Hindi"),
    [language, L] = useState("English"),
    [toast, T] = useState(""),
    [modal, Modal] = useState(""),
    [messages, Msgs] = useState([
      {
        by: 'doctor',
        text: 'Hello! Welcome to HealthSpeak AI. I can help you share your health concerns in your preferred language. What symptoms or concerns would you like to tell us about today?'
    },
    ]),
    [message, Msg] = useState(""),
    [voice, V] = useState(""),
    [listening, Listen] = useState(false),
    [recordsIndex, RI] = useState(0),
    [patients, Patients] = useState(patients0),
    [selected, Selected] = useState(patients0[0]),
    [query, Q] = useState(""),
    [filter, F] = useState("All"),
    [editing, Editing] = useState(false),
    [editName, EN] = useState("Rohan Das"),
    [editStatus, ES] = useState("Waiting"),
    [note, Note] = useState("");
  const notify = (x) => {
    T(x);
    setTimeout(() => T(""), 3000);
  };

  const recognitionRef = useRef(null);

  const toggleListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
      Listen(false);
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      notify("Speech recognition is not supported. Use Chrome or Edge.");
      return;
    }

    const recognition = new SpeechRecognition();

    const languageCodes = {
      English: "en-IN",
      Hindi: "hi-IN",
      Urdu: "ur-PK",
      Dogri: "hi-IN",
      Punjabi: "pa-IN",
    };

    recognition.lang = languageCodes[language] || "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join("");

      V(transcript);
    };

    recognition.onerror = (event) => {
      Listen(false);
      recognitionRef.current = null;
      notify("Microphone error: " + event.error);
    };

    recognition.onend = () => {
      Listen(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
      Listen(true);
    } catch (error) {
      recognitionRef.current = null;
      Listen(false);
      notify("Could not start microphone. Try again.");
    }
  };
  const go = (x) => {
    S(x);
    Modal("");
    window.scrollTo(0, 0);
  };
  const filtered = useMemo(
    () =>
      patients.filter(
        (p) =>
          (p.name.toLowerCase().includes(query.toLowerCase()) ||
            p.id.toLowerCase().includes(query.toLowerCase())) &&
          (filter === "All" || p.status === filter),
      ),
    [patients, query, filter],
  );
  const login = () => {
    if (!email.trim() || !password.trim())
      return notify("Enter your email/mobile number and password.");
    go(role === "Patient" ? "dashboard" : "staff");
    notify("Logged in successfully (demo).");
  };
  const send = () => {
    if (!message.trim()) return;

    Msgs(m => [
        ...m,
        { by: 'patient', text: message },
        {
        by: 'doctor',
        text: 'Thank you for sharing your concern. Your response has been added to your intake summary. You can share any additional symptoms or information. Your information will be reviewed by medical staff.'
        }
    ]);

    Msg('');
  };
  const voiceContinue = () => {

  // Do not continue if no speech or text was entered
    if (!voice.trim()) {
        notify('Please speak or enter your health concern first.');
        return;
    }

    // Stop microphone if it is still active
    if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
    }

    Listen(false);

    // Add the patient's actual words to the chat
    Msgs(m => [
        ...m,
        {
        by: 'patient',
        text: voice
        },
        {
        by: 'doctor',
        text: 'Thank you for sharing your concern with HealthSpeak AI. Your information has been added to the intake summary for medical staff review.'
        }
    ]);

    go('chat');
    };
  const update = (patch) => {
    let p = { ...selected, ...patch };
    Selected(p);
    Patients((a) => a.map((x) => (x.id === p.id ? p : x)));
  };
  const toastUI = toast && (
    <div className="toast">
      <CheckCircle2 />
      {toast}
      <button onClick={() => T("")}>
        <X />
      </button>
    </div>
  );
  return (
    <div className="app">
      {page === "home" && (
        <>
          <header className="topbar">
            <Brand go={go} />
            <nav>
              <a href="#home">Home</a>
              <a href="#features">Features</a>
              <a href="#languages">Languages</a>
              <a href="#faqs">FAQs</a>
              <a href="#contact">Contact us</a>
            </nav>
            <Btn onClick={() => go("login")}>Log in</Btn>
          </header>
          <main className="landing" id="home">
            <section className="hero">
              <div>
                <span className="eyebrow">
                  <Sparkles /> Welcome to AI Health Assistant
                </span>
                <h1>
                  Your Health,
                  <br />
                  <em>Your Language.</em>
                </h1>
                <p>
                   Share your health concerns with HealthSpeak AI in the language
                    you are comfortable with. Your information will be organised
                    for medical staff review.
                </p>
                <div className="actions">
                  <Btn onClick={() => go("login")}>
                    Start Chatting Now <ArrowRight />
                  </Btn>
                  <Btn kind="outline" onClick={() => go("voice")}>
                    <Mic /> Voice Input
                  </Btn>
                </div>
              </div>
              <div className="hero-art">
                <div className="hero-blob">
                  <div className="phone-art">
                    <MessageCircle />
                    <b>
                      How can we help
                      <br />
                      you today?
                    </b>
                    <span>∿ ∿ ∿</span>
                  </div>
                  <div className="doctor-art">
                    <Stethoscope />
                    <b>Care in your language</b>
                  </div>
                </div>
                <span className="float f1">
                  <AudioLines /> Voice + Text
                </span>
                <span className="float f2">
                  <Languages /> Multiple languages
                </span>
              </div>
            </section>
            <section className="features" id="features">
              <article>
                <AudioLines />
                <b>Voice & Text</b>
                <p>Speak or type your concern in the way that feels natural.</p>
              </article>
              <article>
                <Languages />
                <b>Multiple Languages</b>
                <p>Communicate comfortably in your preferred language.</p>
              </article>
              <article>
                <Clock3 />
                <b>24/7 Availability</b>
                <p>Start your intake whenever you need assistance.</p>
              </article>
            </section>
            <section className="how">
              <div>
                <span className="eyebrow">A simpler first step</span>
                <h2>
                  Better conversations.
                  <br />
                  <em>Better care.</em>
                </h2>
                <p>
                  Share what you are experiencing. HealthSpeak AI helps
                  structure your information so the medical team can review it.
                </p>
              </div>
              <div className="how-cards">
                <article>
                  <i>01</i>
                  <h3>Choose your language</h3>
                  <p>
                    Start with voice or text in a language you are comfortable
                    with.
                  </p>
                </article>
                <article>
                  <i>02</i>
                  <h3>Share your concern</h3>
                  <p>
                    Describe your symptoms and answer a few simple questions.
                  </p>
                </article>
                <article>
                  <i>03</i>
                  <h3>Staff review</h3>
                  <p>
                    Your structured intake is routed to the appropriate medical
                    team.
                  </p>
                </article>
              </div>
            </section>
            <section className="cta" id="languages">
              <div>
                <h2>Care begins with being understood.</h2>
                <p>Choose your language and start a conversation.</p>
              </div>
              <Btn onClick={() => go("login")}>
                Get started <ArrowRight />
              </Btn>
            </section>
            <section className="faq-section" id="faqs">
              <span className="eyebrow">FREQUENTLY ASKED QUESTIONS</span>
              <h2>Good to know</h2>
              <div>
                <article>
                  <b>Can I use my preferred language?</b>
                  <p>
                    Yes. Select your preferred language in the voice or chat intake
                    screen. Voice transcription depends on browser speech recognition
                    support and language availability.
                  </p>
                </article>
                <article>
                  <b>Does the AI provide a medical diagnosis?</b>
                  <p>
                    No. HealthSpeak AI structures the information you share for
                    review by the medical team. The demo does not provide
                    clinical decisions.
                  </p>
                </article>
                <article>
                  <b>Is my information stored?</b>
                  <p>
                    No. This frontend prototype uses temporary in-memory sample
                    data and has no backend or database.
                  </p>
                </article>
              </div>
            </section>
            <footer id="contact">
              <Brand go={go} />
              <span>
                © 2026 HealthSpeak AI · Frontend demonstration prototype
              </span>
              <a href="#faqs">FAQs</a>
            </footer>
          </main>
        </>
      )}
      {page === "login" && (
        <Auth go={go}>
          <div className="auth-form">
            <button className="back" onClick={() => go("home")}>
              <ArrowLeft /> Back to home
            </button>
            <span className="eyebrow">YOUR HEALTH, YOUR LANGUAGE</span>
            <h2>Welcome Back 👋</h2>
            <p>Please select your role and enter your details to log in.</p>
            <b className="label-title">I am logging in as</b>
            <div className="roles">
              {["Patient", "Doctor", "Staff"].map((r) => (
                <button
                  className={role === r ? "chosen" : ""}
                  onClick={() => R(r)}
                >
                  {r === "Patient" ? (
                    <UserRound />
                  ) : r === "Doctor" ? (
                    <Plus />
                  ) : (
                    <Users />
                  )}
                  {r}
                </button>
              ))}
            </div>
            <Field
              label="Email or Phone Number"
              placeholder="Enter your email or mobile number"
              value={email}
              onChange={(e) => E(e.target.value)}
            />
            <label className="field">
              <span>Password</span>
              <div className="pass">
                <input
                  type={showPass ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => P(e.target.value)}
                />
                <button onClick={() => SP(!showPass)}>
                  {showPass ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </label>
            <div className="forgot">
              <button onClick={() => Modal("forgot")}>Forgot Password?</button>
            </div>
            <Btn onClick={login}>Log in</Btn>
            <p className="switch">
              Don't have an account?{" "}
              <button onClick={() => go("signup")}>Sign up</button>
            </p>
            <small className="demo-note">
              Demo only · Any non-empty credentials will work
            </small>
          </div>
        </Auth>
      )}
      {page === "signup" && (
        <Auth go={go}>
          <form
            className="auth-form signup"
            onSubmit={(e) => {
              e.preventDefault();
              if (!name || !mobile || !dob || !gender || password.length < 6)
                return notify(
                  "Complete all fields. Password needs at least 6 characters.",
                );
              go("dashboard");
              notify("Account created successfully (demo).");
            }}
          >
            <button type="button" className="back" onClick={() => go("home")}>
              <ArrowLeft /> Back to home
            </button>
            <span className="eyebrow">JOIN HEALTHSPEAK AI</span>
            <h2>Create your account</h2>
            <p>Join as a patient. Make care more connected.</p>
            <label className="field">
              <span>Preferred Language (AI Voice & Text)</span>
              <select value={pref} onChange={(e) => Pref(e.target.value)}>
                {[
                  "Hindi",
                  "English",
                  "Urdu",
                  "Dogri",
                  "Punjabi",
                  "Bengali",
                  "Tamil",
                  "Telugu",
                ].map((x) => (
                  <option>{x}</option>
                ))}
              </select>
            </label>
            <Field
              label="Full Name"
              placeholder="e.g. Ankit Kumar"
              value={name}
              onChange={(e) => N(e.target.value)}
              required
            />
            <Field
              label="Mobile Number"
              placeholder="+91 Enter your mobile number"
              value={mobile}
              onChange={(e) => M(e.target.value)}
              required
            />
            <div className="two">
              <Field
                label="Date of Birth"
                type="date"
                value={dob}
                onChange={(e) => D(e.target.value)}
                required
              />
              <label className="field">
                <span>Gender</span>
                <select
                  value={gender}
                  onChange={(e) => G(e.target.value)}
                  required
                >
                  <option value="">Select</option>
                  {["Female", "Male", "Other", "Prefer not to say"].map((x) => (
                    <option>{x}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Create Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => P(e.target.value)}
                minLength="6"
                required
                placeholder="At least 6 characters"
              />
            </label>
            <label className="check">
              <input type="checkbox" required /> I agree to the Terms &
              Conditions
            </label>
            <Btn type="submit">Create Account</Btn>
            <p className="switch">
              Already have an account?{" "}
              <button type="button" onClick={() => go("login")}>
                Log in
              </button>
            </p>
          </form>
        </Auth>
      )}
      {page === "voice" && (
        <div className="voice-screen">
          <header>
            <Brand go={go} />
            <Btn kind="ghost" onClick={() => go("chat")}>
              Skip to text chat <ArrowRight />
            </Btn>
          </header>
          <div className="voice-center">
            <span className="eyebrow">VOICE INTAKE</span>
            <h2>{listening ? "Listening..." : "Speak in your language"}</h2>
            <p>
              {listening
                ? "Listening for your concern. Tap the microphone when finished."
                : "Press the microphone and tell us what you are experiencing."}
            </p>
            <div className={"sound " + (listening ? "on" : "")}>
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
            </div>
            <textarea
              value={voice}
              onChange={(e) => V(e.target.value)}
              placeholder="Your words will appear here..."
            />
            <div className="mic-controls">
              <button onClick={() => Modal("voicehelp")}>?</button>
              <button
                className={"mic " + (listening ? "recording" : "")}
                onClick={toggleListening}
              >
                {listening ? <AudioLines /> : <Mic />}
              </button>
              <button onClick={() => {
                if (recognitionRef.current) {
                    recognitionRef.current.stop();
                    recognitionRef.current = null;
                }

                V('');
                Listen(false);
                }}>
                <X/>
                </button>
            </div>
            <div className="voice-bottom">
              <label>
                <Languages /> Language{" "}
                <select value={language} onChange={(e) => L(e.target.value)}>
                  {["English", "Hindi", "Urdu", "Dogri", "Punjabi"].map((x) => (
                    <option>{x}</option>
                  ))}
                </select>
              </label>
              <Btn onClick={voiceContinue}>
                Continue to chat <ArrowRight />
              </Btn>
            </div>
            <small className="demo-note">
                Speech recognition uses your browser's microphone feature.
                Please review the transcribed text before continuing.
            </small>
          </div>
        </div>
      )}
      {page === "chat" && (
        <div className="chat-page">
          <header>
        <Brand go={go}/>
        <div>
            <span className="online-dot"/>
            HealthSpeak AI Intake Assistant
            <Btn kind="danger" onClick={()=>Modal('endchat')}>
            End Chat
            </Btn>
        </div>
        </header>
          <main className="chat-main">
            <div className="doctor-line">
            <div className="avatar">HS</div>
            <div>
                <b>HealthSpeak AI</b>
                <small>
                <span className="online-dot"/>
                AI Intake Assistant
                </small>
            </div>
            </div>
            <div className="messages">
              {messages.map((m) => (
                <div className={"message " + m.by}>
                  <div className="avatar">
                    {m.by === "patient" ? "You" : "HS"}
                  </div>
                  <p>{m.text}</p>
                </div>
              ))}
            </div>
            <div className="composer">
              <div className="compose-tools">
                <button
                  onClick={() => document.getElementById("attach").click()}
                >
                  <Paperclip />
                </button>
                <input
                  id="attach"
                  type="file"
                  hidden
                  onChange={(e) =>
                    e.target.files[0] &&
                    notify(e.target.files[0].name + " attached")
                  }
                />
                <select value={language} onChange={(e) => L(e.target.value)}>
                  {["English", "Hindi", "Urdu", "Dogri"].map((x) => (
                    <option>{x}</option>
                  ))}
                </select>
                <button onClick={() => go("voice")}>
                  <Mic />
                </button>
              </div>
              <div className="sendline">
                <input
                  value={message}
                  onChange={(e) => Msg(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Type your message here..."
                />
                <button onClick={send}>
                  <Send />
                </button>
              </div>
              <small>
                Medical staff review information before care decisions.
              </small>
            </div>
          </main>
        </div>
      )}
      {page === "doctor" && (
        <div className="profile-page">
          <section className="profile-card">
            <div className="profile-head">
              <Brand go={go} />
              <Btn kind="outline" onClick={() => go("chat")}>
                <X /> Close
              </Btn>
            </div>
            <span className="eyebrow">YOUR CARE TEAM</span>
            <h2>Doctor Profile</h2>
            <p>Information about your assigned healthcare professional.</p>
            <div className="doctor-profile">
              <div>DS</div>
              <section>
                <h3>Dr. Divya Sharma</h3>
                <p>General Medicine Specialist</p>
                <span className="status done">● Online</span>
              </section>
            </div>
            <div className="detail-grid">
            <Info label="Department" value="Internal Medicine (OPD)"/>
            <Info label="Hospital / Clinic Location" value="HealthSpeak Main City Hospital"/>
            <Info label="Specialization" value="General Physician"/>
            <Info label="Cabin / Room Number" value="Room 304, Block A"/>
            <Info label="Profile Status" value="Sample doctor profile"/>
            </div>

            <p className="demo-note">
            This is illustrative doctor information for the frontend prototype.
            No real doctor assignment or consultation is taking place.
            </p>
            <Btn onClick={() => go("chat")}>
              <ArrowLeft /> Back to Chat
            </Btn>
          </section>
        </div>
      )}
      {page === "dashboard" && (
        <PatientDashboard
          go={go}
          language={language}
          setLanguage={L}
          setIndex={RI}
          notify={notify}
        />
      )}
      {page === "summary" && (
        <div className="summary">
          <header>
            <div>
              <h2>Consultation Summary</h2>
              <b>{records[recordsIndex].date}</b>
            </div>
            <Btn kind="outline" onClick={() => go("dashboard")}>
              <ArrowLeft /> Back
            </Btn>
          </header>
          <main>
            <div className="quote">
              <div className="avatar">AK</div>
              <blockquote>“{records[recordsIndex].quote}”</blockquote>
            </div>
            <section className="structured">
              <div className="section-title">
                <h3>
                  <ClipboardList /> Structured Intake & Resolution
                </h3>
                <span className="status blue">Sample Extraction Output</span>
              </div>
              <div className="summary-grid">
                <Info
                  label="Reported symptoms"
                  value={records[recordsIndex].symptoms}
                />
                <b className="confidence">
                Sample: {records[recordsIndex].confidence}
                </b>
                <Info
                  label="Routed department"
                  value={records[recordsIndex].dept}
                />
                <b className="confidence">Sample:95%</b>
                <Info
                  label="Consulting Doctor"
                  value={records[recordsIndex].doctor}
                />
                <Info
                  label="Hospital / Location"
                  value={records[recordsIndex].location}
                />
                <Info
                  label="Prescribed Medicine / Action"
                  value={records[recordsIndex].meds}
                />
              </div>
              <p className="disclaimer">
                <ShieldCheck /> Demo data only. Medication and care information
                must be verified by a qualified healthcare professional.
              </p>
            </section>
          </main>
        </div>
      )}
      {page === "staff" && (
        <Staff
          patients={filtered}
          all={patients}
          query={query}
          setQuery={Q}
          filter={filter}
          setFilter={F}
          go={go}
          choose={(p) => {
            Selected(p);
            EN(p.name);
            ES(p.status);
            go("workspace");
          }}
          notify={notify}
        />
      )}
      {page === "workspace" && (
        <Workspace
          patient={selected}
          editName={editName}
          setEditName={EN}
          editStatus={editStatus}
          setEditStatus={ES}
          editing={editing}
          setEditing={Editing}
          update={update}
          go={go}
          notify={notify}
          note={note}
          setNote={Note}
          modal={Modal}
        />
      )}
      {modal === "forgot" && (
        <ModalBox title="Reset your password" close={() => Modal("")}>
          <p>
            Enter your registered email or mobile number. Reset is simulated in
            this demo.
          </p>
          <Field
            label="Email or mobile number"
            value={email}
            onChange={(e) => E(e.target.value)}
            placeholder="Registered email or phone"
          />
          <Btn
            onClick={() => {
              if (!email.trim())
                return notify("Enter your email or mobile number.");
              Modal("");
              notify("Password reset instructions sent (demo).");
            }}
          >
            Send reset instructions
          </Btn>
        </ModalBox>
      )}
      {modal === "endchat" && (
        <ModalBox title="End this conversation?" close={() => Modal("")}>
          <p>
            Your intake conversation will be closed. You can still view your
            consultation history.
          </p>
          <div className="actions">
            <Btn kind="outline" onClick={() => Modal("")}>
              Continue chat
            </Btn>
            <Btn
              onClick={() => {
                go("dashboard");
                notify("Chat ended. Intake is available for staff review.");
              }}
            >
              End chat
            </Btn>
          </div>
        </ModalBox>
      )}
      {modal === "voicehelp" && (
        <ModalBox title="Using voice input" close={() => Modal("")}>
          <p>1. Choose your preferred language.</p>
          <p>2. Tap the microphone and speak clearly about your concern.</p>
          <p>3. Review the transcribed text, then continue to chat.</p>
          <p className="demo-note">
            Allow microphone access when your browser asks for permission.
            Speech recognition may require an internet connection.
          </p>
        </ModalBox>
      )}
      {modal === "intake" && (
        <ModalBox title="AI intake summary" close={() => Modal("")}>
          <p>
            <b>Reported symptoms:</b> {selected.symptoms}
          </p>
          <p>
            <b>Assigned department:</b> {selected.dept}
          </p>
          <p>
            <b>Review status:</b> {selected.intake}
          </p>
          <p className="demo-note">
            This sample intake must be reviewed by authorised medical staff.
          </p>
        </ModalBox>
      )}
      {toastUI}
    </div>
  );
}
function Auth({ children, go }) {
  return (
    <div className="auth-layout">
      <aside className="auth-aside">
        <Brand go={go} />
        <div className="medical-art">
          <div className="art-circle">
            <Stethoscope />
            <span>•••</span>
            <b>+</b>
          </div>
        </div>
        <div className="aside-copy">
          <h1>
            Your Health,
            <br />
            <em>Your Language.</em>
          </h1>
          <p>
            Bringing people and care closer.
            <br />
            Powered by AI. Connected through language.
          </p>
          <div>
            <b>Better conversations. Better care.</b>
            <small>One connected experience for patients and care teams.</small>
          </div>
        </div>
      </aside>
      <main className="auth-main">{children}</main>
    </div>
  );
}
function PatientDashboard({ go, language, setLanguage, setIndex, notify }) {
  return (
    <div className="patient-layout">
      <aside className="patient-sidebar">
        <Brand go={go} />
        <nav>
          <button className="active">
            <LayoutDashboard /> Dashboard
          </button>
          <button
            onClick={() =>
              notify("Profile details are available in this demo account.")
            }
          >
            <User /> My Profile
          </button>
          <button onClick={() => go("chat")}>
            <MessageCircle /> AI Consultation (Chat)
          </button>
          <button
            onClick={() =>
              document
                .getElementById("history")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            <History /> Past History
          </button>
        </nav>
        <label className="language">
          <Languages />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            {["English", "Hindi", "Urdu", "Dogri", "Punjabi"].map((x) => (
              <option>{x}</option>
            ))}
          </select>
          <ChevronDown />
        </label>
      </aside>
      <main className="patient-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">PATIENT DASHBOARD</span>
            <h2>Welcome to HealthSpeak AI</h2>
            <p>How are you feeling today?</p>
          </div>
          <button className="user-chip" onClick={()=>notify('Patient demo account')}>
            HS
            </button>
        </header>
        <div className="patient-grid">
          <div>
            <section className="consult">
              <div>
                <span className="eyebrow">NEED TO CONSULT A DOCTOR?</span>
                <h3>Start a multilingual AI intake</h3>
                <p>
                  Tell us your symptoms via voice or text, and we'll route you
                  to the right department.
                </p>
                <div className="actions">
                  <Btn onClick={() => go("voice")}>
                    <Mic /> Tap to Speak
                  </Btn>
                  <Btn kind="outline" onClick={() => go("chat")}>
                    <MessageCircle /> Start Text Chat
                  </Btn>
                </div>
              </div>
              <HeartPulse />
            </section>
            <section className="history" id="history">
              <div className="section-title">
                <div>
                  <span className="eyebrow">YOUR RECORDS</span>
                  <h3>Recent Medical History</h3>
                </div>
                <button
                  className="link"
                  onClick={() =>
                    notify("All available demo records are shown.")
                  }
                >
                  View all <ArrowRight />
                </button>
              </div>
              <div className="history-table">
                <div className="history-row head">
                  <span>Date</span>
                  <span>Extracted Symptoms</span>
                  <span>Department</span>
                  <span>Action</span>
                </div>
                {records.map((r, i) => (
                  <div className="history-row">
                    <span>{r.date}</span>
                    <span>{r.symptoms}</span>
                    <span>{r.dept}</span>
                    <button
                      className="link"
                      onClick={() => {
                        setIndex(i);
                        go("summary");
                      }}
                    >
                      View Summary <ArrowRight />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <aside className="intake-card">
            <div className="section-title">
              <h3>Sample Intake Status</h3>
              <span className="status blue">Routed</span>
            </div>
            <small>Reported Symptoms</small>
            <small className="demo-note">
            Illustrative information for demonstration only.
            </small>
            <b>Fever, Headache, Weakness</b>
            <div className="confidence-row">
            <span>Illustrative Demo Score</span>
            <b>94%</b>
            </div>
            <div className="progress">
              <i />
            </div>
            <small>Triage Level</small>
            <span className="status done">Normal</span>
            <Info label="Routed Department" value="General Medicine" />
            <div className="assigned">
            <div className="avatar">HS</div>
            <div>
                <b>HealthSpeak AI</b>
                <small>Intake information awaiting medical staff review</small>
            </div>
            </div>
            <p className="notice">
              <ShieldCheck /> Intake information is a draft for medical staff
              review.
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}
function Staff({
  patients,
  all,
  query,
  setQuery,
  filter,
  setFilter,
  go,
  choose,
  notify,
}) {
  return (
    <div className="staff-layout">
      <aside className="staff-sidebar">
        <Brand go={go} />
        <nav>
          <button className="active">
            <LayoutDashboard /> Overview
          </button>
          <button onClick={() => notify("Patient queue is displayed here.")}>
            <Users /> Patient queue
          </button>
          <button
            onClick={() =>
              notify("Reports are not connected in this prototype.")
            }
          >
            <FileText /> Reports
          </button>
          <button onClick={() => notify("Settings are simulated.")}>
            <Settings /> Settings
          </button>
        </nav>
        <div className="staff-user">
          <div className="avatar">RK</div>
          <div>
            <b>Reception · Rahul</b>
            <small>Staff workspace</small>
          </div>
          <button onClick={() => go("home")}>
            <LogOut />
          </button>
        </div>
      </aside>
      <main className="staff-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">WEDNESDAY, 18 NOVEMBER 2026</span>
            <h2>Good morning, Rahul</h2>
            <p>Here’s your daily overview. Let's make care connected.</p>
          </div>
          <span className="user-chip">RK</span>
        </header>
        <div className="stats">
          <Stat
            icon={<Users />}
            label="Today's patients"
            value={String(all.length).padStart(2, "0")}
          />
          <Stat icon={<Clock3 />} label="Waiting for review" value="05" />
          <Stat icon={<CheckCircle2 />} label="Completed visits" value="02" />
        </div>
        <section className="queue">
          <div className="section-title">
            <div>
              <span className="eyebrow">LIVE QUEUE</span>
              <h3>Demo patient queue</h3>
            </div>
            <Btn
              kind="outline"
              onClick={() => {
                setQuery("");
                setFilter("All");
              }}
            >
              Clear filters
            </Btn>
          </div>
          <div className="queue-tools">
            <div className="search">
              <Search />
              <input
                placeholder="Search patient name, token or ID"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              {["All", "Waiting", "Checked-in", "Completed"].map((x) => (
                <option>{x}</option>
              ))}
            </select>
          </div>
          <div className="queue-table">
            <div className="queue-row queue-head">
              <span>Token</span>
              <span>Patient name</span>
              <span>Intake</span>
              <span>Doctor</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {patients.map((p) => (
              <div className="queue-row">
                <b>{p.id}</b>
                <span>
                  <b>{p.name}</b>
                  <small>
                    {p.age} yrs · {p.gender}
                  </small>
                </span>
                <span>{p.intake}</span>
                <span>{p.doctor}</span>
                <Status value={p.status} />
                <button className="link" onClick={() => choose(p)}>
                  Open <ArrowRight />
                </button>
              </div>
            ))}
            {!patients.length && (
              <p className="empty">No patients match your search.</p>
            )}
          </div>
        </section>
        <p className="notice">
          <ShieldCheck /> Patient information shown here is sample data for the
          frontend prototype.
        </p>
      </main>
    </div>
  );
}
function Stat({ icon, label, value }) {
  return (
    <div className="stat">
      <span>{icon}</span>
      <div>
        <small>{label}</small>
        <b>{value}</b>
      </div>
    </div>
  );
}
function Workspace({
  patient: p,
  editName,
  setEditName,
  editStatus,
  setEditStatus,
  editing,
  setEditing,
  update,
  go,
  notify,
  note,
  setNote,
  modal,
}) {
  return (
    <div className="workspace">
      <aside className="staff-sidebar compact">
        <Brand go={go} />
        <nav>
          <button onClick={() => go("staff")}>
            <LayoutDashboard />
          </button>
          <button className="active">
            <Users />
          </button>
          <button>
            <FileText />
          </button>
          <button>
            <Settings />
          </button>
        </nav>
      </aside>
      <main>
        <header className="dash-head">
          <div>
            <span className="eyebrow">RECEPTION / PATIENT QUEUE</span>
            <h2>Patient workspace</h2>
            <p>Wednesday, 18 November · Today's patient queue</p>
          </div>
          <div className="workspace-links">
            <button className="link" onClick={() => go("staff")}>
              <ArrowLeft /> Back to queue
            </button>
            <button className="link" onClick={() => setEditing(!editing)}>
              {editing ? "Cancel" : "Edit full screen"}
            </button>
          </div>
        </header>
        <div className="workspace-grid">
          <section className="workspace-card">
            <div className="patient-title">
              <div>
                <span className="eyebrow">PATIENT DETAILS / TOKEN {p.id}</span>
                {editing ? (
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                  />
                ) : (
                  <h1>{p.name}</h1>
                )}
                <p>
                  {p.age} yrs · {p.gender}
                </p>
              </div>
              <Status value={p.status} />
            </div>
            <div className="workspace-details">
              <div>
                <span className="eyebrow">VISIT DETAILS</span>
                <Info label="Token number" value={p.id} />
                <Info label="Appointment time" value={p.time} />
                <div className="info">
                  <small>Current status</small>
                  {editing ? (
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value)}
                    >
                      {["Waiting", "Checked-in", "Completed"].map((x) => (
                        <option>{x}</option>
                      ))}
                    </select>
                  ) : (
                    <Status value={p.status} />
                  )}
                </div>
              </div>
              <div>
                <span className="eyebrow">ASSIGNED DOCTOR</span>
                <h3>{p.doctor}</h3>
                <p>{p.dept}</p>
                <small>Assigned to this department's queue</small>
              </div>
            </div>
            <div className="workspace-section">
              <span className="eyebrow">AI INTAKE</span>
              <p className="intake-done">
                <CheckCircle2 /> {p.intake}
              </p>
              <p>{p.symptoms}</p>
              <button className="link" onClick={() => modal("intake")}>
                View intake summary <ArrowRight />
              </button>
            </div>
            <div className="workspace-section">
              <span className="eyebrow">STAFF NOTES</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add an internal note for the care team..."
              />
              <Btn
                kind="outline"
                onClick={() =>
                  notify(
                    note.trim()
                      ? "Staff note added (demo)."
                      : "Write a note first.",
                  )
                }
              >
                Save note
              </Btn>
            </div>
            {editing && (
              <Btn
                onClick={() => {
                  update({ name: editName, status: editStatus });
                  setEditing(false);
                  notify("Patient details updated.");
                }}
              >
                Save changes <Check />
              </Btn>
            )}
          </section>
          <aside>
            <div className="side-card">
              <span className="eyebrow">QUICK ACTIONS</span>
              <button
                onClick={() => {
                  update({ status: "Checked-in" });
                  notify("Patient checked in.");
                }}
              >
                <CheckCircle2 /> Mark as checked-in
              </button>
              <button
                onClick={() => {
                  update({ status: "Completed" });
                  notify("Visit marked completed.");
                }}
              >
                <Check /> Complete visit
              </button>
              <button onClick={() => notify("Care team notified (demo).")}>
                <Phone /> Notify care team
              </button>
            </div>
            <div className="side-card">
              <span className="eyebrow">REVIEW REMINDER</span>
              <p>
                AI intake information should be reviewed and confirmed by
                authorised medical staff before any clinical decision.
              </p>
              <p className="notice">
                <ShieldCheck /> Staff review required
              </p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
function ModalBox({ title, children, close }) {
  return (
    <div
      className="overlay"
      onClick={(e) => e.target === e.currentTarget && close()}
    >
      <section>
        <header>
          <h3>{title}</h3>
          <button onClick={close}>
            <X />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
