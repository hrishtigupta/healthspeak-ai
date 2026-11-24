import React, { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
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
  updateMyLanguage,
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
  analyseIntake,
  listDepartments,
  LANGUAGE_NAMES,
  REVIEW_LABELS,
  TRANSLATION_LABELS,
  formatDate,
} from "./services/intake.js";
import { Btn, Brand, Field, Info, Stat, ModalBox, initials, pad2 } from "./components/ui.jsx";
import QueuePanel from "./pages/staff/QueuePanel.jsx";
import VisitWorkspace from "./pages/staff/VisitWorkspace.jsx";
import DoctorHome from "./pages/doctor/DoctorHome.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import VisitStatus from "./pages/patient/VisitStatus.jsx";
import { staffDashboard } from "./services/visits.js";
import i18n, { deviceLanguage, setDeviceLanguage, translateError } from "./i18n/index.js";
import LanguageSwitcher from "./components/LanguageSwitcher.jsx";
import { kioskIdleSeconds, kioskKey, sendHeartbeat } from "./services/kiosk.js";
// The greeting is shown in the reader's display language (it is not stored).
const GREETING = { by: "doctor", key: "chat.greeting" };
const NAME_BY_CODE = { en: "English", hi: "Hindi", ur: "Urdu" };
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
export default function App() {
  const { t } = useTranslation();
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
    [visitId, VisitId] = useState(null), // queue entry open in the visit workspace
    [staffDash, StaffDash] = useState(null), // today's counts for the staff overview
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
    [transcriptionId, TranscriptionId] = useState(null), // transcription shown in the voice box
    [departments, Departments] = useState([]); // active departments (staff confirmation)
  const notify = (x) => {
    T(x);
    setTimeout(() => T(""), 3000);
  };
  // Change the DISPLAY language: saved on the server for a logged-in user (only
  // their own account), otherwise remembered for this device.
  const changeUiLanguage = async (code) => {
    i18n.changeLanguage(code);
    if (user) {
      try {
        SetUser(await updateMyLanguage(code));
      } catch (err) {
        notify(translateError(err));
      }
    } else {
      setDeviceLanguage(code);
    }
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
      notify(t("voice.notSupported"));
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      notify(t("voice.blocked"));
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
        notify(translateError(err));
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
  const login = async () => {
    if (!email.trim() || !password.trim())
      return notify(t("auth.needIdPassword"));
    if (busy) return;
    Busy(true);
    try {
      // The backend decides the role; the role buttons are only a hint.
      const u = await apiLogin(email, password);
      SetUser(u);
      i18n.changeLanguage(u.ui_language); // this user's own display language
      L(NAME_BY_CODE[u.ui_language] || "English"); // default speaking language
      P("");
      go({ patient: "dashboard", staff: "staff", doctor: "doctor", admin: "admin" }[u.role] || "home");
      const label = ROLE_LABELS[u.role] || u.role;
      notify(
        label === role
          ? t("common.welcomeName", { name: u.full_name })
          : t("common.loggedInAs", { role: t(`roles.${u.role}`), name: u.full_name }),
      );
    } catch (err) {
      notify(translateError(err));
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
    i18n.changeLanguage(deviceLanguage()); // back to this device's language
    go("home");
    notify(t("common.loggedOut"));
  };
  const openConsent = async () => {
    ConsentDoc(null);
    Modal("consent");
    try {
      ConsentDoc(await getConsent(LANGUAGE_CODES[pref] || "en"));
    } catch (err) {
      ConsentDoc({ error: translateError(err) });
    }
  };
  // Only a logged-in patient can save a concern (it needs their profile + consent).
  const requirePatient = () => {
    if (user && user.role === "patient") return true;
    if (user) {
      notify(t("chat.onlyPatients"));
    } else {
      notify(t("chat.loginFirst"));
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
      notify(translateError(err));
    } finally {
      Sending(false);
    }
  };
  const voiceContinue = async () => {
    // Do not continue if no speech or text was entered
    if (!voice.trim()) {
      notify(t("voice.speakFirst"));
      return;
    }
    if (listening || transcribing) {
      notify(t("voice.waitTranscribe"));
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
      notify(translateError(err));
    } finally {
      Sending(false);
    }
  };
  const endChat = async () => {
    const cid = convId;
    try {
      if (cid) {
        await submitConversation(cid);
        notify(t("chat.sent"));
      } else {
        notify(t("chat.closed"));
      }
    } catch (err) {
      // 422 = nothing was written yet; the empty chat simply stays open for later.
      notify(err.status === 422 ? t("chat.closed") : translateError(err));
      if (err.status !== 422) return;
    }
    ConvId(null);
    Msgs([GREETING]);
    go("dashboard");
  };
  // ----- Kiosk mode (shared device opened with ?kiosk=KEY) -----
  const [kiosk] = useState(() => kioskKey());
  useEffect(() => {
    if (!kiosk) return undefined;
    const beat = () => sendHeartbeat(kiosk, i18n.language).catch(() => {});
    beat();
    const timer = setInterval(beat, 60000);
    return () => clearInterval(timer);
  }, [kiosk]);
  // On a kiosk, log a person out after a period without any activity so the
  // next person never sees their information.
  useEffect(() => {
    if (!kiosk || !user) return undefined;
    const events = ["pointerdown", "keydown", "touchstart", "scroll"];
    let timer;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        await doLogout();
        notify(t("kiosk.idleLogout"));
      }, kioskIdleSeconds() * 1000);
    };
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [kiosk, user]);
  // Load real data when a page that shows it is opened.
  useEffect(() => {
    // Clear first so stale data is never shown while the fresh copy loads.
    if (page === "dashboard" && user && user.role === "patient") {
      MyIntakeList(null);
      myIntakes()
        .then(MyIntakeList)
        .catch((err) => notify(translateError(err)));
    }
    if (page === "staff" && user && user.role === "staff") {
      StaffDash(null);
      staffDashboard().then(StaffDash).catch(() => StaffDash(null));
      StaffIntakes(null);
      listIntakes("pending_review")
        .then((r) => StaffIntakes(r))
        .catch((err) => notify(translateError(err)));
    }
  }, [page, user]);
  const openReview = async (id) => {
    try {
      const [intake, depts] = await Promise.all([getIntake(id), listDepartments()]);
      Departments(depts);
      ReviewIntake(intake);
      go("intake");
    } catch (err) {
      notify(translateError(err));
    }
  };
  const reanalyse = async () => {
    if (!reviewIntake || busy) return;
    Busy(true);
    try {
      ReviewIntake(await analyseIntake(reviewIntake.id, "final_text"));
      notify("Summary re-created from the staff-reviewed text.");
    } catch (err) {
      notify(translateError(err));
    } finally {
      Busy(false);
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
      notify(translateError(err));
    } finally {
      Busy(false);
    }
  };
  const saveReview = async (finalText, reason, andConfirm, departmentId) => {
    if (!reviewIntake || busy) return;
    if (andConfirm && !departmentId) {
      notify("Choose the department before confirming.");
      return;
    }
    Busy(true);
    try {
      const updated = andConfirm
        ? await confirmIntake(reviewIntake.id, departmentId, finalText, reason)
        : await correctIntake(reviewIntake.id, finalText, reason);
      ReviewIntake(updated);
      notify(andConfirm ? "Intake confirmed." : "Correction saved. The previous text is kept in the history.");
    } catch (err) {
      notify(translateError(err));
    } finally {
      Busy(false);
    }
  };
  const toastUI = toast && (
    <div className="toast" role="status" aria-live="polite">
      <CheckCircle2 />
      {toast}
      <button onClick={() => T("")} aria-label={t("common.close")}>
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
              <a href="#home">{t("home.nav.home")}</a>
              <a href="#features">{t("home.nav.features")}</a>
              <a href="#languages">{t("home.nav.languages")}</a>
              <a href="#faqs">{t("home.nav.faqs")}</a>
              <a href="#contact">{t("home.nav.contact")}</a>
            </nav>
            <LanguageSwitcher onChange={changeUiLanguage} />
            <Btn onClick={() => go("login")}>{t("common.login")}</Btn>
          </header>
          <main className="landing" id="home">
            <section className="hero">
              <div>
                <span className="eyebrow">
                  <Sparkles /> {t("home.eyebrow")}
                </span>
                <h1>
                  {t("home.titleA")}
                  <br />
                  <em>{t("home.titleB")}</em>
                </h1>
                <p>{t("home.intro")}</p>
                <div className="actions">
                  <Btn onClick={() => go("login")}>
                    {t("home.startChat")} <ArrowRight />
                  </Btn>
                  <Btn kind="outline" onClick={() => go("voice")}>
                    <Mic /> {t("home.voiceInput")}
                  </Btn>
                </div>
              </div>
              <div className="hero-art">
                <div className="hero-blob">
                  <div className="phone-art">
                    <MessageCircle />
                    <b>{t("home.howHelp")}</b>
                    <span>∿ ∿ ∿</span>
                  </div>
                  <div className="doctor-art">
                    <Stethoscope />
                    <b>{t("home.careInLanguage")}</b>
                  </div>
                </div>
                <span className="float f1">
                  <AudioLines /> {t("home.voiceText")}
                </span>
                <span className="float f2">
                  <Languages /> {t("home.multiLang")}
                </span>
              </div>
            </section>
            <section className="features" id="features">
              <article>
                <AudioLines />
                <b>{t("home.f1t")}</b>
                <p>{t("home.f1d")}</p>
              </article>
              <article>
                <Languages />
                <b>{t("home.f2t")}</b>
                <p>{t("home.f2d")}</p>
              </article>
              <article>
                <Clock3 />
                <b>{t("home.f3t")}</b>
                <p>{t("home.f3d")}</p>
              </article>
            </section>
            <section className="how">
              <div>
                <span className="eyebrow">{t("home.howEyebrow")}</span>
                <h2>
                  {t("home.howA")}
                  <br />
                  <em>{t("home.howB")}</em>
                </h2>
                <p>{t("home.howIntro")}</p>
              </div>
              <div className="how-cards">
                <article>
                  <i>01</i>
                  <h3>{t("home.s1t")}</h3>
                  <p>{t("home.s1d")}</p>
                </article>
                <article>
                  <i>02</i>
                  <h3>{t("home.s2t")}</h3>
                  <p>{t("home.s2d")}</p>
                </article>
                <article>
                  <i>03</i>
                  <h3>{t("home.s3t")}</h3>
                  <p>{t("home.s3d")}</p>
                </article>
              </div>
            </section>
            <section className="cta" id="languages">
              <div>
                <h2>{t("home.ctaTitle")}</h2>
                <p>{t("home.ctaText")}</p>
              </div>
              <Btn onClick={() => go("login")}>
                {t("home.getStarted")} <ArrowRight />
              </Btn>
            </section>
            <section className="faq-section" id="faqs">
              <span className="eyebrow">{t("home.faqEyebrow")}</span>
              <h2>{t("home.faqTitle")}</h2>
              <div>
                {["1", "2", "3"].map((n) => (
                  <article key={n}>
                    <b>{t(`home.q${n}`)}</b>
                    <p>{t(`home.a${n}`)}</p>
                  </article>
                ))}
              </div>
            </section>
            <footer id="contact">
              <Brand go={go} />
              <span>{t("home.footer")}</span>
              <a href="#faqs">{t("home.nav.faqs")}</a>
            </footer>
          </main>
        </>
      )}
      {page === "login" && (
        <Auth go={go} onLanguage={changeUiLanguage}>
          <div className="auth-form">
            <button className="back" onClick={() => go("home")}>
              <ArrowLeft /> {t("common.backHome")}
            </button>
            <span className="eyebrow">{t("auth.eyebrow")}</span>
            <h2>{t("auth.welcomeBack")}</h2>
            <p>{t("auth.selectRole")}</p>
            <b className="label-title">{t("auth.loggingInAs")}</b>
            <div className="roles">
              {["Patient", "Doctor", "Staff"].map((r) => (
                <button
                  key={r}
                  className={role === r ? "chosen" : ""}
                  onClick={() => R(r)}
                  aria-pressed={role === r}
                >
                  {r === "Patient" ? (
                    <UserRound />
                  ) : r === "Doctor" ? (
                    <Plus />
                  ) : (
                    <Users />
                  )}
                  {t(`roles.${r.toLowerCase()}`)}
                </button>
              ))}
            </div>
            <Field
              label={t("auth.idLabel")}
              placeholder={t("auth.idPlaceholder")}
              value={email}
              onChange={(e) => E(e.target.value)}
            />
            <label className="field">
              <span>{t("auth.password")}</span>
              <div className="pass">
                <input
                  type={showPass ? "text" : "password"}
                  placeholder={t("auth.passwordPlaceholder")}
                  value={password}
                  onChange={(e) => P(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => SP(!showPass)}
                  aria-label={t("auth.showPassword")}
                >
                  {showPass ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </label>
            <div className="forgot">
              <button onClick={() => Modal("forgot")}>{t("auth.forgot")}</button>
            </div>
            <Btn onClick={login} disabled={busy}>
              {busy ? t("auth.loggingIn") : t("common.login")}
            </Btn>
            <p className="switch">
              {t("auth.noAccount")}{" "}
              <button onClick={() => go("signup")}>{t("common.signup")}</button>
            </p>
            <small className="demo-note">{t("auth.demoNote")}</small>
          </div>
        </Auth>
      )}
      {page === "signup" && (
        <Auth go={go} onLanguage={changeUiLanguage}>
          <form
            className="auth-form signup"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!name || !mobile || !dob || !gender || password.length < 8)
                return notify(t("auth.completeAll"));
              if (!agreed) return notify(t("auth.acceptConsent"));
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
                  ui_language: i18n.language, // display language chosen on this screen
                  preferred_language: lang, // language they will speak in
                  consent: {
                    version: consent.version,
                    granted: true,
                    language: consent.language || lang,
                  },
                });
                SetUser(data.user);
                L(pref);
                clearPersonalForms();
                go("dashboard");
                notify(t("auth.created"));
              } catch (err) {
                notify(translateError(err));
              } finally {
                Busy(false);
              }
            }}
          >
            <button type="button" className="back" onClick={() => go("home")}>
              <ArrowLeft /> {t("common.backHome")}
            </button>
            <span className="eyebrow">{t("auth.joinEyebrow")}</span>
            <h2>{t("auth.createTitle")}</h2>
            <p>{t("auth.createText")}</p>
            <label className="field">
              <span>{t("auth.speakingLanguage")}</span>
              <select value={pref} onChange={(e) => Pref(e.target.value)}>
                {/* The backend supports English, Hindi and Urdu. */}
                {Object.keys(LANGUAGE_CODES).map((x) => (
                  <option key={x} value={x}>
                    {t(`lang.${LANGUAGE_CODES[x]}`)}
                  </option>
                ))}
              </select>
            </label>
            <Field
              label={t("auth.fullName")}
              placeholder={t("auth.fullNamePh")}
              value={name}
              onChange={(e) => N(e.target.value)}
              required
            />
            <Field
              label={t("auth.mobile")}
              placeholder={t("auth.mobilePh")}
              value={mobile}
              onChange={(e) => M(e.target.value)}
              required
            />
            <div className="two">
              <Field
                label={t("auth.dob")}
                type="date"
                value={dob}
                onChange={(e) => D(e.target.value)}
                required
              />
              <label className="field">
                <span>{t("auth.gender")}</span>
                <select
                  value={gender}
                  onChange={(e) => G(e.target.value)}
                  required
                >
                  <option value="">{t("auth.select")}</option>
                  {["Female", "Male", "Other", "Prefer not to say"].map((x) => (
                    <option key={x} value={x}>
                      {t(`gender.${x}`)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>{t("auth.createPassword")}</span>
              <input
                type="password"
                value={password}
                onChange={(e) => P(e.target.value)}
                minLength="8"
                required
                placeholder={t("auth.passwordMin")}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => Agreed(e.target.checked)}
                required
              />{" "}
              {t("auth.agreeA")}{" "}
              <button type="button" className="link" onClick={openConsent}>
                {t("auth.consentLink")}
              </button>
            </label>
            <Btn type="submit" disabled={busy}>
              {busy ? t("auth.creating") : t("auth.createAccount")}
            </Btn>
            <p className="switch">
              {t("auth.haveAccount")}{" "}
              <button type="button" onClick={() => go("login")}>
                {t("common.login")}
              </button>
            </p>
          </form>
        </Auth>
      )}
      {page === "voice" && (
        <div className="voice-screen">
          <header>
            <Brand go={go} />
            <LanguageSwitcher onChange={changeUiLanguage} />
            <Btn kind="ghost" onClick={() => go("chat")}>
              {t("voice.skip")} <ArrowRight />
            </Btn>
          </header>
          <div className="voice-center">
            <span className="eyebrow">{t("voice.eyebrow")}</span>
            <h2>
              {listening
                ? t("voice.listening")
                : transcribing
                  ? t("voice.writing")
                  : t("voice.speak")}
            </h2>
            <p>
              {listening
                ? t("voice.listeningText")
                : transcribing
                  ? t("voice.writingText")
                  : t("voice.pressMic")}
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
              placeholder={t("voice.placeholder")}
              aria-label={t("voice.placeholder")}
              dir="auto"
            />
            <div className="mic-controls">
              <button onClick={() => Modal("voicehelp")} aria-label={t("voice.help")}>
                ?
              </button>
              <button
                className={"mic " + (listening ? "recording" : "")}
                onClick={toggleListening}
                aria-label={t("voice.mic")}
                aria-pressed={listening}
              >
                {listening ? <AudioLines /> : <Mic />}
              </button>
              <button
                aria-label={t("voice.clear")}
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
                <Languages /> {t("lang.speaking")}{" "}
                <select value={language} onChange={(e) => L(e.target.value)}>
                  {Object.keys(LANGUAGE_CODES).map((x) => (
                    <option key={x} value={x}>
                      {t(`lang.${LANGUAGE_CODES[x]}`)}
                    </option>
                  ))}
                </select>
              </label>
              <Btn onClick={voiceContinue}>
                {t("voice.continue")} <ArrowRight />
              </Btn>
            </div>
            <small className="demo-note">{t("voice.privacy")}</small>
          </div>
        </div>
      )}
      {page === "chat" && (
        <div className="chat-page">
          <header>
        <Brand go={go}/>
        <div>
            <span className="online-dot"/>
            {t("chat.assistant")}
            <LanguageSwitcher onChange={changeUiLanguage} />
            <Btn kind="danger" onClick={()=>Modal('endchat')}>
            {t("chat.endChat")}
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
                {t("chat.assistantShort")}
                </small>
            </div>
            </div>
            <div className="messages">
              {messages.map((m, i) => (
                <div className={"message " + m.by} key={i}>
                  <div className="avatar">
                    {m.by === "patient" ? t("common.you") : "HS"}
                  </div>
                  <p dir="auto">{m.key ? t(m.key) : m.text}</p>
                </div>
              ))}
            </div>
            <div className="composer">
              <div className="compose-tools">
                <select
                  value={language}
                  onChange={(e) => L(e.target.value)}
                  aria-label={t("lang.speaking")}
                  title={t("lang.speaking")}
                >
                  {Object.keys(LANGUAGE_CODES).map((x) => (
                    <option key={x} value={x}>
                      {t(`lang.${LANGUAGE_CODES[x]}`)}
                    </option>
                  ))}
                </select>
                <button onClick={() => go("voice")} aria-label={t("chat.voice")}>
                  <Mic />
                </button>
              </div>
              <div className="sendline">
                <input
                  value={message}
                  onChange={(e) => Msg(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder={t("chat.placeholder")}
                  aria-label={t("chat.placeholder")}
                  dir="auto"
                />
                <button onClick={send} disabled={sending} aria-label={t("chat.send")}>
                  <Send />
                </button>
              </div>
              <small>{t("chat.footer")}</small>
            </div>
          </main>
        </div>
      )}
      {page === "doctor" && user && (
        <DoctorHome
          go={go}
          onLanguage={changeUiLanguage}
          notify={notify}
          userName={user.full_name}
          onLogout={doLogout}
          onOpen={(id) => {
            VisitId(id);
            go("workspace");
          }}
        />
      )}
      {page === "admin" && user && (
        <AdminHome
          go={go}
          onLanguage={changeUiLanguage}
          notify={notify}
          userName={user.full_name}
          onLogout={doLogout}
        />
      )}
      {page === "dashboard" && (
        <PatientDashboard
          go={go}
          onLanguage={changeUiLanguage}
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
              <h2>{t("summary.title")}</h2>
              <b>{formatDate(summaryIntake.created_at)}</b>
            </div>
            <Btn kind="outline" onClick={() => go("dashboard")}>
              <ArrowLeft /> {t("common.back")}
            </Btn>
          </header>
          <main>
            <div className="quote">
              <div className="avatar">{t("common.you")}</div>
              <blockquote dir="auto">“{summaryIntake.original_text}”</blockquote>
            </div>
            <section className="structured">
              <div className="section-title">
                <h3>
                  <ClipboardList /> {t("summary.status")}
                </h3>
                <span
                  className={
                    "status " +
                    (summaryIntake.review_status === "confirmed" ? "done" : "wait")
                  }
                >
                  {t(`review.${summaryIntake.review_status}`)}
                </span>
              </div>
              <div className="summary-grid">
                <Info
                  label={t("summary.languageUsed")}
                  value={t(`lang.${summaryIntake.original_language}`)}
                />
                <Info
                  label={t("common.submitted")}
                  value={formatDate(summaryIntake.created_at)}
                />
                <Info
                  label={t("summary.reviewedBy")}
                  value={
                    summaryIntake.reviewed_at
                      ? formatDate(summaryIntake.reviewed_at)
                      : t("common.notYet")
                  }
                />
                <Info
                  label={t("common.department")}
                  value={
                    summaryIntake.confirmed_department_name ||
                    t("common.assignedAfterReview")
                  }
                />
              </div>
              <p className="disclaimer">
                <ShieldCheck /> {t("summary.disclaimer")}
              </p>
            </section>
          </main>
        </div>
      )}
      {page === "staff" && (
        <Staff
          go={go}
          notify={notify}
          userName={user && user.full_name}
          onLogout={doLogout}
          intakes={staffIntakes}
          canReview={Boolean(user && user.role === "staff")}
          onReview={openReview}
          dash={staffDash}
          onLanguage={changeUiLanguage}
          onOpen={(id) => {
            VisitId(id);
            go("workspace");
          }}
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
          onReanalyse={reanalyse}
          departments={departments}
        />
      )}
      {page === "workspace" && visitId && user && (
        <VisitWorkspace
          key={visitId}
          entryId={visitId}
          role={user.role}
          go={go}
          notify={notify}
          onBack={() => go(user.role === "doctor" ? "doctor" : "staff")}
        />
      )}
      {modal === "forgot" && (
        <ModalBox title={t("auth.forgotTitle")} close={() => Modal("")}>
          <p>{t("auth.forgotText")}</p>
          <Btn onClick={() => Modal("")}>{t("common.close")}</Btn>
        </ModalBox>
      )}
      {modal === "consent" && (
        <ModalBox
          title={(consentDoc && consentDoc.title) || t("auth.consentTitle")}
          close={() => Modal("")}
        >
          {!consentDoc ? (
            <p>{t("common.loading")}</p>
          ) : consentDoc.error ? (
            <p>{consentDoc.error}</p>
          ) : (
            <>
              <p dir="auto">{consentDoc.text}</p>
              <p className="demo-note">
                {t("auth.version", { v: consentDoc.version })}
                {consentDoc.is_draft ? ` · ${t("auth.draft")}` : ""}
              </p>
              <Btn
                onClick={() => {
                  Agreed(true);
                  Modal("");
                }}
              >
                {t("auth.iAgree")}
              </Btn>
            </>
          )}
        </ModalBox>
      )}
      {modal === "endchat" && (
        <ModalBox title={t("chat.endTitle")} close={() => Modal("")}>
          <p>{t("chat.endText")}</p>
          <div className="actions">
            <Btn kind="outline" onClick={() => Modal("")}>
              {t("chat.continueChat")}
            </Btn>
            <Btn onClick={endChat}>{t("chat.endAndSend")}</Btn>
          </div>
        </ModalBox>
      )}
      {modal === "voicehelp" && (
        <ModalBox title={t("voice.helpTitle")} close={() => Modal("")}>
          <p>{t("voice.help1")}</p>
          <p>{t("voice.help2")}</p>
          <p>{t("voice.help3")}</p>
          <p className="demo-note">{t("voice.helpNote")}</p>
        </ModalBox>
      )}
      {toastUI}
    </div>
  );
}
function Auth({ children, go, onLanguage }) {
  const { t } = useTranslation();
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
            {t("auth.asideA")}
            <br />
            <em>{t("auth.asideB")}</em>
          </h1>
          <p>
            {t("auth.asideText1")}
            <br />
            {t("auth.asideText2")}
          </p>
          <div>
            <b>{t("auth.asideTag")}</b>
            <small>{t("auth.asideSmall")}</small>
          </div>
        </div>
      </aside>
      <main className="auth-main">
        <LanguageSwitcher onChange={onLanguage} className="auth-lang" />
        {children}
      </main>
    </div>
  );
}
function PatientDashboard({
  go,
  onLanguage,
  intakes,
  onView,
  notify,
  userName,
  onLogout,
}) {
  const { t } = useTranslation();
  const latest = intakes && intakes.length ? intakes[0] : null;
  return (
    <div className="patient-layout">
      <aside className="patient-sidebar">
        <Brand go={go} />
        <nav>
          <button className="active">
            <LayoutDashboard /> {t("dash.nav.dashboard")}
          </button>
          <button onClick={() => notify(t("dash.profileSoon"))}>
            <User /> {t("dash.nav.profile")}
          </button>
          <button onClick={() => go("chat")}>
            <MessageCircle /> {t("dash.nav.chat")}
          </button>
          <button
            onClick={() =>
              document
                .getElementById("history")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            <History /> {t("dash.nav.history")}
          </button>
          <button onClick={onLogout}>
            <LogOut /> {t("common.logout")}
          </button>
        </nav>
        <LanguageSwitcher onChange={onLanguage} className="language" />
      </aside>
      <main className="patient-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">{t("dash.eyebrow")}</span>
            <h2>
              {userName ? t("common.welcomeName", { name: userName }) : t("dash.welcome")}
            </h2>
            <p>{t("dash.feeling")}</p>
          </div>
          <span className="user-chip">{initials(userName)}</span>
        </header>
        <div className="patient-grid">
          <div>
            <section className="consult">
              <div>
                <span className="eyebrow">{t("dash.consultEyebrow")}</span>
                <h3>{t("dash.consultTitle")}</h3>
                <p>{t("dash.consultText")}</p>
                <div className="actions">
                  <Btn onClick={() => go("voice")}>
                    <Mic /> {t("dash.tapToSpeak")}
                  </Btn>
                  <Btn kind="outline" onClick={() => go("chat")}>
                    <MessageCircle /> {t("dash.startText")}
                  </Btn>
                </div>
              </div>
              <HeartPulse />
            </section>
            <VisitStatus />
            <section className="history" id="history">
              <div className="section-title">
                <div>
                  <span className="eyebrow">{t("dash.recordsEyebrow")}</span>
                  <h3>{t("dash.recordsTitle")}</h3>
                </div>
              </div>
              <div className="history-table">
                <div className="history-row head">
                  <span>{t("common.date")}</span>
                  <span>{t("dash.whatYouShared")}</span>
                  <span>{t("common.status")}</span>
                  <span>{t("common.action")}</span>
                </div>
                {intakes === null && <p className="empty">{t("common.loading")}</p>}
                {intakes && !intakes.length && <p className="empty">{t("dash.nothingYet")}</p>}
                {(intakes || []).map((r) => (
                  <div className="history-row" key={r.id}>
                    <span>{formatDate(r.created_at)}</span>
                    <span dir="auto">
                      {r.original_text.length > 70
                        ? r.original_text.slice(0, 70) + "…"
                        : r.original_text}
                    </span>
                    <span>{t(`review.${r.review_status}`)}</span>
                    <button className="link" onClick={() => onView(r)}>
                      {t("common.view")} <ArrowRight />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <aside className="intake-card">
            <div className="section-title">
              <h3>{t("dash.latest")}</h3>
              {latest && (
                <span
                  className={
                    "status " +
                    (latest.review_status === "confirmed" ? "done" : "blue")
                  }
                >
                  {t(`review.${latest.review_status}`)}
                </span>
              )}
            </div>
            {latest ? (
              <>
                <small>{t("dash.whatYouShared")}</small>
                <b dir="auto">
                  {latest.original_text.length > 120
                    ? latest.original_text.slice(0, 120) + "…"
                    : latest.original_text}
                </b>
                <Info label={t("common.submitted")} value={formatDate(latest.created_at)} />
                <Info
                  label={t("common.department")}
                  value={latest.confirmed_department_name || t("common.assignedAfterReview")}
                />
              </>
            ) : (
              <small>{t("dash.noIntake")}</small>
            )}
            <div className="assigned">
              <div className="avatar">HS</div>
              <div>
                <b>HealthSpeak AI</b>
                <small>{t("common.staffReviewEvery")}</small>
              </div>
            </div>
            <p className="notice">
              <ShieldCheck /> {t("common.noDiagnosis")}
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}
function Staff({
  go,
  notify,
  userName,
  onLogout,
  intakes,
  canReview,
  onReview,
  dash,
  onOpen,
  onLanguage,
}) {
  const { t, i18n: i18 } = useTranslation();
  const q = dash ? dash.queue : null;
  const today = new Date().toLocaleDateString(i18.language, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return (
    <div className="staff-layout">
      <aside className="staff-sidebar">
        <Brand go={go} />
        <LanguageSwitcher onChange={onLanguage} className="language" />
        <nav>
          <button className="active">
            <LayoutDashboard /> {t("staff.overview")}
          </button>
          <button
            onClick={() =>
              document.getElementById("live-queue")?.scrollIntoView({ behavior: "smooth" })
            }
          >
            <Users /> {t("staff.queueNav")}
          </button>
        </nav>
        <div className="staff-user">
          <div className="avatar">{initials(userName)}</div>
          <div>
            <b>{userName}</b>
            <small>{t("staff.workspace")}</small>
          </div>
          <button onClick={onLogout} title={t("common.logout")} aria-label={t("common.logout")}>
            <LogOut />
          </button>
        </div>
      </aside>
      <main className="staff-main">
        <header className="dash-head">
          <div>
            <span className="eyebrow">{today.toUpperCase()}</span>
            <h2>{t("staff.hello", { name: userName })}</h2>
            <p>{t("staff.daily")}</p>
          </div>
          <span className="user-chip">{initials(userName)}</span>
        </header>
        <div className="stats">
          <Stat
            icon={<Users />}
            label={t("staff.inQueue")}
            value={q ? pad2(Object.values(q).reduce((a, b) => a + b, 0)) : "--"}
          />
          <Stat
            icon={<Clock3 />}
            label={t("staff.awaiting")}
            value={intakes ? String(intakes.total).padStart(2, "0") : "--"}
          />
          <Stat icon={<CheckCircle2 />} label={t("staff.completedVisits")} value={q ? pad2(q.completed) : "--"} />
        </div>
        {canReview && (
          <section className="queue">
            <div className="section-title">
              <div>
                <span className="eyebrow">{t("staff.aiEyebrow")}</span>
                <h3>{t("staff.awaiting")}</h3>
              </div>
            </div>
            <div className="queue-table">
              <div className="queue-row queue-head">
                <span>{t("staff.submitted")}</span>
                <span>{t("staff.patient")}</span>
                <span>{t("staff.language")}</span>
                <span>{t("staff.shared")}</span>
                <span>{t("common.status")}</span>
                <span>{t("common.action")}</span>
              </div>
              {intakes === null && <p className="empty">{t("common.loading")}</p>}
              {intakes && !intakes.items.length && <p className="empty">{t("staff.noneWaiting")}</p>}
              {(intakes ? intakes.items : []).map((i) => (
                <div className="queue-row" key={i.id}>
                  <small>{formatDate(i.created_at)}</small>
                  <b>{i.patient_name}</b>
                  <span>{t(`lang.${i.original_language}`)}</span>
                  <span dir="auto">{i.snippet}</span>
                  <span>
                    <span className="status wait">{t("staff.unreviewed")}</span>
                    {i.needs_attention && (
                      <span className="status attention" title="Mentions words marked for prompt staff attention">
                        {t("staff.attention")}
                      </span>
                    )}
                    {i.suggested_department && (
                      <small className="suggestion">
                        {t("staff.suggests", { d: i.suggested_department })}
                      </small>
                    )}
                  </span>
                  <button className="link" onClick={() => onReview(i.id)}>
                    {t("common.review")} <ArrowRight />
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
        <div id="live-queue">
          <QueuePanel
            eyebrow={t("staff.liveEyebrow")}
            title={t("staff.liveTitle")}
            emptyText={t("staff.liveEmpty")}
            onOpen={onOpen}
            notify={notify}
          />
        </div>
      </main>
    </div>
  );
}
function IntakeReview({
  intake,
  busy,
  go,
  onSave,
  onRetryTranslation,
  onReanalyse,
  departments,
}) {
  const [text, SetText] = useState(
    intake.final_text || intake.english_text || "",
  );
  const [reason, SetReason] = useState("");
  const a = intake.analysis;
  const sug = a ? a.suggestion : null;
  const [dept, SetDept] = useState(
    (intake.confirmed_department && intake.confirmed_department.id) ||
      (sug && sug.department_id) ||
      "",
  );
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
                    disabled={busy || !text.trim() || !dept}
                    onClick={() => onSave(text, reason, true, dept)}
                  >
                    Confirm intake <Check />
                  </Btn>
                )}
              </div>
            </div>
            <div className="workspace-section">
              <span className="eyebrow">DEPARTMENT (CHOSEN BY STAFF)</span>
              {confirmed ? (
                <p>
                  <b>{intake.confirmed_department ? intake.confirmed_department.name : "—"}</b>
                </p>
              ) : (
                <select
                  className="dept-select"
                  value={dept}
                  onChange={(e) => SetDept(e.target.value)}
                  aria-label="Department"
                >
                  <option value="">Choose a department...</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <AnalysisPanel analysis={a} busy={busy} onReanalyse={onReanalyse} hasFinal={Boolean(intake.final_text)} />
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
function AnalysisPanel({ analysis: a, busy, onReanalyse, hasFinal }) {
  if (!a) {
    return (
      <div className="workspace-section analysis">
        <span className="eyebrow">AI-ASSISTED SUMMARY · UNCONFIRMED</span>
        <p>
          No automatic summary yet. It is created once an English version of the
          patient's words exists.
        </p>
        {hasFinal && (
          <Btn kind="outline" disabled={busy} onClick={onReanalyse}>
            Create summary from reviewed text
          </Btn>
        )}
      </div>
    );
  }
  const ex = a.extraction;
  const sug = a.suggestion;
  const statusText = {
    matched: `Suggests ${sug.department_name}`,
    ambiguous: "Several departments possible — staff must choose",
    default: `No routing rule matched — default department ${sug.department_name}`,
    no_rules: "No routing rules configured",
  }[sug.status];
  return (
    <div className="workspace-section analysis">
      <span className="eyebrow">
        AI-ASSISTED SUMMARY · UNCONFIRMED · FROM {a.source === "final_text" ? "STAFF-REVIEWED TEXT" : "ENGLISH TEXT"}
      </span>
      {sug.attention.length > 0 && (
        <p className="attention-box">
          <b>Prompt staff attention:</b> the patient's words include{" "}
          {sug.attention.map((m) => `"${m.evidence}"`).join(", ")}. This is a
          flag for staff, not a triage decision.
        </p>
      )}
      <p>{a.summary}</p>
      <div className="analysis-grid">
        <div>
          <small>Reported (exact words)</small>
          {ex.reported.length ? (
            <ul>
              {ex.reported.map((m) => (
                <li key={m.term}>
                  {m.term}: <q>{m.evidence.text}</q>
                </li>
              ))}
            </ul>
          ) : (
            <p>None identified</p>
          )}
        </div>
        <div>
          <small>Said they do NOT have</small>
          {ex.denied.length ? (
            <ul>
              {ex.denied.map((m) => (
                <li key={m.term}>
                  {m.term}: <q>{m.evidence.text}</q>
                </li>
              ))}
            </ul>
          ) : (
            <p>—</p>
          )}
        </div>
        <div>
          <small>Not mentioned (ask the patient)</small>
          <ul>
            {ex.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      </div>
      <p>
        <b>Department suggestion:</b> {statusText}
        {sug.candidates.length > 0 && (
          <>
            {" "}
            (because of{" "}
            {sug.candidates
              .flatMap((c) => c.matches.map((m) => `"${m.evidence}" → ${c.name}`))
              .join("; ")}
            )
          </>
        )}
      </p>
      <small>
        Rule-based suggestion, not a diagnosis. Rules {a.ruleset_version} ·{" "}
        {a.engine_version}
      </small>
      {hasFinal && (
        <div className="actions">
          <Btn kind="outline" disabled={busy} onClick={onReanalyse}>
            Re-create summary from reviewed text
          </Btn>
        </div>
      )}
    </div>
  );
}
