refine gdpr

# 2. the type is either already defined in gdpr.lex or should be defined in this rex file.
type user_id  is string
type file_id  is string
#for the GDPR rules (gdpr.lex) art5
type activity_id is string


# 1. observable, suppressable or causable events, defined in .sig file
#observable := The system sees this event, logs it, but it cannot block or create it.
#suppressable := If a rule is violated, then Lex can suppress (block) this event.
#causable := If system does not do this event, then the monitor can CAUSE (emit) it.

observable event StartSession
  inUid  : user_id
  p      : purpose
  reason : string

observable event StopSession
  inUid  : user_id

suppressable event Use
  fid   : file_id
  exUid : user_id

observable event Write
  fid : file_id
  p     : purpose

observable event Consent
  exUid : user_id
  p     : purpose

observable event Collect
  fid   : file_id
  exUid : user_id

observable event Revoke
  exUid : user_id
  p     : purpose

observable event RequestAccess
  exUid : user_id

observable event RequestErasure
  exUid : user_id

observable event UseNonPII
  fid   : file_id
  exUid : user_id

#5. the assumptions 
#for art5a's obligations
assume true PersonalData
  """data is personal data whenever it is used (art5a)"""

assume true IsFair
  """data is processed fairly whenever it is used by an activity/event (art5a)"""

assume true IsTransparent
  """the way data is processed/used is transparent to the ds (art5a)"""

#3. refine the types of events in order to connect to GDPR rules (gdpr.lex)
refine type data_subject  is user_id
refine type data          is file_id #.sig file's fid is considered as `data` in gdpr.lex art5 
#for the GDPR rules (gdpr.lex) art5
refine type activity      is activity_id
refine type entity        is string # controller/processor are both string constants in gdpr.lex


#4. define refinement rules
#The refinement can only use the variables I use in `whenever` part.
# refine := remplacer un événement abstrait de la loi (eg: DataProcessing event) par un événement concret du système (Use event).

#art5a(l159) is triggered by both DataProcessing(l39) and PersonalData(l34) events
rule "r_DataProcessing"
  whenever
    Use(d, ds)
  refine
    DataProcessing("GDPRFS", "GDPRFS", "Use", d) #l39 #todo: "Use" activity? coz gdpr.lex l42: Data d is processed by processor "GDPRFS" on behalf of controller "GDPRFS" as part of data processing activity "Use"

#Use refines to DataProcessing. i.e. Use replaces DataProcessing event.
#this rule is a translator from the system events of FS (computer) to the GDPR law (juridical). 
#Whenever the system sees a `Use` event, it is translated to a `DataProcessing` event in the GDPR sense.

#art5b rule "must_have_purpose" (l157)
#DataProcessing event has been refined; PersonalData predicate is assumed; HasPurpose predicate is refined.

rule "r_HasPurpose" #gdpr.lex l67: Data processing activity a has purpose p
  whenever
    Use(d, ds) #see rule "r_DataProcessing": Data processing = Use event
    NOT StopSession(inUid) SINCE StartSession(inUid, p, reason) #must use StartSession event in order to have the purpose `p` in the refinement of HasPurpose predicate.
    #a session has started, and not yet stopped. := the same session
    # this session has this event Use.
  refine
    HasPurpose("Use", p) #todo: "Use" activity? coz gdpr.lex l67: Data processing activity "Use" has purpose p

# r_HasPurpose is also for art5b rule "purpose_conditions" (l183)
#because gdpr.lex's rule "purpose_conditions" is triggered by HasPurpose event, i.e.
#"Whenever HasPurpose exists => check these (gdpr.lex l187-189) obligations."

#for art5b rule "purpose_conditions"'s obligations (l183)
assume true IsSpecified
  """Purpose is specified whenever a data d is processed/used (art5b rule purpose_conditions)"""

assume true IsExplicit
  """Purpose is explicit whenever a data d is processed/used (art5b rule purpose_conditions)"""

#Purpose is legitimate if it is marketing, service or analytics
rule "r_IsLegitimate"
    whenever
        p = "marketing" OR p = "service" OR p = "analytics"
    refine
        IsLegitimate(p)

#art5b rule "purpose_limitation" (l192)
#l60 so use a Collect event
#todo: dans instrlib, implemente `Collect`
rule "r_IsCollection"
    whenever
        Collect(d, ds)
    refine
        IsCollection("Collect", ds) #todo: "Collect" activity? coz gdpr.lex l63: """Data processing activity Collect collects personal data from data subject {ds}"""
# Collect event refines to IsCollection event. i.e. Collect replaces IsCollection event.

#art5b rule "general_purpose"
assume true IsCompatibleWithPurpose
  """The data processing activity is compatible with purpose """

#art5b rule "archiving_purpose"
assume false IsArchival
  """No archiving purposes in the public interest (eg: long‑term preservation for public‑interest, historical or scientific research) is performed."""

#art5c
assume true IsAdequate
  """Data d processed or collected is enough in quantity and quality to fulfil purpose p, but not more than that."""

assume true IsRelevant
  """Only data d that is relevant to purpose p are processed."""

assume true IsLimitedToWhatIsNecessary
  """The system must not process or collect more personal data than is strictly needed to achieve purpose p."""

#art5d rule "accurate_and_up_to_date"

#Write event but not Use event, coz "Data must be accurate and, where necessary, kept up to date." i.e. "If data is inaccurate, Then I must **correct** it."
rule "r_IsAccurate"
  whenever
    Write(d, p)
  refine 
    IsAccurate(d, p)

rule "r_IsUpToDate"
  whenever
    Write(d, p)
  refine
    IsUpToDate(d, p)

#art5d rule "accuracy_deletion"
assume false UndueDataDelay
    """We do not wait to delete data."""

#todo: can I do this? `Rectify(fid, fid)`
#Whenever a file fid is written (i.e. updated),
#the olf data in `fid` is rectified to the new data in `fid`.

#so Every write operation counts as correcting the data.

rule "r_Rectify"
  whenever
    Write(fid, p)
  refine
    Rectify(fid, fid) #allowed, coz we're updating data in file id, so old_data => fid, old_data => fid ?  
# Write event refines to Rectify event. i.e. Write replaces Rectify event. 
# coz Writing is considered a correction/rectification.

#art5e rule "temporal_storage_limitation"

#Data is stored when: it exists on disk, and it has not been deleted.
# so treat `Write(d,p)` as implying data is stored
#rule "r_Stored"
#  whenever
#    Write(d, p) #todo: error: Write must be sup?! but why this doesn't happen w/ `r_GiveConsent`?
#    NOT Delete(d) SINCE Write(d, p)
#  refine
#    Stored(d)
assume false Stored
assume true IsNecessary

#art5e rule "storage_limitation_exception"
assume false TechnicalAndOrganisationalMeasures
    """We do not claim any technical and organizational measures for archival purposes."""

assume false JustifiesStorage
    """No archiving is performed."""

#art5f
assume true EnsuresAppropriateSecurity
  """We protect personal data d when processing it by appropriate technical and organisational security measures"""

#art6.1.a
rule "r_GiveConsent"
    whenever
        Consent(ds, p)
    refine
        GiveConsent(ds, p, "GDPRFS")
# Consent event refines to GiveConsent event. i.e. Consent replaces GiveConsent event.

#art6.1.b
assume false EndContract
    """No contracts are being concluded."""
assume false PrepareContract
    """No contracts are being concluded."""
assume false StartContract
    """No contracts are being concluded."""
assume false IsContractParty
    """No contracts are being concluded."""
assume false IsNecessaryForContract
    """No contracts are being concluded."""

#art6.1.c
assume false IsNecessaryForLegalObligation
    """This FileSystem does not process data due to legal obligations."""

#art6.1.d
assume false IsNecessaryForVitalInterests
    """This FileSystem does not process data to protect the vital interests of data subjects. 
    vital interests := medical data in an emergency to save someone's life.
    This FileSystem only have p = "marketing", "service" or "analytics" purposes, but no p = "emergency"."""

#art6.1.e
assume false IsNecessaryForPublicInterest
    """No public interest is involved in the data processing activities of this FileSystem."""
assume false IsPerformanceOfPublicAuthorityTask
    """Data processing activities of this FileSystem are not part of the performance of a public authority task."""
assume false IsPublicAuthority
    """This FileSystem is not a public authority."""

#art6.1.f
rule "r_LegitimateInterest"
  whenever
    Use(d, ds)
    NOT StopSession(inUid) SINCE StartSession(inUid, p, reason)
    p = "marketing" #todo: assume the legitimate interest to protect the marketing purpose?
  refine #todo: my interest OK?
    IsNecessaryForLegitimateInterest("Use", "GDPRFS", "the interests with purpose marketing, service, or analytics, by performing GDPRFS's Read operations.")

#todo: seems to be correct?
rule "r_IsOverriddenByDataSubjectInterests"
    whenever
        Use(d, ds) OR Write(d, p)
        NOT (p = "marketing")
    refine
        IsOverriddenByDataSubjectInterests("GDPRFS", "ds's interests", ds)

#art6.2
#already done previously.
