Collect(fid: string, exUid: string)
Consent(exUid: string, p: string)
Contains(de: string, de2: string)+
Delete(d: string)+
IsCategory(de: string, cat: string)+
Record(pr: string, c: string, a: string, p: string, v: string)+
Rectify(d_old: string, d_new: string)+
RequestAccess(exUid: string)
RequestErasure(exUid: string)
RequestResponse(ds: string, rq: string, rs: string)+
Revoke(exUid: string, p: string)
SpecialConsent(exUid: string, p: string, spCat: string)
SpecialData(fid: string, spCat: string)
StartSession(inUid: string, p: string, reason: string)
StopSession(inUid: string)
TP(t: int)
Use(fid: string, exUid: string)-
UseNonPII(fid: string, exUid: string)
Write(fid: string, p: string)-
fun string_of_category(cat: string) : string
fun string_of_country_io(co: int) : string
fun string_of_declaration(de: string) : string
fun string_of_entity(c: string) : string
fun string_of_purpose(p: string) : string
fun string_of_safeguards(sg: int) : string
fun string_of_span(t: int) : string