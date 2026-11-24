import React, { useEffect, useMemo, useState, useRef } from "react";
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
import {
  login as apiLogin,
  logout as apiLogout,
  registerPatient,
  getConsent,
  LANGUAGE_CODES,
  GENDER_CODES,
} from "./services/auth.js";
import {
  openConversation,
  sendMessage,
  submitConversation,
  myIntakes,
  listIntakes,
  getIntake,
  correctIntake,
  confirmIntake,
  transcribeAudio,
  retryTranslation,
  LANGUAGE_NAMES,
  REVIEW_LABELS,
  TRANSLATION_LABELS,
  formatDate,
} from "./services/intake.js";
const GREETING = {
  by: "doctor",
  text: "Hello! Welcome to HealthSpeak AI. I can help you share your health concerns in your preferred language. What symptoms or concerns would you like to tell us about today?",
};
// Server messages -> the chat bubble format the UI already uses.
const toChat = (m) => ({
  by: m.sender === "patient" ? "patient" : "doctor",
  text: m.content,
});
const ROLE_LABELS = {
  patient: "Patient",
  doctor: "Doctor",
  staff: "Staff",
  admin: "Administrator",
};
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
    [messages, Msgs] = useState([GREETING]),
    [message, Msg] = useState(""),
    [voice, V] = useState(""),
    [listening, Listen] = useState(false),
    [summaryIntake, SummaryIntake] = useState(null), // intake shown on the summary page
    [patients, Patients] = useState(patients0),
    [selected, Selected] = useState(patients0[0]),
    [query, Q] = useState(""),
    [filter, F] = useState("All"),
    [editing, Editing] = useState(false),
    [editName, EN] = useState("Rohan Das"),
    [editStatus, ES] = useState("Waiting"),
    [note, Note] = useState(""),
    [user, SetUser] = useState(null), // logged-in user from the backend
    [busy, Busy] = useState(false), // a login/sign-up request is in flight
    [agreed, Agreed] = useState(false), // sign-up consent checkbox
    [consentDoc, ConsentDoc] = useState(null), // consent text from the backend
    [convId, ConvId] = useState(null), // the patient's open conversation
    [sending, Sending] = useState(false),
    [myIntakeList, MyIntakeList] = useState(null), // patient's own submissions
    [staffIntakes, StaffIntakes] = useState(null), // intakes awaiting review
    [reviewIntake, ReviewIntake] = useState(null), // intake open in the review screen
    [transcribing, Transcribing] = useState(false), // server is transcribing a recording
    [transcriptionId, TranscriptionId] = useState(null); // transcription shown in the voice box
  const notify = (x) => {
    T(x);
    setTimeout(() => T(""), 3000);
  };

  // Voice: record in the browser, transcribe on OUR server with the local model.
  // (The browser's built-in speech recognition sends audio to cloud services.)
  const recorderRef = useRef(null);
  const stopRecorder = (cancel = false) => {
    const r = recorderRef.current;
    if (r && r.state !== "inactive") {
      r._cancelled = cancel;
      r.stop();
    }
  };
  const toggleListening = async () => {
    if (listening) return stopRecorder();
    if (transcribing || !requirePatient()) return;
    if (!navigator.mediaDevices || typeof window.MediaRecorder === "undefined") {
      notify("Recording is not supported in this browser. Please type your concern.");
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      notify("Microphone access was blocked. Allow the microphone, or type your concern instead.");
      return;
    }
    const mime =
      ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find(
        (t) => window.MediaRecorder.isTypeSupported(t),
      ) || "";
    const rec = new window.MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    rec.ondataavailable = (e) => e.data && e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      clearTimeout(rec._timer);
      stream.getTracks().forEach((t) => t.stop());
      recorderRef.current = null;
      Listen(false);
      if (rec._cancelled || !chunks.length) return;
      Transcribing(true);
      try {
        const cid = await ensureConversation();
        const blob = new Blob(chunks, { type: rec.mimeType || mime || "audio/webm" });
        const t = await transcribeAudio(cid, blob, LANGUAGE_CODES[language] || "en");
        V(t.text); // the patient reviews (and may edit) this before sending
        TranscriptionId(t.id);
      } catch (err) {
        notify(err.message);
      } finally {
        Transcribing(false);
      }
    };
    rec._timer = setTimeout(() => stopRecorder(), 110000); // server limit is 120 s
    recorderRef.current = rec;
    rec.start();
    Listen(true);
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
  const login = async () => {
    if (!email.trim() || !password.trim())
      return notify("Enter your email/mobile number and password.");
    if (busy) return;
    Busy(true);
    try {
      // The backend decides the role; the role buttons are only a hint.
      const u = await apiLogin(email, password);
      SetUser(u);
      P("");
      go(u.role === "patient" ? "dashboard" : "staff");
      const label = ROLE_LABELS[u.role] || u.role;
      notify(
        label === role
          ? `Welcome, ${u.full_name}.`
          : `Logged in as ${label}: ${u.full_name}.`,
      );
    } catch (err) {
      notify(err.message);
    } finally {
      Busy(false);
    }
  };
  // Forget everything a previous person typed (important on a shared kiosk).
  const clearPersonalForms = () => {
    N("");
    M("");
    D("");
    G("");
    P("");
    Agreed(false);
    ConsentDoc(null);
  };
  const doLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // The token is already forgotten locally; nothing else to do.
    }
    SetUser(null);
    E("");
    clearPersonalForms();
    // Drop everything loaded for the previous person.
    ConvId(null);
    Msgs([GREETING]);
    Msg("");
    V("");
    stopRecorder(true);
    TranscriptionId(null);
    MyIntakeList(null);
    StaffIntakes(null);
    ReviewIntake(null);
    SummaryIntake(null);
    go("home");
    notify("You have been logged out.");
  };
  const openConsent = async () => {
    ConsentDoc(null);
    Modal("consent");
    try {
      ConsentDoc(await getConsent(LANGUAGE_CODES[pref] || "en"));
    } catch (err) {
      ConsentDoc({ error: err.message });
    }
  };
  // Only a logged-in patient can save a concern (it needs their profile + consent).
  const requirePatient = () => {
    if (user && user.role === "patient") return true;
    if (user) {
      notify("Only patient accounts can submit a health concern.");
    } else {
      notify("Please log in or create an account so your concern can be saved for staff review.");
      go("login");
    }
    return false;
  };
  // Save one message in the patient's conversation (creating/resuming it first).
  const ensureConversation = async () => {
    if (convId) return convId;
    const conv = await openConversation();
    ConvId(conv.id);
    Msgs([GREETING, ...conv.messages.map(toChat)]); // resume an unfinished chat
    return conv.id;
  };
  const postToIntake = async (text, inputMode, tid = null) => {
    const cid = await ensureConversation();
    const ex = await sendMessage(cid, text, LANGUAGE_CODES[language] || "en", inputMode, tid);
    Msgs((m) => [...m, toChat(ex.patient_message), toChat(ex.assistant_message)]);
  };
  const send = async () => {
    if (!message.trim() || sending) return;
    if (!requirePatient()) return;
    Sending(true);
    try {
      await postToIntake(message, "text");
      Msg("");
    } catch (err) {
      notify(err.message);
    } finally {
      Sending(false);
    }
  };
  const voiceContinue = async () => {
    // Do not continue if no speech or text was entered
    if (!voice.trim()) {
      notify("Please speak or enter your health concern first.");
      return;
    }
    if (listening || transcribing) {
      notify("Please wait until the recording has been transcribed.");
      return;
    }
    if (!requirePatient() || sending) return;
    Sending(true);
    try {
      // The patient has reviewed this text. If it came from a recording, the raw
      // machine transcript stays stored separately on the server.
      await postToIntake(voice, transcriptionId ? "voice_server" : "text", transcriptionId);
      V("");
      TranscriptionId(null);
      go("chat");
    } catch (err) {
      notify(err.message);
    } finally {
      Sending(false);
    }
  };
  const endChat = async () => {
    const cid = convId;
    try {
      if (cid) {
        await submitConversation(cid);
        notify("Your concern has been sent for staff review.");
      } else {
        notify("Chat closed.");
      }
    } catch (err) {
      // 422 = nothing was written yet; the empty chat simply stays open for later.
      notify(err.status === 422 ? "Chat closed." : err.message);
      if (err.status !== 422) return;
    }
    ConvId(null);
    Msgs([GREETING]);
    go("dashboard");
  };
  // Load real data when a page that shows it is opened.
  useEffect(() => {
    // Clear first so stale data is never shown while the fresh copy loads.
    if (page === "dashboard" && user && user.role === "patient") {
      MyIntakeList(null);
      myIntakes()
        .then(MyIntakeList)
        .catch((err) => notify(err.message));
    }
    if (page === "staff" && user && user.role === "staff") {
      StaffIntakes(null);
      listIntakes("pending_review")
        .then((r) => StaffIntakes(r))
        .catch((err) => notify(err.message));
    }
  }, [page, user]);
  const openReview = async (id) => {
    try {
      ReviewIntake(await getIntake(id));
      go("intake");
    } catch (err) {
      notify(err.message);
    }
  };
  const retryReviewTranslation = async () => {
    if (!reviewIntake || busy) return;
    Busy(true);
    try {
      const updated = await retryTranslation(reviewIntake.id);
      ReviewIntake(updated);
      notify(
        updated.translation_status === "completed"
          ? "Machine translation added. Please check it against the original."
          : updated.translation_error || "Translation is still unavailable.",
      );
    } catch (err) {
      notify(err.message);
    } finally {
      Busy(false);
    }
  };
  const saveReview = async (finalText, reason, andConfirm) => {
    if (!reviewIntake || busy) return;
    Busy(true);
    try {
      const updated = andConfirm
        ? await confirmIntake(reviewIntake.id, finalText, reason)
        : await correctIntake(reviewIntake.id, finalText, reason);
      ReviewIntake(updated);
      notify(andConfirm ? "Intake confirmed." : "Correction saved. The previous text is kept in the history.");
    } catch (err) {
      notify(err.message);
    } finally {
      Busy(false);
    }
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
            <Btn onClick={login} disabled={busy}>
              {busy ? "Logging in..." : "Log in"}
            </Btn>
            <p className="switch">
              Don't have an account?{" "}
              <button onClick={() => go("signup")}>Sign up</button>
            </p>
            <small className="demo-note">
              Log in with your HealthSpeak account. Synthetic demo accounts
              for local testing are listed in backend/README.md.
            </small>
          </div>
        </Auth>
      )}
      {page === "signup" && (
        <Auth go={go}>
          <form
            className="auth-form signup"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!name || !mobile || !dob || !gender || password.length < 8)
                return notify(
                  "Complete all fields. Password needs at least 8 characters.",
                );
              if (!agreed)
                return notify("Please read and accept the consent statement.");
              if (busy) return;
              Busy(true);
              try {
                const lang = LANGUAGE_CODES[pref] || "en";
                // Record the exact consent version the patient was shown.
                const consent =
                  consentDoc && consentDoc.version
                    ? consentDoc
                    : await getConsent(lang);
                const data = await registerPatient({
                  full_name: name,
                  phone: mobile,
                  date_of_birth: dob,
                  gender: GENDER_CODES[gender],
                  password,
                  ui_language: lang,
                  preferred_language: lang,
                  consent: {
                    version: consent.version,
                    granted: true,
                    language: consent.language || lang,
                  },
                });
                SetUser(data.user);
                clearPersonalForms();
                go("dashboard");
                notify("Account created successfully.");
              } catch (err) {
                notify(err.message);
              } finally {
                Busy(false);
              }
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
                {/* The backend supports English, Hindi and Urdu. */}
                {Object.keys(LANGUAGE_CODES).map((x) => (
                  <option key={x}>{x}</option>
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
                minLength="8"
                required
                placeholder="At least 8 characters"
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => Agreed(e.target.checked)}
                required
              />{" "}
              I have read and agree to the{" "}
              <button type="button" className="link" onClick={openConsent}>
                consent statement
              </button>
            </label>
            <Btn type="submit" disabled={busy}>
              {busy ? "Creating account..." : "Create Account"}
            </Btn>
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
            <h2>
              {listening
                ? "Listening..."
                : transcribing
                  ? "Writing down your words..."
                  : "Speak in your language"}
            </h2>
            <p>
              {listening
                ? "Listening for your concern. Tap the microphone when finished."
                : transcribing
                  ? "This can take a few seconds."
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
              placeholder="Your words will appear here. You can also type."
              dir="auto"
            />
            <div className="mic-controls">
              <button onClick={() => Modal("voicehelp")}>?</button>
              <button
                className={"mic " + (listening ? "recording" : "")}
                onClick={toggleListening}
              >
                {listening ? <AudioLines /> : <Mic />}
              </button>
              <button
                aria-label="Clear"
                onClick={() => {
                  stopRecorder(true);
                  V("");
                  TranscriptionId(null);
                }}
              >
                <X/>
                </button>
            </div>
            <div className="voice-bottom">
              <label>
                <Languages /> Language{" "}
                <select value={language} onChange={(e) => L(e.target.value)}>
                  {Object.keys(LANGUAGE_CODES).map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <Btn onClick={voiceContinue}>
                Continue to chat <ArrowRight />
              </Btn>
            </div>
            <small className="demo-note">
                Your recording is turned into text on the hospital's own
                HealthSpeak server, not by an outside service, and the audio is
                deleted afterwards. Please check the text before continuing.
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
                  {Object.keys(LANGUAGE_CODES).map((x) => (
                    <option key={x}>{x}</option>
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
                <button onClick={send} disabled={sending} aria-label="Send">
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
          intakes={myIntakeList}
          onView={(intake) => {
            SummaryIntake(intake);
            go("summary");
          }}
          notify={notify}
          userName={user && user.full_name}
          onLogout={doLogout}
        />
      )}
      {page === "summary" && summaryIntake && (
        <div className="summary">
          <header>
            <div>
              <h2>Your submitted concern</h2>
              <b>{formatDate(summaryIntake.created_at)}</b>
            </div>
            <Btn kind="outline" onClick={() => go("dashboard")}>
              <ArrowLeft /> Back
            </Btn>
          </header>
          <main>
            <div className="quote">
              <div className="avatar">You</div>
              <blockquote dir="auto">“{summaryIntake.original_text}”</blockquote>
            </div>
            <section className="structured">
              <div className="section-title">
                <h3>
                  <ClipboardList /> Intake status
                </h3>
                <span
                  className={
                    "status " +
                    (summaryIntake.review_status === "confirmed" ? "done" : "wait")
                  }
                >
                  {REVIEW_LABELS[summaryIntake.review_status]}
                </span>
              </div>
              <div className="summary-grid">
                <Info
                  label="Language you used"
                  value={LANGUAGE_NAMES[summaryIntake.original_language]}
                />
                <Info
                  label="Submitted"
                  value={formatDate(summaryIntake.created_at)}
                />
                <Info
                  label="Reviewed by staff"
                  value={
                    summaryIntake.reviewed_at
                      ? formatDate(summaryIntake.reviewed_at)
                      : "Not yet"
                  }
                />
                <Info
                  label="Department"
                  value="Assigned by staff after review"
                />
              </div>
              <p className="disclaimer">
                <ShieldCheck /> HealthSpeak AI does not diagnose or prescribe.
                Medical staff review the information you share.
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
          userName={user && user.full_name}
          onLogout={doLogout}
          intakes={staffIntakes}
          canReview={Boolean(user && user.role === "staff")}
          onReview={openReview}
        />
      )}
      {page === "intake" && reviewIntake && (
        <IntakeReview
          key={reviewIntake.id + reviewIntake.updated_at}
          intake={reviewIntake}
          busy={busy}
          go={go}
          onSave={saveReview}
          onRetryTranslation={retryReviewTranslation}
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
      {modal === "consent" && (
        <ModalBox
          title={(consentDoc && consentDoc.title) || "Consent statement"}
          close={() => Modal("")}
        >
          {!consentDoc ? (
            <p>Loading...</p>
          ) : consentDoc.error ? (
            <p>{consentDoc.error}</p>
          ) : (
            <>
              <p dir="auto">{consentDoc.text}</p>
              <p className="demo-note">
                Version {consentDoc.version}
                {consentDoc.is_draft
                  ? " · Draft wording pending hospital review"
                  : ""}
              </p>
              <Btn
                onClick={() => {
                  Agreed(true);
                  Modal("");
                }}
              >
                I agree
              </Btn>
            </>
          )}
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
              onClick={endChat}
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
            Your recording is processed on the hospital's own server.
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
function PatientDashboard({
  go,
  language,
  setLanguage,
  intakes,
  onView,
  notify,
  userName,
  onLogout,
}) {
  const latest = intakes && intakes.length ? intakes[0] : null;
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
          <button onClick={onLogout}>
            <LogOut /> Log out
          </button>
        </nav>
        <label className="language">
          <Languages />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            {Object.keys(LANGUAGE_CODES).map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <ChevronDown />
        </label>
      </aside>
      <main className="patient-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">PATIENT DASHBOARD</span>
            <h2>
              {userName ? `Welcome, ${userName}` : "Welcome to HealthSpeak AI"}
            </h2>
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
                  <h3>Your submitted concerns</h3>
                </div>
              </div>
              <div className="history-table">
                <div className="history-row head">
                  <span>Date</span>
                  <span>What you shared</span>
                  <span>Status</span>
                  <span>Action</span>
                </div>
                {intakes === null && <p className="empty">Loading...</p>}
                {intakes && !intakes.length && (
                  <p className="empty">
                    Nothing submitted yet. Start a voice or text intake above.
                  </p>
                )}
                {(intakes || []).map((r) => (
                  <div className="history-row" key={r.id}>
                    <span>{formatDate(r.created_at)}</span>
                    <span dir="auto">
                      {r.original_text.length > 70
                        ? r.original_text.slice(0, 70) + "…"
                        : r.original_text}
                    </span>
                    <span>{REVIEW_LABELS[r.review_status]}</span>
                    <button className="link" onClick={() => onView(r)}>
                      View <ArrowRight />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <aside className="intake-card">
            <div className="section-title">
              <h3>Latest intake</h3>
              {latest && (
                <span
                  className={
                    "status " +
                    (latest.review_status === "confirmed" ? "done" : "blue")
                  }
                >
                  {REVIEW_LABELS[latest.review_status]}
                </span>
              )}
            </div>
            {latest ? (
              <>
                <small>What you shared</small>
                <b dir="auto">
                  {latest.original_text.length > 120
                    ? latest.original_text.slice(0, 120) + "…"
                    : latest.original_text}
                </b>
                <Info label="Submitted" value={formatDate(latest.created_at)} />
                <Info
                  label="Department"
                  value="Assigned by staff after review"
                />
              </>
            ) : (
              <small>No intake submitted yet.</small>
            )}
            <div className="assigned">
              <div className="avatar">HS</div>
              <div>
                <b>HealthSpeak AI</b>
                <small>Medical staff review every submission</small>
              </div>
            </div>
            <p className="notice">
              <ShieldCheck /> HealthSpeak AI does not diagnose or prescribe.
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
  userName,
  onLogout,
  intakes,
  canReview,
  onReview,
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
          <button onClick={onLogout} title="Log out" aria-label="Log out">
            <LogOut />
          </button>
        </div>
      </aside>
      <main className="staff-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">WEDNESDAY, 18 NOVEMBER 2026</span>
            <h2>Good morning, {userName || "Rahul"}</h2>
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
          <Stat
            icon={<Clock3 />}
            label="Intakes awaiting review"
            value={intakes ? String(intakes.total).padStart(2, "0") : "--"}
          />
          <Stat icon={<CheckCircle2 />} label="Completed visits" value="02" />
        </div>
        {canReview && (
          <section className="queue">
            <div className="section-title">
              <div>
                <span className="eyebrow">AI INTAKE · NEEDS STAFF REVIEW</span>
                <h3>Intakes awaiting review</h3>
              </div>
            </div>
            <div className="queue-table">
              <div className="queue-row queue-head">
                <span>Submitted</span>
                <span>Patient</span>
                <span>Language</span>
                <span>What the patient shared</span>
                <span>Status</span>
                <span>Action</span>
              </div>
              {intakes === null && <p className="empty">Loading...</p>}
              {intakes && !intakes.items.length && (
                <p className="empty">No intakes are waiting for review.</p>
              )}
              {(intakes ? intakes.items : []).map((i) => (
                <div className="queue-row" key={i.id}>
                  <small>{formatDate(i.created_at)}</small>
                  <b>{i.patient_name}</b>
                  <span>{LANGUAGE_NAMES[i.original_language]}</span>
                  <span dir="auto">{i.snippet}</span>
                  <span className="status wait">Unreviewed</span>
                  <button className="link" onClick={() => onReview(i.id)}>
                    Review <ArrowRight />
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
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
function IntakeReview({ intake, busy, go, onSave, onRetryTranslation }) {
  const [text, SetText] = useState(
    intake.final_text || intake.english_text || "",
  );
  const [reason, SetReason] = useState("");
  const confirmed = intake.review_status === "confirmed";
  const p = intake.patient;
  return (
    <div className="workspace">
      <aside className="staff-sidebar compact">
        <Brand go={go} />
        <nav>
          <button onClick={() => go("staff")} aria-label="Back to staff overview">
            <LayoutDashboard />
          </button>
        </nav>
      </aside>
      <main>
        <header className="dash-head">
          <div>
            <span className="eyebrow">STAFF / INTAKE REVIEW</span>
            <h2>Review intake</h2>
            <p>Submitted {formatDate(intake.created_at)}</p>
          </div>
          <div className="workspace-links">
            <button className="link" onClick={() => go("staff")}>
              <ArrowLeft /> Back to overview
            </button>
          </div>
        </header>
        <div className="workspace-grid">
          <section className="workspace-card">
            <div className="patient-title">
              <div>
                <span className="eyebrow">PATIENT</span>
                <h1>{p.full_name}</h1>
                <p>
                  {p.age} yrs · {p.gender.replace(/_/g, " ")} · prefers{" "}
                  {LANGUAGE_NAMES[p.preferred_language]}
                </p>
              </div>
              <span className={"status " + (confirmed ? "done" : "wait")}>
                {confirmed ? "Confirmed by staff" : "Unreviewed"}
              </span>
            </div>
            <div className="workspace-section">
              <span className="eyebrow">
                PATIENT'S ORIGINAL WORDS · {LANGUAGE_NAMES[intake.original_language].toUpperCase()}
              </span>
              <p dir="auto" style={{ whiteSpace: "pre-wrap" }}>
                {intake.original_text}
              </p>
              <small>Stored exactly as submitted. This text is never changed.</small>
            </div>
            <div className="workspace-section">
              <span className="eyebrow">
                ENGLISH VERSION · {TRANSLATION_LABELS[intake.translation_status].toUpperCase()}
              </span>
              {intake.english_text ? (
                <p style={{ whiteSpace: "pre-wrap" }}>{intake.english_text}</p>
              ) : (
                <p>
                  No English version yet. Write the English version in the box
                  below before confirming.
                </p>
              )}
              {intake.translation_model && (
                <small>
                  Machine translation by {intake.translation_model}. It may
                  contain mistakes; compare it with the original words.
                </small>
              )}
              {intake.translation_error && (
                <small className="demo-note">{intake.translation_error}</small>
              )}
              {["pending", "failed"].includes(intake.translation_status) && (
                <div className="actions">
                  <Btn kind="outline" disabled={busy} onClick={onRetryTranslation}>
                    Retry machine translation
                  </Btn>
                </div>
              )}
            </div>
            <div className="workspace-section">
              <span className="eyebrow">STAFF-REVIEWED TEXT (ENGLISH)</span>
              <textarea
                value={text}
                onChange={(e) => SetText(e.target.value)}
                placeholder="Corrected English version of what the patient reported..."
              />
              <input
                className="reason"
                value={reason}
                onChange={(e) => SetReason(e.target.value)}
                placeholder="Reason for change (optional)"
                maxLength={500}
              />
              <div className="actions">
                <Btn
                  kind="outline"
                  disabled={busy || !text.trim()}
                  onClick={() => onSave(text, reason, false)}
                >
                  Save correction
                </Btn>
                {!confirmed && (
                  <Btn
                    disabled={busy || !text.trim()}
                    onClick={() => onSave(text, reason, true)}
                  >
                    Confirm intake <Check />
                  </Btn>
                )}
              </div>
            </div>
          </section>
          <aside>
            <div className="side-card">
              <span className="eyebrow">CHANGE HISTORY</span>
              {!intake.revisions.length && <p>No changes yet.</p>}
              {intake.revisions.map((r, i) => (
                <p key={i}>
                  <b>{formatDate(r.created_at)}</b>
                  <br />
                  {r.field === "review_status"
                    ? `Status: ${r.old_value} → ${r.new_value}`
                    : r.old_value
                      ? "Reviewed text edited"
                      : "Reviewed text added"}
                  {r.reason ? ` (${r.reason})` : ""}
                </p>
              ))}
            </div>
            <div className="side-card">
              <span className="eyebrow">REVIEW REMINDER</span>
              <p>
                Check the patient's original words. AI and translations can be
                wrong. HealthSpeak AI does not diagnose or prescribe.
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
