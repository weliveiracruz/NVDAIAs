# NVDAIAs – Chat with ChatGPT, Gemini and Claude from NVDA

* Author: Wellington Cruz
* Version: 1.1.0
* Compatibility: NVDA 2024.1 or later (last tested with NVDA 2026.2), Windows 10 and 11
* License: GNU General Public License, version 2
* Documentation in Portuguese (Brazil): docs/pt_BR/readme.md

NVDAIAs opens an accessible NVDA window where you ask questions to **ChatGPT** (OpenAI), **Gemini** (Google) or **Claude** (Anthropic) and read the answers without leaving the program you are working in. It can also **describe images of the screen** with the AI.

Parts of this add-on were written with the help of AI (Claude), and reviewed and tested by the author.

## Before you start: the access token

The three services only let third-party programs connect through an **access token**, also called an **API key**. There is no official way to sign in to ChatGPT, Gemini or Claude with your e-mail and password from another program. The NVDAIAs "login screen" is therefore the **Connect account** screen, where you paste the token generated on each provider's site.

| AI | Where to create the token | Cost |
|---|---|---|
| ChatGPT | platform.openai.com/api-keys | Pay per use, billed separately from ChatGPT Plus; the platform account needs credit. |
| Gemini | aistudio.google.com/app/apikey | Has a free tier with usage limits. |
| Claude | console.anthropic.com/settings/keys | Pay per use, billed separately from Claude Pro; the Console account needs credit. |

## First use

1. Press **NVDA+Alt+I**. With no AI connected yet, the **Connect account** screen opens.
2. Choose the AI, read the instructions and press **Open page to generate token**.
3. Sign in on the site, create the key, copy it, paste it in **Token (API key)** and press **Connect**.
4. NVDAIAs tests the token (listing the models, which costs nothing) and stores it encrypted.

## The chat window

Open it with **NVDA+Alt+I** or NVDA menu > Tools > **NVDAIAs - Chat with AI**. Focus starts in the Question field.

Tab order: **AI** (combo box), **Model**, **Conversation** (list of messages), **Question**, then the buttons Send, Cancel sending, Read message, Copy message, New conversation, Save conversation, Connect account, Settings and Close. **Shift+Tab from the Question field goes straight to the conversation list.**

The window has a visual theme that also helps people with low vision: navy header, light background, orange accents, larger fonts and a **thick orange frame around the field that has the focus**. A **status line** under the header shows the AI, the model and the state (connected, answering, last question failed); colours only repeat what the text says. The theme turns itself off in Windows high contrast and can be turned off in the settings, which also offer larger text. Buttons stay standard Windows buttons.

| Where | Key | Action |
|---|---|---|
| Question | Enter | Sends the question |
| Question | Shift+Enter | New line |
| Question | Shift+Tab | Goes to the conversation list |
| Conversation list | Enter | Opens the full message in a browse mode window (headings, lists, links) |
| Conversation list | Ctrl+C | Copies the selected message |
| Anywhere | Escape | Closes the window; the conversation is kept until NVDA restarts |

While waiting, a short beep plays every 1.5 seconds. When the answer arrives NVDA reads it (press Ctrl to stop). On errors, NVDA explains what happened and puts the question back in the field. You can switch AI in the middle of a conversation: the new AI receives the whole history.

## Commands

| Command | Action |
|---|---|
| NVDA+Alt+I | Opens the chat window |
| NVDA+Alt+D | Sends an image of the navigator object to the AI and reads the description |
| NVDA+Shift+Alt+D | Same for the whole screen (monitor of the active window) |
| (unassigned) | Opens the NVDAIAs settings |

All commands can be changed in NVDA menu > Preferences > Input gestures, category **NVDAIAs**.

## Settings

NVDA menu > Preferences > Settings > **NVDAIAs**: default AI; for each AI the token status, a field to paste a new token, Open page to generate token, Test connection, Remove saved token, Model and Update model list; the instructions sent to the AI with every question (with Restore default instructions); read answers automatically; beep while waiting; remove formatting symbols; use the visual theme; larger text; maximum answer size for Claude; time limit.

## Privacy and security

* Tokens are not stored in nvda.ini. They are kept in `NVDAIAs-credentials.json` in the NVDA configuration folder, **encrypted with the Windows Data Protection API (DPAPI)** for the current Windows user. The file is deleted when the add-on is uninstalled.
* Questions, conversation history and the screenshots you ask to describe are sent directly from your computer to the chosen provider (OpenAI, Google or Anthropic) over HTTPS, and to no one else. Each provider handles the data under its own privacy policy.
* Screenshots include everything visible in the captured area.
* The add-on does not run on secure screens (logon, UAC).
* The conversation lives only in memory; use **Save conversation** to keep it in a text file.

## Changes

### 1.1.0

* Visual theme built from design tokens: navy header, orange accents, larger fonts, status line and thick focus frame. All colours meet WCAG 2.2 AA; off in Windows high contrast. New options: use the visual theme, larger text. AI and Model side by side, Send next to the question.

### 1.0.0

* First release: chat window with ChatGPT, Gemini and Claude; account connection screen with token; settings panel; description of the navigator object and of the screen; Portuguese (Brazil) translation.
