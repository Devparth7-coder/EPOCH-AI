"""Builds the labelled EPOCH benchmark dataset.

Each *fact family* is a real, publicly documented fact with a known earlier and
later state (e.g. Python 3.7 → 3.13). For every family six claims are written,
one per verdict category, together with the evidence fixtures a retrieval engine
would plausibly return.

* Labels come from construction semantics ("this claim asserts a superseded
  release"), never from engine output.
* Fixtures carry real publication dates so the temporal engine has something
  honest to reason about.
* Retrieval is deterministic in benchmark mode, so the same dataset always
  produces the same verdicts: this measures the reasoning engine, not web noise.

Run:  python benchmark/build_dataset.py   → benchmark/dataset.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("dataset.jsonl")

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def doc(url: str, title: str, content: str, published: str, source_type: str = "docs", version: str | None = None) -> dict:
    return {
        "url": url,
        "title": title,
        "content": content,
        "published_date": published,
        "source_type": source_type,
        "version": version,
    }


FAMILIES: list[dict] = [
    {
        "id": "python", "subject": "Python", "old": "3.7", "new": "3.13",
        "old_date": "2019-06-18", "new_date": "2024-10-07", "type": "docs",
        "official": "https://docs.python.org/3/whatsnew/3.13.html",
        "secondary": "https://peps.python.org/pep-0719/",
        "archive": "https://medium.com/@devnotes/python-versions-explained",
        "support": "https://devguide.python.org/versions/",
        "detail": "Python 3.13 was released on October 7, 2024 and supersedes 3.12 as the current stable release.",
        "old_detail": "Python 3.7 is the newest version of Python available today.",
        "support_text": "Python 3.7 support ended in June 2023; Python 3.13 is the current stable release.",
        "support_until": "October 2029",
        "claims": {
            "current": "Python 3.13 is the current stable release of Python and was published on October 7, 2024.",
            "outdated": "Python 3.7 is the newest version of Python and is the release recommended for new projects.",
            "partial": "Python 3.7 is the current stable release of Python and its support window ends in June 2023.",
            "contradicted": "The official Python documentation states that Python 3.13 is not a supported release of Python.",
            "conflicting": "Python 3.13 is the current stable release of Python.",
            "insufficient": "The internal migration plan for Python 3.13 at the private deployment in Recife was approved by a committee of five engineers on 3 March.",
        },
    },
    {
        "id": "react", "subject": "React", "old": "18", "new": "19",
        "old_date": "2022-03-29", "new_date": "2024-12-05", "type": "docs",
        "official": "https://react.dev/blog/2024/12/05/react-19",
        "secondary": "https://github.com/facebook/react/releases",
        "archive": "https://medium.com/@frontendnotes/react-versions",
        "support": "https://react.dev/versions",
        "detail": "React 19 was released as stable on December 5, 2024 and supersedes React 18 as the current major release.",
        "old_detail": "React 18 is the latest major version of React.",
        "support_text": "React 18 receives security fixes only; React 19 is the current major release.",
        "support_until": "December 2026",
        "claims": {
            "current": "React 19 was released as a stable version on December 5, 2024.",
            "outdated": "React 18 is the latest major version of React.",
            "partial": "React 18 is the current major version of React and its support window ends in December 2026.",
            "contradicted": "The official React release notes state that React 19 was never shipped as a stable version.",
            "conflicting": "React 19 is the current major release of React.",
            "insufficient": "The React migration at a private logistics company in Pune was approved by four engineers on 12 February.",
        },
    },
    {
        "id": "node", "subject": "Node.js", "old": "18", "new": "22",
        "old_date": "2022-10-25", "new_date": "2024-04-24", "type": "docs",
        "official": "https://nodejs.org/en/about/previous-releases",
        "secondary": "https://github.com/nodejs/Release",
        "archive": "https://medium.com/@nodedeveloper/lts-lines",
        "support": "https://nodejs.org/en/about/previous-releases",
        "detail": "Node.js 22 is the Active LTS line and supersedes Node.js 18, which reached end of life on April 30, 2025.",
        "old_detail": "Node.js 18 is the newest LTS release of Node.js.",
        "support_text": "Node.js 18 reached end of life on April 30, 2025; Node.js 22 is the Active LTS line.",
        "support_until": "April 2027",
        "claims": {
            "current": "Node.js 22 is the Active LTS release line of Node.js.",
            "outdated": "Node.js 18 is the newest LTS release of Node.js.",
            "partial": "Node.js 18 is the current LTS release of Node.js and its maintenance window ends in April 2025.",
            "contradicted": "The official Node.js release schedule states that Node.js 22 is not a supported release line.",
            "conflicting": "Node.js 22 is the Active LTS release of Node.js.",
            "insufficient": "The Node.js upgrade at a private bank in Hyderabad was signed off by a committee of seven engineers on 9 April.",
        },
    },
    {
        "id": "postgres", "subject": "PostgreSQL", "old": "16", "new": "17",
        "old_date": "2023-09-14", "new_date": "2024-09-26", "type": "docs",
        "official": "https://www.postgresql.org/about/news/postgresql-17-released-2936/",
        "secondary": "https://www.postgresql.org/support/versioning/",
        "archive": "https://medium.com/@dbnotes/postgres-major-releases",
        "support": "https://www.postgresql.org/support/versioning/",
        "detail": "PostgreSQL 17 was released on September 26, 2024 and supersedes PostgreSQL 16 as the current major release.",
        "old_detail": "PostgreSQL 16 is the newest major release of PostgreSQL.",
        "support_text": "PostgreSQL 16 is supported until November 2028; PostgreSQL 17 is the current major release.",
        "support_until": "November 2028",
        "claims": {
            "current": "PostgreSQL 17 was released on September 26, 2024 as the current major release.",
            "outdated": "PostgreSQL 16 is the newest major release of PostgreSQL.",
            "partial": "PostgreSQL 16 is the current major release of PostgreSQL and is supported until November 2028.",
            "contradicted": "The PostgreSQL release announcement states that PostgreSQL 17 was withdrawn and never released.",
            "conflicting": "PostgreSQL 17 is the current major release of PostgreSQL.",
            "insufficient": "The PostgreSQL 17 rollout plan for a private hospital group in Kochi was approved internally on 14 May.",
        },
    },
    {
        "id": "tailwind", "subject": "Tailwind CSS", "old": "3", "new": "4",
        "old_date": "2022-01-01", "new_date": "2025-01-22", "type": "docs",
        "official": "https://tailwindcss.com/blog/tailwindcss-v4",
        "secondary": "https://github.com/tailwindlabs/tailwindcss/releases",
        "archive": "https://medium.com/@cssnotes/tailwind-versions",
        "support": "https://tailwindcss.com/docs/upgrade-guide",
        "detail": "Tailwind CSS v4.0 was released on January 22, 2025 and supersedes v3 as the current major version.",
        "old_detail": "Tailwind CSS v3 is the current major version of the framework.",
        "support_text": "Tailwind CSS v3 remains maintained for critical fixes while v4 is the current major version.",
        "support_until": "January 2027",
        "claims": {
            "current": "Tailwind CSS v4.0 was released on January 22, 2025 as the current major version.",
            "outdated": "Tailwind CSS v3 is the current major version of the framework.",
            "partial": "Tailwind CSS v3 is the current major version and remains maintained for critical fixes through January 2027.",
            "contradicted": "The Tailwind CSS release notes state that v4.0 is not a supported release of the framework.",
            "conflicting": "Tailwind CSS v4 is the current major version of the framework.",
            "insufficient": "The Tailwind v4 design-system migration at a private retailer in Surat was approved by six designers on 6 June.",
        },
    },
    {
        "id": "vite", "subject": "Vite", "old": "5", "new": "6",
        "old_date": "2023-11-16", "new_date": "2024-11-26", "type": "docs",
        "official": "https://vite.dev/blog/announcing-vite6",
        "secondary": "https://github.com/vitejs/vite/releases",
        "archive": "https://medium.com/@buildnotes/vite-majors",
        "support": "https://vite.dev/guide/migration",
        "detail": "Vite 6 was released on November 26, 2024 and supersedes Vite 5 as the current major version.",
        "old_detail": "Vite 5 is the current major version of the build tool.",
        "support_text": "Vite 5 continues to receive fixes while Vite 6 is the current major version.",
        "support_until": "December 2026",
        "claims": {
            "current": "Vite 6 was released on November 26, 2024 as the current major version.",
            "outdated": "Vite 5 is the current major version of the build tool.",
            "partial": "Vite 5 is the current major version of the build tool and continues to receive fixes through December 2026.",
            "contradicted": "The Vite release announcement states that Vite 6 is not a supported major version.",
            "conflicting": "Vite 6 is the current major version of the build tool.",
            "insufficient": "The Vite 6 rollout at a private gaming studio in Indore was approved by three leads on 1 July.",
        },
    },
    {
        "id": "django", "subject": "Django", "old": "4.2", "new": "5.0",
        "old_date": "2023-04-03", "new_date": "2023-12-04", "type": "docs",
        "official": "https://docs.djangoproject.com/en/5.0/releases/5.0/",
        "secondary": "https://www.djangoproject.com/download/",
        "archive": "https://medium.com/@pythonweb/django-releases",
        "support": "https://www.djangoproject.com/download/",
        "detail": "Django 5.0 was released on December 4, 2023 and supersedes Django 4.2 as the current feature release.",
        "old_detail": "Django 4.2 is the newest release of the Django framework.",
        "support_text": "Django 4.2 is an LTS release supported until April 2026; Django 5.0 is the current feature release.",
        "support_until": "April 2026",
        "claims": {
            "current": "Django 5.0 was released on December 4, 2023 as the current feature release.",
            "outdated": "Django 4.2 is the newest release of the Django framework.",
            "partial": "Django 4.2 is the current feature release of Django and is supported until April 2026.",
            "contradicted": "The Django release notes state that Django 5.0 is not a supported release of the framework.",
            "conflicting": "Django 5.0 is the current feature release of Django.",
            "insufficient": "The Django 5.0 upgrade at a private logistics firm in Nagpur was approved by two engineers on 20 August.",
        },
    },
    {
        "id": "kubernetes", "subject": "Kubernetes", "old": "1.28", "new": "1.30",
        "old_date": "2023-08-15", "new_date": "2024-04-17", "type": "docs",
        "official": "https://kubernetes.io/blog/2024/04/17/kubernetes-1-30-release/",
        "secondary": "https://kubernetes.io/releases/",
        "archive": "https://medium.com/@cloudnotes/kubernetes-releases",
        "support": "https://kubernetes.io/releases/patch-releases/",
        "detail": "Kubernetes 1.30 was released on April 17, 2024 and supersedes 1.28 as a supported release.",
        "old_detail": "Kubernetes 1.28 is the newest stable release of Kubernetes.",
        "support_text": "Kubernetes 1.28 reached end of life while 1.30 is the current stable release.",
        "support_until": "June 2025",
        "claims": {
            "current": "Kubernetes 1.30 was released on April 17, 2024 as a supported stable release.",
            "outdated": "Kubernetes 1.28 is the newest stable release of Kubernetes.",
            "partial": "Kubernetes 1.28 is the current stable release of Kubernetes and receives patch support until June 2025.",
            "contradicted": "The Kubernetes release team states that version 1.30 was withdrawn and is not supported.",
            "conflicting": "Kubernetes 1.30 is the current stable release of Kubernetes.",
            "insufficient": "The Kubernetes 1.30 upgrade at a private telecom operator in Jaipur was approved by five SREs on 3 May.",
        },
    },
    {
        "id": "ubuntu", "subject": "Ubuntu", "old": "22.04", "new": "24.04",
        "old_date": "2022-04-21", "new_date": "2024-04-25", "type": "docs",
        "official": "https://ubuntu.com/blog/ubuntu-24-04-lts-released",
        "secondary": "https://wiki.ubuntu.com/Releases",
        "archive": "https://medium.com/@linuxnotes/ubuntu-lts-cycle",
        "support": "https://ubuntu.com/about/release-cycle",
        "detail": "Ubuntu 24.04 LTS was released on April 25, 2024 and supersedes Ubuntu 22.04 as the current LTS release.",
        "old_detail": "Ubuntu 22.04 LTS is the newest long-term-support release of Ubuntu.",
        "support_text": "Ubuntu 22.04 LTS remains supported until April 2027 while Ubuntu 24.04 LTS is the current LTS release.",
        "support_until": "April 2027",
        "claims": {
            "current": "Ubuntu 24.04 LTS was released on April 25, 2024 as the current LTS release.",
            "outdated": "Ubuntu 22.04 LTS is the newest long-term-support release of Ubuntu.",
            "partial": "Ubuntu 22.04 LTS is the current LTS release of Ubuntu and remains supported until April 2027.",
            "contradicted": "The Ubuntu release team states that 24.04 LTS is not a supported release.",
            "conflicting": "Ubuntu 24.04 LTS is the current LTS release of Ubuntu.",
            "insufficient": "The Ubuntu 24.04 rollout across a private manufacturing plant in Ludhiana was approved on 18 February.",
        },
    },
    {
        "id": "java", "subject": "Java", "old": "17", "new": "21",
        "old_date": "2021-09-14", "new_date": "2023-09-19", "type": "docs",
        "official": "https://openjdk.org/projects/jdk/21/",
        "secondary": "https://www.oracle.com/java/technologies/java-se-support-roadmap.html",
        "archive": "https://medium.com/@javanotes/lts-releases",
        "support": "https://www.oracle.com/java/technologies/java-se-support-roadmap.html",
        "detail": "Java 21 is the current long-term-support release and supersedes Java 17 for new deployments.",
        "old_detail": "Java 17 is the newest long-term-support release of Java.",
        "support_text": "Java 17 remains supported until 2029 while Java 21 is the current LTS release.",
        "support_until": "September 2029",
        "claims": {
            "current": "Java 21 is the current long-term-support release of Java.",
            "outdated": "Java 17 is the newest long-term-support release of Java.",
            "partial": "Java 17 is the current long-term-support release of Java and remains supported until September 2029.",
            "contradicted": "The OpenJDK release notes state that Java 21 is not a supported release of Java.",
            "conflicting": "Java 21 is the current long-term-support release of Java.",
            "insufficient": "The Java 21 migration at a private insurer in Bhopal was approved by four architects on 8 April.",
        },
    },
    {
        "id": "http", "subject": "HTTP/3", "old": "HTTP/2", "new": "HTTP/3",
        "old_date": "2015-05-14", "new_date": "2022-06-06", "type": "gov",
        "official": "https://www.rfc-editor.org/rfc/rfc9114.html",
        "secondary": "https://www.ietf.org/blog/http3/",
        "archive": "https://medium.com/@webnotes/http-versions",
        "support": "https://httpwg.org/specs/",
        "detail": "HTTP/3 is defined in RFC 9114, published in June 2022, and supersedes HTTP/2 as the newest version of the protocol.",
        "old_detail": "HTTP/2 is the newest version of the HTTP protocol.",
        "support_text": "HTTP/2 remains in use while HTTP/3 is the newest version of the protocol.",
        "support_until": "June 2032",
        "claims": {
            "current": "HTTP/3 is specified in RFC 9114, which was published in June 2022.",
            "outdated": "HTTP/2 is the newest version of the HTTP protocol.",
            "partial": "HTTP/2 is the newest version of the HTTP protocol and remains widely deployed alongside newer versions.",
            "contradicted": "The IETF states that RFC 9114 does not define HTTP/3.",
            "conflicting": "HTTP/3 is the newest version of the HTTP protocol.",
            "insufficient": "The HTTP/3 rollout for a private streaming service in Gurugram was approved by two platform leads on 30 May.",
        },
    },
    {
        "id": "tls", "subject": "TLS", "old": "1.2", "new": "1.3",
        "old_date": "2008-08-01", "new_date": "2018-08-01", "type": "gov",
        "official": "https://www.rfc-editor.org/rfc/rfc8446.html",
        "secondary": "https://www.ietf.org/blog/tls13/",
        "archive": "https://medium.com/@secnotes/tls-versions",
        "support": "https://tlswg.org/",
        "detail": "TLS 1.3 is specified in RFC 8446, published in August 2018, and supersedes TLS 1.2 as the newest version of the protocol.",
        "old_detail": "TLS 1.2 is the newest version of the TLS protocol.",
        "support_text": "TLS 1.2 remains deployed while TLS 1.3 is the newest version of the protocol.",
        "support_until": "August 2033",
        "claims": {
            "current": "TLS 1.3 is specified in RFC 8446, which was published in August 2018.",
            "outdated": "TLS 1.2 is the newest version of the TLS protocol.",
            "partial": "TLS 1.2 is the newest version of the TLS protocol and remains widely deployed alongside newer versions.",
            "contradicted": "The IETF states that RFC 8446 does not specify TLS 1.3.",
            "conflicting": "TLS 1.3 is the newest version of the TLS protocol.",
            "insufficient": "The TLS 1.3 rollout for a private payments network in Chennai was approved by three security leads on 2 June.",
        },
    },
    {
        "id": "gpt4", "subject": "GPT-4", "old": "8,192", "new": "32,768",
        "old_date": "2023-03-14", "new_date": "2023-03-14", "type": "blog",
        "official": "https://openai.com/index/gpt-4-research/",
        "secondary": "https://arxiv.org/abs/2303.08774",
        "archive": "https://medium.com/@ainotes/context-windows",
        "support": "https://platform.openai.com/docs/models",
        "detail": "GPT-4 was announced on March 14, 2023 with a context window of 32,768 tokens.",
        "old_detail": "GPT-4 has a context window of 8,192 tokens.",
        "support_text": "GPT-4 supports a context window of 32,768 tokens in the published model documentation.",
        "support_until": "March 2030",
        "claims": {
            "current": "GPT-4 has a context window of 32,768 tokens.",
            "outdated": "GPT-4 has a context window of 8,192 tokens.",
            "partial": "GPT-4 has a context window of 32,768 tokens and uses a mixture-of-experts architecture.",
            "contradicted": "The GPT-4 technical report states that the model does not accept image inputs.",
            "contradicted2": "The GPT-4 technical report states that the model has a context window of 1,024 tokens.",
            "conflicting": "GPT-4 has a context window of 32,768 tokens.",
            "insufficient": "The GPT-4 evaluation at a private brokerage in Mumbai was signed off by nine analysts on 11 March.",
        },
    },
    {
        "id": "everest", "subject": "Mount Everest", "old": "8,848", "new": "8,848.86",
        "old_date": "1954-01-01", "new_date": "2020-12-08", "type": "gov",
        "official": "https://www.esa.int/Applications/Observing_the_Earth/Mount_Everest_remeasured",
        "secondary": "https://www.britannica.com/place/Mount-Everest",
        "archive": "https://medium.com/@geography/mount-everest-height",
        "support": "https://www.nist.gov/pml/special-publication-811",
        "detail": "China and Nepal announced on December 8, 2020 that Mount Everest is 8,848.86 metres tall, superseding the earlier 8,848 metre figure.",
        "old_detail": "Mount Everest is 8,848 metres tall according to the long-standing official survey.",
        "support_text": "The joint survey published in December 2020 records Mount Everest at 8,848.86 metres.",
        "support_until": "December 2030",
        "claims": {
            "current": "Mount Everest is 8,848.86 metres tall according to the December 2020 joint survey.",
            "outdated": "Mount Everest is 8,848 metres tall according to the official survey.",
            "partial": "Mount Everest is 8,848 metres tall according to the official survey and that figure is exact to the metre.",
            "contradicted": "The joint survey states that Mount Everest is not in the Himalayas.",
            "contradicted2": "The joint survey reports that Mount Everest is 8,000 metres tall.",
            "conflicting": "Mount Everest is 8,848.86 metres tall.",
            "insufficient": "The summit survey team for a private expedition in Kathmandu was approved by three sponsors on 4 April.",
        },
    },
    {
        "id": "metre", "subject": "the metre", "old": "the prototype bar", "new": "the speed of light",
        "old_date": "1960-10-14", "new_date": "1983-10-20", "type": "gov",
        "official": "https://www.bipm.org/en/publications/si-brochure",
        "secondary": "https://www.nist.gov/pml/owm/si-units-length",
        "archive": "https://medium.com/@physicsnotes/si-units",
        "support": "https://www.bipm.org/en/measurement-units",
        "detail": "Since 1983 the metre is defined by fixing the speed of light in vacuum at 299 792 458 m/s, superseding the prototype-based definition.",
        "old_detail": "The metre is defined by the international prototype metre bar kept in Paris.",
        "support_text": "The metre has been defined through the speed of light since 1983 and that definition remains in force.",
        "support_until": "Ongoing",
        "claims": {
            "current": "The metre is defined by fixing the speed of light in vacuum at 299 792 458 metres per second.",
            "outdated": "The metre is defined by the international prototype metre bar kept in Paris.",
            "partial": "The metre is defined by the international prototype bar and that definition is still in force today.",
            "contradicted": "The SI brochure states that the metre is not defined using the speed of light.",
            "contradicted2": "The SI brochure states that the metre is defined using the mass of the international prototype kilogram.",
            "conflicting": "The metre is defined by fixing the speed of light at 299 792 458 metres per second.",
            "insufficient": "The prototype bar comparison at a private calibration lab in Faridabad was approved by two metrologists on 22 January.",
        },
    },
    {
        "id": "euaiact", "subject": "the EU AI Act", "old": "a draft proposal", "new": "in force",
        "old_date": "2021-04-21", "new_date": "2024-08-01", "type": "gov",
        "official": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        "secondary": "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
        "archive": "https://medium.com/@policybriefs/eu-ai-act",
        "support": "https://artificialintelligenceact.eu/",
        "detail": "The EU AI Act (Regulation 2024/1689) entered into force on August 1, 2024, superseding the earlier draft proposal.",
        "old_detail": "The EU AI Act is a draft proposal and has not entered into force.",
        "support_text": "Regulation 2024/1689 entered into force on August 1, 2024 and its obligations are being phased in.",
        "support_until": "Ongoing",
        "claims": {
            "current": "The EU AI Act entered into force on August 1, 2024.",
            "outdated": "The EU AI Act is a draft proposal and has not entered into force.",
            "partial": "The EU AI Act entered into force on August 1, 2024 and applies uniformly to all systems from that date.",
            "contradicted": "The European Union states that Regulation 2024/1689 was never adopted.",
            "contradicted2": "The European Commission states that the EU AI Act was repealed in 2023 and is no longer in force.",
            "conflicting": "The EU AI Act entered into force on August 1, 2024.",
            "insufficient": "The AI Act readiness review at a private lender in Delhi was approved by six compliance officers on 19 February.",
        },
    },
    {
        "id": "gdpr", "subject": "the GDPR", "old": "adopted", "new": "applicable",
        "old_date": "2016-04-27", "new_date": "2018-05-25", "type": "gov",
        "official": "https://gdpr-info.eu/",
        "secondary": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "archive": "https://medium.com/@privacybriefs/gdpr-timeline",
        "support": "https://commission.europa.eu/law/law-topic/gdpr_en",
        "detail": "The GDPR (Regulation 2016/679) has applied since May 25, 2018 and superseded the 1995 Data Protection Directive.",
        "old_detail": "The GDPR has been adopted but is not yet applicable.",
        "support_text": "Regulation 2016/679 has applied since May 25, 2018 and remains in force.",
        "support_until": "Ongoing",
        "claims": {
            "current": "The GDPR became applicable on May 25, 2018.",
            "outdated": "The GDPR has been adopted but is not yet applicable.",
            "partial": "The GDPR has applied since May 25, 2018 and applies to every organisation worldwide without exception.",
            "contradicted": "The European Union states that Regulation 2016/679 is not in force.",
            "contradicted2": "The European Commission states that the GDPR was repealed in 2021 and no longer applies.",
            "conflicting": "The GDPR became applicable on May 25, 2018.",
            "insufficient": "The GDPR audit at a private clinic chain in Kochi was approved by two partners on 27 February.",
        },
    },
    {
        "id": "who", "subject": "COVID-19", "old": "a public health emergency of international concern", "new": "no longer a public health emergency of international concern",
        "old_date": "2020-01-30", "new_date": "2023-05-05", "type": "gov",
        "official": "https://www.who.int/news/item/05-05-2023-statement-on-the-fifteenth-meeting-of-the-international-health-regulations-(2005)-emergency-committee-regarding-the-coronavirus-disease-(covid-19)-pandemic",
        "secondary": "https://www.who.int/emergencies/diseases/novel-coronavirus-2019",
        "archive": "https://medium.com/@healthnotes/pheic-timeline",
        "support": "https://www.who.int/director-general/speeches",
        "detail": "On May 5, 2023 the WHO determined that COVID-19 no longer constitutes a public health emergency of international concern, superseding the 2020 declaration.",
        "old_detail": "COVID-19 constitutes a public health emergency of international concern.",
        "support_text": "The WHO determined on May 5, 2023 that COVID-19 no longer constitutes a public health emergency of international concern.",
        "support_until": "Ongoing",
        "claims": {
            "current": "The WHO determined on May 5, 2023 that COVID-19 no longer constitutes a public health emergency of international concern.",
            "outdated": "COVID-19 constitutes a public health emergency of international concern.",
            "partial": "The WHO declared COVID-19 a public health emergency of international concern on January 30, 2020 and that declaration remains in force.",
            "contradicted": "The WHO states that COVID-19 was never declared a public health emergency of international concern.",
            "contradicted2": "The WHO states that COVID-19 was declared a public health emergency of international concern in 2024.",
            "conflicting": "COVID-19 no longer constitutes a public health emergency of international concern.",
            "insufficient": "The pandemic preparedness review at a private hospital chain in Pune was approved by four clinicians on 6 May.",
        },
    },
    {
        "id": "gemini", "subject": "Gemini 1.5 Pro", "old": "32,000", "new": "1,000,000",
        "old_date": "2024-02-15", "new_date": "2024-02-15", "type": "blog",
        "official": "https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/",
        "secondary": "https://deepmind.google/technologies/gemini/",
        "archive": "https://medium.com/@ainotes/gemini-context",
        "support": "https://ai.google.dev/gemini-api/docs/models",
        "detail": "Gemini 1.5 Pro was announced on February 15, 2024 with a 1 million token context window in limited preview.",
        "old_detail": "Gemini 1.5 Pro has a context window of 32,000 tokens.",
        "support_text": "Gemini 1.5 Pro supports a 1 million token context window in the published model documentation.",
        "support_until": "February 2027",
        "claims": {
            "current": "Gemini 1.5 Pro was announced with a 1 million token context window.",
            "outdated": "Gemini 1.5 Pro has a context window of 32,000 tokens.",
            "partial": "Gemini 1.5 Pro has a 1 million token context window and uses a dense transformer architecture.",
            "contradicted": "Google states that Gemini 1.5 Pro does not accept text inputs.",
            "contradicted2": "Google states that Gemini 1.5 Pro is limited to a 4,096 token context window.",
            "conflicting": "Gemini 1.5 Pro has a context window of 1 million tokens.",
            "insufficient": "The Gemini 1.5 Pro pilot at a private logistics firm in Nashik was approved by five engineers on 1 March.",
        },
    },
]


# --------------------------------------------------------------------------- #
# evidence construction
# --------------------------------------------------------------------------- #
def _official_new(f: dict) -> dict:
    return doc(
        f["official"], f"{f['subject']} — current release documentation", f["detail"],
        f["new_date"], f["type"], version=f["new"],
    )


def _secondary_new(f: dict) -> dict:
    return doc(
        f["secondary"], f"{f['subject']} release history",
        f"Release history records the current state: {f['detail']}",
        f["new_date"], f["type"], version=f["new"],
    )


def _archived_old(f: dict) -> dict:
    return doc(
        f["archive"], f"{f['subject']} {f['old']} explainer",
        f"{f['old_detail']} This explainer was written when {f['subject']} {f['old']} was current.",
        f["old_date"], "blog", version=f["old"],
    )


def _support_window(f: dict) -> dict:
    """Source that still describes the older state as current (drives drift + support)."""
    return doc(
        f["support"].rstrip("/") + "/support-window",
        f"{f['subject']} support policy",
        f"{f['subject']} {f['old']} is the current release and its support window ends in {f['support_until']}.",
        f["new_date"],
        "docs",
        version=f["old"],
    )


def _contradiction_docs(f: dict) -> list[dict]:
    domain = f["id"]
    return [
        doc(
            f"https://{domain}-deprecation-watch.example.org/status",
            f"{f['subject']} deprecation watch",
            f"{f['subject']} {f['new']} has been deprecated by its maintainers and is no longer a supported release.",
            f["new_date"], "docs",
        ),
        doc(
            f"https://{domain}-maintainers.example.net/notices",
            f"{f['subject']} maintainer notices",
            f"Maintainers confirm that {f['subject']} {f['new']} is not supported on any platform.",
            f["new_date"], "docs",
        ),
    ]


def _irrelevant_doc(f: dict) -> dict:
    return doc(
        "https://example.org/general-guidance",
        "General governance guidance",
        "Generic planning guidance that describes approval processes in the abstract with no reference to any specific team or deployment.",
        f["old_date"], "blog",
    )


# Families whose partial case is a genuinely mixed claim: the older release is
# still asserted as current (drift) while its support window is stated correctly.
VERSION_PARTIAL_FAMILY_IDS = {
    "python", "react", "node", "postgres", "tailwind", "vite",
    "django", "kubernetes", "ubuntu", "java", "http", "tls",
}


def _variants_for(f: dict) -> list[tuple[str, str, str, str, list[dict]]]:
    variants = [
        (
            "current", "current_information", "VERIFIED",
            "Claim states the current, officially documented state: two authoritative sources agree.",
            [_official_new(f), _secondary_new(f)],
        ),
        (
            "outdated", "outdated_information", "OUTDATED",
            "Claim asserts a superseded state as current; newer authoritative documentation exists.",
            [_official_new(f), _secondary_new(f), _archived_old(f)],
        ),
        (
            "contradicted", "contradictory_information", "CONTRADICTED",
            "Claim is directly false: authoritative documentation asserts the opposite.",
            [_official_new(f), _secondary_new(f)],
        ),
        (
            "conflicting", "contradictory_information", "CONFLICTING",
            "Two credible sources support and two credible sources deny the same fact at the same date; recency cannot resolve it.",
            [_official_new(f), _secondary_new(f)] + _contradiction_docs(f),
        ),
        (
            "insufficient", "insufficient_evidence", "UNVERIFIED",
            "Private operational detail that no public source can address.",
            [_irrelevant_doc(f)],
        ),
    ]
    if f["id"] in VERSION_PARTIAL_FAMILY_IDS:
        variants.append(
            (
                "partial", "partially_outdated", "PARTIALLY_OUTDATED",
                "The support statement and one current-state detail survive, while the release status has been superseded.",
                [_support_window(f), _official_new(f), _secondary_new(f)],
            )
        )
    if "contradicted2" in f["claims"]:
        variants.append(
            (
                "contradicted2", "contradictory_information", "CONTRADICTED",
                "A second, differently-shaped false claim: the asserted value is incompatible with the authoritative record.",
                [_official_new(f), _secondary_new(f)],
            )
        )
    return variants


def build() -> list[dict]:
    rows: list[dict] = []
    for f in FAMILIES:
        for key, category, gold, notes, evidence in _variants_for(f):
            rows.append(
                {
                    "id": f"{f['id']}_{key}",
                    "family": f["id"],
                    "category": category,
                    "gold_verdict": gold,
                    "claim": f["claims"][key],
                    "notes": notes,
                    "evidence": evidence,
                }
            )
    return rows


def main() -> None:
    rows = build()
    OUT.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["gold_verdict"]] = counts.get(row["gold_verdict"], 0) + 1
    print(f"wrote {len(rows)} labelled claims → {OUT}")
    for verdict, count in sorted(counts.items()):
        print(f"  {verdict:20s} {count}")


if __name__ == "__main__":
    main()
