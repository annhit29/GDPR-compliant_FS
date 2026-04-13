law "GDPR"

note "This is a draft formalization of GDPR Articles 5-10, 12-22, 30, 45(1), 46(1), 49"
note "Author: François Hublet"
note "Date: 3 Oct 2025"
note "Status: Untested"

import formex GDPR

type activity
type data
type data_subject
type purpose is string
type entity
type interest
type contract
type legal_basis is string
type legal_obligation is string
type public_interest is string
type vital_interests is string
type declaration
type special_data_category is string
type request
type country_or_international_organisation
type criteria
type requirement is string
type file
type country_io
type safeguards
type register

article "5" "Principles relating to processing of personal data"

# predicate := a logical fact, not necc. an event
# event := something that the system does.
observable predicate PersonalData
    """Data {d} is personal data of data subject {ds}"""
    d : data
    ds : data_subject

suppressable event DataProcessing
    """Data {d} is processed by processor {p} on behalf of controller {c} as part of data processing activity {a}"""
    p : entity
    c : entity
    a : activity
    d : data

internal predicate IsLawful 
    """Data processing activity {a} is lawful with legal basis {b}"""
    a : activity
    b : legal_basis

observable predicate IsFair
    """Data processing activity {a} is fair"""
    a : activity

observable predicate IsTransparent
    """Data processing activity {a} is transparent in relation to data subject {ds}"""
    a : activity
    ds : data_subject

observable event IsCollection
    """Data processing activity {a} collects personal data from data subject {ds}"""
    a : activity 
    ds : data_subject

suppressable predicate HasPurpose
    """Data processing activity {a} has purpose {p}"""
    a : activity
    p : purpose

internal predicate CompatibleWithPurpose
    """Data processing activity {a} is compatible with purpose {p}, taking into account ... (see Art. 6(4))"""
    a : activity
    p : purpose

observable predicate IsCompatibleWithPurpose
    """Data processing activity {a} is compatible with purpose {p}"""
    a : activity
    p : purpose

observable predicate IsSpecified
    """Purpose {p} is specified"""
    p : purpose

observable predicate IsExplicit
    """Purpose {p} is explicit"""
    p : purpose

observable predicate IsLegitimate
    """Purpose {p} is legitimate"""
    p : purpose

observable predicate IsArchival
    """Activity {a} is one of the activities described in Article 89(1)"""
    a : activity

# adequate := Data d processed or collected is enough in quantity and quality to fulfil purpose p, but not more than that.
# Eg: if the purpose is to send a newsletter, collecting email is adequate; collecting full CVs, health data, or ID numbers is not, because those go far beyond what is needed.
observable predicate IsAdequate
    """Data {d} is adequate in relation to purpose {p}"""
    d : data
    p : purpose

# := Only data d that is relevant to purpose p should be processed. 
# Eg: if the purpose is to send a newsletter, collecting email is relevant; collecting full CVs, health data, or ID numbers is not, because those are irrelevant to the purpose.
observable predicate IsRelevant
    """Data {d} is relevant in relation to purpose {p}"""
    d : data
    p : purpose

# := The system must not process or collect more personal data than is strictly needed to achieve purpose p.
observable predicate IsLimitedToWhatIsNecessary
    """Data {d} is limited to what is necessary in relation to purpose {p}"""
    d : data
    p : purpose

observable predicate IsAccurate
    """Data {d} is accurate in relation to purpose {p}"""
    d : data
    p : purpose

observable predicate IsUpToDate
    """Data {d} is up to date in relation to purpose {p}, where necessary"""
    d : data
    p : purpose

observable predicate UndueDataDelay
    """Data {d} is not deleted or rectified with undue delay"""
    d : data

causable observable event Delete
    """Data {d} is deleted"""
    d : data

causable observable event Rectify
    """Data {d_old} is rectified into {d_new}"""
    d_old : data
    d_new : data

observable predicate EnsuresAppropriateSecurity
    """Activity {a} ensures appropriate security of data {d}, including ... (see Art. 5(1)(f))"""
    a : activity
    d : data

suppressable event Stored
    """Data {d} is stored"""
    d : data

observable predicate IsNecessary
    """Data {d} is necessary to fulfill purpose {p}"""
    d : data
    p : purpose

observable predicate TechnicalAndOrganisationalMeasures
    """Appropriate technical and organisational measures have been taken to justify an exception to storage limiation requirements for activity {a} as by Article 89(1)"""
    a : activity

observable predicate JustifiesStorage
    """Activity {a} justifies the storage of data {d}"""
    a : activity
    d : data

paragraph "1"

point "a"

rule 
    whenever
        DataProcessing(p, c, a, d)
        PersonalData(d, ds)
    oblige
        EXISTS b. IsLawful(a, b)
        IsFair(a)
        IsTransparent(a, ds)
    transparently enforceable suppressing condition[0]
#everytime there's DataProcessing event AND PersonalData event,
# the three principles of lawfulness, fairness and transparency must be satisfied.

point "b"

rule "must_have_purpose"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
    oblige 
        EXISTS p. HasPurpose(a, p)
    transparently enforceable suppressing condition[0] #means: if an obligation isn't satisfied, then suppress the DataProcessing event which is the 0th condition

rule "purpose_conditions"
    whenever
        HasPurpose(a, p)
    oblige
        IsSpecified(p)
        IsExplicit(p)
        IsLegitimate(p)
    transparently enforceable suppressing condition[0] #means: if an obligation isn't satisfied, then suppress the HasPurpose event which is the 0th condition

rule "purpose_limitation"
    whenever
        DataProcessing(pr, co, a, d)
        PersonalData(d, ds)
    oblige
        EXISTS c, p. CompatibleWithPurpose(a, p) AND ONCE (DataProcessing(pr, co, c, d) AND IsCollection(c, ds) AND HasPurpose(c, p))
    transparently enforceable suppressing condition[0]

rule "general_purpose"
    whenever
        IsCompatibleWithPurpose(a, p)
    constitute
        CompatibleWithPurpose(a, p)
  
rule "archiving_purpose"
    whenever
        IsArchival(a) #archive = “archiving purposes in the public interest”
        # IsArchival(a) := “activity a is one of the archival‑type activities (e.g., long‑term preservation for public‑interest, historical or scientific research) described in Article 89(1).”
    constitute
        CompatibleWithPurpose(a, "Archiving")

point "c"

rule
    whenever
        DataProcessing(pr, co, a, d)
        PersonalData(d, ds)
        HasPurpose(a, p)
    oblige 
        IsAdequate(d, p)
        IsRelevant(d, p)
        IsLimitedToWhatIsNecessary(d, p)
    transparently enforceable suppressing condition[0]

point "d"

rule "accurate_and_up_to_date"
    whenever
        DataProcessing(pr, co, a, d)
        HasPurpose(a, p)
    oblige
        IsAccurate(d, p)
        IsUpToDate(d, p)
    transparently enforceable suppressing condition[0]

rule "accuracy_deletion"
    whenever
        NOT IsAccurate(d, p)
        EXISTS c, ds'. ONCE (DataProcessing(pr, co, c, d) AND IsCollection(c, ds') AND HasPurpose(c, p))
    oblige
        (NOT UndueDataDelay(d)) UNTIL (Delete(d) OR EXISTS d'. Rectify(d, d'))
    transparently enforceable causing effects

point "e"

rule "temporal_storage_limitation"
    whenever
        Stored(d)
        PersonalData(d, ds)
        EXISTS c, ds'. ONCE (DataProcessing(pr, co, c, d) AND IsCollection(c, ds') AND HasPurpose(c, p))
    oblige
        IsNecessary(d, p)
    transparently enforceable suppressing condition[0]

# If data is stored,
# and it was collected for a purpose,
# then the data must still be necessary to fulfill that purpose p.
#i.e.
# If you collected personal data for a purpose,
# you must delete (or anonymise) it once that purpose is finished.

rule "storage_limitation_exception"
    whenever
        IsArchival(a) AND TechnicalAndOrganisationalMeasures(a) AND JustifiesStorage(a, d)
    except
        rule "temporal_storage_limitation"

point "f"

rule
    whenever
        DataProcessing(p, c, a, d)
    oblige
        EnsuresAppropriateSecurity(a, d)
    transparently enforceable suppressing condition[0]

article "6" "Lawfulness of processing"

suppressable event GiveConsent
    """Data subject {ds} gives consent to processor {c} to use their data for purpose {p}.
       Per Art. 4(11), consent means 'any freely given, specific, informed and unambiguous indication of the data subject's wishes by which they, 
       by a statement or by a clear affirmative action, signifies agreement to the processing of personal data relating to them.'
       Per Art. 7(4), 'when assessing whether consent is freely given, utmost account shall be taken of whether, inter alia, the performance of a contract,
       including the provision of a service, is conditional on consent to the processing of personal data that is not necessary for the performance of that contract.'"""
    ds : data_subject
    p : purpose
    c : entity

observable predicate IsNecessaryForLegitimateInterest
    """Data processing activity {a} is necessary to protect the interest {i} of party {e}"""
    a : activity
    e : entity
    i : interest

observable predicate IsOverriddenByDataSubjectInterests
    """Interest {i} of entity {e} is overriden by the interests of data subject {ds}, in particular when {ds} is a child"""
    e : entity
    i : interest
    ds : data_subject

observable predicate IsPublicAuthority
    """Entity {e} is a public authority"""
    e : entity

observable predicate IsPerformanceOfPublicAuthorityTask
    """Data processing activity {a} is part of the performance of a public authority task"""
    a : activity
# a public authority := a public‑sector body (e.g., police, tax authorities, social‑security agencies, courts)

observable event StartContract
    """The period of effect of contract {co} starts"""
    co : contract

observable predicate PrepareContract
    """The contract {co} is being prepared"""
    co : contract

observable event EndContract
    """The period of effect of contract {co} ends"""
    co : contract

observable predicate IsNecessaryForContract
    """Data processing activity {a} is necessary for the performance of contract {co}"""
    a : activity
    co : contract

observable predicate IsContractParty
    """Data subject {ds} is a party to contract {co}"""
    ds : data_subject
    co : contract

observable predicate IsNecessaryForLegalObligation
    """Data processing activity {a} is necessary for the performance of legal obligation {l}"""
    a : activity
    l : legal_obligation

observable predicate IsNecessaryForVitalInterests
    """Data processing activity {a} is necessary to protect the vital interests {v} of person {ds'}"""
    a : activity
    ds' : data_subject
    v : vital_interests

observable predicate IsNecessaryForPublicInterest
    """Data processing activity {a} is necessary for the performance of a task carried out in the public interest
       or in the exercise of official authority, with {pi} being the specific public interest"""
    a : activity
    pi : public_interest
# Public interest := a task that serves the wider community or society, such as public safety, public health, taxation, social security, or administration of justice.

paragraph "1"

paragraph[1] "1"

point "a"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        ONCE GiveConsent(ds, p, c)
    constitute
        IsLawful(a, "6(1)(a)")

point "b"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        (NOT EndContract(co)) SINCE ((PrepareContract(co) OR StartContract(co)) AND IsContractParty(ds, co))
        IsNecessaryForContract(a, co)
    constitute
        IsLawful(a, "6(1)(b)")

point "c"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsNecessaryForLegalObligation(a, l)
    constitute
        IsLawful(a, "6(1)(c)")

point "d"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsNecessaryForVitalInterests(a, ds', v)
    constitute
        IsLawful(a, "6(1)(d)")

point "e"

rule 
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsNecessaryForPublicInterest(a, pi) OR IsPerformanceOfPublicAuthorityTask(a) AND IsPublicAuthority(c)
    constitute
        IsLawful(a, "6(1)(e)")

point "f"

rule "legitimate_interest"
    whenever
        DataProcessing(pr, c, a, d)
        IsNecessaryForLegitimateInterest(a, e, i)
    constitute
        IsLawful(a, "6(1)(f)")

rule
    whenever
        PersonalData(d, ds)
        IsOverriddenByDataSubjectInterests(e, i, ds)
    except
        rule "legitimate_interest"

paragraph[1] "2"

rule
    whenever
        IsPublicAuthority(c)
        IsPerformanceOfPublicAuthorityTask(a)
    except
        paragraph[1] "1" point "f"

note "Skipped: OPENING CLAUSE in (2)-(3)."
note "Paragraph (4) provides condition to assess the compatibility of purposes. This is integrated in the docstring of CompatibleWithPurpose."

#art7

# a declaration := a formal statement included in the controller’s response to a request.
# a subdeclaration := a statement inside a larger declaration.
causable observable predicate Contains
    """Written declaration {de} contains subdeclaration {de2}"""
    de : declaration
    de2 : declaration

causable observable predicate IsIntelligible
    """Declaration {de} is intelligible"""
    de : declaration

causable observable predicate IsEasilyAccessible
    """Declaration {de} is easily accessible"""
    de : declaration

causable observable predicate IsClearAndPlainLanguage
    """Declaration {de} is written in clear and plain language"""
    de : declaration

causable observable predicate Inform
    """Controller {c} informs data subject {ds} about declaration {de}"""
    c : entity
    ds : data_subject
    de : declaration

observable predicate WithdrawConsent
    """Data subject {ds} withdraws their consent previously given to controller {c} for purpose {p}. 
       Per Art. 7(3)(1), can be performed at any time. 
       Per Art. 7(3)(4), shall be as easy to withdraw as to give consent."""
    ds : data_subject
    p : purpose
    c : entity

article "7" 
paragraph "3"
point "2"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        (NOT WithdrawConsent(ds, p, c)) SINCE GiveConsent(ds, p, c)
    scope
        article "6" paragraph "1" paragraph[1] "1" point "a"

article "9" "Processing of special categories of personal data"

observable predicate IsSpecialData
    """The data {d} reveals information of special data category {sp}.
       Special data categories include personal data revealing racial or ethnic origin, political opinions, religious or philosophical beliefs,
       trade union membership, the processing of genetic data, biometric data for the purpose of uniquely identifying a natural person,
       data concerning health or data concerning a natural person's sex life or sexual orientation"""
    d : data
    sp : special_data_category

suppressable event GiveSpecialConsent
    """Data subject {ds} gives explicit consent to processor {c} to use data of special category {sp} for purpose {p}.
       Per Art. 4(11), consent means 'any freely given, specific, informed and unambiguous indication of the data subject's wishes by which they, 
       by a statement or by a clear affirmative action, signifies agreement to the processing of personal data relating to them.'
       Per Art. 9(2)(a), 'the data subject has given explicit consent to the processing of those personal data for one or more specified purposes,
       except where Union or Member State law provide that the prohibition referred to in paragraph 1 may not be lifted by the data subject.'"""
    ds : data_subject
    p : purpose
    c : entity
    sp : special_data_category

observable predicate IsNecessaryForEmploymentLaw
    """Processing activity {a} is necessary for the purposes of carrying out the obligations and exercising specific rights of the
       controller or of the data subject in the field of employment and social security and social protection law in so far as
       it is authorised by Union or Member State law or a collective agreement pursuant to Member State law providing for
       appropriate safeguards for the fundamental rights and the interests of the data subject."""
    a : activity

# safeguards := technical & organisational protections that prevent abuse.
observable event ImplementFundamentalRightsSafeguards
    """Processing activity {a} provides for appropriate safeguards to protect the fundamental rights and interests of data subject {ds}."""
    a : activity
    ds : data_subject

observable predicate IsUnableToConsent
    """Data subject {ds} is physically or legally unable to give consent"""
    ds : data_subject

observable predicate IsLegitimateActivity
    """Processing activity {a} is legitimate in relation to controller {c}"""
    a : activity
    c : entity

observable predicate IsNonProfit
    """Controller {c} is a non-profit entity such as a foundation, association or any other not-for-profit body"""
    c : entity  

observable predicate HasPoliticalAim
    """Controller {c} has a political aim"""
    c : entity

observable predicate HasPhilosophicalAim
    """Controller {c} has a philosophical aim"""
    c : entity

observable predicate HasReligiousAim
    """Controller {c} has a religious aim"""
    c : entity

observable predicate HasTradeUnionAim
    """Controller {c} has a trade union aim"""
    c : entity

observable predicate IsMember
    """Data subject {ds} is a member of controller {c}"""
    ds : data_subject
    c : entity

# "In connection with its purposes" := the contact must relate to the political, philosophical, religious, or trade union aims of the non-profit, not general business dealings.
observable predicate HasRegularContact
    """Data subject {ds} has regular contact with controller {c} in connection with the purposes of controller {c}'s legitimate activities"""  
    ds : data_subject
    c : entity

# IsOutsideDisclosure(a, c, d) := processing activity a shares or transmits data d to entities or people outside the controller c's organisation without the data subject's consent.
observable predicate IsOutsideDisclosure
    """Processing activity {a} involves disclosure of data {d} to outsiders of controller {c}"""
    a : activity
    c : entity
    d : data

observable predicate MakePublic #:= like github opensource, but with ds' personal data instead of code.
    """Data subject {ds} makes data {d} public"""
    ds : data_subject
    d : data

# IsNecessaryForJudicialClaims := processing activity a is **strictly** required for legal proceedings, court cases, or judicial functions — either preparing for, conducting, or defending against legal claims.
observable predicate IsNecessaryForJudicialClaims
    """Processing activity {a} is necessary for the establishment, exercise or defence of legal claims
       or whenever courts are acting in their judicial capacity"""
    a : activity

# IsNecessaryForSubstantialPublicInterest(a) := processing activity a is explicitly authorised by EU or Member State law for a major public benefit (like elections, public health crises, equality monitoring, or national security)
observable predicate IsNecessaryForSubstantialPublicInterest
    """Processing activity {a} is necessary for reasons of substantial public interest, on the basis of Union or Member State law which shall 
       be proportionate to the aim pursued, respect the essence of the right to data protection and provide for
       suitable and specific measures to safeguard the fundamental rights and the interests of the data subject"""
    a : activity

# IsNecessaryForSpecialMedicalReasons(a) := processing activity a is essential for legitimate medical, occupational health, or social care purposes, and is either directly authorised by EU/Member State law or conducted under contract with a qualified health professional who is bound by professional secrecy.
observable predicate IsNecessaryForSpecialMedicalReasons
    """Processing activity {a} is necessary for the purposes of preventive or occupational medicine, 
       for the assessment of the working capacity of the employee, medical diagnosis, the provision
       of health or social care or treatment or the management of health or social care systems and 
       services on the basis of Union or Member State law or pursuant to contract with a health professional"""
    a : activity

observable predicate IsHealthRelated
    """Public interest {pi} is related to the area of public health, such as protecting against 
       serious cross-border threats to health or ensuring high standards of quality and safety of 
       health care and of medicinal products or medical devicess, on the basis of Union or Member 
       State law which provides for suitable and specific measures to safeguard the rights and
       freedoms of the data subject, in particular professional secrecy"""
    pi : public_interest

# IsNecessaryForArchivalPurposes(a) := processing activity a is required for legitimate archiving/research/statistics
observable predicate IsNecessaryForArchivalPurposes
    """Processing activity {a} is necessary for archiving purposes in the public interest, 
       scientific or historical research purposes or statistical purposes in accordance with 
       Article 89(1) based on Union or Member State law which shall be proportionate to the aim
       pursued, respect the essence of the right to data protection and provide for suitable and 
       specific measures to safeguard the fundamental rights and the interests of the data subject"""
    a : activity

observable predicate IsSubjectToProfessionalSecrecy
    """Entity {e} is subject to the obligation of professional secrecy under Union or Member
       State law or rules established by national competent bodies"""
    e : entity

paragraph "1"

rule
    whenever
        IsSpecialData(d, sp)
        PersonalData(d, ds)
    oblige
        NOT DataProcessing(pr, c, a, d)
    transparently enforceable causing effects

paragraph "2"

point "a"

rule "special_data_consent_exception"
    whenever
        IsSpecialData(d, sp)
        PersonalData(d, ds)
        DataProcessing(pr, c, a, d)
        ONCE GiveSpecialConsent(ds, p, c, sp)
    except
        paragraph "1"

rule "special_data_consent_valid"
    whenever
        IsSpecialData(d, sp)
        PersonalData(d, ds)
        DataProcessing(pr, c, a, d)
        ONCE GiveSpecialConsent(ds, p, c, sp)
    constitute
        IsLawful(a, "9(2)(a)")

note "Skipped: except where Union or Member State law provide that the prohibition referred to in paragraph 1 may not be lifted by the data subject (OPENING CLAUSE)"

point "b"

rule
    whenever
        IsNecessaryForEmploymentLaw(a)
    except
        paragraph "1"
    
point "c"

rule
    whenever
        IsNecessaryForVitalInterests(a, ds', v)
        IsUnableToConsent(ds)
    except
        paragraph "1"

point "d"

rule
    whenever
        ImplementFundamentalRightsSafeguards(a, ds)
        IsLegitimateActivity(a, c)
        IsNonProfit(c)
        HasPoliticalAim(c) OR HasPhilosophicalAim(c) OR HasReligiousAim(c) OR HasTradeUnionAim(c)
        (ONCE IsMember(ds, c)) OR HasRegularContact(ds, c)
        NOT IsOutsideDisclosure(a, c, d)
    except
        paragraph "1"

point "e"

rule
    whenever
        ONCE MakePublic(ds, d)
    except
        paragraph "1"

point "f"

rule
    whenever
        IsNecessaryForJudicialClaims(a)
    except
        paragraph "1"

point "g"

rule "substantial_public_interest_exception"
    whenever
        IsNecessaryForSubstantialPublicInterest(a)
    except
        paragraph "1"

rule "substantial_public_interest_valid"
    whenever
        IsNecessaryForSubstantialPublicInterest(a)
    constitute
        IsLawful(a, "9(2)(g)")

point "h"

rule
    whenever
        IsNecessaryForSpecialMedicalReasons(a)
    except
        paragraph "1"

point "i"

rule
    whenever
        IsNecessaryForPublicInterest(a, pi)
        IsHealthRelated(pi)
    except
        paragraph "1"

point "j"

rule
    whenever
        IsNecessaryForArchivalPurposes(a)
    except
        paragraph "1"

paragraph "3"

rule
    whenever
        IsSubjectToProfessionalSecrecy(c)
        IsSubjectToProfessionalSecrecy(pr)
    scope
        paragraph "2" point "h"

note "Skipped: OPENING CLAUSE in (4)."

#art10
observable predicate RelatesToCriminalConvictionsOrOffences
    """Data {d} relates to criminal convictions and offences or related security measures"""
    d : data

article "12" "Transparent information, communication and modalities for the exercise of the rights of the data subject"

observable predicate IsConcise
    """Declaration {de} is concise"""
    de : declaration

observable predicate IsTransparentDeclaration
    """Declaration {de} is transparent"""
    de : declaration

observable event Request
    """Data subject {ds} performs request {rq} to controller {c}"""
    ds : data_subject
    rq : request
    c : entity

causable observable event RequestResponse #genere une reponse automatiquement 
    """Controller {c} responds to data subject {ds}'s request {rq} with response {rs}"""
    ds : data_subject
    rq : request
    rs : declaration

observable predicate UndueDelay
    """Request {rq} is subject to undue delay"""
    rq : request

suppressable event RequestExtension
    """Controller {c} requests an extension for responding to request {rq}"""
    c : entity
    rq : request

observable predicate IsReasonForRequestExtension
    """Declaration {re} contains the reason for the request extension for request {rq}"""
    re : declaration
    rq : request

observable predicate IsElectronicRequest
    """Request {rq} is made by electronic means"""
    rq : request

observable predicate RequestsNonElectronic
    """Request {rq} requests a non-electronic response"""
    rq : request

observable predicate IsImpossibleElectronic
    """It is impossible to provide response to request {rq} by electronic means"""
    rq : request

observable predicate IsElectronicDeclaration
    """Declaration {de} is provided by electronic means"""
    de : declaration

suppressable event RefuseRequest
    """Controller {c} refuses to respond to request {rq}, e.g., because it is manifestly unfounded 
       or excessive (Article 12(5)(b))"""
    c : entity
    rq : request

causable observable predicate IsReasonForRequestRefusal
    """Declaration {re} contains the reason for the refusal of request {rq}"""
    re : declaration
    rq : request

causable observable predicate IsComplaintStatement
    """Declaration {re} contains a statement informing the data subject of their right to lodge 
       a complaint with a supervisory authority regarding request {rq}"""
    re : declaration
    rq : request

suppressable event ChargeForRequest
    """A fee {fee} is charged for responding to request {rq}"""
    rq : request
    fee : money EUR

observable predicate IsUnfoundedOrExcessive
    """Request {rq} is unfounded or excessive, in particular because of its repetitive character"""
    rq : request

observable predicate IsReasonableFee
    """Fee {fee} is reasonable"""
    fee : money EUR

paragraph "1"

rule
    whenever
        Inform(c, ds, de)
    oblige
        IsConcise(de)
        IsTransparentDeclaration(de)
        IsIntelligible(de)
        IsEasilyAccessible(de)
        IsClearAndPlainLanguage(de)

note "Skipped: When requested by the data subject, the information may be provided orally, provided that... (MODEL)"

paragraph "2"

note "Skipped: facilitate the exercise of the rights, integrated in the MODEL's design"

paragraph "3"

observable predicate IsExtensionNecessary
    """Request extension for request {rq} is necessary due to the complexity of the request or 
       the number of requests"""
    rq : request

rule "request_response_standard"
    whenever
        Request(ds, rq, c)
    oblige
        (NOT UndueDelay(rq)) UNTIL[0, 1M] (RequestExtension(c, rq) OR (EXISTS rs. RequestResponse(ds, rq, rs)))
    transparently enforceable causing effects

rule "request_response_extension_condition"
    whenever
        RequestExtension(c, rq)
    oblige
        IsExtensionNecessary(rq)
    transparently enforceable suppressing conditions

rule "request_response_extended"
    whenever
        ONCE Request(ds, rq, c)
        RequestExtension(c, rq)
    oblige
        (NOT UndueDelay(rq)) UNTIL[0, 2M] (EXISTS rs. RequestResponse(ds, rq, rs))
    transparently enforceable causing effects

rule "request_response_extension_inform"
    whenever
        RequestExtension(c, rq)
    oblige
        ONCE[1M, *] (EXISTS de, ds. Request(ds, rq, c) UNTIL[0, 1M] (Inform(c, ds, de) AND (EXISTS re. Contains(de, re) AND IsReasonForRequestExtension(re, rq))))
    enforceable suppressing conditions

rule "request_response_electronic"
    whenever
        ONCE (Request(ds, rq, c) AND IsElectronicRequest(rq) AND NOT RequestsNonElectronic(rq))
        RequestResponse(ds, rq, rs)
        NOT IsImpossibleElectronic(rq)
    oblige
        IsElectronicDeclaration(rs)

paragraph "4"

note "The first rule is implicit in the formulation of (4)"

rule "refuse_request"
    whenever
        ONCE Request(ds, rq, c)
        RefuseRequest(c, rq)
    except
        paragraph "3" rule "request_response_standard"
        paragraph "3" rule "request_response_extended"

rule "refusal_information"
    whenever
        RefuseRequest(c, rq)
    oblige
        ONCE[1M, *] (EXISTS de, ds. Request(ds, rq, c) UNTIL[0, 1M] (Inform(c, ds, de) AND (EXISTS re. Contains(de, re) AND IsReasonForRequestRefusal(re, rq)) AND (EXISTS re. Contains(de, re) AND IsComplaintStatement(re, rq))))
    enforceable suppressing conditions

paragraph "5"

rule "free_of_charge"
    whenever
        Request(ds, rq, c)
    oblige
        ALWAYS (NOT ChargeForRequest(rq, fee))
    transparently enforceable causing effects

rule "unfounded_exception"
    whenever
        IsUnfoundedOrExcessive(rq)
    except
        rule "free_of_charge"

rule "charge_reasonable_fee"
    whenever
        ChargeForRequest(rq, fee)
    oblige
        IsReasonableFee(fee)
    transparently enforceable suppressing conditions

note "Skipped: (b) and second subparagraph integrated in the docstring of RefuseRequest."
note "Skipped: (6) as the MODEL assumes that ds is identified."
note "Skipped: The information to be provided to data subjects... may [use] standardised icons (PERMISSION)"
note "Skipped: OPENING CLAUSE in (8)."

#art13
# "categories" := types or classes of personal data being processed
#the categories: `id`; `name`; `email`; purhaps `health data`
observable predicate HasCategory
    """Data {d} belongs to category {cat}"""
    d : data
    cat : special_data_category

causable observable predicate IsCategory
    """Declaration {de} declares that the data belongs to category {cat}"""
    de : declaration
    cat : special_data_category

observable predicate IsControllerRepresentative
    """Entity {c'} is the controller representative of controller {c}"""
    c : entity
    c' : entity

#art13.b
observable predicate IsDataProtectionOfficer
    """Entity {c'} is the data protection officer of controller {c}"""
    c : entity
    c' : entity

#art13.e
observable predicate HasIntendedRecipient
    """The {d} is collected with the intent to share it with recipient {e}"""
    d : data
    e : entity

causable observable predicate IsRecipient
    """Declaration {de} declares intended recipient {e}"""
    de : declaration
    e : entity

observable predicate HasIntendedRecipientCategory
    """The {d} is collected with the intent to share it with recipient category {e}"""
    d : data
    e : entity

causable observable predicate IsRecipientCategory
    """Declaration {de} declares intended recipient category {e}"""
    de : declaration
    e : entity

causable observable predicate IsPurposeOfProcessing
    """Declaration {de} declares the purpose of processing {p}"""
    de : declaration
    p : purpose

# para2.a
observable predicate HasStoragePeriod
    """Data {d} has a specified storage period {t}"""
    d : data
    t : span

observable predicate HasStorageCriteria
    """Data {d} has specified storage criteria {c}"""
    d : data
    c : criteria

causable observable predicate IsStoragePeriod
    """Declaration {de} declares the storage period {t}"""
    de : declaration
    t : span

causable observable predicate IsStorageCriteria
    """Declaration {de} declares the storage criteria {c}"""
    de : declaration
    c : criteria

#para2.b
causable observable predicate IsRights
    """Declaration {de} declares the existence of the right to request from the controller access 
       to and rectification or erasure of personal data or restriction of processing concerning 
       the data subject or to object to processing as well as the right to data portability.
       The right to object (Article 21(1-2)) referred shall be explicitly brought to the attention 
       of the data subject and shall be presented clearly and separately from any other information."""
    de : declaration

#art13.f
# Profiling := any automated processing of personal data to evaluate or predict personal aspects of an individual.
observable predicate HasIntendedAutomatedDecision
    """The {d} is collected with the intent to use it for automated decision-making, including profiling,
       which produces legal effects concerning the data subject or similarly significantly affects the data subject with
       meaningful information about the logic involved, as well as the significance and the envisaged consequences
       of such processing for the data subject, declared in {de}"""
    d : data    
    de : declaration

causable observable predicate IsAutomatedDecision
    """Declaration {de} declares that data is used for automated decision-making, including profiling, with meaningful
       information about the logic involved, as well as the significance and the envisaged consequences
       of such processing for the data subject"""
    de : declaration

observable predicate HasIntendedTransfer
    """The {d} is collected with the intent to transfer it to country or international organisation {co}"""
    d : data
    co : country_or_international_organisation

causable observable predicate IsTransfer
    """Declaration {de} declares intended transfer to country or international organisation {co}"""
    de : declaration
    co : country_or_international_organisation

causable observable predicate IsTransferBasis
    """Declaration {de} declares the existence or absence of an adequacy decision by the Commission
       with respect to the country or international organisation {co} to which the personal data are
       intended to be transferred, or in the case of transfers referred to in Article 46 or 47, or 
       the second subparagraph of Article 49(1), reference to the appropriate or suitable safeguards 
       and the means by which to obtain a copy of them or where they have been made available."""
    de : declaration
    co : country_or_international_organisation

#art14
observable predicate IsReception
    """Activity {a} consists in reception of data from sender entity {e}"""
    a : activity
    e : entity

internal predicate IsIndirectCollection
    a : activity
    d : data
    ds : data_subject

rule "indirect_collection_def_1"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsCollection(a, ds')
        ds <> ds'
    constitute
        IsIndirectCollection(a, d, ds)

rule "indirect_collection_def_2"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsReception(a, e)
    constitute
        IsIndirectCollection(a, d, ds)

paragraph "1"

#art14.f
causable observable predicate IsReceptionSource
    """Declaration {re} declares the source {e} from which the personal data originate, and if applicable,
       whether it came from publicly accessible sources"""
    re : declaration
    e : entity

causable observable predicate IsDSSource
    """Declaration {re} declares the data subject {ds'} from which the personal data originate, and if applicable,
       whether it came from publicly accessible sources"""
    re : declaration
    ds' : data_subject

article "15" "Right of access by the data subject"

paragraph "1"

observable predicate IsAccessRequest
    """Request {rq} is an access request"""
    rq : request

causable observable predicate IsDataProcessingOngoing
    """Declaration {de} states the data subject's data is being processed"""
    de : declaration

causable observable predicate IsDataProcessingNotOngoing
    """Declaration {de} states the data subject's data is not being processed"""
    de : declaration

rule "data_processing_ongoing"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds))
    oblige
        EXISTS de. Contains(rs, de) AND IsDataProcessingOngoing(de)
    transparently enforceable causing effects

rule "data_processing_not_ongoing"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        NOT (EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds)))
    oblige
        EXISTS de. Contains(rs, de) AND IsDataProcessingNotOngoing(de) 
    transparently enforceable causing effects

point "a"

rule
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasPurpose(a, p))
    oblige
        EXISTS de. Contains(rs, de) AND IsPurposeOfProcessing(de, p)
    transparently enforceable causing effects

point "b"

rule
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasCategory(d, cat))
    oblige
        EXISTS de. Contains(rs, de) AND IsCategory(de, cat)
    transparently enforceable causing effects

point "c"

rule "access_request_recipient"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasIntendedRecipient(d, e))
    oblige
        EXISTS de. Contains(rs, de) AND IsRecipient(de, e)
    transparently enforceable causing effects

rule "access_request_recipient_category"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasIntendedRecipientCategory(d, cat))
    oblige
        EXISTS de. Contains(rs, de) AND IsRecipientCategory(de, cat)
    transparently enforceable causing effects

point "d"

rule "access_request_storage_period"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasStoragePeriod(d, t))
    oblige
        EXISTS de. Contains(rs, de) AND IsStoragePeriod(de, t)
    transparently enforceable causing effects

rule "access_request_storage_criteria"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasStorageCriteria(d, cr))
    oblige
        EXISTS de. Contains(rs, de) AND IsStorageCriteria(de, cr)
    transparently enforceable causing effects

point "e"

rule
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds))
    oblige
        EXISTS de. Contains(rs, de) AND IsRights(de)
    transparently enforceable causing effects

point "f"

rule
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND PersonalData(d, ds))
    oblige
        EXISTS de. Contains(rs, de) AND IsComplaintStatement(de, rq)
    transparently enforceable causing effects

point "g"

rule "access_request_reception_source"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND IsIndirectCollection(a, d, ds) AND IsReception(a, e))
    oblige
        EXISTS de. Contains(rs, de) AND IsReceptionSource(de, e)
    transparently enforceable causing effects

rule "access_request_dssource"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE DataProcessing(pr, c, a, d) AND IsIndirectCollection(a, d, ds) AND IsCollection(a, ds') AND ds <> ds')
    oblige
        EXISTS de. Contains(rs, de) AND IsDSSource(de, ds')
    transparently enforceable causing effects

point "h"

rule "access_request_automated_decision"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasIntendedAutomatedDecision(d, de)))
    oblige
        EXISTS de. Contains(rs, de) AND IsAutomatedDecision(de)
    transparently enforceable causing effects

paragraph "2"

rule
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasIntendedTransfer(d, co)))
    oblige
        ONCE (EXISTS de. Contains(rs, de) AND IsTransfer(de, co))
        ONCE (EXISTS de. Contains(rs, de) AND IsTransferBasis(de, co))
    transparently enforceable causing effects

paragraph "3"

causable observable predicate ContainsData
    """Declaration {de} contains data file {f}"""
    de : declaration
    f : file

causable observable predicate PersonalDataCopy
    """File {f} is a copy of personal data of data subject {ds}, not adversely affecting the rights and freedoms of others."""
    f : file
    ds : data_subject

causable observable predicate IsCommonlyUsedFormat
    """File {f} is in a commonly used format"""
    f : file

observable predicate IsFurtherCopy
    """Request {rq} requests a further copy of the personal data undergoing processing"""
    rq : request

rule "data_copy"
    whenever
        ONCE (Request(ds, rq, c) AND IsAccessRequest(rq))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds)))
    oblige
        EXISTS f. ContainsData(rs, f) AND PersonalDataCopy(f, ds) AND IsCommonlyUsedFormat(f)
    transparently enforceable causing effects

rule "further_copy"
    whenever
        IsFurtherCopy(rq)
    except
        article "12" paragraph "5" rule "free_of_charge"

paragraph "4"

note "Skipped: Integrated in the docstring of PersonalDataCopy"

article "16" "Right to rectification"

internal predicate IsObligedToRectify
    """Controller {c} is obliged to rectify data {d} to data {d'}"""
    c : entity
    d : data
    d' : data

observable predicate IsRectificationRequest
    """Request {rq} is a rectification request, specifying that data {d} should be rectified to {d'}.
       This includes requests to have incomplete personal data completed, including by means of providing 
       a supplementary statement."""
    rq : request
    d : data
    d' : data

observable event HasInaccuracy
    """Data {d} has inaccuracy"""
    d : data

rule "rectification_obligation"
    whenever
        IsObligedToRectify(c, d, d')
    oblige
        (NOT UndueDataDelay(d)) UNTIL Rectify(d, d')
    transparently enforceable causing effects

rule "rectification_request_inaccuracy"
    whenever
        ONCE (Request(ds, rq, c) AND IsRectificationRequest(rq, d, d'))
        RequestResponse(ds, rq, rs)
        EXISTS pr, a, d. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds)))
        HasInaccuracy(d)
    constitute
        IsObligedToRectify(c, d, d')

article "17" "Right to erasure ('right to be forgotten')"

observable predicate IsErasureRequest
    """Request {rq} is an erasure request, specifying that data {d} should be deleted."""
    rq : request
    d : data

observable event DataReview
    """Controller {c} reviews data {d} for the purpose of erasure. Must occur regularly to comply with the
       storage limitation principle."""
    c : entity
    d : data

internal predicate ValidObjection
    """Data subject {ds} has objected to the processing of data {d}, and there are no overriding legitimate
       grounds for the processing, or the data subject has objected to the processing of data {d} for direct
       marketing purposes."""
    ds : data_subject
    d : data

internal predicate IsObligedToDelete
    """Controller {c} is obliged to delete data {d}."""
    c : entity
    d : data

paragraph "1"

rule
    whenever
        IsObligedToDelete(c, d)
    oblige
        NOT UndueDataDelay(d) UNTIL Delete(d)
    transparently enforceable causing effects

point "a"

rule
    whenever
        (ONCE (EXISTS rq. Request(ds, rq, c) AND IsErasureRequest(rq, d)) AND RequestResponse(ds, rq, rs)) OR DataReview(c, d)
        NOT (EXISTS pr, a, d, p. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND HasPurpose(a, p))) AND IsNecessary(d, p))
    constitute
        IsObligedToDelete(c, d)
        
point "b"

rule
    whenever
        (ONCE (EXISTS rq. Request(ds, rq, c) AND IsErasureRequest(rq, d)) AND RequestResponse(ds, rq, rs)) OR DataReview(c, d)
        NOT (EXISTS pr, a, d. (NOT WithdrawConsent(ds, p, c)) SINCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds) AND (IsLawful(a, "6(1)(a)") OR IsLawful(a, "9(2)(a)"))) AND NOT (EXISTS ba. IsLawful(a, ba)))
    constitute
        IsObligedToDelete(c, d)

point "c"

internal event IsActiveObjection
    """Data subject {ds} has objected to processing of data by controller {c} for purpose {p} with justification {de},
       and there are no overriding legitimate grounds for the processing, or the data subject has objected to the
       processing of data for direct marketing purposes."""
    ds : data_subject
    c : entity
    p : purpose
    de : declaration

rule
    whenever
        IsActiveObjection(ds, c, p, de)
        EXISTS pr, a. (ONCE (DataProcessing(pr, c, a, d) AND PersonalData(d, ds)))
    constitute
        IsObligedToDelete(c, d)

point "d"

note "Skipped: personal data is never unlawfully processed (NO VIOLATION)."

point "e"

note "Skipped: OPENING CLAUSE."

point "f"

rule
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        IsLawful(a, "8(1)")
    constitute
        IsObligedToDelete(c, d)

paragraph "2"

observable event Share
    """Controller {c} shares data {d} with entity {e}"""
    c : entity
    e : entity
    d : data

causable observable event NotifyOfErasure
    """The controller {c}, taking account of available technology and the cost of implementation, takes 
       reasonable steps, including technical measures, to inform {e} that the data subject has requested 
       the erasure of any links to, or copy or replication of, data {d}."""
    c : entity
    e : entity
    d : data

rule
    whenever
        IsObligedToDelete(c, d)
        ONCE Share(c, e, d)
    oblige
        NOT UndueDataDelay(d) UNTIL (EXISTS e. NotifyOfErasure(c, e, d))
    transparently enforceable causing effects

paragraph "3"

point "a"

observable predicate IsNecessaryForFreedomOfExpression
    """Activity {a} is necessary for exercising the right to freedom of expression and information."""
    a : activity

rule
    whenever
        IsNecessaryForFreedomOfExpression(a)
    except
        paragraph "1"
        paragraph "2"

point "b" 

rule 
    whenever
        DataProcessing(pr, c, a, d)
        (EXISTS l. IsNecessaryForLegalObligation(a, l)) OR (EXISTS pi. IsNecessaryForPublicInterest(a, pi)) OR IsPerformanceOfPublicAuthorityTask(a) AND IsPublicAuthority(c)
    except
        paragraph "1"
        paragraph "2"   

point "c"

rule
    whenever
        DataProcessing(pr, c, a, d)
        IsNecessaryForPublicInterest(a, pi)
        IsHealthRelated(pi)
    except
        paragraph "1"
        paragraph "2"

point "d"

rule
    whenever
        DataProcessing(pr, c, a, d)
        IsNecessaryForArchivalPurposes(a)
    except
        paragraph "1"
        paragraph "2"

point "e"

rule
    whenever
        DataProcessing(pr, c, a, d)
        IsNecessaryForJudicialClaims(a)
    except
        paragraph "1"
        paragraph "2"

article "21" "Right to object"

observable event Object
    """Data subject {ds} objects to processing of data by controller {c} for purpose {p} with justification {de}."""
    ds : data_subject
    c : entity
    p : purpose
    de : declaration

observable predicate DemonstrateOverridingCompellingGrounds
    """Controller {c} demonstrates that there are overriding legitimate grounds for purpose {p} which
       override the interests, rights and freedoms of the data subject {ds} as stated in {de}, or for the
       establishment, exercise or defence of legal claims."""
    c : entity
    ds : data_subject
    p : purpose
    de : declaration

paragraph "1"

rule "object_ef_exception"
    whenever
        DataProcessing(pr, c, a, d)
        HasPurpose(a, p)
        (NOT DemonstrateOverridingCompellingGrounds(c, ds, p, de)) SINCE Object(ds, c, p, de)
    except
        article "6" paragraph "1" paragraph[1] "1" point "e"
        article "6" paragraph "1" paragraph[1] "1" point "f"

rule "object_ef_definition"
    whenever
        (NOT DemonstrateOverridingCompellingGrounds(c, ds, p, de)) SINCE Object(ds, c, p, de)
    constitute
        IsActiveObjection(ds, c, p, de)

paragraph "2"
paragraph "3"

observable predicate IsDirectMarketing
    """Purpose {p} is a direct marketing purpose."""
    p : purpose

rule "object_dm_exception"
    whenever
        DataProcessing(pr, c, a, d)
        HasPurpose(a, p)
        PersonalData(d, ds)
        IsDirectMarketing(p)
        ONCE Object(ds, c, p, de)
    except
        article "6" paragraph "1"

rule "object_dm_definition"
    whenever
        ONCE Object(ds, c, p, de)
        IsDirectMarketing(p)
    constitute
        IsActiveObjection(ds, c, p, de)

paragraph "4"

note "Skipped: integrated in the docstring of IsRights."
note "Skipped: PERMISSION in (5)"

paragraph "6"

rule "object_archiving_exception"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasPurpose(a, "Archiving")
        ONCE Object(ds, c, "Archiving", de)
    except
        article "6" paragraph "1"

rule "object_archiving_definition"
    whenever
        ONCE Object(ds, c, "Archiving", de)
    constitute
        IsActiveObjection(ds, c, "Archiving", de)

rule "object_archiving_override"
    whenever
        DataProcessing(pr, c, a, d)
        IsNecessaryForPublicInterest(a, pi)
    except
        rule "object_archiving_exception"
        rule "object_archiving_definition"

article "30" "Records of processing activities"

causable observable event Record
    """A record in the record of processing activities of {pr} processing data on behalf of {c}, setting the property 
       {p} of data processing activity {a} to value {v}."""
    pr : entity
    c : entity
    a : activity
    p : string
    v : string

observable predicate IsJointController
    """Entity {jc} is a joint controller with controller {c} for data processing activity {a}."""
    a : activity
    c : entity
    jc : entity
    
suppressable event Transfer
    """Activity {a} involves a transfer whereby the data is transferred to controller {c'} with processor {pr'} in country or 
       international organisation {co} subject to safeguards {sg}."""
    a : activity
    c' : entity
    pr' : entity
    co : country_io
    sg : safeguards

function string_of_entity(
    c : entity
) -> string

function string_of_purpose(
    p : purpose
) -> string

function string_of_category(
    cat : special_data_category
) -> string

function string_of_country_io(
    co : country_io
) -> string

function string_of_safeguards(
    sg : safeguards
) -> string

function string_of_span(
    t : span
) -> string

function string_of_declaration(
    de : declaration
) -> string

paragraph "1"

point "a"

rule "controller_record"
    whenever
        DataProcessing(pr, c, a, d)
    oblige
        Record(pr, c, a, "Controller", string_of_entity(c))
    transparently enforceable causing effects

rule "controller_representative_record"
    whenever
        DataProcessing(pr, c, a, d)
        IsControllerRepresentative(c, cr)
    oblige
        Record(pr, c, a, "ControllerRepresentative", string_of_entity(cr))
    transparently enforceable causing effects

rule "joint_controller_record"
    whenever
        DataProcessing(pr, c, a, d)
        IsJointController(a, c, jc)
    oblige
        Record(pr, c, a, "JointController", string_of_entity(jc))
    transparently enforceable causing effects

rule "dpo_record"
    whenever
        DataProcessing(pr, c, a, d)
        IsDataProtectionOfficer(c, dpo)
    oblige
        Record(pr, c, a, "DPO", string_of_entity(dpo))
    transparently enforceable causing effects

point "b"

rule "purpose_record"
    whenever
        DataProcessing(pr, c, a, d)
        HasPurpose(a, p)
    oblige
        Record(pr, c, a, "Purpose", string_of_purpose(p))
    transparently enforceable causing effects

point "c"

observable predicate HasDataSubjectCategory
    """Activity {a} is performed with data from data subject category {cat}."""
    a : activity
    cat : special_data_category

rule "categories_of_data_subjects_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasDataSubjectCategory(a, cat)
    oblige
        Record(pr, c, a, "DataSubjectCategory", string_of_category(cat))
    transparently enforceable causing effects

rule "categories_of_data_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasCategory(d, cat)
    oblige
        Record(pr, c, a, "DataCategory", string_of_category(cat))
    transparently enforceable causing effects

point "d"

rule "recipients_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasIntendedRecipient(d, e)
    oblige
        Record(pr, c, a, "Recipient", string_of_entity(e))
    transparently enforceable causing effects

rule "recipient_categories_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasIntendedRecipientCategory(d, cat)
    oblige
        Record(pr, c, a, "RecipientCategory", string_of_entity(cat))
    transparently enforceable causing effects

point "e"

rule "transfer_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        Transfer(a, c', pr', co, sg)
    oblige
        Record(pr, c, a, "TransferRecipient", string_of_country_io(co))
        Record(pr, c, a, "TransferSafeguards", string_of_safeguards(sg))
    transparently enforceable causing effects

point "f"

rule "storage_period_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasStoragePeriod(d, t)
    oblige
        Record(pr, c, a, "StoragePeriod", string_of_span(t))
    transparently enforceable causing effects

point "g"

observable predicate HasSecurityMeasuresDeclaration
    """Activity {a} is performed with security measures declaration {de}."""
    a : activity
    de : declaration

rule "security_measures_record"
    whenever
        DataProcessing(pr, c, a, d)
        PersonalData(d, ds)
        HasSecurityMeasuresDeclaration(a, de)
    oblige
        Record(pr, c, a, "SecurityMeasures", string_of_declaration(de))
    transparently enforceable causing effects

paragraph "2" 

note "Skip: redundant with point (1) above."

paragraph "3"

note "Skip: all records are in electronic form in our model"

note "Skip (4): not a system property"

paragraph "5"

observable predicate IsSME
    """Controller {c} is a small or medium-sized enterprise (SME) with fewer than 250 employees."""
    c : entity

observable predicate IsRiskyProcessing
    """Activity {a} is likely to result in a high risk to the rights and freedoms of natural persons."""
    a : activity

observable predicate IsOccasionalProcessing
    """Activity {a} is occasional processing."""
    a : activity

rule "SME_exemption"
    whenever
        DataProcessing(pr, c, a, d)
        IsSME(c)
        IsSME(pr)
    except
        paragraph "1"
        paragraph "2"

rule
    whenever
        IsRiskyProcessing(a)
        NOT IsOccasionalProcessing(a)
        EXISTS d', sp. (DataProcessing(pr, c, a, d') AND IsSpecialData(d', sp) OR RelatesToCriminalConvictionsOrOffences(d'))
    except
        rule "SME_exemption"
