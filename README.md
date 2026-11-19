# HealthSpeak AI — Frontend Prototype

A responsive React + Vite frontend prototype based on the 16-page HealthSpeak AI reference PDF. This is a demonstration only: it has no backend, database, real authentication, API calls, clinical decision engine, or persistent storage.

## Prerequisites

1. Install **Node.js LTS** (includes npm) from https://nodejs.org/.
2. Install **Visual Studio Code** from https://code.visualstudio.com/.
3. Optional VS Code extensions: **ES7+ React/Redux/React-Native snippets**, **Prettier - Code formatter**, and **JavaScript and TypeScript Nightly**. The project does not require extensions to run.
4. Internet access is needed for the first `npm install` to download project packages. After installation, the local development server runs on your PC.

## Open and run in VS Code (Windows)

1. Extract `healthspeak-ai-prototype.zip` to a folder such as `Documents/HealthSpeakAI`.
2. Open VS Code.
3. Choose **File → Open Folder...** and select the extracted `healthspeak-ai` folder (the folder containing `package.json`).
4. Open **Terminal → New Terminal**.
5. Check that Node and npm are installed:

   ```bash
   node -v
   npm -v
   ```

6. Install dependencies (first run only):

   ```bash
   npm install
   ```

7. Start the development server:

   ```bash
   npm run dev
   ```

8. VS Code's terminal displays a local address, usually `http://localhost:5173/`. Hold **Ctrl** and click it, or copy it into Chrome.
9. To stop the server, return to the terminal and press **Ctrl + C**.

## Project structure

```text
healthspeak-ai/
├── index.html          # Browser entry point
├── package.json        # Dependencies and run scripts
├── README.md           # Setup instructions
└── src/
    ├── main.jsx        # React entry point
    ├── App.jsx         # Screens, sample data, navigation and interactions
    └── styles.css      # Theme, layout and responsive styling
```

## Screens and interactions

- Landing page, feature section, FAQs and contact footer
- Login with Patient / Doctor / Staff role selection; demo credentials accept any non-empty values
- Patient registration with required-field validation
- Voice intake screen with simulated listening/transcription controls
- Text chat with simulated medical-team responses, attachment selection and language selector
- Doctor profile
- Patient dashboard, current intake status and three consultation-history summaries
- Staff dashboard with patient search, status filtering and queue
- Patient workspace with edit mode, status changes, check-in/completion actions, intake summary and staff notes
- Modal dialogs, success/error toast notifications and responsive layouts

## Important prototype notes

- Voice input is simulated. The browser microphone is not accessed.
- Chat replies and sample patient records are mock data.
- Patient and staff changes exist only in React memory and reset when the page is refreshed.
- No medical advice, diagnosis, prescription validation, or real patient records are provided. Clinical information in the reference is reproduced as illustrative sample content only.
- The palette is approximated from the photographed PDF pages; exact Figma colour tokens and font files were not embedded in the PDF.

## Build a production bundle locally

```bash
npm run build
npm run preview
```
