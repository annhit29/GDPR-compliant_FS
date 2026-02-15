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

observable event Collect
  exUid : user_id
  p     : purpose

causable observable event Delete #todo: or `causable event`?
  fid : file_id

observable event Consent
  exUid : user_id
  p     : purpose

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
#for art5a <- these are the obligations
assume true IsLawful #todo: delete this assumption when writing art6, coz o/w art5a will always never fail.
assume true IsFair
assume true IsTransparent

#3. refine the types of events in order to connect to GDPR rules (gdpr.lex)
refine type data_subject  is user_id
refine type data          is file_id #.sig file's fid is considered as `data` in gdpr.lex art5 
#for the GDPR rules (gdpr.lex) art5
refine type activity      is activity_id
refine type entity        is string # controller/processor are both string constants in gdpr.lex


# the data controller GDPRFS
const Controller : entity = "GDPRFS"

#the Use event's activity is "Use"
const UseActivity : activity = "Use"


#4. define refinement rules
#The refinement can only use the variables I use in `whenever` part.

#art5a(l159) is triggered by both DataProcessing(l39) and PersonalData(l34) events
rule "r_DataProcessing"
  whenever
    Use(d, ds)
  refine
    DataProcessing(Controller, Controller, UseActivity, d) #l39
#this rule is a translator from the system events of FS (computer) to the GDPR law (juridical). 
#Whenever the system sees a `Use` event, it is translated to a `DataProcessing` event in the GDPR sense.

rule "r_PersonalData"
  whenever
    Use(d, ds)
  refine
    PersonalData(d, ds) #l34

#art5b rule "must_have_purpose" l157
internal predicate SessionActive
  ds : data_subject
  p  : purpose

rule "r_SessionActive_start"
  whenever 
    StartSession(ds, p, r)
  constitute #:= create an event
    SessionActive(ds, p)

rule "r_SessionActive_stop"
  whenever 
    StopSession(ds)
  revoke #todo or other lex keywords for "STOP the current active session"?
    SessionActive(ds, p)

rule "r_HasPurpose"
  whenever
    Use(d, ds)
    SessionActive(ds, p) #todo: SessionActive coherent? coz I defined rule r_SessionActive_start to avoid "both Use and StartSession happen at the same time". O/w any other easier way to do? coz StartSession event doesn't necc. starts at the same time as Use event. 
    #both Use event and SessionActive event must happen at the same time.
  refine
    HasPurpose(UseActivity, p)



