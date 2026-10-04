# NVDAIAs – Chat with ChatGPT, Gemini and Claude from NVDA

* Author: Wellington Cruz
* Version: 1.5.0
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

Tab order: **AI** (combo box), **Model**, **Conversation** (a tree with two branches: **Previous conversations**, collapsed, and **Current conversation (N messages)**, expanded; both collapse and expand with the arrows or Enter, and the current one opens again when a new answer arrives), **Question**, **Attach files**, Send, the **Attached files** list (only while files are waiting), then the buttons Cancel sending, Read message, Copy message, Actions for this message, New conversation, Save conversation, Connect account, Settings and Close. **Shift+Tab from the Question field goes straight to the conversation list.**

The window has a visual theme that also helps people with low vision: navy header, light background, orange accents, larger fonts and a **thick orange frame around the field that has the focus**. A **status line** under the header shows the AI, the model and the state (connected, answering, last question failed); colours only repeat what the text says. The theme turns itself off in Windows high contrast and can be turned off in the settings, which also offer larger text. Buttons stay standard Windows buttons.

| Where | Key | Action |
|---|---|---|
| Question | Enter | Sends the question |
| Question | Shift+Enter | New line |
| Question | Shift+Tab | Goes to the conversation list |
| Conversation | Right / Left arrow | Expands / collapses "Previous conversations" or a previous conversation |
| Conversation, current message | Enter, Applications key or Shift+F10 | Opens the **message actions** menu |
| Conversation, previous conversation or one of its messages | Enter | Reopens that conversation to be continued |
| Conversation | Ctrl+C | Copies the selected message |
| Conversation, previous conversation | Delete | Deletes it from the history (asks first) |
| Anywhere | Escape | Closes the window; the conversation stays open and is already saved |

While waiting, a short beep plays every 1.5 seconds. When the answer arrives NVDA reads it (press Ctrl to stop). On errors, NVDA explains what happened and puts the question back in the field. You can switch AI in the middle of a conversation: the new AI receives the whole history.

### Message actions

Enter (or the Applications key, Shift+F10 or the **Actions for this message** button) on a message of the current conversation opens a menu: **Read message** (browse mode window), **Copy**, **Delete** (asks first; also updates the history), **Translate to** (12 languages), **Describe this image in more detail** (messages with images and their answers) and **Improve this answer** (AI answers). Messages of previous conversations offer Read, Copy and Open this conversation. Actions that ask the AI something appear in the conversation as a new question with its answer.

### Attach files

**Attach files** (next to the Question field, Tab from it) opens the standard Windows file dialog with all formats; several files can be chosen.

| File | What happens | AIs |
|---|---|---|
| Images (JPG, PNG, GIF, WebP; BMP, TIFF and others are converted to PNG) | Sent as an image | ChatGPT, Gemini, Claude |
| PDF | Sent as a document | ChatGPT, Gemini, Claude |
| .docx, .xlsx, .pptx (with notes), .odt, .ods, .odp, EPUB, RTF, HTML | Text extracted on this computer | ChatGPT, Gemini, Claude |
| Text, CSV, JSON, XML, Markdown, source code and any other text file | Sent as text | ChatGPT, Gemini, Claude |
| Audio and video | Sent to be listened to or watched | Gemini only |
| .doc, .xls, .ppt, programs, archives and other binaries | Not read; a message explains how to convert | - |

Attached files are listed under the question (Delete removes one) and go with the next question; you can send without typing (the AI is asked to analyse and summarise them). On errors or cancel the question and files come back. Files stay in the conversation and in the history. Limits: 20 MB per file; text cut at 300,000 characters.

### Previous conversations

Every conversation is saved automatically. The first item of the Conversation tree, **Previous conversations (N)**, starts collapsed. Expand it with the Right arrow; each previous conversation shows its date, AIs, first question and number of messages, and expands to show its messages. **Enter** on a previous conversation or on any of its messages reopens it as the current conversation, focus goes to the Question field and the AI receives the whole history. The conversation that was open goes to the history. **New conversation** saves the current one and starts a blank one.

## Commands

| Command | Action |
|---|---|
| NVDA+Alt+I | Opens the chat window |
| NVDA+Alt+D | Sends an image of the navigator object to the AI and reads the description |
| NVDA+Shift+Alt+D | Same for the whole screen (monitor of the active window) |
| (unassigned) | Opens the NVDAIAs settings |

All commands can be changed in NVDA menu > Preferences > Input gestures, category **NVDAIAs**.

## Settings

NVDA menu > Preferences > Settings > **NVDAIAs**: default AI; for each AI the token status, a field to paste a new token, Open page to generate token, Test connection, Remove saved token, Model and Update model list; the instructions sent to the AI with every question (with Restore default instructions); read answers automatically; beep while waiting; remove formatting symbols; keep previous conversations, maximum number and Delete all previous conversations; use the visual theme; larger text; maximum answer size for Claude; time limit.

## Privacy and security

* Tokens are not stored in nvda.ini. They are kept in `NVDAIAs-credentials.json` in the NVDA configuration folder, **encrypted with the Windows Data Protection API (DPAPI)** for the current Windows user. Updating the add-on keeps the tokens and the history; only a real uninstall deletes them.
* Questions, conversation history and the screenshots you ask to describe are sent directly from your computer to the chosen provider (OpenAI, Google or Anthropic) over HTTPS, and to no one else. Each provider handles the data under its own privacy policy.
* Screenshots include everything visible in the captured area.
* The add-on does not run on secure screens (logon, UAC).
* Conversations are saved automatically after each answer in the `NVDAIAs-history` folder of the NVDA configuration, **encrypted with DPAPI** like the tokens (screenshots and attached files included). Delete one with the Delete key, delete all in the settings or turn the history off. The history is kept when the add-on is updated and deleted when it is uninstalled. **Save conversation** writes a plain text file.

## Changes

### 1.5.0

* Tokens and conversation history kept when the add-on is updated, also coming from 1.0.0 to 1.4.0.
* The current conversation is a collapsible branch of the tree.

### 1.4.0

* Message actions (Enter, Applications key or button): read, copy, delete, translate to 12 languages, describe image in more detail, improve answer.
* Security and accessibility fixes found by the new test plan (docs/SDD-TESTES.md).

### 1.3.0

* Attach files button next to the question, any file: images and PDF to the three AIs; Office, OpenDocument, EPUB, RTF, HTML and text files read locally; audio and video to Gemini.

### 1.2.0

* Previous conversations: first item of the conversation tree, collapsed by default; each saved conversation expands to show its messages and Enter on any of them reopens it to be continued. Saved automatically, encrypted with DPAPI. Delete removes one. New options: keep previous conversations, maximum number, delete all.

### 1.1.0

* Visual theme built from design tokens: navy header, orange accents, larger fonts, status line and thick focus frame. All colours meet WCAG 2.2 AA; off in Windows high contrast. New options: use the visual theme, larger text. AI and Model side by side, Send next to the question.

### 1.0.0

* First release: chat window with ChatGPT, Gemini and Claude; account connection screen with token; settings panel; description of the navigator object and of the screen; Portuguese (Brazil) translation.
