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
assume true IsLawful
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

# a single activity named "collection" representing all data collection in your system.
# const CollectionActivity : activity = "collection"

#4. define refinement rules
#The refinement can only use the variables I use in `whenever` part.

#art5a(l159) is triggered by both DataProcessing(l39) and PersonalData(l34) events
rule "r_DataProcessing"
  whenever
    Use(d, ds)
  refine
    DataProcessing("GDPRFS", "GDPRFS", "Use", d) #l39
#this rule is a translator from the system events of FS (computer) to the GDPR law (juridical). 
#Whenever the system sees a `Use` event, it is translated to a `DataProcessing` event in the GDPR sense.

rule "r_PersonalData"
  whenever
    Use(d, ds)
  refine
    PersonalData(d, ds) #l34
