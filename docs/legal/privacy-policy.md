# Tenura Privacy Policy

**Version 1.3 — last updated 21 October 2026**

Tenura is a tenancy-agreement analysis tool. You paste or upload a tenancy
agreement and it returns flagged clauses, missing protections and questions to
ask before you sign. You can use it as a guest, or create an account to keep the
analyses you run. This policy explains what personal data each of those involves,
why we use it, who else sees it, and what you can ask us to do about it.

We have tried to write this in plain language rather than legal padding. If
anything is unclear, ask us — the contact details are at the end.

## 1. Who we are

The data controller for the Service is:

| | |
| --- | --- |
| **Data controller** | NORMID INC |
| **Contact** | privacy@tenura.online |
| **Registered address** | FJQG+XWH Oke Ogun, Ilorin, Kwara State, Nigeria |
| **Service** | Tenura, at www.tenura.online |

"Controller" means we decide why and how personal data is processed. We are not
a law firm and we do not give legal advice — see our [Terms of Service](/terms).

## 2. At a glance

You can use Tenura without an account. If you do, your document is analysed
and **nothing is kept** — no document text, no result. If you are signed in, the
analysis and the document text behind it are saved to your history until you
delete them.

| What we hold | Why | Who else sees it |
| --- | --- | --- |
| The text of the agreement you submit, **only when you are signed in** | To produce your analysis, and to reopen it later from your history | Rumpty AI Inference (selected parts only — see section 5), Rumpty Cloud (hosting and database) |
| The analysis we generate — flagged clauses, missing protections, questions, risk score — **only when you are signed in** | To show you the result and keep it for you | Rumpty Cloud |
| If you have an account: your **email address**, your **password hash**, and the **one-time codes** we send you | To sign you in, verify your email, and let you reset a forgotten password | Rumpty Cloud; and our email provider, Resend, to deliver the message |
| A **session cookie** holding your signed-in state | To keep you logged in between pages | Nobody — it is set by us and never shared |
| Server logs: IP address, timestamps, requested pages, error traces | To run the Service, debug failures and prevent abuse | Rumpty Cloud |

We run no analytics and no advertising, and no third-party scripts load on the
page. We do not sell your data. We do not use your document to train anyone's AI
model.

## 3. What we collect

### 3.1 The document you submit

This is the heart of it. When you paste text or upload a file, we take the text
of the tenancy agreement and analyse it.

**As a guest, nothing about your document is kept.** The result is returned to
your browser and then forgotten: no copy of the text and no copy of the analysis
is stored on our side. (To let you keep a result if you sign up straight
afterwards, your own browser may briefly hold the text you typed — see
section 3.2.)

**When you are signed in, we keep the analysis and the document text behind it**,
so you can reopen it from your history later. You can delete any saved analysis
yourself from the history page, which removes the text for good.

- We keep the **extracted text** of the document. If you upload a PDF, Word file
  or photo, we keep the text we pulled out of it.
- We **do not keep your uploaded file**. Uploads are read into memory, converted
  to text, and never written to disk as files.
- Your **filename is not stored**. It is used only at the moment of upload to
  work out which file format you sent.

A tenancy agreement is a document full of personal data, and almost none of it
is ours to ask for. It typically contains names, postal addresses, phone numbers
and email addresses, the landlord's or agent's details, rent and payment
amounts, sometimes bank or account details, and signatures. All of that arrives
simply because it is inside the document you sent us.

**Please do not upload a document you are not entitled to share.** If it
contains information about someone else — a landlord, an agent, a co-tenant —
you need a lawful reason to give it to us, and to let us process it as described
here.

We also reject anything that is not a tenancy agreement. If you upload a receipt,
a photo, a different kind of contract or an unreadable file, we tell you so and
**we do not store it at all**. No record of a rejected upload is kept beyond the
ordinary server logs described below.

### 3.2 Accounts, and what we still do not collect

An account needs an email address and a password, and nothing else. We do not ask
for your name, phone number, date of birth, or address.

- **Passwords** are hashed with Argon2id before they are stored. We never store
  the password itself and we cannot recover it. A forgotten password is reset
  through a one-time code emailed to you, not by us reading anything out.
- **One-time codes** are stored hashed as well, expire after 10 minutes, can be
  used once, and are replaced when you ask for a new one.
- **One session cookie**, named `tenura_session`, holds your signed-in state. It is
  set `httpOnly` (JavaScript on the page cannot read it), `Secure`, and
  `SameSite=Lax`, and it contains only a signed user reference and an expiry — no
  password, no document data. Signing out clears it.
- **No analytics, no advertising identifiers, no third-party trackers.** No
  external scripts load on the page at all.
- **No payment details.** The Service is free and takes no payments.
- **No location data, contacts, or device identifiers** beyond what any web
  server sees in a standard request.
- **If you analyse as a guest**, the text you typed may be held briefly in your
  own browser's session storage, so that we can offer to save the result if you
  then create an account. It stays on your device, disappears when you close the
  tab, and is cleared the moment you save it or dismiss the offer. Uploaded files
  are never held this way.

### 3.3 Technical data in logs

Like any web service, our servers log the IP address a request came from, the
time, the path requested and any error trace. Because of how the analysis is
logged, **operational logs can also contain short excerpts of document text** —
for example a clause the model was asked about, or its answer. Logs are used for
debugging and security only.

One thing that is never logged: **one-time codes and passwords**. Neither is
written to a log, and neither is stored in a form anyone can read.

## 4. Why we are allowed to use it

The Nigeria Data Protection Act 2023 ("NDPA") sets out the lawful bases for
processing. We rely on:

- **Performing the service you asked for** — analysing the document you submit
  and returning your results, and, where you have an account, signing you in and
  keeping your history. This is the main basis for the document text, the
  analysis, and your account details.
- **Our legitimate interests** — keeping the Service working and secure,
  diagnosing failures, and preventing abuse. We keep this as narrow as we can,
  and it never overrides your rights.
- **Consent** — where you specifically give it, such as when you write to us
  asking us to keep information, or where the law requires consent.
- **Legal obligation** — where we are required to keep or disclose something by
  law.

## 5. AI processing: what actually leaves our server

This is the part most privacy policies mumble through, so here is the detail.

To judge a clause, we send **that one clause's text** and the relevant Nigerian
rental norm to an AI model operated by Rumpty Cloud ("Rumpty AI Inference") over
an OpenAI-compatible API. We do not send your whole document for clause
analysis, and we do not send one document as a single request.

There is one other case. Before analysing anything, we decide whether the input
is really a tenancy agreement. Most files are decided by fixed rules with no AI
involved. If, and only if, the answer is genuinely ambiguous, we send **only the
first 1,800 characters** of the text to the model to have it decide.

Much of the analysis involves no AI at all. Known high-confidence traps — such
as a re-entry clause that operates "whether or not lawfully demanded", or a
non-refundable caution fee — are caught by fixed rules in our own code, and when
a rule fires we do not ask the model about that clause. Missing protections and
the questions to ask are worked out entirely by fixed code.

Two things follow from this that you should know:

- **Clause text can contain personal data** — names, addresses, rent figures —
  and text we send to the AI provider therefore may too. It is sent for the
  purpose of evaluating the clause, and nothing else.
- **AI output is a suggestion, not a finding.** Every flag that comes from the
  model must quote exact words from the clause, and our code verifies that the
  quote really appears there before showing it. AI-derived flags are labelled
  "[AI suggestion — worth a manual check]" in your results.

## 6. Who we share it with

| Recipient | What they receive | Why |
| --- | --- | --- |
| Rumpty AI Inference (Rumpty Cloud) | Individual clause text together with the matching rental norm; or the first 1,800 characters, but only when the document type is ambiguous | To evaluate a clause, or to classify the document |
| Rumpty Cloud | Our application and the managed PostgreSQL database, which holds your stored text and analysis | Hosting the Service and storing the data |
| Resend | Your email address and the one-time code message | To deliver verification and password-reset emails |

We do not sell, rent or trade personal data. We do not share it with advertisers
or data brokers. We do not allow a provider to use your document for their own
purposes.

We may disclose personal data where we are legally required to — for example a
valid court order or a lawful request from a competent Nigerian authority — or
where it is necessary to protect someone's safety or our legal rights. If that
ever happens, we disclose only what is actually required.

## 7. Transfers outside Nigeria

Our hosting and AI providers may process data on servers located outside
Nigeria. Where personal data is transferred out of the country, we rely on the
safeguards the NDPA requires for such transfers, including ensuring the
recipient is bound to protect the data to a comparable standard. If you need
details of where a particular transfer goes, ask us.

## 8. How long we keep it

**Guest analyses are not stored at all**, so there is nothing to keep.

For an account:

- **Saved analyses and their agreement text** are kept until you delete them.
  You can delete any of them yourself from [your history](/history), and deletion
  removes the agreement text permanently and immediately.
- **Your account** — the email address and password hash — is kept while the
  account exists. To close it, delete your saved analyses and email us to remove
  the account itself.
- **One-time codes** expire after 10 minutes, and are marked spent as soon as they
  are used. They are never reused.
- **Server logs** are kept only as long as they are needed for debugging and
  security.

There is no automatic expiry on saved analyses. We would rather say that plainly
than claim a retention period we do not enforce — and it is the reason the delete
button is in your hands rather than ours.

To close your account, or to have anything else deleted, email
**privacy@tenura.online** from the address on the account.

## 9. How we protect it

- **In transit** over HTTPS.
- **At rest** in a managed PostgreSQL database on Rumpty Cloud.
- **Uploads are handled in memory** and are not saved to disk as files.
- **Passwords are hashed with Argon2id** and are never stored or logged in plain
  text. Signed-in sessions use a signed, expiring cookie that page scripts cannot
  read, and no sign-in token is kept in browser storage where a script could reach
  it.
- **One-time codes are hashed, single-use, short-lived and attempt-limited.**
- **Every account can reach only its own records** — checked on the server for
  every query, not merely hidden in the interface.
- **Sign-in, sign-up and code requests are rate-limited** to slow down guessing
  and abuse.
- **Access is limited** to the people who operate and maintain the Service.

No system is perfectly secure and we do not pretend otherwise. Tenura is an
early-stage project, not a bank. If you are uncomfortable sending a particular
document, consider redacting the parts that are not relevant to the clauses you
want checked — the names, phone numbers and account details — before you submit
it. The analysis works fine without them.

## 10. Your rights

Under the NDPA you have the right to:

- **Be informed** about how your data is used — that is what this policy is for.
- **Access** the personal data we hold about you.
- **Rectify** anything inaccurate.
- **Erase** your data — see section 8.
- **Restrict or object** to certain processing.
- **Data portability**, where it applies.
- **Withdraw consent** at any time, where consent is what we relied on.
- **Complain** to the Nigeria Data Protection Commission (NDPC).

To exercise any of these, email **privacy@tenura.online**. We aim to respond
within 30 days and will not charge you for a reasonable request.

One honest note on access and erasure: if you have an account, the fastest route
is to manage your own data — [your history](/history) lists what we hold against
you and lets you rename or delete any of it directly. If you used Tenura as a
guest, nothing was stored, so there is nothing to retrieve or erase beyond
ordinary server logs. For anything else, email us; if we need more from you to
find a record, we will say so.

## 11. Automated decisions

Your results, including the risk score, are generated automatically. That score
is a rough indicator built from how many clauses were flagged and how many
expected protections were missing — it is not a legal assessment of your
agreement and it is not a decision *about you*.

The NDPA restricts decisions based solely on automated processing that produce
legal effects or similarly significantly affect you. Tenura does not make
that kind of decision. It gives you information about a document, and the choice
of what to do with it — sign, renegotiate, walk away, take it to a lawyer —
remains yours. Please treat every flag as a prompt to look, not a verdict.

## 12. Children

The Service is not intended for anyone under 18. Tenancy agreements are entered
into by adults, and we do not knowingly collect data from children. If you
believe a child has submitted a document, contact us and we will remove it.

## 13. Changes to this policy

We will update this policy as the Service changes. The version number and date
at the top will change with it, and we will note material changes on the site.
Continuing to use the Service after a change means you accept the updated
policy.

## 14. Contact and complaints

Questions, requests and complaints about privacy go to:

**NORMID INC** — privacy@tenura.online — FJQG+XWH Oke Ogun, Ilorin, Kwara State, Nigeria

If you are not satisfied with how we have handled something, you have the right
to complain to the **Nigeria Data Protection Commission (NDPC)**. We would
appreciate the chance to put it right first.

See also our [Terms of Service](/terms).
