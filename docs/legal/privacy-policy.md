# RentCheck Privacy Policy

**Version 1.0 — last updated 20 October 2026**

RentCheck is a tenancy-agreement analysis tool. You paste or upload a tenancy
agreement and it returns flagged clauses, missing protections and questions to
ask before you sign. This policy explains what personal data that involves, why
we use it, who else sees it, and what you can ask us to do about it.

We have tried to write this in plain language rather than legal padding. If
anything is unclear, ask us — the contact details are at the end.

## 1. Who we are

The data controller for the Service is:

| | |
| --- | --- |
| **Data controller** | NORMID INC |
| **Contact** | faizahmadadetola@gmail.com |
| **Registered address** | [REGISTERED ADDRESS] |
| **Service** | RentCheck, at rentcheck.rumptycloud.app |

"Controller" means we decide why and how personal data is processed. We are not
a law firm and we do not give legal advice — see our [Terms of Service](/terms).

## 2. At a glance

| What we hold | Why | Who else sees it |
| --- | --- | --- |
| The text of your tenancy agreement (pasted, or extracted from your PDF, Word file or photo) | To produce your analysis | Rumpty AI Inference (selected parts only — see section 5), Rumpty Cloud (hosting and database) |
| The analysis we generate for you: flagged clauses, missing protections, questions, risk score | To show you the result and keep it for you | Rumpty Cloud |
| Server logs: IP address, timestamps, requested pages, error traces | To run the Service, debug failures and prevent abuse | Rumpty Cloud |

We do not use cookies. We do not run analytics or advertising. We do not sell
your data. We do not use your document to train anyone's AI model.

## 3. What we collect

### 3.1 The document you submit

This is the heart of it. When you paste text or upload a file, we take the text
of the tenancy agreement and analyse it.

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

### 3.2 What we do not collect

- **No account.** There is no sign-up, no login, and we never ask for your name
  or email address in order to use the Service.
- **No payment details.** The Service is free and takes no payments.
- **No cookies, no analytics, no advertising identifiers, no third-party
  trackers.** The page loads no external scripts at all.
- **No location data, contacts, or device identifiers** beyond what any web
  server sees in a standard request.

### 3.3 Technical data in logs

Like any web service, our servers log the IP address a request came from, the
time, the path requested and any error trace. Because of how the analysis is
logged, **operational logs can also contain short excerpts of document text** —
for example a clause the model was asked about, or its answer. Logs are used for
debugging and security only.

## 4. Why we are allowed to use it

The Nigeria Data Protection Act 2023 ("NDPA") sets out the lawful bases for
processing. We rely on:

- **Performing the service you asked for** — analysing the document you submit
  and returning your results. This is the main basis for the document text and
  the analysis.
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

Your agreement text and its analysis are kept in our database **until you ask us
to delete them**. There is currently no automatic expiry.

We would rather say that plainly than claim a retention period we do not
enforce. It also means deletion is something you should ask for actively, and
here is how.

To have your data deleted, email **faizahmadadetola@gmail.com**. Because the
results screen does not show an analysis ID and we have no accounts to look you
up by, please give us something that lets us find the record — for example the
date you ran the analysis, or the landlord's or agent's name or the property
address as it appears in the agreement. We will delete the stored text and its
analysis, and confirm when it is done.

## 9. How we protect it

- **In transit** over HTTPS.
- **At rest** in a managed PostgreSQL database on Rumpty Cloud.
- **Uploads are handled in memory** and are not saved to disk as files.
- **No passwords to steal**: there are no accounts on the Service.
- **Access is limited** to the people who operate and maintain the Service.

No system is perfectly secure and we do not pretend otherwise. RentCheck is an
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

To exercise any of these, email **faizahmadadetola@gmail.com**. We aim to respond
within 30 days and will not charge you for a reasonable request.

One honest limitation: because there are no accounts, we can only find your data
if you help us identify it. A request that says only "delete my data" may not be
something we can act on, and we will tell you if we need more from you.

## 11. Automated decisions

Your results, including the risk score, are generated automatically. That score
is a rough indicator built from how many clauses were flagged and how many
expected protections were missing — it is not a legal assessment of your
agreement and it is not a decision *about you*.

The NDPA restricts decisions based solely on automated processing that produce
legal effects or similarly significantly affect you. RentCheck does not make
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

**NORMID INC** — faizahmadadetola@gmail.com — [REGISTERED ADDRESS]

If you are not satisfied with how we have handled something, you have the right
to complain to the **Nigeria Data Protection Commission (NDPC)**. We would
appreciate the chance to put it right first.

See also our [Terms of Service](/terms).
